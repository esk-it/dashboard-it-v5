# Changelog

Toutes les versions notables. Pour le détail complet, voir les messages de commit ou la liste des releases sur GitHub.

---

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
