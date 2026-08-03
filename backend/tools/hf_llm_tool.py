import os
from pathlib import Path
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from dotenv import load_dotenv

# ⭐ Chercher le .env dans plusieurs emplacements
current_dir = Path(__file__).parent
env_paths = [
    current_dir / '.env',
    current_dir.parent / '.env',  # backend/.env
    Path.cwd() / '.env',
    Path.cwd() / 'backend' / '.env',
]

env_loaded = False
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[LLM] ✅ .env chargé depuis: {env_path}")
        env_loaded = True
        break

if not env_loaded:
    print("[LLM] ⚠️ Aucun fichier .env trouvé — tentative de chargement par défaut")
    load_dotenv()

GROQ_MODEL = "llama-3.3-70b-versatile"


def get_llm(temperature: float = 0.7, max_tokens: int = 1024):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "❌ GROQ_API_KEY non trouvée !\n"
            "   Créez un fichier .env dans le dossier backend/ avec :\n"
            "   GROQ_API_KEY=votre_clé_api_groq\n"
            "   Obtenez une clé sur : https://console.groq.com/keys"
        )
    return ChatGroq(
        api_key=api_key,
        model=GROQ_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def infer(prompt: str, max_new_tokens: int = 1024, temperature: float = 0.7, retries: int = 2) -> str:
    last_error = None
    for attempt in range(retries):
        try:
            llm = get_llm(temperature=temperature, max_tokens=max_new_tokens)
            response = llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            last_error = e
            error_msg = str(e)
            # Si c'est une erreur d'authentification, pas la peine de réessayer
            if '401' in error_msg or 'Invalid API Key' in error_msg or 'invalid_api_key' in error_msg:
                raise RuntimeError(
                    f"❌ Clé API Groq invalide !\n"
                    f"   Vérifiez votre GROQ_API_KEY dans le fichier .env\n"
                    f"   Obtenez une clé gratuite sur : https://console.groq.com/keys\n"
                    f"   Erreur: {e}"
                )
            if attempt < retries - 1:
                print(f"    Inference attempt {attempt + 1} failed, retrying...")
                import time
                time.sleep(2)
    
    raise RuntimeError(f"Inference failed after {retries} attempts: {last_error}")


def build_chain(system_prompt: str, human_template: str, temperature: float = 0.7, max_new_tokens: int = 1024):
    import re
    input_vars = list(set(re.findall(r"\{(\w+)\}", human_template)))

    def build_prompt(inputs: dict) -> str:
        human_content = PromptTemplate.from_template(human_template).format(**inputs)
        return f"{system_prompt}\n\n{human_content}"

    llm = get_llm(temperature=temperature, max_tokens=max_new_tokens)
    parser = StrOutputParser()
    chain = RunnableLambda(build_prompt) | llm | parser
    return chain