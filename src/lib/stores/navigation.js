import { writable } from 'svelte/store';

export const currentPage = writable('/');
export const sidebarOpen = writable(true);

// Flat list of nav items with section markers (`type: 'section'`) and a
// `bottom: true` flag for items that render in the bottom group of the
// sidebar (Outils / Utilisateurs / Paramètres).
export const navItems = [
  { type: 'section', label: 'VOTRE ENTREPRISE' },
  { key: 'home',      path: '/',           icon: 'Home',         label: 'Accueil',     emoji: '\u{1F3E0}' },
  { key: 'tasks',     path: '/tasks',      icon: 'CheckSquare',  label: 'Tâches',      emoji: '✅' },
  { key: 'projects',  path: '/projects',   icon: 'Target',       label: 'Projets',     emoji: '\u{1F3AF}' },
  { key: 'planning',  path: '/planning',   icon: 'Calendar',     label: 'Planning',    emoji: '\u{1F4C5}' },
  { key: 'documents', path: '/documents',  icon: 'FileText',     label: 'Documents',   emoji: '\u{1F4C1}' },
  { key: 'email',     path: '/email',      icon: 'Mail',         label: 'Email',       emoji: '\u{1F4E7}' },
  { key: 'news',      path: '/news',       icon: 'Globe',        label: 'Actualités',  emoji: '\u{1F310}' },

  { type: 'section', label: 'NOS OUTILS' },
  { key: 'parc',        path: '/parc',        icon: 'Monitor',        label: 'Parc',         emoji: '\u{1F5A5}️' },
  { key: 'chromebooks', path: '/chromebooks', icon: 'Laptop',         label: 'Chromebooks',  emoji: '\u{1F4BB}' },
  { key: 'suppliers',  path: '/suppliers',  icon: 'Users',          label: 'Prestataires',emoji: '\u{1F4C7}' },
  { key: 'security',   path: '/security',   icon: 'Shield',         label: 'Sécurité',    emoji: '\u{1F6E1}️' },
  { key: 'monitoring', path: '/monitoring', icon: 'Activity',       label: 'Monitoring',  emoji: '\u{1F4E1}' },
  { key: 'wiki',       path: '/wiki',       icon: 'BookOpen',       label: 'Procédures',  emoji: '\u{1F4D6}' },
  { key: 'changelog',  path: '/changelog',  icon: 'ClipboardList',  label: 'Changelog',   emoji: '\u{1F4CB}' },
  { key: 'launcher',   path: '/launcher',   icon: 'Rocket',         label: 'Lanceur',     emoji: '\u{1F680}' },

  { key: 'tools',     path: '/tools',     icon: 'Wrench',   label: 'Outils',       emoji: '\u{1F527}', bottom: true },
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
