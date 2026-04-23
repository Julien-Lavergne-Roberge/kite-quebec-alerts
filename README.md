# Kite Québec Alerts

Script quotidien qui interroge 3 modèles météo (Open-Meteo ECMWF, GEM
d'Environnement Canada, MET Norway), évalue chaque heure entre 9h et 19h sur
6 spots de kitesurf, écrit un résumé pour un dashboard web, et envoie une
alerte Telegram à 6h30 (EDT) seulement si au moins un spot a des conditions
vertes aujourd'hui ou demain.

## Spots suivis

Oka · Saint-Placide · Pointe-du-Moulin · Saint-Zotique · Salaberry-Valleyfield ·
Cap-Saint-Jacques.

Modifier `config.py` pour ajuster coordonnées, orientations acceptables ou
critères (vent, température, pluie).

## Installation

### 1. Révoquer l'ancien token Telegram et en créer un nouveau

Dans Telegram, @BotFather → `/token` → choisir ton bot → révoquer → prendre
le nouveau token. **Ne le colle jamais dans le code, seulement dans les
GitHub Secrets (étape 4).**

### 2. Trouver ton `chat_id` Telegram

1. Dans Telegram, ouvre ton bot et envoie-lui `/start`.
2. Dans un navigateur, va à
   `https://api.telegram.org/bot<TON_NOUVEAU_TOKEN>/getUpdates`
3. Note le nombre après `"chat":{"id":`. C'est ton `chat_id`.

### 3. Créer le repo GitHub et pousser ces fichiers

```bash
cd "C:\Users\joula\OneDrive - polymtl.ca\Documents\2026\Claude\Kitesurf"
git init
git add .
git commit -m "Initial commit"
gh repo create kite-quebec-alerts --public --source=. --remote=origin --push
```

(Si tu n'as pas `gh`, crée le repo manuellement sur github.com puis
`git remote add origin https://github.com/<TON_USER>/kite-quebec-alerts.git`
et `git push -u origin main`.)

### 4. Ajouter les GitHub Secrets

Dans le repo sur github.com → Settings → Secrets and variables → Actions →
New repository secret, ajoute :

- `TELEGRAM_TOKEN` : le nouveau token du bot
- `TELEGRAM_CHAT_ID` : ton chat_id
- `DASHBOARD_URL` : `https://<TON_USER>.github.io/kite-quebec-alerts/`

### 5. Activer GitHub Pages

Settings → Pages → Source : `Deploy from a branch` → Branch : `main`,
dossier `/docs` → Save. Attends ~1 minute.

### 6. Premier lancement

Actions → `Daily kite check` → `Run workflow`. Après ~30 sec, vérifie :

- `docs/data.json` est mis à jour (commit automatique du bot).
- Le dashboard `https://<TON_USER>.github.io/kite-quebec-alerts/` affiche les
  6 spots.
- Si au moins un spot est vert aujourd'hui ou demain, tu reçois un Telegram.
  Sinon, silence (c'est voulu).

## Tester en local (Spyder)

```bash
pip install -r requirements.txt
# PowerShell (Windows) :
$env:TELEGRAM_TOKEN="..."
$env:TELEGRAM_CHAT_ID="..."
python check_kite.py
```

Si les variables d'environnement ne sont pas définies, le script imprime le
message Telegram en console au lieu de l'envoyer — pratique pour tester.

## Ajouter l'icône à l'écran d'accueil iPhone

Safari → ouvre le dashboard → bouton Partager → « Sur l'écran d'accueil ».
L'app s'ouvrira en plein écran comme une vraie app.

(Les fichiers `icon-192.png` et `icon-512.png` référencés dans
`manifest.json` ne sont pas fournis. Tu peux en générer via
favicon.io ou similaire, ou ignorer — l'app fonctionne sans.)

## Fuseau horaire

Le cron GitHub Actions tourne à **10:30 UTC** = 6:30 EDT (heure avancée,
avril-novembre). En EST (novembre-mars) ça devient 5:30, mais la saison
kite au Québec coïncide avec EDT donc pas d'enjeu. Si tu veux ajuster,
édite `.github/workflows/daily.yml`.

## Structure

```
.
├── check_kite.py            # script principal
├── config.py                # spots + critères (à customiser)
├── requirements.txt
├── .github/workflows/daily.yml
├── docs/                    # PWA (GitHub Pages)
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   ├── manifest.json
│   └── data.json            # écrit par le script, commité par GH Actions
└── README.md
```

## Idées pour plus tard

- Heure d'alerte variable selon l'heure de pointe du vent.
- Score météo plus fin (tendance horaire, swell, couverture nuageuse).
- Historique des prédictions vs réalité pour calibrer les critères.
- Ajout d'autres spots (est du Québec, Gaspésie).
- Compte de confiance par source (si GEM et MET divergent souvent d'Open-Meteo,
  pondérer en conséquence).
