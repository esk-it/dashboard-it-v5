# Guide complet : Configuration CI/CD, Build, Signature et Mise à jour automatique

Ce fichier explique **exactement** comment configurer le système de build automatique, signature et mise à jour pour le projet ITManager Dashboard v5 (Tauri v2).

## Résumé du fonctionnement

1. Tu pushes un **tag** `v*` (ex: `v5.0.0`) sur GitHub
2. GitHub Actions **build** l'app (frontend Svelte + backend PyInstaller + Tauri)
3. L'exe NSIS est **zippé** (méthode Store, pas Deflate) et **signé**
4. Un fichier `latest.json` est créé avec la signature et l'URL du zip
5. Tout est **uploadé** comme assets de la release GitHub
6. L'app installée vérifie `latest.json` au démarrage et propose la mise à jour

---

## Étape 1 : Générer les clés de signature

Dans un terminal (PowerShell ou CMD) :
```bash
cd C:\Users\jdeniel\Documents\Projets\Dashboard-Web-v5
npx tauri signer generate -w ~/.tauri/itmanager-v5.key
```

Quand il demande un password → **appuie sur Entrée** (pas de mot de passe).

Il affiche :
- **Your public key:** `dW50cnVz...` → NOTE-LA (pour tauri.conf.json)
- Le fichier privé est dans `~/.tauri/itmanager-v5.key` → NOTE SON CONTENU (pour GitHub secret)

Pour lire la clé privée :
```bash
cat ~/.tauri/itmanager-v5.key
```

Pour lire la clé publique :
```bash
cat ~/.tauri/itmanager-v5.key.pub
```

---

## Étape 2 : Configurer GitHub Secret

1. Va sur **https://github.com/esk-it/dashboard-it-v5/settings/secrets/actions**
2. Clique **New repository secret**
3. **Name** : `TAURI_SIGNING_PRIVATE_KEY`
4. **Secret** : colle le contenu ENTIER du fichier `~/.tauri/itmanager-v5.key`
5. Clique **Add secret**

---

## Étape 3 : Configurer tauri.conf.json

Dans `src-tauri/tauri.conf.json`, la section `bundle` doit contenir l'updater avec la clé publique.

Voici la structure complète à avoir dans `tauri.conf.json` :

```json
{
  "$schema": "../node_modules/@tauri-apps/cli/config.schema.json",
  "productName": "ITManager-Dashboard",
  "version": "5.0.0",
  "identifier": "com.esk-it.itmanager-dashboard-v5",
  "build": {
    "frontendDist": "../dist",
    "devUrl": "http://localhost:5173",
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build"
  },
  "app": {
    "windows": [
      {
        "title": "ITManager Dashboard",
        "width": 1400,
        "height": 900,
        "resizable": true,
        "fullscreen": false,
        "maximized": true
      }
    ]
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "externalBin": ["binaries/backend"],
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ]
  },
  "plugins": {
    "updater": {
      "endpoints": [
        "https://github.com/esk-it/dashboard-it-v5/releases/latest/download/latest.json"
      ],
      "pubkey": "COLLE_LA_CLÉ_PUBLIQUE_ICI"
    }
  }
}
```

**IMPORTANT** : Remplace `COLLE_LA_CLÉ_PUBLIQUE_ICI` par la clé publique obtenue à l'étape 1.

**IMPORTANT** : Change l'`identifier` pour qu'il soit différent de l'ancien projet (`com.esk-it.itmanager-dashboard-v5` au lieu de `com.esk-it.itmanager-dashboard`), sinon les deux apps vont se confondre sur Windows.

---

## Étape 4 : Le workflow CI (`.github/workflows/release.yml`)

Ce fichier doit être exactement comme ci-dessous. Il gère tout le build + signature + release :

```yaml
name: Release

on:
  push:
    tags:
      - "v*"

jobs:
  release:
    runs-on: windows-latest
    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Setup Rust
        uses: dtolnay/rust-toolchain@stable

      - name: Rust cache
        uses: swatinem/rust-cache@v2
        with:
          workspaces: src-tauri

      - name: Install npm dependencies
        run: npm ci --legacy-peer-deps

      - name: Install PyInstaller
        run: pip install pyinstaller

      - name: Install Python backend dependencies
        run: pip install -r requirements.txt

      - name: Build backend with PyInstaller
        run: pyinstaller --noconfirm backend.spec

      - name: Create sidecar directory and copy backend binary
        run: |
          New-Item -ItemType Directory -Path "src-tauri\binaries" -Force
          Copy-Item "dist\backend.exe" "src-tauri\binaries\backend-x86_64-pc-windows-msvc.exe" -Force

      - name: Build Tauri app (with signing)
        shell: bash
        env:
          TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}
          TAURI_SIGNING_PRIVATE_KEY_PASSWORD: ""
        run: |
          npx tauri build

      - name: Sign bundles and create release
        shell: bash
        env:
          TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}
          TAURI_SIGNING_PRIVATE_KEY_PASSWORD: ""
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          VERSION="${GITHUB_REF_NAME#v}"
          TAG="${GITHUB_REF_NAME}"
          BUNDLE_DIR="src-tauri/target/release/bundle"

          # Find NSIS exe
          NSIS_EXE=$(find "$BUNDLE_DIR/nsis" -name "*.exe" 2>/dev/null | head -1)
          if [ -z "$NSIS_EXE" ]; then
            echo "FATAL: No .exe found!"
            exit 1
          fi

          # Create zip with STORE method (no compression = max compatibility)
          NSIS_DIR=$(dirname "$NSIS_EXE")
          NSIS_EXE_NAME=$(basename "$NSIS_EXE")
          NSIS_ZIP_NAME="${NSIS_EXE_NAME%.exe}.nsis.zip"
          rm -f "$NSIS_DIR/$NSIS_ZIP_NAME"
          pushd "$NSIS_DIR"
          7z a -tzip -mx=0 "$NSIS_ZIP_NAME" "$NSIS_EXE_NAME"
          popd
          NSIS_ZIP="$NSIS_DIR/$NSIS_ZIP_NAME"

          # Sign the zip
          npx tauri signer sign "$NSIS_ZIP"
          NSIS_ZIP_SIG=$(cat "${NSIS_ZIP}.sig")

          # Extract release notes from commit message
          RELEASE_NOTES_JSON=$(git log -1 --pretty=format:"%s" 2>/dev/null | sed 's/"/\\"/g' | sed 's/^v[0-9.]* [-—] //' || echo "Nouvelle version")

          # Build latest.json
          NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
          NSIS_ZIP_NAME=$(basename "$NSIS_ZIP")
          DOWNLOAD_URL="https://github.com/$GITHUB_REPOSITORY/releases/download/$TAG/$NSIS_ZIP_NAME"
          printf '{\n  "version": "%s",\n  "notes": "%s",\n  "pub_date": "%s",\n  "platforms": {\n    "windows-x86_64": {\n      "signature": "%s",\n      "url": "%s"\n    }\n  }\n}\n' "$VERSION" "$RELEASE_NOTES_JSON" "$NOW" "$NSIS_ZIP_SIG" "$DOWNLOAD_URL" > latest.json

          # Create GitHub Release
          gh release create "$TAG" \
            --repo "$GITHUB_REPOSITORY" \
            --title "ITManager Dashboard $TAG" \
            --notes "$RELEASE_NOTES_JSON" \
            --latest

          sleep 3

          # Upload assets
          NSIS_EXE=$(find "$BUNDLE_DIR/nsis" -name "*.exe" 2>/dev/null | head -1)
          MSI_FILE=$(find "$BUNDLE_DIR/msi" -name "*.msi" 2>/dev/null | head -1)

          for f in latest.json "$NSIS_EXE" "$MSI_FILE" "$NSIS_ZIP"; do
            if [ -n "$f" ] && [ -f "$f" ]; then
              echo "Uploading: $f"
              gh release upload "$TAG" "$f" --repo "$GITHUB_REPOSITORY" --clobber
            fi
          done

          # Upload .sig files
          find "$BUNDLE_DIR" -name "*.sig" 2>/dev/null | while read sigfile; do
            gh release upload "$TAG" "$sigfile" --repo "$GITHUB_REPOSITORY" --clobber
          done

          echo "Release $TAG published!"
```

---

## Étape 5 : Les permissions Tauri (capabilities)

Le fichier `src-tauri/capabilities/default.json` doit contenir :

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "default",
  "description": "enables the default permissions",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "shell:allow-spawn",
    "shell:allow-stdin-write",
    "shell:allow-kill",
    "shell:allow-open",
    "updater:default",
    "dialog:default",
    "fs:default"
  ]
}
```

---

## Étape 6 : Les dépendances Rust (Cargo.toml)

Dans `src-tauri/Cargo.toml`, section `[dependencies]` :

```toml
serde_json = "1.0"
serde = { version = "1.0", features = ["derive"] }
log = "0.4"
tauri = { version = "2.10.3", features = [] }
tauri-plugin-log = "2"
tauri-plugin-shell = "2"
tauri-plugin-updater = "2"
tauri-plugin-dialog = "2"
tauri-plugin-fs = "2"
reqwest = { version = "0.12", features = ["json"] }
```

---

## Étape 7 : Le code Rust de mise à jour (lib.rs)

Le fichier `src-tauri/src/lib.rs` doit enregistrer tous les plugins ET contenir la logique de mise à jour. Voici les points importants :

1. **Enregistrer les plugins** :
```rust
.plugin(tauri_plugin_shell::init())
.plugin(tauri_plugin_updater::Builder::new().build())
.plugin(tauri_plugin_dialog::init())
.plugin(tauri_plugin_fs::init())
.plugin(tauri_plugin_log::Builder::default().level(log::LevelFilter::Info).build())
```

2. **Vérification de MAJ au démarrage** : Le code spawne une tâche async qui attend ~8 secondes puis vérifie les MAJ via l'endpoint configuré dans tauri.conf.json.

3. **Dialog natif** : Utilise `tauri-plugin-dialog` avec `MessageDialogButtons::OkCancelCustom` pour demander à l'utilisateur.

4. **Kill du backend** : Avant l'installation, le backend.exe doit être tué avec `taskkill /F /IM backend.exe` ET `taskkill /F /IM backend-x86_64-pc-windows-msvc.exe`.

5. **Backup pré-MAJ** : Appel HTTP à `http://localhost:8010/api/settings/backup/pre-update` avant de lancer le téléchargement.

6. **Force exit** : Après installation, `std::process::exit(0)` pour laisser NSIS prendre le relais.

Réfère-toi au fichier `src-tauri/src/lib.rs` du projet original (`Dashboard-Web`) pour le code complet.

---

## Étape 8 : Packages npm nécessaires

```bash
npm install @tauri-apps/plugin-dialog @tauri-apps/plugin-fs @tauri-apps/plugin-shell --legacy-peer-deps
```

---

## Étape 9 : Premier build

1. Vérifie que le secret GitHub est configuré (étape 2)
2. Vérifie que la clé publique est dans tauri.conf.json (étape 3)
3. Commit tout et pousse :
```bash
git add -A
git commit -m "v5.0.0 — Initial release with new visual design"
git tag v5.0.0
git push origin main v5.0.0
```
4. Va sur https://github.com/esk-it/dashboard-it-v5/actions pour suivre le build
5. Après ~10 min, la release est disponible sur https://github.com/esk-it/dashboard-it-v5/releases

---

## Pièges à éviter

- **Zip Deflate** : L'updater Tauri ne supporte PAS Deflate. Toujours utiliser `7z a -tzip -mx=0` (méthode Store).
- **Svelte 5** : `{@const}` doit être le PREMIER enfant d'un block `{#each}`, `{#if}`, etc. Pas au milieu d'un `<div>`.
- **Emojis Python** : Utiliser des littéraux (`"✅"`) pas des escapes (`"\u{1F...}"` qui est du Rust/Svelte, pas du Python).
- **Routes FastAPI** : Les endpoints avec path param (`/{id}`) doivent être APRÈS les routes fixes (`/references/tree`).
- **window.open()** : Ne fonctionne pas dans Tauri. Utiliser `@tauri-apps/plugin-shell` → `open(url)`.
- **Backend lent à démarrer** : Le sidecar met 3-5s. Le frontend doit avoir des retries pour charger les settings.
- **Données persistantes** : Toujours utiliser `ITMANAGER_DATA_DIR` (AppData) pour les configs/caches, JAMAIS le dossier d'installation (écrasé à chaque MAJ).
