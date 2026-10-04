#!/usr/bin/env bash
# Script de mise en place — rejouable à l'identique sur n'importe quelle machine
# (poste local aujourd'hui, VM du bac à sable demain). C'est CE script qui doit
# tourner sur ta VM AWS/Azure pour prouver la reproductibilité exigée par le CDC.
set -e

echo "== Setup P059 — Agent IA de commande =="

echo "-- Création de l'environnement virtuel --"

# Sous Windows, la commande s'appelle "python", pas "python3".
PYTHON_BIN=$(command -v python3 || command -v python)
if [ -z "$PYTHON_BIN" ]; then
  echo "Erreur : aucun interpréteur Python trouvé (ni python3, ni python)."
  exit 1
fi
"$PYTHON_BIN" -m venv .venv

# Sous Windows, le venv crée .venv/Scripts/activate (pas .venv/bin/activate comme sur Linux/Mac).
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
elif [ -f .venv/Scripts/activate ]; then
  source .venv/Scripts/activate
else
  echo "Erreur : script d'activation du venv introuvable."
  exit 1
fi

echo "-- Installation des dépendances --"
# pip install --upgrade pip
# pip install -r requirements.txt
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ ! -f .env ]; then
  echo "-- Création de .env depuis .env.example --"
  cp .env.example .env
  echo "!! Renseigne ta clé GROQ_API_KEY dans .env avant de lancer le serveur !!"
fi

echo "-- Exécution des tests offline (ne nécessitent pas de clé API) --"
pytest tests/ -k "not live" -v

echo ""
echo "== Setup terminé =="
echo "Active l'environnement :   source .venv/bin/activate"
echo "Lance le serveur :         uvicorn app.main:app --reload"
echo "Teste l'agent en direct :  curl -X POST localhost:8000/chat -H 'Content-Type: application/json' -d '{\"message\": \"Quelle heure est-il ?\"}'"
