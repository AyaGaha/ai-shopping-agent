# Guide d'exploitation

## Démarrage et vérification

Sur Ubuntu, la reconstruction WooCommerce est décrite dans [INSTALL_WOOCOMMERCE.md](../infra/INSTALL_WOOCOMMERCE.md). Après avoir renseigné `GROQ_API_KEY` dans `.env` :

```bash
sudo systemctl enable --now ai-shopping-agent
sudo systemctl status ai-shopping-agent
curl -fsS http://localhost:8000/health
```

Attendre dans les logs le `search.model_warmup` avec `status=ready` avant le premier chat. Le premier chargement de `all-MiniLM-L6-v2` peut être long sur une VM neuve.

## Logs

```bash
sudo journalctl -u ai-shopping-agent -f
docker compose --env-file infra/.env -f infra/docker-compose.yml logs -f wordpress db
```

Les événements JSON importants sont `chat.request`, `llm.request`, `llm.retry`, `llm.fallback`, `tool.execution`, `guardrail.decision` et `search.model_warmup`. Ils exposent les durées, étapes et décisions; ils ne doivent pas contenir de clé API ni le texte intégral des messages.

## Dégradation du fournisseur LLM

L'agent tente au plus trois appels, avec un délai de 1 puis 2 secondes, pour une erreur de connexion ou les statuts HTTP transitoires prévus. En cas d'épuisement, il répond avec un fallback déterministe et conserve une réponse HTTP 200. S'il a déjà recherché le catalogue, le fallback ne cite que les produits présents dans l'observation serveur. S'il a créé une commande, il précise qu'elle reste en attente et ne relance pas le POST.

Démo locale, sans toucher à la configuration Groq ou WooCommerce :

```bash
.venv/bin/python -m scripts.demo_degraded_mode
```

Le script simule des erreurs de connexion via le client en mémoire, supprime les attentes réelles et passe par la boucle d'agent et son fallback de production. Il ne teste pas une panne réseau réelle.

## Reprise

- **LLM indisponible** : vérifier `llm.request` et `llm.retry`; le client peut réessayer après la réponse de repli.
- **Warmup/recherche en erreur** : ne pas redémarrer en boucle; inspecter `search.model_warmup`, le fichier `data/products.json` et l'index `chroma_data/`.
- **État de commande incertain** : vérifier la commande dans WooCommerce avant toute nouvelle tentative. Les POST de création ne sont jamais rejoués automatiquement.
- **Perte de volume WordPress** : restaurer un backup ou lancer la reconstruction complète; une nouvelle base implique de nouvelles clés REST.

La boutique de démo utilise actuellement HTTP. Ne l'expose pas comme boutique de production : configure HTTPS avant d'envoyer les identifiants REST sur un réseau public.
