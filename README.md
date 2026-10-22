# P059 — AI Shopping Agent

Assistant d’achat avec une interface web React et une API FastAPI. Le frontend et le backend sont deux applications séparées : le frontend peut tourner sur ton PC pendant que l’API tourne sur la VM.

## Structure du projet

```text
ai-shopping-agent/
├── backend/   API FastAPI, agent, catalogue, données et tests Python
└── frontend/  interface React + TypeScript + Vite
```

## Démarrage en développement

### 1. Démarrer l’API sur la VM

Dans le terminal SSH de la VM :

```bash
cd ~/ai-shopping-agent/backend
python3 -m venv .venv       # à faire une seule fois à cet emplacement
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Si le dépôt ou le dossier `backend/` a été déplacé, recrée `.venv` à son nouvel emplacement : les environnements virtuels Python ne sont pas portables. Le fichier `backend/.env` doit contenir les variables nécessaires à l’agent. Ne le publie pas et ne le copie pas dans le frontend.

L’API est alors disponible sur le port `8000` de la VM. Laisse ce terminal ouvert.

### 2. Relier le frontend local à la VM

Dans un **terminal Windows local** (CMD ou PowerShell), ouvre un tunnel SSH. Remplace `IP_DE_LA_VM` par l’adresse utilisée pour te connecter :

```cmd
ssh -N -L 8000:127.0.0.1:8000 azureuser@IP_DE_LA_VM
```

Laisse cette fenêtre ouverte. Le tunnel permet à Vite d’envoyer les requêtes API vers la VM sans ouvrir le port du backend dans le navigateur.

### 3. Lancer l’interface sur ton PC

Dans une autre fenêtre CMD, va dans le dossier `frontend` de ta copie locale du projet :

```cmd
cd /d "C:\chemin\vers\ai-shopping-agent\frontend"
npm install
npm run dev
```

Ouvre l’adresse affichée par Vite, normalement `http://localhost:5173`. La configuration Vite relaie les requêtes `/chat`, `/health`, `/conversations`, `/products` et `/config` vers `localhost:8000`, qui arrive dans le tunnel SSH.

`npm install` génère `frontend/package-lock.json` lors de la première installation. Conserve ce fichier avec le projet ; ensuite, utilise `npm ci` pour installer exactement les versions verrouillées.

## Vérifications

Depuis `frontend/` :

```bash
npm run lint
npm run typecheck
npm run test
npm run build
```

Depuis `backend/`, avec `.venv` activé :

```bash
python -m pytest
```

## Déploiement

Le frontend peut être déployé séparément, par exemple sur Vercel. Dans ce cas, configure `VITE_API_BASE` avec l’adresse HTTPS publique de l’API, puis autorise le domaine du frontend dans la configuration CORS du backend. Le tunnel `localhost` décrit plus haut sert uniquement au développement local.

Pour construire le frontend depuis la VM, avec Node.js 20 ou 22 installé :

```bash
cd ~/ai-shopping-agent/backend
./scripts/build_frontend.sh
```

Le backend sert le build présent dans `frontend/dist/` lorsqu’il existe.

## Documentation complémentaire

- [Documentation du backend](backend/README.md)
- [Plan et notes du frontend](backend/docs/frontend-plan.md)
- [Instructions pour les captures d’écran](backend/docs/screenshots/README.md)
