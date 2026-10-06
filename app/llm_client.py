"""
Client LLM — pointe vers l'API Groq (gratuite, compatible OpenAI SDK).

Pour changer de fournisseur plus tard (Anthropic, OpenAI, Ollama local),
c'est le SEUL fichier à modifier — le reste du code (agent.py) ne connaît
que l'interface OpenAI-style (chat.completions.create avec `tools=`).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"


def get_client() -> OpenAI:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY manquante. Copie .env.example vers .env et renseigne ta clé."
        )
    return OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)


def get_model() -> str:
    return os.environ.get("GROQ_MODEL", DEFAULT_MODEL)
