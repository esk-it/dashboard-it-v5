# Changelog

Toutes les versions notables. Pour le détail complet, voir les messages de commit ou la liste des releases sur GitHub.

---

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
