import { writable } from 'svelte/store';

export const currentPage = writable('/');
export const sidebarOpen = writable(true);

export const navItems = [
  { type: 'section', label: 'VOTRE ENTREPRISE' },
  { key: 'home', path: '/', icon: 'Home', label: 'Accueil' },
  { key: 'news', path: '/news', icon: 'Globe', label: 'Actualités' },
  { key: 'planning', path: '/planning', icon: 'Calendar', label: 'Planning' },
  { key: 'tasks', path: '/tasks', icon: 'CheckSquare', label: 'Tâches' },
  { key: 'documents', path: '/documents', icon: 'FileText', label: 'Documents' },

  { type: 'section', label: 'NOS OUTILS' },
  { key: 'suppliers', path: '/suppliers', icon: 'Users', label: 'Prestataires' },
  { key: 'parc', path: '/parc', icon: 'Monitor', label: 'Parc' },
  { key: 'security', path: '/security', icon: 'Shield', label: 'Sécurité' },
  { key: 'monitoring', path: '/monitoring', icon: 'Activity', label: 'Monitoring' },
  { key: 'wiki', path: '/wiki', icon: 'BookOpen', label: 'Procédures' },
  { key: 'changelog', path: '/changelog', icon: 'ClipboardList', label: 'Changelog' },
  { key: 'launcher', path: '/launcher', icon: 'Rocket', label: 'Lanceur' },
  { key: 'chat', path: '/chat', icon: 'MessageSquare', label: 'Chat' },
  { key: 'email', path: '/email', icon: 'Mail', label: 'Email' },
  { key: 'users', path: '/users', icon: 'Users2', label: 'Utilisateurs' },

  { key: 'tools', path: '/tools', icon: 'Wrench', label: 'Outils', bottom: true },
  { key: 'settings', path: '/settings', icon: 'Settings', label: 'Paramètres', bottom: true },
];
