import { writable } from 'svelte/store';

export const currentPage = writable('/');
export const sidebarOpen = writable(true);

// Sidebar categories — stable keys are used for localStorage persistence of the
// expanded/collapsed state, and as `category` references on individual nav items.
export const navCategories = [
  { key: 'work',   label: 'Travail',         icon: 'Target',   defaultOpen: true  },
  { key: 'docs',   label: 'Documentation',   icon: 'FileText', defaultOpen: true  },
  { key: 'infra',  label: 'Infrastructure',  icon: 'Monitor',  defaultOpen: false },
  { key: 'comms',  label: 'Communication',   icon: 'Mail',     defaultOpen: false },
  { key: 'tools',  label: 'Outils',          icon: 'Wrench',   defaultOpen: false },
  { key: 'system', label: 'Système',         icon: 'Settings', defaultOpen: false },
];

// Flat list of nav items. Items without a `category` are rendered top-level
// (above the categories). The Navbar uses this list to look up the label for
// the current page, so the flat shape is preserved.
export const navItems = [
  // Top-level
  { key: 'home', path: '/', icon: 'Home', label: 'Accueil', emoji: '\u{1F3E0}' },

  // Travail
  { key: 'projects', path: '/projects', icon: 'Target',      label: 'Projets',  emoji: '\u{1F3AF}', category: 'work' },
  { key: 'tasks',    path: '/tasks',    icon: 'CheckSquare', label: 'Tâches',   emoji: '✅',    category: 'work' },
  { key: 'planning', path: '/planning', icon: 'Calendar',    label: 'Planning', emoji: '\u{1F4C5}', category: 'work' },

  // Documentation
  { key: 'documents', path: '/documents', icon: 'FileText', label: 'Documents',    emoji: '\u{1F4C1}', category: 'docs' },
  { key: 'suppliers', path: '/suppliers', icon: 'Users',    label: 'Prestataires', emoji: '\u{1F4C7}', category: 'docs' },
  { key: 'wiki',      path: '/wiki',      icon: 'BookOpen', label: 'Procédures',   emoji: '\u{1F4D6}', category: 'docs' },

  // Infrastructure
  { key: 'parc',       path: '/parc',       icon: 'Monitor',  label: 'Parc',       emoji: '\u{1F5A5}️',     category: 'infra' },
  { key: 'security',   path: '/security',   icon: 'Shield',   label: 'Sécurité',   emoji: '\u{1F6E1}️',    category: 'infra' },
  { key: 'monitoring', path: '/monitoring', icon: 'Activity', label: 'Monitoring', emoji: '\u{1F4E1}',          category: 'infra' },

  // Communication
  { key: 'email', path: '/email', icon: 'Mail',  label: 'Email',      emoji: '\u{1F4E7}', category: 'comms' },
  { key: 'news',  path: '/news',  icon: 'Globe', label: 'Actualités', emoji: '\u{1F310}', category: 'comms' },

  // Outils
  { key: 'launcher',  path: '/launcher',  icon: 'Rocket',        label: 'Lanceur',   emoji: '\u{1F680}', category: 'tools' },
  { key: 'tools',     path: '/tools',     icon: 'Wrench',        label: 'Outils',    emoji: '\u{1F527}', category: 'tools' },
  { key: 'changelog', path: '/changelog', icon: 'ClipboardList', label: 'Changelog', emoji: '\u{1F4CB}', category: 'tools' },

  // Système
  { key: 'users',    path: '/users',    icon: 'Users',    label: 'Utilisateurs', emoji: '\u{1F465}',     category: 'system' },
  { key: 'settings', path: '/settings', icon: 'Settings', label: 'Paramètres',   emoji: '⚙️', category: 'system' },
];

// Mark items as "NEW" if you want a red badge — just add their key here.
export const newItems = new Set([]);
