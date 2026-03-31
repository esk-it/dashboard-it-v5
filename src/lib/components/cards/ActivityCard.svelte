<script>
  import { onMount } from 'svelte';
  import { Clock, FileText, CheckCircle, AlertTriangle, User, Settings, Bell } from 'lucide-svelte';
  import GlassCard from '../GlassCard.svelte';

  let activities = [];
  let loading = true;

  export async function refresh() { await load(); }

  onMount(load);

  async function load() {
    loading = true;
    try {
      const res = await fetch('http://localhost:8010/api/dashboard/activity?limit=10');
      activities = await res.json();
    } catch { activities = []; }
    loading = false;
  }

  function timeAgo(dateStr) {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      const now = new Date();
      const diffMs = now - d;
      const mins = Math.floor(diffMs / 60000);
      if (mins < 1) return "\u00C0 l'instant";
      if (mins < 60) return `Il y a ${mins} min`;
      const hours = Math.floor(mins / 60);
      if (hours < 24) return `Il y a ${hours}h`;
      const days = Math.floor(hours / 24);
      if (days === 1) return 'Hier';
      if (days < 7) return `Il y a ${days}j`;
      return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
    } catch { return ''; }
  }

  // Map activity type/emoji to a Lucide icon component and color
  function getActivityIcon(item) {
    const type = (item.type || '').toLowerCase();
    const emoji = item.emoji || '';

    if (type.includes('task') || type.includes('tache') || emoji.includes('\u2705')) {
      return { icon: CheckCircle, color: '#3A9B94' };
    }
    if (type.includes('doc') || type.includes('file') || emoji.includes('\uD83D\uDCC4')) {
      return { icon: FileText, color: '#F8B940' };
    }
    if (type.includes('alert') || type.includes('warn') || emoji.includes('\u26A0')) {
      return { icon: AlertTriangle, color: '#FF5E5E' };
    }
    if (type.includes('user') || type.includes('login') || emoji.includes('\uD83D\uDC64')) {
      return { icon: User, color: '#58bad7' };
    }
    if (type.includes('setting') || type.includes('config') || emoji.includes('\u2699')) {
      return { icon: Settings, color: '#BB6BD9' };
    }
    if (type.includes('notif') || emoji.includes('\uD83D\uDD14')) {
      return { icon: Bell, color: 'var(--primary)' };
    }
    // Default
    return { icon: Clock, color: 'var(--primary)' };
  }
</script>

<GlassCard padding="0">
  <div class="card-inner">
    <div class="card-header">
      <h3>
        <Clock size={15} style="display:inline;vertical-align:-2px;margin-right:6px;color:var(--primary)" />
        Activit&eacute; r&eacute;cente
      </h3>
    </div>

    <div class="activity-list">
      {#if loading}
        <div class="activity-empty">Chargement...</div>
      {:else if activities.length === 0}
        <div class="activity-empty">Aucune activit&eacute; r&eacute;cente</div>
      {:else}
        {#each activities as item}
          {@const actIcon = getActivityIcon(item)}
          <div class="activity-item">
            <div class="activity-icon" style="background: {actIcon.color}15; color: {actIcon.color};">
              <svelte:component this={actIcon.icon} size={16} />
            </div>
            <div class="activity-info">
              <span class="activity-text">{item.text}</span>
              <span class="activity-time">{timeAgo(item.date)}</span>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </div>
</GlassCard>

<style>
  .card-inner {
    display: flex;
    flex-direction: column;
  }

  .card-header {
    padding: 16px 20px 12px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .card-header h3 {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
    display: flex;
    align-items: center;
  }

  .activity-list {
    padding: 8px 12px;
  }

  .activity-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 8px;
    border-radius: 8px;
    transition: background 0.15s;
  }

  .activity-item:hover {
    background: var(--bg-hover);
  }

  .activity-icon {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 1px;
  }

  .activity-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .activity-text {
    font-size: 13px;
    color: var(--text-primary);
    line-height: 1.35;
  }

  .activity-time {
    font-size: 11px;
    color: var(--text-muted);
  }

  .activity-empty {
    padding: 24px;
    text-align: center;
    color: var(--text-muted);
    font-size: 13px;
  }
</style>
