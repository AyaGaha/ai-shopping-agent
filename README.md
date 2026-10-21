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

## Conversations persistantes

L'historique est stocké côté serveur dans SQLite (`data/conversations.sqlite3` par
défaut) et les conversations inactives sont supprimées après 30 jours. Pour déplacer
la base, définir `CONVERSATION_DB_PATH` avant le démarrage. Ce fichier contient les
conversations et ne doit pas être partagé publiquement.

Le client envoie uniquement son message et, après la première réponse, le
`conversation_id` reçu du serveur :

```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"message": "Bonjour"}'
# La réponse contient conversation_id.

curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"message": "Et toi ?", "conversation_id": "<conversation_id reçu>"}'
```

Un `conversation_id` inconnu renvoie `404`. L'ancien champ client `history` est
rejeté (`422`) : seul le serveur détient l'historique faisant autorité. Le script
`python scripts/chat_cli.py` gère automatiquement cet identifiant; `/reset`
démarre une nouvelle conversation.

## Garde-fous de commande

Une proposition est vérifiée et enregistrée côté serveur avant d'être présentée :
le produit doit être publié et achetable, le stock doit suffire, et le prix/devise
sont relus depuis WooCommerce. Le récapitulatif est composé côté serveur. La
création et la confirmation ne peuvent utiliser que le produit et la quantité
enregistrés dans cette proposition, et nécessitent une confirmation explicite
dans le dernier message (`oui`, `je confirme`, `yes`, `go ahead`, etc.). Les
réponses négatives, ambiguës ou accompagnées d'une réserve ne sont pas des
confirmations.

Limites actuelles : 5 articles maximum par commande et 3 commandes confirmées
par conversation. Les identifiants d'une commande doivent correspondre à une
commande en attente de cette conversation. Les opérations WooCommerce sont
protégées par des transitions atomiques SQLite pour empêcher les doubles appels
concurrents. Le POST de création n'est pas réessayé automatiquement : en cas
d'erreur réseau dont l'issue est incertaine, l'état reste bloqué pour éviter un
doublon et nécessite une vérification manuelle dans WooCommerce.

## Logs et évaluation

Les logs applicatifs sont des lignes JSON sur stdout. Ils distinguent les
requêtes LLM, les exécutions d'outils et les décisions de garde-fou, avec
conversation, étape, décision/code d'erreur et durée. Le texte utilisateur,
les requêtes de recherche, les descriptions de produits et les secrets ne sont
pas consignés dans ces événements. Sur la VM, ils sont consultables dans les
logs du processus/service qui exécute Uvicorn.

Au démarrage, l'application précharge l'embedder et exécute une requête de
recherche en lecture seule avant d'accepter du trafic. Sur une VM froide, ce
chargement peut prendre plusieurs minutes; attendre l'événement JSON
`search.model_warmup` avec `"status":"ready"` avant d'envoyer le premier chat.
L'application ne démarre pas si le catalogue ou le modèle de recherche ne peut
pas être initialisé.

Le jeu versionné de référence est `data/evaluation_cases.json` (recherche
FR/EN, résultats attendus et cas sans résultat, confirmations et injections).
Pour exécuter seulement l'évaluation déterministe des garde-fous, sans réseau :

```bash
python -m scripts.evaluate --only guardrails
```

Pour évaluer la recherche sur l'index ChromaDB courant et comparer les seuils
de distance cosine :

```bash
python -m scripts.evaluate
```

Le rapport JSON comprend Hit@1, Hit@3, MRR, taux de faux positifs sur les
requêtes sans résultat, latences p50/p95, taux d'erreur, taux de blocage des
attaques et taux de faux blocage. Le modèle d'embedding peut devoir être chargé
au premier lancement : le rapport sépare maintenant la latence du premier
résultat (chargement à froid) de la latence des requêtes suivantes (modèle
chaud). Pour tester des seuils particuliers, répéter
`--threshold`, par exemple `--threshold 0.6 --threshold 0.7`.
`scripts/index_catalog.py` configure explicitement la distance ChromaDB en
cosine lors de la création d'un index. L'évaluation hors ligne n'appelle pas le
LLM et ne mesure donc pas le choix d'outil du modèle; ce score nécessite une
évaluation séparée avec un modèle et des outils mockés.

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
