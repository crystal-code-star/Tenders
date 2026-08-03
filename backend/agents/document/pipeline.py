"""
pipeline.py — Complete pipeline for DCE document processing
"""

import os
import logging
import zipfile
from pathlib import Path
from typing import Dict, Any, List

from dce_classifier import classify_dce_file
from extractors import route_extractor
from field_mappers import map_fields_by_type

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("pipeline")

# Set DEBUG_AVIS_TEXT=1 in the environment to print the full extracted
# Avis text (useful when tuning field_mappers patterns). Off by default.
_DEBUG_AVIS_TEXT = os.getenv("DEBUG_AVIS_TEXT", "0") == "1"


def process_single_file(filename: str, file_bytes: bytes) -> Dict[str, Any]:
    """Process a single file through the complete pipeline."""
    classification = classify_dce_file(filename, file_bytes)
    type_doc = classification.get("type_doc", "autre")
    is_scanned = classification.get("is_scanned", False)
    file_type = classification.get("file_type", {})

    extracted = route_extractor(file_bytes, file_type)

    if extracted.get("skipped", False):
        return {
            "filename": filename,
            "type_doc": type_doc,
            "is_scanned": is_scanned,
            "classification": classification,
            "extraction": extracted,
            "fields": {},
            "skipped": True,
            "skip_reason": extracted.get("skip_reason", "Unknown reason")
        }

    extracted_text = extracted.get("text", "")

    if _DEBUG_AVIS_TEXT and type_doc == "avis":
        print(f"\n---AVIS RAW TEXT ({filename}, {len(extracted_text)} chars)---")
        print(extracted_text)
        print("---END---\n")

    fields = map_fields_by_type(extracted_text, type_doc)

    return {
        "filename": filename,
        "type_doc": type_doc,
        "is_scanned": is_scanned,
        "classification": classification,
        "extraction": extracted,
        "fields": fields,
        "skipped": False,
        "skip_reason": None
    }


def process_zip(zip_path: Path) -> List[Dict[str, Any]]:
    """Process all files in a ZIP archive."""
    results = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            try:
                file_bytes = zf.read(name)
                result = process_single_file(name, file_bytes)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing {name}: {e}")
                results.append({
                    "filename": name,
                    "type_doc": "error",
                    "is_scanned": False,
                    "error": str(e),
                    "skipped": True,
                    "skip_reason": f"Error: {e}"
                })
    return results


def aggregate_results_by_ao(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate results into the final required shape:
    {
        "Avis": {"Objet": ..., "Date de soumission": ..., "Estimation (DHS TTC)": ...},
        "RC": {"Dossier Technique": {"Références similaires (publics ou privés)": ...,
                                      "Certificat de qualification et de classification": ...}}
    }
    Only the first Avis file and first RC file found are used to populate the result.
    """
    ao_data: Dict[str, Any] = {
        "Avis": {
            "Objet": "",
            "Date de soumission": "",
            "Estimation (DHS TTC)": ""
        },
        "RC": {
            "Dossier Technique": {
                "Références similaires (publics ou privés)": "Non mentionné",
                "Certificat de qualification et de classification": "Non mentionné"
            }
        }
    }
    skipped_files = []
    avis_filled = False
    rc_filled = False

    for result in results:
        if result.get("skipped", False):
            skipped_files.append({
                "filename": result.get("filename"),
                "reason": result.get("skip_reason")
            })
            continue

        type_doc = result.get("type_doc")
        fields = result.get("fields", {})

        if type_doc == "avis" and not avis_filled and "Avis" in fields:
            avis_fields = fields["Avis"]
            for key, value in avis_fields.items():
                if value:
                    ao_data["Avis"][key] = value
            if any(avis_fields.values()):
                avis_filled = True

        elif type_doc == "rc" and not rc_filled and "RC" in fields:
            rc_dt = fields["RC"].get("Dossier Technique", {})
            for key, value in rc_dt.items():
                if value and value != "Non mentionné":
                    ao_data["RC"]["Dossier Technique"][key] = value
            if any(v and v != "Non mentionné" for v in rc_dt.values()):
                rc_filled = True

    return {
        "result": ao_data,
        "skipped_files": skipped_files
    }


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <path_to_zip>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    results = process_zip(zip_path)
    aggregated = aggregate_results_by_ao(results)

    print(json.dumps(aggregated, ensure_ascii=False, indent=2))