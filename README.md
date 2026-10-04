# P059 — Hello World de l'agent IA de commande

Première brique fonctionnelle : valide que la boucle **Thought → Action → Observation**
(function calling) tourne de bout en bout, avec un seul outil factice (`get_current_time`).
Les vrais outils (`SearchProductTool`, `PlaceOrderTool`) viendront à la phase suivante
(cœur fonctionnel), en suivant exactement la même structure.

## Installation

```bash
chmod +x setup.sh
./setup.sh
```

Le script crée l'environnement virtuel, installe les dépendances, copie `.env.example`
vers `.env`, et lance les tests qui ne nécessitent pas de clé API.

**Renseigne ensuite ta clé dans `.env`** (`GROQ_API_KEY=...`) — clé gratuite disponible sur
[console.groq.com](https://console.groq.com).

## Lancer le serveur

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

## Tester

```bash
# Santé du service
curl localhost:8000/health

# Une question qui ne nécessite pas l'outil
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"message": "Bonjour, comment vas-tu ?"}'

# Une question qui déclenche l'outil (à valider : le LLM doit choisir d'appeler get_current_time)
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"message": "Quelle heure est-il actuellement ?"}'
```

Ou lance directement les tests avec une vraie clé configurée :

```bash
pytest tests/ -v
```

## Structure

```
app/
├── main.py          # FastAPI : endpoints /health et /chat
├── agent.py          # Boucle d'agent (Thought/Action/Observation, max 4 étapes)
├── llm_client.py      # Client LLM (Groq, compatible OpenAI SDK) — seul fichier à
│                        modifier pour changer de fournisseur (Anthropic, Ollama...)
└── tools/
    └── hello_tool.py  # Outil factice de validation — à remplacer par les vrais outils
```

## Critère de succès de cette étape (aligné avec le CDC, phase "hello world")

- [ ] `./setup.sh` s'exécute sans erreur sur une machine vierge
- [ ] Le serveur démarre et `/health` répond
- [ ] Une question sans rapport avec l'heure obtient une réponse directe (pas d'appel d'outil)
- [ ] Une question sur l'heure déclenche bien `get_current_time` (vérifiable dans le champ `trace` de la réponse)
- [ ] Le même `setup.sh` fonctionne à l'identique une fois rejoué sur la VM du bac à sable
