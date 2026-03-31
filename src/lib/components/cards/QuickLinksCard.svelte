<script>
  import { currentPage } from '../../stores/navigation.js';
  import { Zap, ClipboardList, FileText, CalendarDays, Shield, Monitor, BookOpen } from 'lucide-svelte';
  import GlassCard from '../GlassCard.svelte';

  const links = [
    { icon: ClipboardList, label: 'Nouvelle t\u00e2che', action: () => currentPage.set('/tasks'), color: 'var(--primary)' },
    { icon: FileText, label: 'Documents', action: () => currentPage.set('/documents'), color: '#F8B940' },
    { icon: CalendarDays, label: 'Planning', action: () => currentPage.set('/planning'), color: '#3A9B94' },
    { icon: Shield, label: 'S\u00e9curit\u00e9', action: () => currentPage.set('/security'), color: '#FF5E5E' },
    { icon: Monitor, label: 'Parc info', action: () => currentPage.set('/parc'), color: '#58bad7' },
    { icon: BookOpen, label: 'Proc\u00e9dures', action: () => currentPage.set('/wiki'), color: '#BB6BD9' },
  ];
</script>

<GlassCard padding="0">
  <div class="card-inner">
    <div class="card-header">
      <h3>
        <Zap size={15} style="display:inline;vertical-align:-2px;margin-right:6px;color:var(--primary)" />
        Acc&egrave;s rapides
      </h3>
    </div>

    <div class="links-grid">
      {#each links as link}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="link-item" on:click={link.action}>
          <div class="link-icon-wrap" style="background: {link.color}15; color: {link.color};">
            <svelte:component this={link.icon} size={20} />
          </div>
          <span class="link-label">{link.label}</span>
        </div>
      {/each}
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

  .links-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 6px;
    padding: 12px;
  }

  .link-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 14px 8px;
    border-radius: 10px;
    cursor: pointer;
    transition: background 0.15s;
  }

  .link-item:hover {
    background: var(--bg-hover);
  }

  .link-icon-wrap {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .link-label {
    font-size: 11.5px;
    color: var(--text-secondary);
    text-align: center;
    white-space: nowrap;
  }
</style>
