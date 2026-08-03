import React, { useState, useEffect, useCallback } from 'react';
import {
  Sparkles, Loader, AlertCircle, RefreshCw, Table2, ListTree,
  Image as ImageIcon, Download, MessageSquare, Layers, Hash,
  Type as TypeIcon, ChevronRight, Info, Clock, PackageSearch,
} from 'lucide-react';
import { API_URL, authHeaders } from './tenderUtils';
import { BRAND } from '../App';

function extOf(name) {
  const i = name.lastIndexOf('.');
  return i === -1 ? '' : name.slice(i + 1).toLowerCase();
}

function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatTime(ms) {
  if (!ms) return '—';
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

const ANALYSIS_FIELDS = [
  ['maitre_ouvrage', "Maître d'ouvrage"],
  ['objet', 'Objet'],
  ['lieu_execution', "Lieu d'exécution"],
  ['type_marche', 'Type de marché'],
  ['budget_estime', 'Budget estimé'],
  ['date_limite', 'Date limite'],
  ['duree', 'Durée'],
  ['caution_provisoire', 'Caution provisoire'],
  ['caution_definitive', 'Caution définitive'],
  ['conditions_participation', 'Conditions de participation'],
  ['lots', 'Lots'],
  ['criteres_attribution', "Critères d'attribution"],
];

function StatChip({ icon: Icon, label, value }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 p-2.5 bg-gray-50 rounded-lg border border-gray-100">
      <Icon size={13} className="text-gray-400" />
      <span className="text-sm font-bold text-gray-800">{value}</span>
      <span className="text-[10px] text-gray-400 uppercase tracking-wide text-center leading-tight">{label}</span>
    </div>
  );
}

function Section({ title, icon: Icon, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-gray-100">
      <button onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-gray-50 transition-colors">
        <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-gray-500">
          {Icon && <Icon size={12} />} {title}
        </span>
        <ChevronRight size={13} className={`text-gray-300 transition-transform ${open ? 'rotate-90' : ''}`} />
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Per-lot structured tables (price rows / equipment rows)             */
/* ------------------------------------------------------------------ */

function LotGroupedTable({ title, icon: Icon, rowsByLot, columns }) {
  const lotKeys = rowsByLot ? Object.keys(rowsByLot) : [];
  if (lotKeys.length === 0) return null;

  // Keep numeric-looking lot keys ("1","2",...) in natural order; others after.
  const sortedKeys = [...lotKeys].sort((a, b) => {
    const na = Number(a), nb = Number(b);
    if (!isNaN(na) && !isNaN(nb)) return na - nb;
    return a.localeCompare(b);
  });

  return (
    <div className="space-y-3">
      <p className="text-[10px] font-bold uppercase tracking-wide text-gray-400 flex items-center gap-1.5">
        {Icon && <Icon size={11} />} {title}
      </p>
      {sortedKeys.map((lot) => {
        const rows = rowsByLot[lot] || [];
        if (rows.length === 0) return null;
        return (
          <div key={lot} className="border border-gray-100 rounded-lg overflow-hidden">
            <div className="px-2.5 py-1.5 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
              <span className="text-[11px] font-bold text-gray-600">
                {/^\d+$/.test(lot) ? `Lot ${lot}` : lot}
              </span>
              <span className="text-[10px] text-gray-400">{rows.length} ligne{rows.length > 1 ? 's' : ''}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="bg-gray-50/60">
                    {columns.map((col) => (
                      <th key={col.key} className="text-left font-semibold text-gray-500 px-2 py-1 whitespace-nowrap">
                        {col.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={i} className="border-t border-gray-50">
                      {columns.map((col) => (
                        <td key={col.key} className="px-2 py-1.5 text-gray-700 align-top">
                          {row[col.key] || row[col.key] === 0 ? row[col.key] : '—'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
}

const PRICE_COLUMNS = [
  { key: 'designation', label: 'Désignation' },
  { key: 'quantite', label: 'Qté' },
  { key: 'unite', label: 'Unité' },
  { key: 'prix_unitaire', label: 'PU' },
  { key: 'total', label: 'Total' },
];

const EQUIPMENT_COLUMNS = [
  { key: 'reference', label: 'Réf.' },
  { key: 'description', label: 'Description' },
  { key: 'quantite', label: 'Qté' },
  { key: 'unite', label: 'Unité' },
  { key: 'specifications', label: 'Spécifications' },
];

/* ------------------------------------------------------------------ */

export default function DocumentIntelligencePanel({ tenderId, filePath, fileMeta, xlsxState }) {
  const [extraction, setExtraction] = useState(null);
  const [extractLoading, setExtractLoading] = useState(false);
  const [extractError, setExtractError] = useState(null);

  const [analysis, setAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  const ext = filePath ? extOf(filePath) : '';
  const supportsExtraction = ['docx', 'xlsx', 'xlsm', 'xls'].includes(ext);

  const loadExtraction = useCallback(() => {
    if (!filePath || !supportsExtraction) { setExtraction(null); return; }
    setExtractLoading(true); setExtractError(null);
    fetch(`${API_URL}/tenders/${tenderId}/extract/${encodeURIComponent(filePath)}`, { headers: authHeaders() })
      .then(async (r) => {
        if (!r.ok) { const b = await r.json().catch(() => ({})); throw new Error(b.detail || `Server returned ${r.status}`); }
        return r.json();
      })
      .then((data) => {
        // The extractor returns { sheets, stats, type, extraction_time_ms }
        setExtraction(data);
      })
      .catch((e) => setExtractError(e.message))
      .finally(() => setExtractLoading(false));
  }, [tenderId, filePath, supportsExtraction]);

  useEffect(() => {
    setExtraction(null); setExtractError(null);
    setAnalysis(null); setAnalysisError(null);
    loadExtraction();
  }, [filePath, loadExtraction]);

  const runAnalysis = (force = false) => {
    setAnalysisLoading(true); setAnalysisError(null);
    fetch(`${API_URL}/tenders/${tenderId}/analyze/${encodeURIComponent(filePath)}${force ? '?force=true' : ''}`, {
      method: 'POST', headers: authHeaders(),
    })
      .then(async (r) => {
        if (!r.ok) { const b = await r.json().catch(() => ({})); throw new Error(b.detail || `Server returned ${r.status}`); }
        return r.json();
      })
      .then(setAnalysis)
      .catch((e) => setAnalysisError(e.message))
      .finally(() => setAnalysisLoading(false));
  };

  const exportJson = () => {
    const payload = { file: filePath, extraction, analysis };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(filePath || 'document').split('/').pop().replace(/\.[^.]+$/, '')}_extraction.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!filePath) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-6 gap-2">
        <Sparkles size={28} className="text-gray-200" />
        <p className="text-xs text-gray-400">Select a document to see extraction &amp; AI insights.</p>
      </div>
    );
  }

  const hasPriceTables = analysis?.tables_de_prix_par_lot && Object.keys(analysis.tables_de_prix_par_lot).length > 0;
  const hasEquipTables = analysis?.equipements_par_lot && Object.keys(analysis.equipements_par_lot).length > 0;

  return (
    <div className="h-full overflow-y-auto">
      <Section title="Document information" icon={Info}>
        <div className="space-y-2 text-xs">
          <div className="flex justify-between"><span className="text-gray-400">Type</span><span className="font-semibold text-gray-700">{ext.toUpperCase()}</span></div>
          <div className="flex justify-between"><span className="text-gray-400">Size</span><span className="font-semibold text-gray-700">{formatBytes(fileMeta?.size_bytes)}</span></div>
          <div className="flex justify-between">
            <span className="text-gray-400">Extracted</span>
            <span className={`font-semibold ${extraction ? 'text-emerald-600' : 'text-gray-400'}`}>
              {extraction ? 'Yes' : extractLoading ? 'Processing…' : 'No'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Extraction time</span>
            <span className="font-semibold text-gray-700 flex items-center gap-1">
              {extraction?.extraction_time_ms !== undefined ? (
                <><Clock size={12} className="text-gray-400" /> {formatTime(extraction.extraction_time_ms)}</>
              ) : (
                '—'
              )}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">AI status</span>
            <span className={`font-semibold ${analysis ? 'text-violet-600' : 'text-gray-400'}`}>
              {analysis ? 'Analyzed' : 'Not analyzed'}
            </span>
          </div>
        </div>
      </Section>

      {!supportsExtraction && (
        <div className="px-4 py-6 text-center">
          <p className="text-xs text-gray-400">No structured extraction available for .{ext} files.</p>
        </div>
      )}

      {supportsExtraction && (
        <>
          <Section title="Structure" icon={Layers}>
            {extractLoading && <div className="flex items-center gap-2 text-xs text-gray-400 py-3"><Loader size={14} className="animate-spin" /> Extracting…</div>}
            {extractError && <div className="flex items-start gap-2 text-xs text-red-500 py-2"><AlertCircle size={14} className="flex-shrink-0 mt-0.5" /><span>{extractError}</span></div>}
            {extraction && ext === 'docx' && (
              <div className="grid grid-cols-2 gap-2">
                <StatChip icon={TypeIcon} label="Paragraphs" value={extraction.stats?.paragraph_count ?? 0} />
                <StatChip icon={Hash} label="Headings" value={extraction.stats?.heading_count ?? 0} />
                <StatChip icon={Table2} label="Tables" value={extraction.stats?.table_count ?? 0} />
                <StatChip icon={ListTree} label="Lists" value={extraction.stats?.list_count ?? 0} />
                <StatChip icon={ImageIcon} label="Images" value={extraction.stats?.image_count ?? 0} />
              </div>
            )}
            {extraction && ['xlsx', 'xlsm', 'xls'].includes(ext) && (
              <div className="grid grid-cols-2 gap-2">
                <StatChip icon={Layers} label="Sheets" value={extraction.stats?.sheet_count ?? 0} />
                <StatChip icon={Table2} label="Rows" value={extraction.stats?.row_count ?? 0} />
                <StatChip icon={Hash} label="Merged cells" value={extraction.stats?.merged_cells ?? 0} />
                <StatChip icon={TypeIcon} label="Formula cells" value={extraction.stats?.formula_cells ?? 0} />
              </div>
            )}
          </Section>

          {extraction && ext === 'docx' && extraction.headings?.length > 0 && (
            <Section title="Headings" icon={Hash} defaultOpen={false}>
              <ul className="space-y-1">
                {extraction.headings.slice(0, 30).map((h, i) => (
                  <li key={i} className="text-xs text-gray-600 truncate" style={{ paddingLeft: `${(h.level || 1) * 8}px` }}>{h.text}</li>
                ))}
              </ul>
            </Section>
          )}

          {extraction && ['xlsx', 'xlsm', 'xls'].includes(ext) && extraction.sheets?.length > 0 && (
            <Section title="Sheets" icon={Layers} defaultOpen={false}>
              <ul className="space-y-1.5">
                {extraction.sheets.map((s, i) => (
                  <li key={i} className="flex items-center justify-between text-xs">
                    <span className="text-gray-700 truncate">{s.name}</span>
                    <span className="text-gray-400">{s.row_count}×{s.col_count}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          <Section title="AI extraction" icon={Sparkles}>
            {!analysis && !analysisLoading && (
              <button onClick={() => runAnalysis(false)} disabled={extractLoading || !!extractError}
                className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-xs font-bold text-white disabled:opacity-40 transition-all"
                style={{ background: BRAND.gradient }}>
                <Sparkles size={13} /> Run AI extraction
              </button>
            )}
            {analysisLoading && <div className="flex items-center justify-center gap-2 text-xs text-gray-400 py-4"><Loader size={14} className="animate-spin" /> Analyzing with AI…</div>}
            {analysisError && <div className="flex items-start gap-2 text-xs text-red-500 py-2 mb-2"><AlertCircle size={14} className="flex-shrink-0 mt-0.5" /><span>{analysisError}</span></div>}
            {analysis && (
              <div className="space-y-3">
                <button onClick={() => runAnalysis(true)} className="flex items-center gap-1.5 text-[11px] text-gray-400 hover:text-gray-600"><RefreshCw size={11} /> Re-run analysis</button>
                {ANALYSIS_FIELDS.map(([key, label]) => {
                  const val = analysis[key];
                  if (!val || val === 'Non spécifié') return null;
                  return (
                    <div key={key}>
                      <p className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-0.5">{label}</p>
                      <p className="text-xs text-gray-700 leading-relaxed">{val}</p>
                    </div>
                  );
                })}
                {analysis.notes && (
                  <div className="p-2.5 bg-amber-50 rounded-lg border border-amber-100">
                    <p className="text-[10px] font-bold uppercase tracking-wide text-amber-500 mb-0.5">Notes</p>
                    <p className="text-xs text-amber-800">{analysis.notes}</p>
                  </div>
                )}
              </div>
            )}
          </Section>

          {analysis && hasPriceTables && (
            <Section title="Tableaux de prix par lot" icon={Table2}>
              <LotGroupedTable
                title="Prix"
                icon={Table2}
                rowsByLot={analysis.tables_de_prix_par_lot}
                columns={PRICE_COLUMNS}
              />
            </Section>
          )}

          {analysis && hasEquipTables && (
            <Section title="Équipements par lot" icon={PackageSearch} defaultOpen={false}>
              <LotGroupedTable
                title="Équipements"
                icon={PackageSearch}
                rowsByLot={analysis.equipements_par_lot}
                columns={EQUIPMENT_COLUMNS}
              />
            </Section>
          )}

          <Section title="Quick actions" icon={MessageSquare} defaultOpen={false}>
            <div className="space-y-2">
              <button onClick={exportJson} disabled={!extraction && !analysis}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold text-gray-600 border border-gray-200 hover:bg-gray-50 disabled:opacity-40 transition-colors">
                <Download size={13} /> Export JSON
              </button>
            </div>
          </Section>
        </>
      )}
    </div>
  );
}