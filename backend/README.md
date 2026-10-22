# P059 — Hello World de l'agent IA de commande

## Frontend

L’interface React 18, TypeScript et Vite se trouve dans `frontend/`. Pour le développement, lancer l’API FastAPI sur le port 8000, puis depuis `frontend/` exécuter `npm ci` et `npm run dev`. Vite relaie `/chat`, `/health`, `/conversations`, `/products` et `/config` vers l’API locale. `VITE_API_BASE` permet de choisir un autre préfixe d’API.

Pour la production, exécuter `scripts/build_frontend.sh` (Node 20 est requis uniquement pour cette compilation). Le résultat `frontend/dist/` est servi par FastAPI à `/` lorsqu’il existe; les fichiers versionnés sont mis en cache durablement et `index.html` est revalidé. Sans `dist`, le backend conserve son fonctionnement API.

Le client conserve l’index des conversations, les préférences et les brouillons dans le stockage local versionné du navigateur. Les messages et commandes restent côté serveur. Le contenu assistant et les produits sont affichés via Markdown sans HTML brut; aucun secret ni appel de police CDN n’est intégré au frontend. Le catalogue public provient de l’instantané `data/products.json`. Les propositions de commande doivent toujours être confirmées dans un message distinct.

La politique CSP du frontend autorise par défaut la même origine et les images locales ou `data:`. Si des images WooCommerce distantes sont configurées, `CSP_IMAGE_HOSTS` accepte une liste d’origines HTTPS autorisées séparées par des espaces. Les navigateurs qui désactivent le stockage local ne conserveront pas l’index entre deux sessions.

Gates frontend: `npm run lint`, `npm run typecheck`, `npm run test` et `npm run build` depuis `frontend/`.

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

## Résilience de l'appel LLM

Chaque requête LLM a un timeout de 20 secondes. L'agent effectue au maximum
3 tentatives au total, avec un délai exponentiel de 1 puis 2 secondes, pour les
erreurs de connexion et les statuts HTTP 408, 409, 429 et 5xx. Les erreurs
client comme HTTP 400 ne sont pas réessayées. Les retries automatiques du SDK
sont désactivés afin que cette politique reste bornée et observable.

Après épuisement des tentatives, l'agent retourne et persiste une réponse de
repli. Elle reprend les résultats vérifiés du catalogue si la recherche a déjà
réussi; si une commande est déjà créée, elle précise qu'elle reste en attente
et n'a pas été confirmée. Le journal signale `llm.retry`, `llm.fallback` et
`chat.request` avec l'issue `degraded`. La création d'une commande WooCommerce
reste sans retry automatique pour éviter les doublons.

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

Pour mesurer le premier choix d'outil du modèle sur les scénarios de référence :

```bash
python -m scripts.evaluate --only tool-selection
```

Ce mode appelle le LLM une fois par scénario, mais n'exécute aucun outil : les
commandes de création, confirmation et annulation ne sont donc jamais envoyées
à WooCommerce. Il mesure l'outil choisi (ou l'absence d'outil), la précision et
la latence p50/p95.

Le rapport JSON comprend Hit@1, Hit@3, MRR, taux de faux positifs sur les
requêtes sans résultat, latences p50/p95, taux d'erreur, taux de blocage des
attaques et taux de faux blocage. Le modèle d'embedding peut devoir être chargé
au premier lancement : le rapport sépare maintenant la latence du premier
résultat (chargement à froid) de la latence des requêtes suivantes (modèle
chaud). Pour tester des seuils particuliers, répéter
`--threshold`, par exemple `--threshold 0.6 --threshold 0.7`.
`scripts/index_catalog.py` configure explicitement la distance ChromaDB en
cosine lors de la création d'un index. Les modes `retrieval` et `guardrails`
sont hors ligne; seul `tool-selection` appelle le LLM.

Le comparatif des modèles est archivé dans `reports/embedding-model-comparison.json`
et analysé dans `docs/evaluation-retrieval.md`. Le modèle de production reste
`all-MiniLM-L6-v2`; le modèle multilingue n'est pas activé, son coût mesuré sur
la VM étant trop élevé.

## Reconstruction de WordPress et WooCommerce

Sur une VM Ubuntu neuve, `infra/cloud-init.yaml` installe Docker/Compose, récupère
le dépôt, lit l'IP publique depuis Azure IMDS et lance `infra/provision.sh`. Le
script crée WordPress et MySQL, installe WooCommerce par WP-CLI, règle la devise
TND, ajoute ou met à jour les neuf produits de démonstration, crée une clé REST,
puis synchronise le catalogue et reconstruit l'index avec le modèle de production
`all-MiniLM-L6-v2`.

Pour reconstruire sur une VM déjà préparée :

```bash
cd ~/ai-shopping-agent
SITE_URL=http://<IP_PUBLIQUE_VM> infra/provision.sh
```

Le port WordPress par défaut est **80** (`WORDPRESS_PORT` le remplace). Le port
FastAPI est **8000**. Ouvre ces ports dans le NSG Azure pour la démonstration.
Les secrets générés restent dans `infra/.env`, `infra/.secrets/` et `.env`, tous
ignorés par Git avec des permissions restrictives. Le provisionnement conserve
les volumes Docker et peut être relancé. Pour une reconstruction à blanc, il
faut supprimer explicitement les volumes `db_data` et `wp_data`.

Le script installe les dépendances Python s'il n'y a pas déjà de `.venv`. Il ne
peut pas fournir une clé Groq : ajoute `GROQ_API_KEY` dans `.env`, puis démarre
l'application avec `uvicorn app.main:app --host 0.0.0.0 --port 8000`. Le fichier
cloud-init installe également une unité systemd; une fois la clé ajoutée, lance
`sudo systemctl enable --now ai-shopping-agent` et consulte les journaux avec
`sudo journalctl -u ai-shopping-agent -f`.

Les détails, les choix d'images et les limites du test de reconstruction sont
dans [`infra/INSTALL_WOOCOMMERCE.md`](infra/INSTALL_WOOCOMMERCE.md). Ne lance pas
`docker compose down -v` sur la VM existante : cette commande efface sa base et
son contenu.

Le diagramme du flux est dans [`docs/architecture.md`](docs/architecture.md), le
guide de service dans [`docs/operations.md`](docs/operations.md), et les choix
structurants dans [`docs/decisions.md`](docs/decisions.md). La démo du fallback
LLM se lance avec `.venv/bin/python -m scripts.demo_degraded_mode`.

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
