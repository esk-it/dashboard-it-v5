import { writable } from 'svelte/store';

export const currentPage = writable('/');
export const sidebarOpen = writable(true);

export const navItems = [
  { type: 'section', label: 'VOTRE ENTREPRISE' },
  { key: 'home', path: '/', icon: 'Home', label: 'Dashboard', emoji: '\u{1F3E0}' },
  { key: 'tasks', path: '/tasks', icon: 'CheckSquare', label: 'Tâches', emoji: '✅' },
  { key: 'projects', path: '/projects', icon: 'Target', label: 'Projets', emoji: '\u{1F3AF}' },
  { key: 'planning', path: '/planning', icon: 'Calendar', label: 'Planning', emoji: '\u{1F4C5}' },
  { key: 'documents', path: '/documents', icon: 'FileText', label: 'Documents', emoji: '\u{1F4C1}' },
  { key: 'email', path: '/email', icon: 'Mail', label: 'Email', emoji: '\u{1F4E7}' },
  { key: 'news', path: '/news', icon: 'Globe', label: 'Actualités', emoji: '\u{1F310}' },
  { type: 'section', label: 'NOS OUTILS' },
  { key: 'parc', path: '/parc', icon: 'Monitor', label: 'Parc', emoji: '\u{1F5A5}\uFE0F' },
  { key: 'suppliers', path: '/suppliers', icon: 'Users', label: 'Prestataires', emoji: '\u{1F4C7}' },
  { key: 'security', path: '/security', icon: 'Shield', label: 'Sécurité', emoji: '\u{1F6E1}\uFE0F' },
  { key: 'monitoring', path: '/monitoring', icon: 'Activity', label: 'Monitoring', emoji: '\u{1F4E1}' },
  { key: 'wiki', path: '/wiki', icon: 'BookOpen', label: 'Procédures', emoji: '\u{1F4D6}' },
  { key: 'changelog', path: '/changelog', icon: 'ClipboardList', label: 'Changelog', emoji: '\u{1F4CB}' },
  { key: 'launcher', path: '/launcher', icon: 'Rocket', label: 'Lanceur', emoji: '\u{1F680}' },
  { key: 'tools', path: '/tools', icon: 'Wrench', label: 'Outils', emoji: '\u{1F527}', bottom: true },
  { key: 'users', path: '/users', icon: 'Users', label: 'Utilisateurs', emoji: '\u{1F465}', bottom: true },
  { key: 'settings', path: '/settings', icon: 'Settings', label: 'Paramètres', emoji: '\u2699\uFE0F', bottom: true },
];
