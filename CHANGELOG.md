# Changelog

Toutes les versions notables. Pour le détail complet, voir les messages de commit ou la liste des releases sur GitHub.

---

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
