# Changelog

Toutes les versions notables. Pour le détail complet, voir les messages de commit ou la liste des releases sur GitHub.

---

## v7.0.9 — Import : faux "doublon SHA256" sur des fichiers déjà supprimés

Tu pouvais avoir un message **"Ce fichier existe déjà (doublon SHA256)"** alors que le fichier en question avait été supprimé du disque (manuellement ou par v7.0.7's cleanup-orphans). La row en base avait encore le `file_hash`, donc tout nouveau upload du même contenu trébuchait dessus.

### Le fix

Le check de doublon distingue maintenant 2 cas :

1. **Vrai doublon** (la row a un `file_path` qui existe sur disque) → erreur 409 avec un message utile :
   > « Un document avec ce contenu existe déjà : "Devis Konica 04-2026" (id=42). Utilise « + Rattacher un document » au lieu de le ré-importer. »

2. **Orphelin** (la row existe mais son fichier est manquant) → on supprime silencieusement la row + ses tags + ses liens, et on poursuit l'import normalement. Aucune action utilisateur requise.

Bonus : si on jette une 409 (vrai doublon), on supprime le fichier fraîchement uploadé pour ne pas accumuler de copies inutiles sur le disque.

## v7.0.8 — Documents : édition/suppression complète + retrait de la vue à plat

Toutes les fonctionnalités utiles du module Documents à plat sont maintenant disponibles directement dans la vue Dossiers. La vue à plat est supprimée.

### Backend

- **`upload_document` accepte `supplier_id`** (form param) en plus du nom. L'ID prend précédence — sync presta ↔ doc garantie, sans ambiguïté de noms.
- **Recherche dossiers étendue** : la barre de recherche du module matche maintenant aussi les titres et références (internes/externes) des documents rattachés. Tape "Konica" et tu trouves tous les dossiers contenant une facture Konica, même si le titre du dossier ne contient pas "Konica".

### Frontend — nouveaux contrôles sur chaque document

Sur chaque ligne de document dans le panel détail d'un dossier, **4 boutons** :

| Icône | Action |
|---|---|
| 👁 | Aperçu (modal iframe sur le PDF) — déjà là depuis v7.0.6 |
| ✏️ | **NOUVEAU** Éditer : titre, type, date, référence externe, prestataire, notes, flag acompte (sur facture) |
| ✕ | Détacher du dossier (le document survit, juste plus dans ce dossier) |
| 🗑 | **NOUVEAU** Supprimer définitivement (DB + fichier) — confirm explicite |

### Sync presta ↔ doc

Quand tu importes un doc dans un dossier qui a un presta, le doc est désormais relié au presta par son `supplier_id` (et apparaît dans "Documents liés" du module Prestataires). Si tu détaches le doc du dossier, le lien presta reste (le doc EST émis par ce presta, peu importe où on le range). Si tu supprimes définitivement, ça disparaît partout.

### Cleanup — vue Documents à plat supprimée

- Fichier `src/lib/pages/DocumentsPage.svelte` supprimé
- Import retiré dans `src/App.svelte` et `src/lib/pages/DossiersPage.svelte`
- Toggle "Documents (à plat)" retiré du topbar Dossiers
- CSS leftover (view-switch, ds-toggle) nettoyé

L'ancienne route `/documents` continue de fonctionner — elle pointe directement sur la vue Dossiers (déjà le cas depuis v7.0.0).

## v7.0.7 — Documents : cache busting + nettoyage des orphelins

Deux corrections autour de la liste des documents.

### 1. Cache WebView qui servait des listes périmées

Quand tu supprimais un document via la vue à plat, le Chromium embarqué de Tauri continuait à servir l'ancienne réponse de `/api/documents` en cache. Résultat : le doc supprimé restait visible dans la popup "Rattacher un document" jusqu'au prochain redémarrage de l'app.

Fix : ajout de `cache: 'no-store'` sur toutes les requêtes de l'API client. Chaque GET refait un vrai aller-retour réseau.

### 2. Documents dont le fichier a été supprimé du disque

Si tu fais le ménage manuellement dans `data/documents/` (ou si un fichier est perdu pour une autre raison), l'entrée en base reste mais pointe vers le vide. Ces orphelins polluaient la liste de "Rattacher un document".

Deux mesures :
- **Filtrage auto** : chaque document expose maintenant un champ `file_missing` (calculé via `os.path.exists`). La popup "Rattacher" filtre désormais ces orphelins par défaut.
- **Nettoyage explicite** : nouveau bouton **🧹 Nettoyer les orphelins** dans le header de la popup "Rattacher". Clic → `POST /api/documents/cleanup-orphans` qui supprime de la base les rows dont le fichier n'existe plus, et te dit combien ont été nettoyés.

Aucun fichier réel n'est jamais supprimé par cette action (par définition, ils n'existent déjà plus). Seules les rows en base sont nettoyées.

### À tester

1. Supprime un document depuis la vue "Documents (à plat)"
2. Bascule sur la vue Dossiers
3. Sélectionne un dossier, clique sur "+ Rattacher" → le doc supprimé n'apparaît plus dans la liste
4. Si tu as déjà des orphelins issus de v7.0.6 ou antérieures, ouvre "+ Rattacher" et clique sur 🧹 pour les nettoyer

## v7.0.6 — Dossiers : logos prestas, import doc, renommage auto, preview 👁

4 ajouts cohérents qui complètent le flow d'utilisation des dossiers.

### 1. Logos prestataires affichés partout

Quand un prestataire a un logo uploadé (`logo_path` non vide), le programme affiche maintenant son image au lieu de l'avatar coloré avec initiales. Appliqué à :
- L'avatar de la card du milieu (Ageona en grand)
- Le pill prestataire dans le panel détail
- Chaque item du dropdown du menu prestataire

Fallback gracieux : si pas de logo uploadé, les initiales colorées restent. Fond clair derrière l'image pour que les logos sombres restent lisibles sur thème sombre.

### 2. Bouton "+ Importer" dans le panel détail

À côté de "+ Rattacher un document" (qui prend un doc existant), un nouveau bouton **"+ Importer"** ouvre un dialog d'upload complet :

- File picker (PDF / PNG / JPG / WebP)
- Type de document (Devis / Proposition / BPA / Bon / Contrat / Facture / Rapport / Autre)
- Date du document (avec auto-détection depuis le filename)
- Référence externe (optionnel)
- Checkbox "Acompte" si type = Facture

À la soumission, le document est créé via `POST /api/documents/upload`, puis automatiquement rattaché au dossier sélectionné via `POST /api/dossiers/{id}/attach` dans la même action. Plus besoin de basculer en vue plate pour importer.

### 3. Renommage auto intelligent

Le titre du doc est **pré-rempli automatiquement** avec un format lisible : `[Type] [Prestataire] - [Date]`.

Exemple : tu importes un PDF "FV202500508250.pdf" pour le dossier rattaché à Ageona, et le titre s'écrit tout seul **"Facture Ageona - 15/04/2026"**. Tu peux toujours le modifier manuellement.

Le système essaie aussi de **deviner le type** depuis le nom du fichier ("FV..." → Facture, "devis_..." → Devis, etc.) et la **date** (formats YYYY-MM-DD ou DD-MM-YYYY embarqués dans le filename).

### 4. Preview 👁 sur chaque document

Bouton **👁 Aperçu** ajouté à côté du ✕ Détacher sur chaque ligne de document. Clic → modal plein-écran avec :
- Header avec titre + référence interne + bouton "Ouvrir dans un onglet" (utile pour zoomer / imprimer)
- Iframe sur `/api/documents/{id}/preview` qui sert le PDF / image en inline
- Fermeture au clic sur l'overlay ou la croix

Pareil que dans la vue à plat — la fonctionnalité que tu avais perdue est de retour.

## v7.0.5 — LE bug du prestataire enfin trouvé (table `suppliers` n'a pas de colonne `color`)

Tous mes fixes v7.0.1 → v7.0.4 cherchaient dans le frontend. La cause était côté backend depuis le début.

### Le bug

`_supplier_brief()` faisait :
```sql
SELECT id, name, COALESCE(color, '#6C63FF'), COALESCE(logo_path, '')
FROM suppliers WHERE id = ?
```

Mais la table `suppliers` **n'a pas de colonne `color`** (la couleur vient de `supplier_domains` joint sur `suppliers.domain`). SQLite lève une `OperationalError: no such column: color`. J'avais mis un `try/except` global qui silencait l'erreur et retournait `None`.

Conséquence : que tu assignes ou non un prestataire dans le UI, le backend renvoyait toujours `supplier: null` dans la réponse → la card et le panel détail montraient "(sans prestataire)" même quand `dossiers.supplier_id` était bien à `5` en DB.

Tous les patches précédents (binding, custom dropdown, detection mismatch…) étaient des fausses pistes — le supplier_id se sauvegardait CORRECTEMENT à chaque fois, mais le supplier brief de la réponse était toujours null.

### Le fix

Nouveau SQL avec JOIN sur supplier_domains :
```sql
SELECT s.id, s.name,
       COALESCE(sd.color_hex, '#6C63FF') AS color,
       COALESCE(s.logo_path, '') AS logo_path
FROM suppliers s
LEFT JOIN supplier_domains sd ON sd.name = s.domain
WHERE s.id = ?
```

Chaque prestataire hérite de la couleur de son domaine (Réseau → bleu, Sécurité → rouge, etc.), avec un fallback violet `#6C63FF` si pas de domaine assigné.

Le `try/except` n'avale plus l'erreur en silence — il log un warning explicite.

### À tester

Recharge le module Documents. Les dossiers avec `supplier_id` non-null devraient maintenant afficher le nom + l'avatar coloré du presta, dans la card du milieu ET dans le pill "Prestataire" du panel détail.

Si tu assignes un nouveau presta via le pill, le changement doit être visible immédiatement.

## v7.0.4 — Dossiers : refonte des controls statut/presta (les patches précédents n'avaient pas marché)

Les 3 builds précédents (v7.0.1 / v7.0.2 / v7.0.3) tentaient de fixer les mêmes 2 bugs (prestataire qui ne se sauve pas + statut invisible en thème clair) en bricolant le `<select>` natif. Aucun n'a fonctionné. Cette fois je retire entièrement le `<select>` natif et je reconstruis from scratch.

### 1. Dropdowns custom (HTML + CSS purs, plus de `<select>`)

Le `<select>` natif a trop de comportements inconsistants entre les thèmes (texte coloré qui disparaît sur fond clair) et entre les browsers (la coercion `bind:value` qui ne préserve pas toujours le type number). Je le remplace par un **dropdown custom** :

- Le pill cliquable affiche `dot coloré + texte` (toujours lisible : texte sur `var(--text-heading)`)
- Le menu déroulant est un `<div>` ordinaire que je contrôle entièrement en CSS
- Backdrop transparent qui catche les clics extérieurs pour fermer
- Pas de coercion implicite : chaque option appelle directement une fonction avec la bonne valeur

### 2. Quick-edit inline pour Statut ET Prestataire

Sortie du dialog d'édition : le statut et le prestataire sont maintenant éditables **directement dans le panneau détail**. Tu cliques sur le pill, le menu s'ouvre, tu choisis → PATCH immédiat envoyé. Pas de dialog, pas de save bouton, pas de form state qui peut foirer.

Le dialog d'édition complet (✏️) reste dispo pour les autres champs (titre, description, site, projet, budget, notes).

### 3. Détection automatique d'un bug de sauvegarde

Côté frontend, après chaque PATCH on compare la valeur envoyée avec la valeur reçue. Si elles diffèrent, on t'affiche un **toast d'erreur explicite** style `[BUG] envoyé supplier_id=5, reçu null — vérifie les logs`. Plus de bug silencieux.

### 4. Logging backend

L'endpoint `PUT /api/dossiers/{id}` log maintenant le payload reçu + le payload après filtrage Pydantic. Si ça reFait foirer on a les logs pour comprendre.

## v7.0.3 — Dossiers : prestataire qui ne se sauvait pas + statut illisible en clair

### 1. Le prestataire ne s'enregistrait pas après édition

Bug subtil de Svelte avec `bind:value` sur le dropdown du prestataire : quand l'option de départ était `null` (— Aucun —) et que l'utilisateur sélectionnait un presta (ex : Ageona, id=5), Svelte coerçait la valeur en string `"5"` plutôt qu'en number, et le backend recevait parfois la mauvaise donnée.

Fix : remplacement de `bind:value` par `value=... on:change=...` avec coercion explicite (`parseInt`). Maintenant la valeur envoyée au backend est garantie d'être soit `null`, soit un number. Même fix appliqué au dropdown du projet lié.

### 2. Dropdown statut invisible en thème clair

Précédente version : le `<select>` avait un fond légèrement teinté (rgba 4%) et le TEXTE en couleur du statut (vert pour Livré, gris pour Demande). Sur fond sombre OK, sur fond cream/clair le contraste tombait à 2-3:1, c'était illisible.

Refonte : remplacement par un pattern **dot + texte**. La pastille colorée à gauche porte le code couleur (toujours visible), et le texte du select utilise `var(--text-heading)` (noir/blanc selon thème) → lisible à 100% sur les deux modes.

### 3. Affichage explicite quand un dossier n'a pas de prestataire

Avant : si pas de presta, la ligne meta du panel détail était simplement vide → l'utilisateur ne voyait pas qu'il manquait une info. Maintenant : chip jaune cliquable **"⚠ Aucun prestataire — cliquer pour assigner"** qui ouvre directement le dialog d'édition.

## v7.0.2 — Dossiers : 4 ajustements après retour utilisateur

### 1. Status dropdown invisible en thème clair

Le `<select>` du statut avait `background: transparent` et `color: <couleur du statut>`. Sur le thème sombre la couleur ressortait, sur le thème clair le composant disparaissait dans le fond.

Fix : fond explicite (`var(--bg-input, rgba(0,0,0,0.04))`) qui s'adapte aux deux thèmes, label "STATUT" repassé sur `--text-secondary` (au lieu de `--text-muted` qui s'effaçait en clair), styles `<option>` forcés.

### 2. Auto-détection du prestataire dans le titre du dossier

Le backfill v7.0.1 ne marchait que si AU MOINS un document du dossier avait un `supplier_id`. Pour des docs uploadés à l'époque où la colonne presta n'existait pas / n'était pas remplie, le backfill ne trouvait rien.

Nouveau pass : pour chaque dossier encore sans presta, on scanne son **titre + titres/références des docs rattachés** à la recherche d'un nom de prestataire connu. Si "Devis 16122 **ageona** licences" et que "Ageona" est dans ta table prestataires → lien fait automatiquement.

Garde-fous :
- Noms de prestataires < 4 caractères ignorés (évite les faux positifs "OVH" ou "SU")
- Match sur le nom le plus long en premier ("Notre-Dame du Kreisker" gagne sur "Notre-Dame")
- Pass idempotente, tournée à chaque démarrage tant qu'il reste des dossiers à compléter

Si un match est mauvais, tu peux toujours corriger via le ✏️.

### 3. Dialogs trop transparents

`background: var(--ds-card)` pouvait résoudre vers une valeur semi-transparente. Fix : `background: var(--bg-card, #ffffff)` (fallback opaque) + overlay plus sombre (72% au lieu de 55%) + shadow plus marquée. Le dialog se découpe maintenant clairement du fond.

### 4. Champ "Validé" restreint aux Devis

La logique derrière la double saisie :

- **Devis** = "ce que le presta propose". On a `Montant` (prix devisé) + `Négocié` (prix après négo). Le champ Négocié reste vide si tu acceptes le devis tel quel.
- **BPA** = "ce que la direction a validé". Un seul champ `Montant` suffit, il EST déjà la validation.
- **Facture** = "ce qui est facturé". Un seul champ `Montant`.

Du coup l'input "Négocié" n'apparaît plus que sur les Devis et Propositions. Renommé : `€` → `Montant`, `Validé` → `Négocié` (plus parlant).

## v7.0.1 — Dossiers : correctifs après premier passage en prod

Cinq correctifs sur la base v7.0.0 d'hier.

### 1. Prestataires manquants sur les dossiers migrés

La migration v7.0.0 ne prenait le `supplier_id` que sur le "main doc" du dossier (le devis en général). Si ce doc n'avait pas de prestataire renseigné mais qu'un autre doc de la chaîne en avait un, le dossier finissait en "(sans prestataire)".

Nouveau backfill au démarrage : pour chaque dossier sans prestataire, on prend le `supplier_id` du premier doc de la chaîne qui en a un. Tournée idempotente, donc rejouée à chaque démarrage tant qu'il reste des dossiers sans presta.

### 2. Édition des dossiers existants

Bouton ✏️ ajouté à côté de la corbeille dans le panneau détail. Ouvre un dialog "Éditer le dossier" qui réutilise le formulaire de création (titre, description, statut, presta, projet lié, établissement, budget estimé, notes internes).

### 3. Montants invisibles + non éditables

Les montants étaient stockés uniquement dans `project_documents`. Donc tout doc pas rattaché à un projet n'affichait aucun montant.

- Nouvelles colonnes `documents.amount` et `documents.amount_accepted` (source de vérité directe)
- Migration : copie depuis `project_documents` au premier démarrage v7.0.1
- Nouveau endpoint `PUT /api/documents/{id}/amount` qui met à jour la doc ET synchronise `project_documents` (pour que la page Projets reste cohérente)
- Inputs inline dans le panel détail Dossier : chaque doc a un champ "€" (montant déclaré) et — pour les devis/BPA — un champ "Validé" (montant après négo). Sauvegarde au blur.
- Le bloc "Budget · pour info" en bas du panel se recalcule automatiquement.

### 4. Dropdown statut affichait une case blanche vide

Svelte n'évalue pas `value={x}` comme attendu sur un `<select>` — il faut un `bind:value`. Correction faite : le dropdown affiche maintenant correctement le statut courant, et conserve la couleur du statut sur le bord du select.

### 5. Filtres latéraux ambigus ("Devis reçu : 0")

Les labels suggéraient "dossiers qui contiennent un X" alors qu'ils filtrent en réalité par état courant. Reformulés pour lever l'ambiguïté + tooltip de description :

- "Devis reçu" → **"Devis · sans BPA"** *(devis reçu, BPA pas encore signé)*
- "BPA signé" → **"BPA · sans commande"** *(BPA signé, commande/facture pas encore reçue)*
- "Commandé" *(facture reçue, en attente de livraison)*
- "Livré / Installé" *(matériel reçu et déployé)*
- "Archivé" *(clos, plus de suivi)*

Survole un filtre pour voir le détail dans la bulle d'aide.

### À tester après update

1. Recharge le module Documents → les dossiers existants devraient maintenant afficher le bon prestataire (si l'un des docs du dossier en avait un)
2. Clique sur un dossier → bouton ✏️ ouvre le dialog d'édition
3. Dans le panel détail, les montants apparaissent sous chaque doc + sont éditables au clic
4. Le dropdown statut affiche bien le statut courant en couleur
5. Survol des filtres : tooltip explique chaque état

## v7.0.0 — Refonte du module Documents autour des "Dossiers"

Première version d'une refonte majeure du module Documents. Le module pivote de "liste de documents avec ensembles" vers "**Dossiers**" — un dossier représente une opération d'achat IT complète (ex. "Renouvellement firewall NDK") et agrège tous ses documents (Devis, BPA, Facture) + son état d'avancement + son fil d'activité.

Voir la maquette de référence : `docs/documents-redesign-mockup.html`.

### Pourquoi cette refonte

L'ancien module raisonnait par document isolé. Un Devis tout seul a peu de sens — ce qui compte c'est l'opération dont il fait partie. La nouvelle vue rend cette opération de premier niveau : un seul endroit pour voir où en est l'achat, plus besoin de reconstituer la chaîne mentalement.

Le module est aussi recadré sur le **cycle achat IT** (et pas sur la compta) : *demande → devis → BPA → commande → livraison → archivage*. On ne suit plus le paiement (pas ton métier).

### Backend

- **Nouvelle table `dossiers`** : id, title, status, supplier_id, project_id, site, estimated_budget, next_action_date, notes, received_at, archived_at, created_at, updated_at
- **Nouvelle table `dossier_comments`** : fil d'activité (notes, changements de statut, ajout de docs)
- **Nouvelle colonne `documents.dossier_id`** : FK vers dossiers, nullable
- **Migration automatique** au premier démarrage :
  - Pour chaque chaîne dans `document_links`, un dossier est créé qui regroupe ces docs
  - Les docs sans liens deviennent des dossiers mono-document
  - Le titre, le prestataire et le statut initial sont devinés depuis la composition de la chaîne
  - Tous les documents existants sont préservés, rien n'est supprimé
- **Nouveau router** `backend/routers/dossiers.py` avec endpoints CRUD + stats + commentaires + attach/detach + change_status

### Frontend

- **Nouvelle page** `DossiersPage.svelte` avec **layout 3 colonnes** (style Inbox) :
  - Sidebar filtres : état du dossier, établissement, prestataire
  - Liste centrale : cards avec mini-timeline visuelle (Devis → BPA → Facture), montants 3 colonnes, statut coloré
  - Panel détail à droite : titre + statut éditable, liste des documents avec rattachement/détachement, budget récap, fil d'activité
- **Toggle "Documents (à plat)"** en haut : conserve l'ancienne vue comme filet de sécurité. Tu peux y revenir à tout moment et continuer d'importer des documents par l'ancien flux pendant que tu apprivoises les Dossiers.
- **Dialog "Nouveau dossier"** : crée un dossier vide directement (sans doc), idéal pour matérialiser "j'ai envoyé une demande de devis, j'attends la réponse"
- **Dialog "Rattacher un document"** : liste tous les docs et permet de les attacher à un dossier existant
- **Changement de statut** depuis le panel détail : dropdown avec les 6 états, chaque transition est enregistrée dans le fil d'activité

### États de dossier (lifecycle)

1. **Demande envoyée** (gris) — tu as demandé un devis, en attente
2. **Devis reçu** (bleu) — devis dans le dossier
3. **BPA signé** (violet) — accord direction obtenu
4. **Commandé** (vert clair) — facture reçue, commande en cours
5. **Livré / Installé** (vert foncé) — matériel reçu et déployé
6. **Archivé** (gris foncé) — clos, plus de suivi

### Reporté à v7.0.1

- **Smart filters intelligents** ("À relancer", "Livraison attendue", "À installer", "Garantie expire bientôt") — l'infrastructure backend existe (`next_action_date`, stats), reste à câbler le UI
- **Ajout de notes / commentaires depuis le UI** — le backend les enregistre déjà (sur les changements de statut + ajouts de doc), reste à exposer un champ libre dans le panel détail
- **OCR sur ajout de PDF** — à creuser via pdfjs côté client
- **Drag & drop d'un PDF directement dans un dossier**
- **Auto-création de dossier au moment de l'import d'un document** (actuellement les nouveaux docs arrivent sans dossier, à attacher à la main)

### Migration côté utilisateur

Au premier lancement de v7.0.0 :
1. La table `dossiers` est créée
2. Tes documents existants sont regroupés automatiquement en dossiers (un par chaîne workflow + un par doc orphelin)
3. Le module Documents affiche désormais les Dossiers par défaut
4. Tu peux revenir à la vue à plat via le toggle en haut si besoin

Les titres de dossiers générés automatiquement viennent du document le plus ancien (généralement le devis). Tu pourras les renommer librement après coup.

## v6.9.2 — Lanceur : upload de fichier, card favoris sur l'accueil, presets fiabilisés

Trois fixes sur le module Lanceur.

### 1. Upload de fichier pour l'icône

Le champ icône avait deux modes (Logo URL / Emoji). Ajout d'un troisième : **Fichier**.

- Nouveau bouton "📁 Fichier" dans le dialog création/édition d'un launcher (à côté de URL et Emoji)
- Drag & drop ou click sur le file picker pour choisir un PNG/JPG/SVG/WebP/GIF/ICO
- Aperçu instantané via FileReader, upload effectué après la sauvegarde du launcher
- Nouvel endpoint backend `POST /api/launcher/{id}/icon/upload` (multipart, pattern copié de suppliers/établissements)
- Le dossier `data/launcher_icons/` est inclus dans les backups + flux de restauration
- En mode édition d'un launcher qui a déjà une icône uploadée, l'icône actuelle est affichée — choisir un nouveau fichier la remplace

### 2. Card "Favoris" sur l'accueil

La feature avait été oubliée : la colonne `favorite` existait, le toggle fonctionnait dans le module Lanceur, mais aucune card n'apparaissait sur le dashboard.

- Nouveau composant `LauncherFavoritesCard.svelte`
- Position : nouvelle row "Favoris" sur la Home, entre "Par établissement" et "Projets en cours"
- Grille auto-fit de boutons cliquables (logo + nom), bord gauche coloré avec la couleur du launcher
- Clic → ouvre l'URL dans le navigateur par défaut (via `@tauri-apps/plugin-shell`, fallback `window.open` en dev)
- Si aucun favori : message d'accroche cliquable qui ouvre le module Lanceur
- Refresh automatique avec le bouton "Actualiser" + auto-refresh toutes les 5 min comme les autres cards

### 3. Presets fiabilisés

Les 18 modèles utilisaient presque tous `cdn.simpleicons.org` qui a perdu plusieurs marques (Windows retiré par Microsoft, VMware retiré après acquisition Broadcom, etc.). L'icône "Active Directory" pointait par erreur vers `microsoftazure`. GLPI utilisait une URL WordPress fragile.

- Bascule complète vers **Google's favicon service** : `https://www.google.com/s2/favicons?domain={domain}&sz=128`
- Marche pour TOUT site avec un favicon — pas de risque qu'une marque soit retirée du catalogue
- Tous les 18 presets mis à jour avec le bon domaine
- L'utilisateur peut toujours uploader son propre logo via le nouveau mode Fichier si la favicon ne plaît pas

### Fichiers supprimés

- `src/lib/components/cards/LauncherFavCard.svelte` (orphelin, jamais utilisé)

## v6.9.1 — Status complet sur les tâches (todo / en cours / terminé) + Gantt aligné

Le `done` booléen ne suffisait plus pour piloter le Gantt : il manquait l'état intermédiaire "en cours". Cette version introduit un vrai champ `status` à 3 états et propage la couleur partout.

### Modèle de données

- Nouvelle colonne `tasks.status` (`'todo'` / `'in_progress'` / `'done'`)
- Migration : `ALTER TABLE ADD COLUMN`, backfill `done=1 → 'done'`, sinon `'todo'`
- Le booléen `done` est **conservé** et reste synchronisé avec `status='done'` (compat avec kanban legacy, KPIs dashboard, etc.)
- Endpoints :
  - `POST /api/tasks` accepte `status` (défaut `'todo'`)
  - `PUT /api/tasks/{id}` accepte `status`
  - **Nouveau** `PATCH /api/tasks/{id}/status` pour les changements rapides depuis le dropdown
  - `PATCH /api/tasks/{id}/done` (toggle existant) synchronise désormais aussi `status` : check → `'done'`, uncheck → `'in_progress'` (reprise du travail, pas redémarrage à zéro)

### UX dans le module Tâches

- Le dropdown de la colonne Statut passe de 2 options à **3 options** : À faire / En cours / Terminée
- Nouveau champ "Statut" dans le dialog de création/édition d'une tâche
- Couleurs alignées avec le Gantt : gris (todo), bleu (in_progress), vert (done), rouge (overdue computed)
- **Vue Kanban** : 3 colonnes par statut (au lieu de 3 par priorité). **Drag & drop** d'une card entre colonnes change le statut côté backend.

### Gantt projet

- Les barres lisent désormais `task.status` au lieu de deviner depuis `done` + dates
- L'orange "bientôt dû" (`soon`) est **supprimé**
- Couleurs finales : todo (gris) / in_progress (bleu) / done (vert) / late (rouge, override visuel sur status != 'done' avec end_date passée)
- Légende Gantt nettoyée : 4 entrées au lieu de 5
- Le dialog tâche-dans-projet a aussi son dropdown Statut

### Bonus visuel

- Le logo établissement sur les project-cards de la page Projets passe de `size=sm` à `size=md` (un peu plus présent comme demandé)

### À tester après update

1. Ouvre une tâche existante → tu vois "À faire" dans le dropdown si elle n'était pas done, sinon "Terminée"
2. Passe-la en "En cours" → vérifie que la couleur du chip change (bleu)
3. Sur le Gantt projet : tâches non-done deviennent grises (todo) ou bleues (in_progress) au lieu d'être systématiquement bleues
4. Vue Kanban tâches : 3 colonnes, drag d'une card entre elles

## v6.9.0 — Logos établissements (NDK / SU / NDE) dans 4 modules

Première version du système d'établissements : chaque module clé carry maintenant un logo + couleur identifiant l'école concernée (Lycée Notre Dame du Kreisker, Collège Sainte Ursule, Collège Notre Dame d'Espérance).

### Fondations

- Table `establishments` (id, code, name, color, logo_path, aliases, sort_order) avec seed NDK / SU / NDE au premier lancement
- Router `backend/routers/establishments.py` : `GET /api/establishments`, `PUT /api/establishments/{id}`, `POST/GET/DELETE /api/establishments/{id}/logo` — pattern copié sur celui des suppliers
- Logos stockés dans `data/establishments/` (séparé des logos prestataires), inclus dans les backups + flux de restauration
- Migrations : ajout d'une colonne `site` (TEXT, défaut '') sur `projects` et `planning_events`
- Store Svelte `establishments.js` (chargé au démarrage de l'app) + composant `<EstablishmentBadge code size showLabel />` réutilisable (logo si uploadé, sinon fallback colored chip avec le code)

### Settings → Établissements (nouvel onglet)

Nouvelle section avec 3 cards (une par établissement) :
- Édition du nom complet
- Color picker pour la teinte d'accent
- Upload de logo (PNG/JPG/SVG/WebP/GIF, accepte multipart)
- Champ aliases (textarea, un par ligne — réservé pour la Phase 2 Parc, pas encore utilisé)
- Bouton retirer le logo

### Modules câblés

- **Tâches** — colonne Site rend un `<EstablishmentBadge>` (logo + code). En vue kanban, badge inline dans la card. Tag dupliqué dans la colonne Tags retiré (redondant). Le tag projet `Projet: X` reste indépendant (couleur rose magenta).
- **Planning** — dropdown "Établissement" ajouté au dialog create/edit event. Sur le calendrier, un mini-logo est préfixé à chaque event via le hook `eventDidMount` de FullCalendar (img de 14×14 ou fallback colored).
- **Projets** — dropdown "Établissement" dans le dialog projet, badge dans la fiche projet (à côté du status), petit badge sur chaque project-card de la liste, gros badge sur la tuile "Projets en cours" de l'accueil (top-left du bandeau coloré).
- **Accueil** — nouvelle row "Par établissement" sous les KPI cards : 3 cards (NDK / SU / NDE) chacune avec logo + nom + 4 stats (tâches, en retard, projets in_progress, events 7j). Clic sur une card → navigue vers `/tasks` filtré sur ce site (via sessionStorage).
- **Export PDF projet** — logo de l'établissement embedded en haut à droite du header PDF, ligne "Etablissement : NDK — Lycée Notre Dame du Kreisker" ajoutée sous la date.

### Notes d'utilisation après installation

1. Aller dans **Paramètres → Établissements** et uploader les 3 logos (PNG ou SVG, fond transparent recommandé).
2. Éditer les projets existants pour leur assigner un site (dropdown dans le dialog d'édition) — sinon ils restent "sans logo".
3. Pareil pour les events Planning existants (édition au cas par cas).
4. Les tâches existantes ont déjà leur `site` rempli (NDK/SU/NDE/Global) — les logos remontent automatiquement.

### Reporté à plus tard

- Module Parc (GLPI) : impose un travail d'aliasing entre `glpi_location` et nos codes établissement, reporté à v6.9.x si pertinent
- Module Documents : pas convaincus que la friction d'ajouter un champ site à chaque upload soit justifiée — on reverra si le besoin émerge

## v6.8.9 — Email : affichage des destinataires + fix "Répondre à tous"

Deux bugs liés sur le module Email.

**Bug 1 — CC invisible** : la vue d'un mail reçu n'affichait pas les destinataires (`To`) ni les copies (`Cc`). Impossible de savoir qui d'autre était dans le mail.

**Bug 2 — Reply All ne prend que l'expéditeur** : la logique de `openCompose(mode='replyAll')` lit bien `replyMsg.cc` pour pré-remplir le champ Cc du compose, mais ce champ était vide pour les mails déjà cachés en local.

Origine : la colonne `cc` existait dans le `CREATE TABLE` d'`emails_cache` mais **aucune migration** ne l'ajoutait sur les DBs déjà créées avant son apparition. Résultat : aucun `cc` parsé n'a jamais été stocké côté SQLite, donc tout part dans le vide.

Fixes :
- **Migration `emails_cache.cc`** dans `_run_migrations()` : `ALTER TABLE ADD COLUMN cc TEXT DEFAULT ''`. Idempotente. Après ajout, on remet `fetched_full = 0` sur tous les rows existants pour qu'ils soient re-tirés depuis Gmail au prochain `openMessage()` — comme ça les anciens mails finissent par avoir leur CC eux aussi.
- **Endpoint liste** (`list_messages_local` dans `backend/services/gmail.py`) : ajout de `cc` au `SELECT` (le détail le renvoyait déjà).
- **Vue mail** (`EmailPage.svelte`) : nouveau bloc `read-recipients` sous l'expéditeur, affiche `À : ...` et `Cc : ...` quand présents.

Après update, ouvre un mail déjà connu une fois pour déclencher le re-fetch — ensuite "Répondre à tous" pré-remplira le Cc correctement.

## v6.8.8 — Compléments v6.8.7 : 2 zones budget oubliées + tag projet recoloré

Trois ajustements suite au feedback de la v6.8.7.

- **Bandeau budget compact en haut de la fiche projet** : il n'affichait que Engagé / Facturé. Ajout de la card **Validé** entre les deux + ajout de `budgetValide` à la condition d'affichage du bloc (sinon on ne voyait rien quand toute la valeur était dans Validé). Labels précisés : "Engagé (devis seul)" / "Validé (BPA signé)".
- **Résumé du panneau "Documents et budget"** : la condition `{#if budgetEngage > 0 || budgetFacture > 0}` masquait le résumé quand tout était en Validé. Élargi à inclure `budgetValide`. Ajout d'une 3e colonne "Validé" entre Engagé et Facturé.
- **Couleur du tag projet** : le `#ccfbf1 / #0f766e` (teal) entrait en collision visuelle avec `.status-select--done` (`#bbe6e3 / #3A9B94`) qui marque les tâches terminées. Repassé en rose/magenta `#fce7f3 / #be185d` — clairement distinct du teal "Terminée", du violet `dt-tag--primary`, du jaune `dt-tag--secondary` et de toutes les couleurs de priorité.

## v6.8.7 — Tag projet coloré dans Tâches + budget par chaîne workflow

### Tag projet d'une couleur distincte dans le module Tâches

Quand on crée une tâche depuis un projet, son `category` est préfixée `Projet: {nom}` côté backend. Sur la page Tâches, ce tag était rendu avec la même classe `dt-tag--primary` (violet pâle) que les catégories utilisateur — pas moyen de distinguer en un coup d'œil.

- Nouvelle classe CSS `dt-tag--project` (vue tableau) et `kc-cat--project` (vue kanban) avec un teal `#ccfbf1` / `#0f766e`. Distinct du violet (catégorie classique) et du jaune (site).
- Application conditionnelle via `task.category.startsWith('Projet: ')` — pas de nouveau champ ni migration backend.

### Budget projet : passage à un calcul par chaîne workflow

L'ancien calcul sommait les montants de **tous** les devis/BPA acceptés du projet, sans tenir compte du fait qu'un Devis et son BPA appartiennent à la même chaîne workflow. Résultat : `Devis 1000 € + BPA 1000 € liés = 2000 € en Engagé` (faux).

Nouveau modèle, **par chaîne** (un Devis lié à son BPA et sa Facture = une seule chaîne) :

| Bucket | Quand ? | Montant compté |
|---|---|---|
| **Engagé** | Chaîne sans BPA ni Facture | Somme des Devis |
| **Validé** | Chaîne avec BPA/Bon mais pas de Facture | Somme des BPA |
| **Facturé** | Chaîne avec au moins une Facture | Somme des Factures (gère les acomptes) |

Chaque chaîne contribue à **un seul** bucket. `Consommé = Engagé + Validé + Facturé` (plus de `max()` qui masquait le double-comptage).

Conséquences sur le cas typique :
- Devis 1000 € seul → Engagé : 1000 €
- + BPA lié 1000 € → Engagé : 0 €, **Validé : 1000 €** (le devis est absorbé)
- + Facture liée 1000 € → Validé : 0 €, **Facturé : 1000 €**

Implémentation :
- `backend/routers/projects.py::_project_dict()` : union-find sur `document_links` pour grouper les docs en chaînes, puis bucketing par état dominant. Renvoie aussi un mapping `_doc_buckets` (interne) que `get_project()` utilise pour annoter chaque doc.
- `backend/routers/projects.py::list_projects()` strippe `_doc_buckets` (pas exposé dans la liste).
- Frontend : `ProjectsPage.svelte` lit directement `selectedProject.budget_engaged / _validated / _invoiced / _consumed` (plus de calcul JS local). La colonne "Compte en" du tableau budget utilise `doc.bucket` renvoyé par l'API.
- Nouvelle 4ème card "Validé" dans le panneau budget projet (entre Engagé et Facturé).
- Les liens marqués `status='refuse'` sont ignorés du calcul.

## v6.8.6 — Card "Projets en cours" + panneau alertes par sévérité

### Card "Projets en cours" sur l'accueil

Nouveau composant `RunningProjectsCard` (style YashAdmin "Running Projects") affiché dans une nouvelle row pleine largeur sur la home, juste sous les 4 KPI cards.

- **Scroll horizontal** : une tuile de 280 px par projet `in_progress`, snap-aligned au défilement.
- **Bandeau coloré** en haut de la tuile avec les initiales du projet et un pill d'échéance :
  - vert/transparent : OK (>7 jours)
  - jaune : J-7 ou aujourd'hui
  - rouge : en retard (J-X)
- **Adaptation solo IT** : pas d'avatars d'équipe, à la place 3 stats concrètes — `done/total tâches`, `nombre de docs liés`, `nombre de prestataires liés`.
- **Clic sur une tuile** : pose `projects.focusId` dans sessionStorage et navigue vers `/projects` (ProjectsPage pourra utiliser ce flag plus tard pour scroll-and-flash le projet, comme on fait déjà pour les Documents).

### Panneau alertes (cloche dans la navbar)

Refonte du dropdown du bouton 🔔 pour le transformer en hub d'alertes actionnables, groupées par sévérité.

- **🔴 Critique** : backend déconnecté (`isOnline = false`), alertes monitoring actives (Zabbix `active_problems`).
- **🟡 Important** : tâches en retard (existant), backup automatique manquant (>=7 jours sans `auto_backup_*.zip` récent — vérifié via `/api/settings/backups`).
- **🔵 Info** : événements de la journée (depuis Google Calendar).
- Chaque ligne est cliquable et navigue vers la source correspondante (Settings, Monitoring, Tasks, Planning…).
- Bord gauche coloré sur chaque alerte pour rappeler la sévérité d'un coup d'œil. Compteur global rouge au-dessus de la cloche.
- Compteur "Tout va bien" en vert quand tout est calme.

Note : l'alerte "Devis en attente +30j" est reportée à plus tard — elle nécessite un endpoint dédié pour scanner les workflow chains côté backend, ce qui dépasse le scope de cette version.

## v6.8.5 — Sidebar : retour à la liste à plat (revert v6.8.0 → v6.8.4)

Les itérations v6.8.0 → v6.8.4 sur la sidebar (catégories pliables, refonte YashAdmin, labels de section) ne convenaient pas. Retour à l'ancienne sidebar à plat avec deux sections "VOTRE ENTREPRISE" et "NOS OUTILS" et le groupe Outils / Utilisateurs / Paramètres en bas. C'est la sidebar qui était en place jusqu'à v6.7.9.

Conservé de la période v6.8.x :
- **Système NEW intelligent** (v6.8.1) : badge `NEW` à droite des modules avec contenu non acquitté, disparaît au premier clic après ouverture de la modal "Quoi de neuf".

Supprimé :
- `navCategories` du store, plus de logique de pliage de catégories.
- Labels `PRINCIPAL` / `MODULES`, plus de chevrons sur les en-têtes.
- Composants `cat-header` / `sub-item` / snippets `topItem` / `subItem`.

## v6.8.4 — Sidebar : sections + air entre les items

Finition de la sidebar v6.8.3 pour matcher la respiration de YashAdmin.

- **Labels de section** ajoutés : `PRINCIPAL` au-dessus de Accueil, `MODULES` au-dessus des catégories. Petit, uppercase, gris muté — purement décoratifs comme les "YOUR COMPANY" / "OUR FEATURES" de YashAdmin. Servent à structurer visuellement la liste.
- **Padding vertical augmenté** des items (10px → 12px) et des sous-items (6.4px → 8px). Plus de respiration entre les lignes, moins de sensation "tassé".
- **Mode collapsed** : les labels de section sont masqués (display: none), seuls les items en icônes restent.

## v6.8.3 — Sidebar : pattern YashAdmin appliqué correctement

Correction de v6.8.0 et v6.8.2 qui partaient dans le mauvais sens.

Le bon pattern YashAdmin (visible sur la card "Apps" de leur sidebar) :
- L'en-tête de catégorie est **une ligne avec icône + label + chevron** (cliquable, le chevron tourne).
- Les items à l'intérieur d'une catégorie ouverte sont rendus avec **un préfixe tiret `-`, sans icône, indentés, en plus petit**. Style "- Chat", "- Users Manager", "- Email".

C'est ce qui donne la hiérarchie claire et propre de YashAdmin. Avant, j'avais mis des mini-icônes sous des en-têtes-icônes (v6.8.0) ou viré le pliage et fait des labels statiques (v6.8.2) — les deux ratés.

Implémentation : deux snippets `topItem` (icône+label, pour Accueil) et `subItem` (dash+label, pour les items sous catégorie). Les en-têtes de catégorie restent cliquables avec chevron qui tourne, état persisté dans `localStorage`.

## v6.8.2 — Sidebar : refonte visuelle YashAdmin

Polish de la sidebar v6.8.0 : les catégories étaient implémentées comme des accordéons (icône + chevron + état pliable), trop chargé visuellement comparé à la référence YashAdmin.

- **Sections = labels décoratifs** (style YashAdmin pur) : uppercase, 11px, letter-spacing, gris muté. Pas d'icône, pas de chevron, pas cliquable. Servent uniquement de séparateur visuel pour grouper les modules.
- **Items à plat** : tous les modules s'affichent au même niveau hiérarchique sous leur label de section. Plus d'indentation différentielle, plus de tailles d'icône variables.
- **Pliage retiré** : YashAdmin ne plie pas ses sections, on fait pareil. Suppression de l'état `sidebar.cat.*` en localStorage et de la logique d'auto-ouverture de la catégorie active.
- **Mode collapsed inchangé** : icônes seulement, sans labels de section.

Le résultat : moins de bruit visuel à l'ouverture, hiérarchie immédiatement lisible. Refactor `Sidebar.svelte` pour utiliser un snippet `navItem` partagé entre items top-level et items sous une section.

## v6.8.1 — Badge NEW intelligent + modal "Quoi de neuf"

Le badge `NEW` ne reste plus indéfiniment. Comportement :
- Le badge s'affiche dans la sidebar tant que l'utilisateur **n'a pas visité** le module concerné.
- Au premier clic sur un module marqué NEW, une **modal "Quoi de neuf"** s'ouvre avec les nouveautés clés du module.
- À la fermeture de la modal, le badge disparaît dans la sidebar (état persisté dans `localStorage`).
- Si une nouvelle vague de changements arrive plus tard, on bump le `since` du module et la modal s'ouvre à nouveau au prochain passage.

Modules marqués NEW pour l'instant :
- **Documents** (depuis 6.7.0) — workflows, ref interne, acompte, 3 modes d'affichage
- **Projets** (depuis 6.5.0) — drag-Gantt, PDF, dépendances, jalons, duplication, budget 3 niveaux
- **Paramètres** (depuis 6.5.1) — restauration backup, diagnostic, chemins de données, bandeau backend offline

Implémentation : nouveau store `seenNewKeys`, helper `markNewSeen(key)`, composant `WhatsNewModal.svelte` déclenché depuis `App.svelte` quand le `currentPage` change vers un module avec contenu non acquitté.

## v6.8.0 — Sidebar : catégories dépliables + badges

Refonte de la navigation latérale pour gérer 13+ modules sans surcharger la liste.

- **Catégories dépliables** : Travail (Projets, Tâches, Planning) · Documentation (Documents, Prestataires, Wiki) · Infrastructure (Parc, Sécurité, Monitoring) · Communication (Email, News) · Outils (Launcher, Tools, Changelog) · Système (Utilisateurs, Paramètres). Click sur l'en-tête de catégorie pour déplier/replier.
- **État persisté** dans `localStorage` (clé `sidebar.cat.{key}`) : tes catégories ouvertes restent ouvertes au prochain démarrage. Par défaut "Travail" et "Documentation" sont ouvertes (les plus utilisées), le reste replié.
- **Auto-ouverture de la catégorie active** : si tu navigues sur un item via raccourci ou URL, sa catégorie s'ouvre automatiquement pour rester repérable.
- **Badges numériques** : tâches en retard (rouge), emails non lus (bleu) — déjà existants, conservés.
- **Badge `NEW`** : ajout d'un set `newItems` dans `navigation.js` ; il suffit d'y ajouter une clé pour qu'un module porte le badge rouge "NEW" pendant la période de mise en avant. Vide par défaut.
- **Mode collapsed (icon-only)** : les en-têtes de catégorie sont masqués, tous les items s'affichent à plat en icônes — la catégorisation n'a pas de sens à largeur réduite.

## v6.7.9 — Import : lien direct + flag acompte sur Facture

- **Lier au moment de l'import** : le champ Tags du dialog d'import est remplacé par un picker "Lier à un document existant". Filtré par fournisseur si tu en as renseigné un (ne montre que les docs du même presta), sinon liste complète des 50 plus récents. À l'envoi, le lien est créé en même temps que le document. Tu peux toujours ajouter des tags plus tard via le dialog d'édition.
- **Acompte sur Facture** : nouvelle colonne `is_acompte` sur les documents (migration auto). Une case à cocher "Cette facture est un acompte" apparaît dans le dialog d'import seulement quand le type = Facture. Sur les lignes du module Documents, un badge rouge `ACOMPTE` se place à côté du type pour distinguer visuellement les acomptes des factures finales.

## v6.7.8 — Hiérarchie workflow + facturation partielle au pourcentage

- **Ordre logique dans les ensembles** : avant, l'ordre dépendait de la date des docs → un BPA daté avant le devis se retrouvait au-dessus visuellement. Maintenant tri par hiérarchie de type : **Devis → BPA → Contrat → Facture → Rapport → Autre**, avec la date en départage. Plus jamais "BPA avant Devis".
- **Calcul de facturation partielle (%)** dans le dialog d'édition de doc lié (module Projet) : si tu as un devis de 10 000 € et qu'on a payé 30 %, tu choisis le devis dans un picker, tu tapes 30 %, click "Appliquer" → le montant 3 000 € est calculé et rempli dans Montant initial + Montant validé. Tu peux ensuite ajuster manuellement. La case n'apparaît que si le projet a au moins un devis avec un montant.

## v6.7.7 — Fix gestion des liens + dialogs empilés + Facture moins flashy

- **"Erreur lors du chargement des liens"** : `GET /api/documents/{id}` plantait à cause d'une collision de kwargs (`tags` passé deux fois à `DocumentDetailResponse`). Le `_row_to_document` ajoutait un champ `tags` (CSV) destiné à la liste, et l'endpoint détail le repassait aussi explicitement comme `list[TagResponse]`. → 500 → le dialog "Liens du document" affichait l'erreur. Corrigé en pop-ant `tags` du dict avant la construction de la réponse.
- **Dialog "Lier à un autre document" passait DERRIÈRE le manager** : ajout d'une classe `.modal-overlay--top` avec `z-index: 1100` (vs 1000 pour les modaux standards). Les deux peuvent maintenant coexister visuellement, le picker se ferme et le manager reste avec le nouveau lien dans la liste.
- **Couleur Facture moins flashy** : `#22C55E` (vert vif Tailwind 500) → `#0D9488` (teal-emerald 600). Plus posé visuellement, lisible sur fond clair comme sombre.

## v6.7.6 — Workflow refs complètes + scroll prestataire + cross-page navigation

- **Refs de TOUS les docs sur les lignes ensemble** : avant on n'affichait que la ref du premier doc (`DEV-2026-001`). Maintenant les 3 refs s'affichent côte à côte (`DEV-2026-001` `BPA-2026-001` `FAC-2026-001`) suivies du nom du premier doc + "et N autres".
- **Panneau prestataire scrollable** : un classique CSS — `min-height: 0` manquant sur le `.detail-body` flex child empêchait l'overflow-y de s'engager. Sans ça, le contenu poussait le panel au-delà de 100vh au lieu de scroller en interne. Maintenant ça scrolle.
- **Clic sur un document depuis la fiche prestataire** → bascule sur le module Documents, ferme tous les filtres, ouvre l'éventuel workflow contenant le doc, scrolle dessus et le flash en violet 1.5s pour qu'on le repère.

## v6.7.5 — Documents : toolbar fix, lignes ensemble enrichies, polish

- **Toolbar refondue** : la classe globale `.ya-toolbar` avait un `max-width: 320px` sur la barre de recherche et un layout flex-wrap qui faisait passer la loupe et le champ sur deux lignes. Custom toolbar `.docs-toolbar` (Importer | Search qui grandit | filtres qui s'étalent à droite). Tout sur une seule ligne propre.
- **Lignes ensemble plus parlantes** : la zone titre ne montrait que les références (`DEV-2026-001 ⇒ BPA-2026-001 ⇒ FAC-2026-001`). Maintenant : tag-style `[DEV-2026-001]` + **nom du premier document** + indication "et N autres". Tu sais immédiatement de quoi parle l'ensemble sans déplier.
- **Référence externe retirée** des lignes : la `internal_ref` (auto, fiable) est désormais le seul identifiant affiché. L'externe reste éditable et indexée pour la recherche, juste pas affichée pour réduire le bruit.
- **Boutons d'action toujours visibles** : avant `opacity: 0` puis 1 au hover, ce qui faisait des trous visuels. Maintenant `opacity: 0.6` par défaut et `1` au hover/expand — toujours là, pas envahissants.
- **Polish divers** : chevron centré, tags-inline en chips, `.workflow-row__more` italique discret pour "et N autres".

## v6.7.4 — Documents : référence interne + 3 modes de vue + ligne homogène

- **Référence interne auto-générée** : chaque document reçoit un identifiant unique au format `{TYPE}-{ANNÉE}-{SEQ}` (ex. `DEV-2026-001`, `FAC-2026-042`). Séquence par type et par année. Migration backfill automatique sur la base existante. La référence externe (celle imprimée sur le PDF du fournisseur) reste un champ optionnel séparé. Recherche les deux.
- **3 modes d'affichage** : sélecteur dans la barre d'outils — `Liste` (workflows pliés en 1 ligne, défaut), `Par date` (chaque doc est une ligne, tri strict décroissant), `Par prestataire` (cartes par fournisseur). Choix mémorisé entre sessions.
- **Ligne workflow homogène** : la ligne d'un ensemble lié partage maintenant la même grille qu'une ligne single — bord coloré (violet), badge type "Ensemble N", supplier-cell (logo + nom), résumé de la chaîne dans la zone titre, date à droite, chevron pour déplier. Plus de différence visuelle entre une ligne seule et un workflow plié.
- **Toolbar repensée** : la barre de recherche prend tout l'espace disponible (`flex: 1`), les filtres restent à taille fixe à droite. Tout sur une seule ligne maintenant.

## v6.7.3 — Documents : tags fonctionnels + auto-réf élargie + UI cleanup

- **Tags persistés à l'import** : le bug était côté backend, le champ `tags` était reçu mais jamais inséré dans `document_tags`. Maintenant chaque tag est créé (s'il n'existe pas) puis lié au document. La liste `GET /api/documents` renvoie aussi les tags en CSV pour qu'ils soient utilisables côté UI (filtre + affichage).
- **Auto-détection de référence assouplie** : avant, seul `[A-Z]{2,5}-\d{4}-\d{3,5}` matchait. Maintenant on score chaque token sur le nombre de chiffres, on ignore les années (`20xx`) et les pures lettres, et on extrait le plus probable (ex: `F16347`, `S02313`, `16122`). Le pattern strict reste prioritaire si présent.
- **Cohérence visuelle des lignes** : chaque ligne en mode liste plate affiche maintenant un badge prestataire compact (logo + nom) à côté du type. Plus de différence entre les lignes selon qu'elles sont seules ou liées.
- **Toolbar nettoyée** : suppression du bouton "Nouveau" (création sans fichier) et "Importer un dossier" (peu utilisé) → ne reste qu'un bouton "Importer". Les filtres et la recherche tiennent maintenant sur une seule ligne.

## v6.7.2 — Documents : liste plate par défaut + toggle vue prestataire

À 4-5 docs la vue par cartes prestataires de v6.7.1 était jolie ; à 100+ docs ça devenait un mur. Nouvelle approche pensée pour scaler :

- **Vue par défaut "Liste plate"** (façon Gmail) : tout est mélangé et trié par date. Chaque ligne représente soit un workflow plié (ex. `🔗 Ageona — Devis 16122 ⇨ BPA ⇨ Facture F16347`) soit un doc seul. Densité constante quel que soit le nombre de docs.
- **Workflows pliés par défaut** : un click sur la ligne workflow déplie ses docs en place, comme un thread Gmail. Le compteur "3 docs" et la date du dernier doc sont toujours visibles.
- **Toggle 🗋 Liste / 📂 Par presta** dans la barre d'outils : passe à la vue cartes prestataires de v6.7.1 quand tu veux explicitement parcourir par fournisseur. Le choix est mémorisé dans `localStorage`.

## v6.7.1 — Documents : présentation unifiée + gestion liens dédiée

- **Cohérence visuelle** : tous les documents sont maintenant dans des cartes de prestataire (une carte = un fournisseur). Plus de différence visuelle entre docs liés et docs seuls. À l'intérieur d'une carte : section "Workflow" pour les chaînes (Devis → BPA → Facture), section "Documents seuls" pour le reste, séparées si les deux coexistent.
- **Gestion des liens repensée** : la chain-bar dans l'expanded view est supprimée (redondante avec le visuel de la carte). Nouveau bouton **🔗** dans les actions de chaque doc → dialog "Liens du document" avec liste des liens existants (× pour retirer) et bouton "+ Lier à un autre document".
- **Click-outside ferme l'expand** : cliquer en dehors d'un document referme la zone détaillée. Re-cliquer le même doc le referme aussi.

## v6.7.0 — Documents : workflow cards (regroupement par chaîne)

- Les documents liés entre eux (Devis ↔ BPA ↔ Facture pour un même achat) sont maintenant **regroupés visuellement** dans une carte unique avec logo prestataire, nom et compteur. Lecture chronologique top-to-bottom, flèche entre chaque document.
- Les documents sans liens restent en ligne simple (rendu inchangé).
- Nouvel endpoint `GET /api/documents/links-graph` côté backend qui renvoie toutes les arêtes du graphe en un seul appel — utilisé pour calculer les composants connectés sur le frontend.
- Quand un doc lié dans une carte référence un doc *hors* de la carte (cas rare), un **chip inline** s'affiche dans la zone détaillée pour naviguer.

## v6.6.2 — Fix username refresh + weather city encoding

- **Nom d'utilisateur** : Settings sauvait bien en backend mais le store global `settings` n'était pas mis à jour → l'accueil affichait l'ancienne valeur jusqu'au prochain redémarrage. Maintenant le store se met à jour dans la foulée du PUT.
- **Météo ville** : URL-encode du nom de ville (les villes avec espace/accent comme "La Rochelle" ou "Mâcon" cassaient l'URL de l'API geocoding). Et plus de fallback silencieux sur Paris quand la ville n'est pas trouvée — la card météo affiche maintenant clairement "Ville 'X' introuvable".

## v6.6.1 — Install per-machine

- L'installeur passe en `perMachine` : l'app est toujours installée dans `C:\Program Files\ITManager-Dashboard\`. Une seule install pour tous les utilisateurs du PC, demande UAC à l'install et à chaque mise à jour. Les données restent dans `%APPDATA%\ITManager-Dashboard\` (Roaming) — séparation propre programme/données.

## v6.6.0 — Production-readiness

- **Bandeau backend déconnecté** : si le sidecar Python crash, un bandeau rouge "Backend déconnecté" apparaît avec un bouton "Réessayer". Détection après 2 échecs consécutifs sur `/api/health` (ping toutes les 30s).
- **Export diagnostic en 1 clic** dans Paramètres → Données : génère un ZIP avec versions, OS, chemins, compteurs de tables, liste des sauvegardes récentes. Aucune donnée sensible. Utile pour diagnostiquer un problème sans avoir à fouiller.
- **CHANGELOG.md** ajouté à la racine du repo (ce fichier).

## v6.5.2 — Critical: restore wipe + auto-restart flow

- **Bug critique corrigé** : la restauration v6.5.1 supprimait la base de données live au lieu de la remplacer (rename src=dst après unlink). Le filet `pre_restore_*.zip` permettait la récupération manuelle, mais c'était inacceptable.
- **Nouveau flow staging + swap au redémarrage** : le restore stage les fichiers en `*.pending-restore`, écrit un marqueur, puis `init_db()` applique le swap au prochain démarrage AVANT d'ouvrir SQLite. La DB live n'est jamais touchée pendant le runtime.
- **Modal de restauration in-app** : étapes (préparation → prêt → countdown 3s → redémarrage), avec annulation possible.
- **Auto-restart Tauri** : nouvelle commande `restart_app` qui kill le backend proprement puis relaunch.
- **Fix `t.autoTable is not a function`** : jspdf-autotable v5 a changé d'API (`autoTable(doc, opts)` au lieu de `doc.autoTable(opts)`). Corrigé sur ProjectsPage et ParcPage.
- Bouton "📁 Ouvrir le dossier parent" sur la ligne Base de données dans Paramètres.

## v6.5.1 — Backup restore/download/import + data paths

- **Restauration de sauvegarde** depuis l'app (auparavant lecture seule).
- **Téléchargement** d'une sauvegarde via dialog Tauri.
- **Import** d'un ZIP externe.
- **Section "Emplacement des données"** dans Paramètres : DB / backups / documents / logos avec boutons Ouvrir / Copier.

## v6.5.0 — Drag-to-edit Gantt, PDF export, deps cliquables

- **Drag-to-edit sur le Gantt** : presser une barre pour la décaler, saisir le bord droit pour redimensionner. Aperçu live (`+2j`, `-5j`), sauvegarde au relâchement.
- **Export PDF du projet** : header + budget + Gantt en image (html2canvas) + tâches + prestataires + documents + journal. Dialog Tauri save.
- **Chips dépendances cliquables** : scroll + flash sur la tâche cible.
- **Audit prod** : 5 `catch {}` silencieux ajoutés un toast, `link_document` / `update_document_link` propagent les erreurs au lieu de retourner `{ok:true}` muet, migrations log au lieu de swallow.

## v6.4.3 — Suppression de tâche, logos prestataires, ordre stable

- Suppression d'une tâche depuis un projet supprime aussi du module Tâches (avant : juste un unlink).
- Logos prestataires affichés dans la vue projet (avec fallback initiales).
- Tri des tâches stable : ne saute plus en bas quand cochée.
- Fix rendu littéral de `\u2715` dans le dialog dépendances.

## v6.4.2 — Alignement Gantt, jalons, édition tâche, budget sans prévu

- **Bug d'alignement Gantt** : la ligne "Aujourd'hui" et les barres utilisaient des référentiels différents (180px de décalage). Corrigé via `calc(180px + (100% - 180px) * X / 100)`.
- **Jalons** : nouvelle case "Cette tâche est un jalon ♦" + losange sur le Gantt.
- **Édition de tâche** : bouton ✏️ sur chaque tâche, dialog pré-rempli.
- **Graduations quotidiennes** sous les mois.
- **Budget sans prévu** : suivi des dépenses possible même sans budget planifié.

## v6.4.1 — Sémantique du %, dates dans la liste, flèches dépendances

- Le % du Gantt n'a plus de fallback "temps écoulé" trompeur (tâches à 100% non terminées). Affiché uniquement avec checklist ou tâche cochée.
- Dates affichées dans la liste des tâches.
- **Flèches SVG entre tâches dépendantes** sur le Gantt (style GanttProject), gris pointillé / vert plein selon l'état.
- Tâches sans date exclues du Gantt (au lieu d'être placées via `created_at`).

## v6.4.0 — Zoom Gantt, duplication projet, dépendances tâches

- **Zoom Gantt** (Auto / Jour / Semaine / Mois).
- **Duplication de projet** (tâches reset, document links remis "en attente", notes non copiées).
- **Dépendances entre tâches** : nouvelle table `task_dependencies`, dialog gestion, badge "🔒 Bloquée", confirmation au toggle done.
- **Multi-contacts prestataires** : colonne `contacts_json`, section "Autres contacts" dans le dialog.
- **Tâches projet en retard** sur le dashboard.

## v6.3.0 — Liaison fournisseurs, Gantt coloré, jauge budget

- **Bug fournisseurs corrigé** : le nom était stocké comme texte libre et jamais résolu en `supplier_id`. Maintenant lookup automatique. Effet domino : doc affiche le presta, page presta liste les docs.
- **Couleurs Gantt par statut** : terminé / en retard / bientôt dû / en cours / à faire.
- **% complétion dans chaque barre** (basé sur la checklist).
- **Jauge budget** sur chaque card projet (consommé/prévu, feux tricolores).

## v6.2.x — Tâches start_date + budget 3-niveaux

- v6.2.1 : fix bug fuseau horaire sur le Gantt, dropdown sites en task form, dropdown fournisseurs dans Documents.
- v6.2.0 : champ `start_date` sur les tâches, refonte budget en **Prévu / Engagé / Facturé**.

## v6.1.x — Projects V2

- v6.1.0 : budget projet, card dashboard, Gantt pro, liens cross-modules.
- v6.1.1-3 : fixes suppliers / doc linking / migration / Gantt.

## v6.0.x — Projects module (initial)

- v6.0.0 : module Projets (tâches, documents, fournisseurs, Gantt, notes).
- v6.0.1-6 : fixes initiaux du module.

---

Pour les versions v5.x et antérieures, voir les tags Git directement.
