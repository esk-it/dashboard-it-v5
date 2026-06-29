import { writable } from 'svelte/store';

export const currentPage = writable('/');
export const sidebarOpen = writable(true);

// Flat list of nav items with section markers (`type: 'section'`) and a
// `bottom: true` flag for items that render in the bottom group of the
// sidebar (Outils / Utilisateurs / Paramètres).
//
// v7.6.0 — `hidden: true` retire l'item de la sidebar. Utilisé pour les
// modules désactivés (Email, Planning, Changelog, Outils) qui font doublon
// avec les outils Google ou ne sont pas utilisés. Le code des pages reste
// sur disque pour un revert facile si besoin.
export const navItems = [
  { type: 'section', label: 'VOTRE ENTREPRISE' },
  { key: 'home',      path: '/',           icon: 'Home',         label: 'Accueil',     emoji: '\u{1F3E0}' },
  { key: 'tasks',     path: '/tasks',      icon: 'CheckSquare',  label: 'Tâches',      emoji: '✅' },
  { key: 'projects',  path: '/projects',   icon: 'Target',       label: 'Projets',     emoji: '\u{1F3AF}' },
  { key: 'planning',  path: '/planning',   icon: 'Calendar',     label: 'Planning',    emoji: '\u{1F4C5}', hidden: true },
  { key: 'documents', path: '/documents',  icon: 'FileText',     label: 'Documents',   emoji: '\u{1F4C1}' },
  { key: 'email',     path: '/email',      icon: 'Mail',         label: 'Email',       emoji: '\u{1F4E7}', hidden: true },
  { key: 'news',      path: '/news',       icon: 'Globe',        label: 'Actualités',  emoji: '\u{1F310}' },

  { type: 'section', label: 'NOS OUTILS' },
  { key: 'parc',        path: '/parc',        icon: 'Monitor',        label: 'Parc',         emoji: '\u{1F5A5}️' },
  { key: 'chromebooks', path: '/chromebooks', icon: 'Laptop',         label: 'Chromebooks',  emoji: '\u{1F4BB}' },
  { key: 'suppliers',  path: '/suppliers',  icon: 'Users',          label: 'Prestataires',emoji: '\u{1F4C7}' },
  { key: 'security',   path: '/security',   icon: 'Shield',         label: 'Sécurité',    emoji: '\u{1F6E1}️' },
  { key: 'monitoring', path: '/monitoring', icon: 'Activity',       label: 'Monitoring',  emoji: '\u{1F4E1}' },
  { key: 'wiki',       path: '/wiki',       icon: 'BookOpen',       label: 'Procédures',  emoji: '\u{1F4D6}' },
  { key: 'changelog',  path: '/changelog',  icon: 'ClipboardList',  label: 'Changelog',   emoji: '\u{1F4CB}', hidden: true },
  { key: 'launcher',   path: '/launcher',   icon: 'Rocket',         label: 'Lanceur',     emoji: '\u{1F680}' },

  { key: 'tools',     path: '/tools',     icon: 'Wrench',   label: 'Outils',       emoji: '\u{1F527}', bottom: true, hidden: true },
  { key: 'users',     path: '/users',     icon: 'Users',    label: 'Utilisateurs', emoji: '\u{1F465}', bottom: true },
  { key: 'settings',  path: '/settings',  icon: 'Settings', label: 'Paramètres',   emoji: '⚙️',        bottom: true },
];

// "What's new" content per module. The NEW badge stays in the sidebar until the
// user actually visits the module for the first time — at that point a modal
// summarises the highlights and the badge disappears (state in localStorage).
//
// To re-flag a module after a future big update: bump `since` and update the
// highlights array. The user has marked the previous version as seen, but a
// `since` change is treated as a fresh badge.
export const whatsNew = {
  chromebooks: {
    since: '7.2.0',
    title: 'Chromebooks — nouveau module',
    highlights: [
      "Synchronisation avec Google Workspace : tire automatiquement les profs et leurs Chromebooks de l'OU « Personnel éducatif »",
      "Association automatique chromebook ↔ prof via le champ « dernier utilisateur » Google",
      "Filtres : statut local (en service, à rendre, rendu, en panne…), modèle, recherche libre",
      "Marquage des profs partants / arrivants en préparation pour la rentrée",
      "Historique complet : qui a eu quel chromebook, quand, dans quel état",
      "Détection des orphelins (chromebooks sans prof identifié) et profs sans device",
      "Politique sync « INSERT/UPDATE seulement » : un device sorti de l'OU reste tracké",
    ],
  },
  documents: {
    since: '6.7.0',
    title: 'Documents — refonte complète',
    highlights: [
      "Regroupement automatique des documents liés (Devis → BPA → Facture) en \"Ensembles\"",
      "Référence interne auto-générée pour chaque document : DEV-2026-001, FAC-2026-042…",
      "3 modes d'affichage : Liste, Par date, Par prestataire (basculer dans la barre)",
      "Au moment de l'import, possibilité de lier directement à un document existant",
      "Flag « Acompte » sur les factures, badge rouge ACOMPTE visible sur la ligne",
      "Boutons d'action toujours visibles, plus de hover-only frustrant",
    ],
  },
  projects: {
    since: '6.5.0',
    title: 'Projets — outillage avancé',
    highlights: [
      "Drag-to-edit sur le Gantt : tirer une barre pour la déplacer, son bord droit pour redimensionner",
      "Export PDF du projet entier (header, budget, Gantt, tâches, prestataires, journal)",
      "Dépendances entre tâches avec flèches sur le Gantt (style GanttProject)",
      "Jalons (milestones) affichés en losange",
      "Édition de tâche directement depuis la liste (bouton ✏️)",
      "Duplication de projet (recopie tâches, dates effacées, document links \"en attente\")",
      "Budget : 3 niveaux Prévu / Engagé / Facturé + helper « % d'un devis » pour les acomptes",
    ],
  },
  settings: {
    since: '6.5.1',
    title: 'Paramètres — outillage prod',
    highlights: [
      "Restauration de backup en 1 clic depuis l'app (avec filet pre-restore automatique)",
      "Téléchargement individuel d'un backup + import d'un ZIP externe",
      "Export diagnostic en 1 clic (versions, chemins, compteurs DB) pour faire du support",
      "Section « Emplacement des données » : DB, backups, documents, logos avec bouton « Ouvrir » et « Copier »",
      "Bandeau rouge « Backend déconnecté » qui apparaît si le sidecar Python plante",
    ],
  },
};

// v7.4.0 — Module help registry. Available via the "?" button in the navbar
// (always visible). Different from `whatsNew` which is one-shot per version :
// help is permanent reference content, whatsNew is "hey look at this new
// thing". Each entry: { title, emoji, description, sections[], tips[] }.
// Sections each have a label + bullet list of features.
export const moduleHelp = {
  home: {
    title: 'Accueil',
    emoji: '🏠',
    description: "Tableau de bord d'entrée. Synthèse de ce qui demande ton attention aujourd'hui.",
    sections: [
      {
        label: 'À quoi ça sert',
        items: [
          "Voir d'un coup d'œil tes tâches en cours, dossiers actifs, événements du jour",
          "Repérer ce qui est en retard ou à relancer",
          "Accéder rapidement aux modules les plus utilisés",
        ],
      },
    ],
    tips: [
      "Les cards sont réorganisables — fais glisser pour mettre ce qui t'intéresse en haut",
      "Clique sur n'importe quelle carte pour aller directement au module concerné",
    ],
  },
  tasks: {
    title: 'Tâches',
    emoji: '✅',
    description: "Gestion des tâches IT au quotidien. Liste + Kanban + Calendrier selon ton humeur.",
    sections: [
      {
        label: 'Fonctionnalités clés',
        items: [
          "3 vues : Liste, Kanban (par statut), Calendrier (par échéance)",
          "Statuts : à faire / en cours / terminé (la coche binaire est conservée pour compat)",
          "Catégories, priorités, dates d'échéance, sites (NDK/SU/NDE)",
          "Tâches récurrentes (quotidien, hebdo, mensuel)",
          "Checklist sous-tâches avec progression",
          "Dépendances entre tâches (visibles sur le Gantt des Projets)",
          "Liaison à un projet pour le retrouver dans le contexte du projet",
        ],
      },
    ],
    tips: [
      "Ctrl+N ouvre la création rapide d'une tâche depuis n'importe où",
      "Les tâches en retard remontent automatiquement dans les alertes (cloche en haut)",
      "Les templates de tâches accélèrent la création des tâches répétitives (clic droit sur une tâche pour en faire un template)",
    ],
  },
  projects: {
    title: 'Projets',
    emoji: '🎯',
    description: "Projets IT pluri-tâches avec Gantt, budget et journal d'activité.",
    sections: [
      {
        label: 'Fonctionnalités clés',
        items: [
          "Gantt drag-to-edit avec dépendances et jalons",
          "Budget en 3 niveaux : Prévu / Engagé / Facturé",
          "Tâches liées au projet, rattachement de prestataires et documents",
          "Export PDF complet (header, budget, Gantt, tâches, etc)",
          "Duplication de projet (recopie tâches, dates effacées)",
        ],
      },
    ],
    tips: [
      "L'helper « % d'un devis » dans le budget est utile pour les acomptes",
      "Le Gantt accepte le drag pour déplacer une barre et le drag du bord droit pour redimensionner",
    ],
  },
  documents: {
    title: 'Documents (Dossiers)',
    emoji: '📁',
    description: "Suivi des achats IT par dossier. Du devis à la facture, tout regroupé.",
    sections: [
      {
        label: 'Le modèle « Dossier »',
        items: [
          "Un dossier = un cas d'achat (ex: renouvellement licences)",
          "Cycle de vie : demande → devis → BPA → commande → livré → archive",
          "Tous les docs liés (Devis, BPA, Facture) groupés sur la même fiche",
          "Activity feed : statuts, notes, dates clés",
        ],
      },
      {
        label: 'Fonctionnalités',
        items: [
          "Référence interne auto (DEV-2026-001, FAC-2026-042)",
          "Filtres par période, prestataire, statut",
          "Tri par date du doc le plus récent ou ancien",
          "Import drag-and-drop avec détection auto du prestataire",
          "Preview document intégré (œil)",
          "Flag « Acompte » sur les factures",
        ],
      },
    ],
    tips: [
      "Pour rattacher un doc existant à un autre dossier : utilise le bouton « Rattacher » plutôt que de réimporter",
      "Le bouton « Cleanup orphelins » dans les paramètres avancés purge les rows DB sans fichier",
    ],
  },
  news: {
    title: 'Actualités',
    emoji: '🌐',
    description: "Lecteur RSS pour suivre les flux IT (cybersécurité, Microsoft, Google, etc).",
    sections: [
      {
        label: 'Fonctionnalités',
        items: [
          "Lecteur de flux RSS configurables (Paramètres → RSS)",
          "Filtrage par catégorie et par source",
          "Marquage lu / non lu",
        ],
      },
    ],
    tips: [
      "Ajoute tes flux préférés dans Paramètres → RSS",
    ],
  },
  parc: {
    title: 'Parc',
    emoji: '🖥️',
    description: "Inventaire du parc IT (PC, serveurs, switches, imprimantes…). Sync GLPI.",
    sections: [
      {
        label: 'Fonctionnalités clés',
        items: [
          "Inventaire par site / bâtiment / salle",
          "Types : PC, Portable, Serveur, Switch, Imprimante, AP Wi-Fi…",
          "Sync GLPI (lecture inventaire externe)",
          "Étiquettes QR imprimables (formats Avery / Apli configurables)",
          "Audit intelligent (équipements sans salle, sans serial, etc.)",
          "Suivi garantie et date d'achat",
        ],
      },
    ],
    tips: [
      "Pour les étiquettes : utilise « Page de calibrage » avant la première impression",
      "GLPI fournit l'inventaire des PC, le reste se rentre à la main",
    ],
  },
  chromebooks: {
    title: 'Chromebooks',
    emoji: '💻',
    description: "Mini-MDM pour les Chromebooks des profs. Sync avec Google Admin Directory.",
    sections: [
      {
        label: 'Fonctionnalités clés',
        items: [
          "Sync automatique avec Google Workspace (OU paramétrable)",
          "Association auto chromebook ↔ prof (via dernier utilisateur connecté)",
          "Statuts locaux : en service, à rendre, rendu, en panne, à effacer, stock",
          "Historique des affectations",
          "Onglet Profs avec statut local (présent/partant/arrivant)",
          "Alerte fin de support OS Google",
        ],
      },
    ],
    tips: [
      "Lance « Synchroniser Google » après une mise à jour du module",
      "Pour les chromebooks utilisés par des non-profs : l'email s'affiche tel quel, pas de panique",
      "Le bouton « Ouvrir dans Google Admin » dans le détail file directement vers la console Google",
    ],
  },
  suppliers: {
    title: 'Prestataires',
    emoji: '📇',
    description: "Mini-CRM des fournisseurs IT avec KPIs, contacts et historique.",
    sections: [
      {
        label: 'Fonctionnalités clés',
        items: [
          "KPIs auto : engagé total / YTD, dossiers actifs, dernière interaction",
          "Statut relationnel auto : actif / dormant / inactif / jamais utilisé",
          "Contacts secondaires (plusieurs interlocuteurs par presta)",
          "Catalogue des services rendus (types de docs)",
          "Timeline d'activité",
          "Domaines avec couleurs (réseau, sécurité, etc.)",
        ],
      },
    ],
    tips: [
      "Filtre « Statut dormant » pour identifier les prestas à relancer",
      "Le logo du presta s'affiche partout où il apparaît (cards de dossiers, etc.)",
    ],
  },
  security: {
    title: 'Sécurité',
    emoji: '🛡️',
    description: "Suivi des incidents sécurité, alertes WithSecure et audits.",
    sections: [
      {
        label: 'Fonctionnalités',
        items: [
          "Alertes WithSecure (devices infectés, alertes EDR)",
          "Audit des comptes (mots de passe expirés, comptes inactifs)",
          "Suivi des actions de remédiation",
        ],
      },
    ],
  },
  monitoring: {
    title: 'Monitoring',
    emoji: '📡',
    description: "État live du parc via Zabbix : hosts up/down, alertes actives.",
    sections: [
      {
        label: 'Fonctionnalités',
        items: [
          "Liste des problèmes actifs sur Zabbix",
          "Filtrage par sévérité et par host",
          "Accusé de réception (ack) directement depuis l'interface",
        ],
      },
    ],
    tips: [
      "Les problèmes critiques remontent dans les alertes (cloche en haut)",
    ],
  },
  wiki: {
    title: 'Procédures (Wiki)',
    emoji: '📖',
    description: "Base de connaissance interne : procédures, notes, guides.",
    sections: [
      {
        label: 'Fonctionnalités',
        items: [
          "Articles avec éditeur riche (HTML)",
          "Catégories pour organiser",
          "Recherche full-text",
          "Versioning des modifications",
        ],
      },
    ],
  },
  launcher: {
    title: 'Lanceur',
    emoji: '🚀',
    description: "Raccourcis vers les outils web utilisés au quotidien.",
    sections: [
      {
        label: 'Fonctionnalités',
        items: [
          "Liens vers des outils web (consoles admin, dashboards, etc.)",
          "Catégories",
          "Favoris en premier",
          "Icônes personnalisables (emoji ou URL d'image)",
        ],
      },
    ],
  },
  users: {
    title: 'Utilisateurs',
    emoji: '👥',
    description: "Gestion des utilisateurs du programme DashboardIT (seulement si plusieurs personnes l'utilisent).",
    sections: [
      {
        label: 'Fonctionnalités',
        items: [
          "Création / édition / suppression de comptes",
          "Rôles (admin / user)",
          "Reset de mot de passe",
        ],
      },
    ],
  },
  settings: {
    title: 'Paramètres',
    emoji: '⚙️',
    description: "Configuration du programme : thème, intégrations, sauvegarde, sécurité DB.",
    sections: [
      {
        label: 'Sections clés',
        items: [
          "Général : nom utilisateur, modules activés, ordre des cards Home",
          "Thème : clair / sombre / glass + couleur d'accent",
          "Intégrations : Google (Gmail/Calendar/Admin Directory), GLPI, Zabbix, WithSecure",
          "RSS : ajouter/supprimer des flux",
          "Établissements : codes, logos, couleurs (NDK/SU/NDE)",
          "Sécurité DB : intégrité, FK check, VACUUM, réparation des FK orphelines",
          "Sauvegardes : manuelles, auto (intervalle configurable), restauration",
        ],
      },
    ],
    tips: [
      "Les sauvegardes auto sont créées toutes les 6 heures par défaut",
      "Avant toute opération destructive (FK repair, restore), une sauvegarde est créée automatiquement",
    ],
  },
};


// Cached set of seen module keys. Loaded once at module load from localStorage.
function _loadSeen() {
  try {
    const raw = localStorage.getItem('whatsNew.seen');
    if (!raw) return new Set();
    const obj = JSON.parse(raw); // shape: { documents: '6.7.0', projects: '6.5.0', … }
    return new Set(Object.keys(obj).filter(k => obj[k] === (whatsNew[k]?.since)));
  } catch { return new Set(); }
}

// Reactive set: items the user has already acknowledged. Updated by markSeen().
export const seenNewKeys = writable(_loadSeen());

export function markNewSeen(key) {
  if (!whatsNew[key]) return;
  try {
    const raw = localStorage.getItem('whatsNew.seen');
    const obj = raw ? JSON.parse(raw) : {};
    obj[key] = whatsNew[key].since;
    localStorage.setItem('whatsNew.seen', JSON.stringify(obj));
  } catch {}
  seenNewKeys.update(s => { const out = new Set(s); out.add(key); return out; });
}

// True when a module has whatsNew content AND the user hasn't dismissed the
// current `since` version yet.
export function isNew(key, seen) {
  return !!whatsNew[key] && !seen.has(key);
}
