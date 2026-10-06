# Installer WooCommerce sur la VM

## 1. Lancer WordPress (sur la VM, en SSH)

```bash
cd infra
sudo apt install -y docker.io docker-compose-plugin
sudo docker compose up -d
```

Vérifie : `curl localhost` doit répondre du HTML WordPress. Ouvre le port **80** dans le NSG Azure (comme pour le port 8000) si ce n'est pas déjà fait.

## 2. Terminer l'installation WordPress (dans ton navigateur)

Va sur `http://<IP_PUBLIQUE_VM>` — l'assistant d'installation WordPress s'affiche. Choisis une langue, un nom de site, un compte admin (note bien le mot de passe). Termine l'installation.

## 3. Installer le plugin WooCommerce

Dans l'admin WordPress (`http://<IP_PUBLIQUE_VM>/wp-admin`) :
1. **Plugins → Add New Plugin**
2. Cherche "WooCommerce", clique **Install Now** puis **Activate**.
3. L'assistant de configuration WooCommerce se lance — tu peux passer rapidement les étapes (devise, adresse boutique...), les valeurs par défaut suffisent pour un projet de démo.

## 4. Ajouter quelques produits

**Products → Add New** — recrée les mêmes produits que `data/products.json` (ou laisse les produits d'exemple si WooCommerce en propose). Pas besoin de variations pour l'instant — des produits simples suffisent pour `create_order`.

## 5. Générer les clés API

**WooCommerce → Settings → Advanced → REST API → Add key**
- Description : `agent-p059`
- Permissions : **Read/Write**
- Clique **Generate API key**

Shopify t'avait appris la leçon : **copie `Consumer key` et `Consumer secret` immédiatement**, ils ne sont affichés qu'une fois. Colle-les dans ton `.env` :

```
WOOCOMMERCE_URL=http://<IP_PUBLIQUE_VM>/wp-json/wc/v3
WOOCOMMERCE_CONSUMER_KEY=ck_...
WOOCOMMERCE_CONSUMER_SECRET=cs_...
```

## 6. Synchroniser le catalogue et tester

```bash
python scripts/sync_woocommerce_catalog.py
python scripts/index_catalog.py
pytest tests/test_order_tools.py -v   # tests offline (mockés), doivent déjà passer
```

Puis test réel :
```bash
uvicorn app.main:app --reload
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"message": "je veux commander un t-shirt noir"}'
```
