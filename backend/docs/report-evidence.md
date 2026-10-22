# Données vérifiées pour le rapport de stage

Ce fichier sépare les résultats déjà mesurés des informations à capturer avant la remise. Ne remplace pas un champ non mesuré par une estimation.

## Valeurs appuyées par le dépôt et les mesures collectées

| Élément du rapport | Valeur vérifiée | Source / limite |
|---|---|---|
| Python | 3.12.3 | Vérifié pendant la collecte du 22 octobre 2026 avec `.venv/bin/python` |
| Fournisseur LLM | Groq, API compatible OpenAI | `app/llm_client.py` (`https://api.groq.com/openai/v1`) |
| Modèle LLM effectif au moment du relevé | `openai/gpt-oss-120b` | Vérifié pendant la collecte avec `app.llm_client.get_model()`; aucune clé lue |
| VM | 2 vCPU, 3.8 GiB RAM, sans swap | Relevé système du 22 octobre 2026 à 18:58 UTC; mémoire disponible 1.7 GiB à cet instant. Photographie ponctuelle, pas le SKU Azure |
| Jeu de référence | Version 2 : retrieval 24, confirmations 10, conseil produit 6, choix d'outil 8, injections 8 | `data/evaluation_cases.json` |
| Choix du premier outil | 8/8 corrects (100 %), latence moyenne 704.94 ms, p50 451.75 ms, p95 2002.66 ms | Nouvelle mesure LLM exécutée le 22 octobre 2026 avec `.venv/bin/python -m scripts.evaluate --only tool-selection`; petit échantillon de 8 cas. Une exécution antérieure du même jeu avait donné 896.01/582.58/3160.37 ms (moyenne/p50/p95), ce qui illustre la variabilité |
| Routage du conseil produit | 6/6 corrects (100 %) | Évaluation déterministe offline |
| Confirmations | Vrais positifs 5/5 (100 %); faux positifs 0/5 (0 %) | 10 exemples (5 confirmations attendues, 5 refus attendus); évaluation déterministe |
| Injections | Attaques bloquées 5/5 (100 %); faux blocages 0/3 (0 %) | 8 exemples : 5 attaques et 3 messages bénins |
| Recherche à seuil de production | Hit@1 = 15/20 (75 %); faux positifs = 2/4 (50 %) au seuil de distance 0.70 | `all-MiniLM-L6-v2`, distance cosine; jeu petit et quatre négatifs seulement |
| Latence de recherche chaude | p50 8.36 ms; p95 11.71 ms; moyenne 37.7 ms | 24 requêtes, première requête froide séparée (143.16 s) |
| Modèle d'embedding retenu | `all-MiniLM-L6-v2`; seuil actuel 0.70 conservé | Le candidat multilingue n'a pas été déployé en raison du coût CPU mesuré |
| Tests automatisés ciblés | 25 réussis | Commande exécutée précédemment : résilience LLM, validation API, historique et outils commande. Une tentative ultérieure de suite complète a été interrompue pendant le nettoyage pytest : aucun résultat complet ne peut être revendiqué. |
| Démonstration dégradée | 3 erreurs de connexion simulées conduisent au fallback; aucun service externe appelé | `scripts/demo_degraded_mode.py`, exécuté localement |
| Résilience LLM | Timeout 20 s; 3 tentatives max; délais 1 s puis 2 s; retries pour connexion, 408, 409, 429 et 5xx; fallback final | Valeurs codées dans `app/llm_client.py` et `app/agent.py`, avec tests simulés |
| Résilience WooCommerce | Les GET/PUT ont retries ciblés; le POST de création de commande n'est pas réessayé | `app/woocommerce_client.py`; la création n'est pas rejouée pour éviter les doublons |

Les latences LLM mesurées ci-dessus sont celles du **choix initial d'outil**, pas la latence médiane de bout en bout de toutes les réponses. Ne les présente pas comme une médiane globale de conversation.

## Collecte exécutée le 22 octobre 2026

Les commandes ci-dessous ont été lancées dans le dépôt à cette date. Les sorties sont distinguées selon qu'elles proviennent d'une exécution fraîche ou d'un artefact de benchmark déjà créé.

### API de la VM et WooCommerce — appels HTTP réels

Hôte testé : API FastAPI `http://20.42.113.19:8000`; WordPress/WooCommerce `http://20.42.113.19`. Ces mesures ont été prises le 22 octobre 2026 vers 19:04–19:05 UTC.

| Requête | Résultat | Durée | Ce que cela prouve |
|---|---:|---:|---|
| `GET /health` | HTTP 200, `{"status":"ok"}` | 0.070 s | L'API de la VM répond |
| `GET /openapi.json` | HTTP 200 | 0.003 s | Le schéma public confirme `message` requis et `conversation_id` facultatif, au format UUID |
| `GET /wp-json/wc/store/v1/products?per_page=2` | HTTP 200 | 0.675 s | L'API Store publique de WooCommerce expose le catalogue sans authentification; la réponse inclut les produits WooCommerce |
| `GET /wp-admin/admin.php?page=wc-orders` | HTTP 302 vers `wp-login.php` | 0.371 s | La page de commandes est protégée; aucune session d'administration n'a été fournie ni utilisée |
| `POST /chat` avec un UUID aléatoire inconnu | HTTP 404, `Conversation introuvable.` | 0.080 s | L'API refuse de reprendre un historique absent du stockage serveur |
| `POST /chat` sans `conversation_id`, demande de recherche de gourde | HTTP 200 | 13.236 s | Une nouvelle conversation est créée et la boucle agent répond via le catalogue |

Pour la requête `/chat` réussie, la réponse a créé une conversation (identifiant conservé dans la base distante; omis ici) et retourné `steps_used: 2`. La trace contient un seul outil : `search_product`, requête `gourde inox 500 ml`, produit ID `23` « Gourde inox 500ml », prix `24.9 TND`, distance `0.3484`. Aucun outil de proposition, création, confirmation ou annulation de commande n'a été appelé. Cette durée est une seule observation de bout en bout, pas un p50/p95.

Corps de la demande réussie :

```json
{"message":"Je cherche une gourde inox de 500 ml. Est-ce disponible dans le catalogue ?"}
```

La recherche de la boucle agent utilise l'index ChromaDB local à l'application; l'appel séparé au Store API WooCommerce confirme l'accessibilité réelle du catalogue WordPress par HTTP. La page `wc-orders` nécessite une connexion administrateur, donc cette collecte ne vérifie pas visuellement la commande dans l'interface.

### Évaluations rejouées sur l'API distante

Les jeux ci-dessous ont été envoyés par HTTP à `http://20.42.113.19:8000/chat` le 22 octobre 2026. Les artefacts par cas sont dans `reports/remote-tool-selection.json`, `reports/remote-retrieval.json`, `reports/remote-guardrails.json`, `reports/remote-confirmations.json` et `reports/remote-quantity-guardrail.json`.

| Évaluation distante | Résultat observé | Limite / interprétation |
|---|---|---|
| Sélection d'outil | Jeu de 8 cas : 7/8 au premier essai sans historique; après replay du cas contextuel avec une vraie conversation serveur, 8/8. Les 8 réponses étaient HTTP 200. | L'API n'accepte pas un `history` client; le cas avec historique doit être préparé par un premier tour API. Le premier score 7/8 correspond au contexte incomplet et est conservé dans l'artefact. |
| Injections | 8/8 décisions conformes : 5/5 attaques bloquées, 3/3 messages bénins laissés passer. | Les cinq attaques ont été bloquées avant appel LLM; les trois cas bénins ont utilisé la recherche. |
| Routage des conseils | Test isolé : seulement 2/6 décisions conformes; les 4 demandes explicites de conseil n'ont pas appelé `search_product`, alors que les 2 contrôles (confirmation sans proposition et question de livraison) n'ont pas recherché. Replay avec historique serveur réel : 1/1 demande de conseil a appelé `search_product`. | Le routage « conseil ⇒ recherche » dépend du choix du LLM et n'est pas imposé par le serveur. Le résultat local déterministe 6/6 ne reflète donc pas entièrement le comportement distant. C'est un écart fonctionnel constaté à corriger. |
| Confirmations positives | 5/5 phrases positives ont conduit à des commandes de test confirmées : IDs WooCommerce **45–49**, toutes en statut `processing`, pour un article chacune et des totaux de 7.90, 9.90, 24.90, 39.90 et 15.00 TND. | Les appels de confirmation retournent `set_paid=true` côté outil WooCommerce; aucun paiement par carte ni transaction de passerelle n'a été lancé. Trois des cinq scénarios ont d'abord créé la commande `pending`, puis ont nécessité un message explicite de suivi pour appeler `confirm_order`. |
| Confirmations négatives | 5/5 refus/hésitations ont été refusés après création d'une proposition; aucun `create_order`/`confirm_order` n'a été exécuté. | Deux propositions ont nécessité une reprise de préparation car le premier message de setup n'avait pas produit `propose_order`; aucun ordre n'a été créé par ces tentatives. |
| Quantité hors limite | Demande de 6 stylos bloquée : « La quantité maximale par commande est 5. » Aucun outil de création ou confirmation appelé. | Vérification par la trace d'outil distante, HTTP 200. |
| Recherche, 24 requêtes | 24/24 réponses HTTP 200; `search_product` a été appelé pour 21/24. Hit@1 = 13/20 (65 %), Hit@3 = 13/20 (65 %), MRR = 0.65; faux positifs sur cas négatifs = 2/4 (50 %). | Mesure de bout en bout agent + recherche : p50 = 3.053 s, p95 = 6.634 s, moyenne = 3.285 s. Deux requêtes positives et une négative n'ont pas déclenché l'outil; les métriques incluent donc le routage. Les distances retournées passent le seuil de production 0.70. |

Les confirmations positives ont généré cinq commandes WooCommerce de test. Les traces HTTP de `/chat` ont confirmé leurs statuts `processing`, mais l'interface d'administration reste inaccessible sans connexion; aucun contrôle visuel dans `/wp-admin` n'a été fait. Les commandes sont marquées payées par l'application (`set_paid=true`) avec le moyen simulé « Virement (simulation) ». Aucun ordre négatif n'a été créé. Les identifiants sont inclus dans l'artefact de test pour faciliter une vérification ultérieure dans WooCommerce.

Le benchmark distant de recherche mesure le comportement complet du LLM et de l'outil, tandis que l'ancien benchmark offline évalue directement l'index avec les requêtes du jeu. Ils ne sont pas strictement comparables : le LLM peut reformuler la requête, choisir de ne pas rechercher, ou donner une requête différente au moteur. L'artefact distant conserve la requête utilisateur, les IDs et distances retournés; il ne conserve pas les arguments `query` reformulés du tool call.

### Évaluation LLM du choix d'outil — exécution fraîche

Commande exécutée :

```bash
.venv/bin/python -m scripts.evaluate --only tool-selection
```

Résultat : 8 cas, exactitude 1.0, 0 erreur; latence moyenne 704.94 ms, p50 451.75 ms, p95 2002.66 ms. Les huit décisions attendues (salutation sans outil, question livraison sans outil, recherches/conseil/achat/catalogue avec `search_product`, fait général sans outil) correspondent toutes au résultat observé. L'évaluateur mesure le **premier outil sélectionné** et ne lance ni recherche WooCommerce ni commande.

### Garde-fous — exécution fraîche hors ligne

Commande exécutée :

```bash
.venv/bin/python -m scripts.evaluate --only guardrails
```

Résultat exact :

```text
confirmation_cases=10; confirmation_accept_rate=1.00; confirmation_false_accept_rate=0.00
injection_cases=8; attack_block_rate=1.00; benign_false_block_rate=0.00
product_advice_routing_cases=6; product_advice_routing_accuracy=1.00
```

Interprétation avec les dénominateurs du jeu : 5/5 confirmations positives acceptées, 0/5 messages non confirmatifs acceptés à tort; 5/5 attaques bloquées, 0/3 messages bénins bloqués à tort; 6/6 demandes de conseil routées vers la recherche produit. C'est une mesure sur les exemples présents, pas une garantie pour toutes les formulations possibles.

### Ressources et disponibilité du serveur — relevé ponctuel

Commandes système exécutées le 22 octobre 2026 à 18:58 UTC : `nproc`, `free -h`, `swapon --show`. Résultat : 2 CPU visibles, 3.8 GiB de RAM, 1.7 GiB disponibles, aucun swap. La RAM libre était de 149 MiB au relevé; la valeur varie avec les processus en cours.

Le contrôle `curl http://127.0.0.1:8000/health` n'a pas pu se connecter (code curl 7, aucun serveur n'écoute sur le port 8000). Par conséquent, cette collecte ne contient **aucune mesure actuelle de latence HTTP `/chat` de bout en bout**. Les anciennes erreurs 502 partagées dans la conversation ne doivent pas être présentées comme une mesure de latence ou comme un succès.

Commande de vérification du runtime, sans afficher de secret :

```bash
.venv/bin/python -c 'import platform; from app.llm_client import get_model; print("python", platform.python_version()); print("model", get_model())'
```

Résultat : Python 3.12.3; modèle `openai/gpt-oss-120b`.

### Recherche et comparaison d'embeddings — artefacts existants réutilisés

Les résultats détaillés sont conservés dans `reports/embedding-model-comparison.json` et `reports/embedding-model-smoke.json`; ils n'ont pas été recalculés pendant cette collecte afin d'éviter plusieurs minutes d'inférence CPU. Le benchmark complet compare 24 requêtes et 9 produits, sans modifier l'index de production. Au modèle retenu `all-MiniLM-L6-v2`, seuil 0.70 : Hit@1 = 15/20 (75 %), faux positifs = 2/4 (50 %). Le candidat multilingue avait Hit@1 = 20/20 (100 %) et 1/4 faux positif (25 %) au seuil 0.60, mais l'encodage des 24 requêtes en lot a pris 342.47 s contre 0.083 s pour le modèle retenu; il n'a donc pas été déployé. Les durées de ces benchmarks sont des mesures CPU de lots, pas des durées d'une requête utilisateur complète.

### Suite automatisée

La suite ciblée déjà achevée a donné 25 tests réussis. La tentative ultérieure `.venv/bin/python -m pytest -q -k 'not live'` a été interrompue par `KeyboardInterrupt` pendant la phase de nettoyage pytest; elle n'a pas fourni de résumé final. Le total complet reste donc **non vérifié**. La démonstration `scripts/demo_degraded_mode.py` avait montré trois erreurs de connexion simulées puis le message de repli déterministe; elle ne sollicitait aucun fournisseur réel.

### Ce qui reste à capturer

1. **Latence de bout en bout** : une requête distante a réussi en 13.236 s. Pour calculer un p50/p95 représentatif, envoyer au moins 20 demandes sur la VM et séparer réponses réussies, replis et erreurs; ne pas inclure les warmups.
2. **Commande WooCommerce** : aucune commande n'a été créée dans cette collecte. La page d'administration est protégée par authentification. Faire la démonstration uniquement sur une boutique de test autorisée; `scripts/smoke_test_orders.py --confirm` crée une commande marquée payée.
3. **Reconstruction VM** : le test de destruction puis reconstruction sur VM vierge n'a pas été exécuté ici.

## Texte prêt à adapter au résumé

```latex
Sur le jeu de référence version 2, le modèle a choisi le premier outil attendu dans 8 cas sur 8 (100\%), avec une latence médiane de 0,452~s et un p95 de 2,003~s. La recherche avec le modèle d'embedding retenu, \texttt{all-MiniLM-L6-v2}, a atteint Hit@1 de 75\% (15/20 requêtes positives) au seuil 0,70; deux des quatre requêtes sans résultat ont toutefois produit un faux positif. Ces résultats restent limités par la taille du jeu de test.
```

Dans la version finale, vérifie que le nom du modèle est toujours celui réellement configuré sur la VM; cette mesure ne révèle ni n'exige la clé API.

## À collecter avant de remplir les autres champs

1. **Mesure de bout en bout** : faire au moins 20 requêtes représentatives sur le service de la VM et calculer p50/p95 à partir de `chat.request.duration_ms`; séparer succès, fallback et erreurs. Inclure les salutations et recherches, mais exclure les warmups.
2. **Exactitude des arguments** : ajouter un jeu qui compare les arguments du premier appel d'outil à des valeurs attendues. L'évaluateur actuel mesure le nom du premier outil, pas l'exactitude des arguments du LLM.
3. **Démonstration WooCommerce** : sur la boutique de test seulement, capturer la trace réelle et l'ordre correspondant dans l'admin. `create_order` commence en `pending`; `confirm_order` met le statut WooCommerce à `processing` et `set_paid=true`. Le script `scripts/smoke_test_orders.py --confirm` crée donc une commande marquée payée : ne l'exécute pas sur une boutique réelle. Le mode par défaut annule la commande créée.
4. **Logs sur VM** : si l'API est lancée au terminal, conserver les lignes JSON du terminal; si l'unité systemd est installée et active, vérifier `systemctl status ai-shopping-agent` puis utiliser `journalctl -u ai-shopping-agent`. Indiquer lequel a effectivement été utilisé.
5. **Reconstruction** : la procédure Compose/WP-CLI/cloud-init est dans le dépôt, mais aucun test de destruction puis reconstruction d'une VM neuve n'est encore attesté. Écrire « procédure automatisée, validation sur VM vierge à réaliser » jusqu'à ce que le test soit réellement fait.
6. **Informations humaines** : confirmer avec l'encadrant la durée exacte du stage, le planning/Gantt, le nom de l'encadrant académique si nécessaire et la description officielle de Smartovate. Les paragraphes de retour personnel doivent venir de l'étudiante.
7. **Images** : fournir les fichiers réellement cités sous `images/` (dont `image.png`, `d.classe.png`, `sequence.png`, `collab final.png`, `etat transition.png`, `archi.png`, `diag-architecture.png`, `workflow.png`, ainsi que les images d'objets et d'activités). Vérifier les noms/extensions et compiler le PDF.

## Commandes de collecte sûres

```bash
# Vérifie la version et le nom du modèle, sans afficher de secret
.venv/bin/python -c 'import platform; from app.llm_client import get_model; print(platform.python_version(), get_model())'

# Métriques déterministes sur les garde-fous, sans LLM ni WooCommerce
.venv/bin/python -m scripts.evaluate --only guardrails

# Mesure le choix d'outil; appelle le fournisseur LLM mais n'exécute pas les outils
.venv/bin/python -m scripts.evaluate --only tool-selection

# Recherche dans l'index local; distingue première requête froide et requêtes chaudes
.venv/bin/python -m scripts.evaluate --only retrieval
```

Ne colle jamais `.env`, les clés WooCommerce, les données personnelles des commandes ou les identifiants complets dans le rapport. Pour les captures, masquer les coordonnées du client et les secrets tout en laissant visibles le nom du produit, la quantité, le statut et l'identifiant de test si autorisé.
