<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../api/client.js';
  import { settings } from '../stores/settings.js';
  import { currentPage } from '../stores/navigation.js';
  import { success } from '../stores/toast.js';
  import KpiCard from '../components/KpiCard.svelte';
  import PriorityCard from '../components/cards/PriorityCard.svelte';
  import SysMonCard from '../components/cards/SysMonCard.svelte';
  import GaugeChart from '../components/cards/GaugeChart.svelte';
  import SparklineChart from '../components/cards/SparklineChart.svelte';
  import DonutChart from '../components/cards/DonutChart.svelte';
  import MixedChart from '../components/cards/MixedChart.svelte';
  import EventsWidget from '../components/cards/EventsWidget.svelte';
  import QuickLinksCard from '../components/cards/QuickLinksCard.svelte';
  import ActivityCard from '../components/cards/ActivityCard.svelte';
  import { ClipboardList, AlertTriangle, CalendarDays, FileText, Monitor, RefreshCw } from 'lucide-svelte';

  const JOURS = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'];
  const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'ao\u00fbt', 'septembre', 'octobre', 'novembre', 'décembre'];

  let clockStr = '';
  let clockTimer;
  let refreshTimer;

  // Weather in header
  let weatherData = null;

  async function loadWeather() {
    try {
      const res = await fetch('http://localhost:8010/api/dashboard/weather');
      weatherData = await res.json();
      if (!weatherData.temperature && weatherData.temperature !== 0) weatherData = null;
    } catch { weatherData = null; }
  }

  // KPI data
  let kpiTasks = 0;
  let kpiOverdue = 0;
  let kpiWeek = 0;
  let kpiDocs = 0;
  let kpiParc = 0;

  // Component refs
  let priorityCard;
  let sysMonCard;
  let gaugeChart;
  let sparklineChart;
  let donutChart;
  let mixedChart;
  let eventsWidget;
  let activityCard;

  $: greeting = getGreeting();
  $: username = $settings.username || 'Utilisateur';
  $: dateStr = getDateStr();

  function getGreeting() {
    const h = new Date().getHours();
    return h >= 18 || h < 6 ? 'Bonsoir' : 'Bonjour';
  }

  function getDateStr() {
    const d = new Date();
    return `${JOURS[d.getDay()]} ${d.getDate()} ${MOIS[d.getMonth()]} ${d.getFullYear()}`;
  }

  function updateClock() {
    const d = new Date();
    clockStr = d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  async function fetchKpis() {
    try {
      const data = await api.get('/api/dashboard/kpis');
      kpiTasks = data.open_tasks || 0;
      kpiOverdue = data.overdue_tasks || 0;
      kpiWeek = data.week_tasks || 0;
      kpiDocs = data.documents || 0;
      kpiParc = data.equipment || 0;
    } catch (e) {
      // keep defaults
    }
  }

  function refreshAll() {
    fetchKpis();
    loadWeather();
    if (priorityCard?.refresh) priorityCard.refresh();
    if (gaugeChart?.refresh) gaugeChart.refresh();
    if (sparklineChart?.refresh) sparklineChart.refresh();
    if (donutChart?.refresh) donutChart.refresh();
    if (mixedChart?.refresh) mixedChart.refresh();
    if (eventsWidget?.refresh) eventsWidget.refresh();
    if (activityCard?.refresh) activityCard.refresh();
    success('Donn\u00e9es actualis\u00e9es');
  }

  function goNewTask() {
    currentPage.set('/tasks');
  }

  onMount(() => {
    updateClock();
    clockTimer = setInterval(updateClock, 1000);
    fetchKpis();
    loadWeather();

    // Auto-refresh
    const mins = $settings.auto_refresh_minutes || 5;
    refreshTimer = setInterval(() => {
      fetchKpis();
    }, mins * 60 * 1000);
  });

  onDestroy(() => {
    if (clockTimer) clearInterval(clockTimer);
    if (refreshTimer) clearInterval(refreshTimer);
  });
</script>

<div class="home-page">
  <!-- Header -->
  <header class="home-header">
    <div class="header-left">
      <h1 class="greeting">{greeting}, <span class="username">{username}</span></h1>
    </div>
    <div class="header-center">
      <p class="date-str">{dateStr}</p>
      {#if weatherData}
        <span class="weather-inline">
          <span class="wi-emoji">{weatherData.emoji}</span>
          <span class="wi-temp">{Math.round(weatherData.temperature)}{'\u00b0'}C</span>
          <span class="wi-desc">{weatherData.description}</span>
          <span class="wi-city">— {weatherData.city}</span>
        </span>
      {/if}
    </div>
    <div class="header-right">
      <div class="clock-frame">
        <span class="clock">{clockStr}</span>
      </div>
      <button class="btn-refresh" on:click={refreshAll} title="Actualiser">
        <RefreshCw size={16} />
      </button>
      <button class="btn-primary" on:click={goNewTask}>
        + T&acirc;che
      </button>
    </div>
  </header>

  <!-- 12-column grid layout -->
  <div class="ya-grid">

    <!-- Row 1: 2 large gradient stat cards (col-6 each) -->
    <div class="ya-col-6">
      <KpiCard
        title="T&Acirc;CHES EN COURS"
        value={kpiTasks}
        bgColor="gradient-primary"
        icon={ClipboardList}
        hint="Total des t&acirc;ches ouvertes"
        sparkData={[3, 5, 2, 8, 6, 4, 7]}
        onClick={() => currentPage.set('/tasks')}
      />
    </div>
    <div class="ya-col-6">
      <KpiCard
        title="EN RETARD"
        value={kpiOverdue}
        bgColor="gradient-secondary"
        icon={AlertTriangle}
        hint={kpiOverdue > 0 ? 'Action requise' : 'Tout est \u00e0 jour'}
        sparkData={[1, 3, 2, 4, 2, 5, 3]}
      />
    </div>

    <!-- Row 2: 4 smaller stat cards (col-3 each) -->
    <div class="ya-col-3">
      <KpiCard
        title="CETTE SEMAINE"
        value={kpiWeek}
        icon={CalendarDays}
        hint="T&acirc;ches planifi&eacute;es"
      />
    </div>
    <div class="ya-col-3">
      <KpiCard
        title="DOCUMENTS"
        value={kpiDocs}
        icon={FileText}
        hint="Fichiers index&eacute;s"
        onClick={() => currentPage.set('/documents')}
      />
    </div>
    <div class="ya-col-3">
      <KpiCard
        title="PARC INFORMATIQUE"
        value={kpiParc}
        bgColor="gradient-info"
        icon={Monitor}
        hint="&Eacute;quipements suivis"
        onClick={() => currentPage.set('/parc')}
      />
    </div>
    <div class="ya-col-3">
      <GaugeChart bind:this={gaugeChart} />
    </div>

    <!-- Row 3: MixedChart (col-8) + EventsWidget (col-4) -->
    <div class="ya-col-8">
      <div class="ya-card">
        <MixedChart bind:this={mixedChart} />
      </div>
    </div>
    <div class="ya-col-4">
      <div class="ya-card">
        <EventsWidget bind:this={eventsWidget} />
      </div>
    </div>

    <!-- Row 4: DonutChart (col-4) + PriorityCard (col-8) -->
    <div class="ya-col-4">
      <div class="ya-card">
        <DonutChart bind:this={donutChart} />
      </div>
    </div>
    <div class="ya-col-8">
      <div class="ya-card">
        <PriorityCard bind:this={priorityCard} />
      </div>
    </div>

    <!-- Row 5: SysMonCard (col-4) + ActivityCard (col-4) + QuickLinksCard (col-4) -->
    <div class="ya-col-4">
      <SysMonCard bind:this={sysMonCard} />
    </div>
    <div class="ya-col-4">
      <ActivityCard bind:this={activityCard} />
    </div>
    <div class="ya-col-4">
      <QuickLinksCard />
    </div>
  </div>
</div>

<style>
  .home-page {
    animation: fadeIn 0.35s ease-out;
  }

  /* ── Header ────────────────────────────────── */
  .home-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 28px;
    gap: 16px;
    flex-wrap: wrap;
  }

  .header-left {
    flex: 1;
    min-width: 180px;
  }

  .greeting {
    font-size: 26px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
    letter-spacing: -0.3px;
  }

  .username {
    color: var(--accent);
  }

  .header-center {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }

  .date-str {
    font-size: 14px;
    color: var(--text-secondary);
    margin: 0;
    text-align: center;
  }

  .weather-inline {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 4px 12px;
  }

  .wi-emoji { font-size: 18px; line-height: 1; }
  .wi-temp { font-size: 14px; font-weight: 700; color: var(--text-primary); }
  .wi-desc { font-size: 12px; color: var(--text-secondary); }
  .wi-city { font-size: 11px; color: var(--text-muted); }

  .header-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1;
    justify-content: flex-end;
  }

  .clock-frame {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 6px 14px;
  }

  .clock {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.5px;
  }

  .btn-refresh {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-refresh:hover {
    background: var(--bg-hover);
    border-color: var(--border-hover);
    color: var(--text-primary);
  }

  .btn-primary {
    background: var(--accent);
    border: none;
    border-radius: 10px;
    color: #fff;
    font-size: 13px;
    font-weight: 600;
    padding: 8px 16px;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
    box-shadow: 0 2px 12px rgba(var(--accent-rgb), 0.3);
  }

  .btn-primary:hover {
    filter: brightness(1.15);
    box-shadow: 0 4px 20px rgba(var(--accent-rgb), 0.4);
  }

  /* ── 12-column CSS Grid ────────────────────── */
  .ya-grid {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 20px;
    align-items: stretch;
  }

  .ya-col-3  { grid-column: span 3; }
  .ya-col-4  { grid-column: span 4; }
  .ya-col-6  { grid-column: span 6; }
  .ya-col-8  { grid-column: span 8; }
  .ya-col-12 { grid-column: span 12; }

  /* Make child components fill their grid cell */
  .ya-col-3 > :global(*),
  .ya-col-4 > :global(*),
  .ya-col-6 > :global(*),
  .ya-col-8 > :global(*),
  .ya-col-12 > :global(*) {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  /* ya-card wrapper for chart/widget sections */
  .ya-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 1.25rem;
    overflow: hidden;
    transition: box-shadow 0.2s ease;
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .ya-card:hover {
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  }

  .ya-card > :global(*) {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  /* ── Animation delays for stagger effect ───── */
  .ya-grid > :nth-child(1)  { animation: fadeIn 0.4s ease-out 0.00s both; }
  .ya-grid > :nth-child(2)  { animation: fadeIn 0.4s ease-out 0.04s both; }
  .ya-grid > :nth-child(3)  { animation: fadeIn 0.4s ease-out 0.08s both; }
  .ya-grid > :nth-child(4)  { animation: fadeIn 0.4s ease-out 0.12s both; }
  .ya-grid > :nth-child(5)  { animation: fadeIn 0.4s ease-out 0.16s both; }
  .ya-grid > :nth-child(6)  { animation: fadeIn 0.4s ease-out 0.20s both; }
  .ya-grid > :nth-child(7)  { animation: fadeIn 0.4s ease-out 0.24s both; }
  .ya-grid > :nth-child(8)  { animation: fadeIn 0.4s ease-out 0.28s both; }
  .ya-grid > :nth-child(9)  { animation: fadeIn 0.4s ease-out 0.32s both; }
  .ya-grid > :nth-child(10) { animation: fadeIn 0.4s ease-out 0.36s both; }
  .ya-grid > :nth-child(11) { animation: fadeIn 0.4s ease-out 0.40s both; }
  .ya-grid > :nth-child(12) { animation: fadeIn 0.4s ease-out 0.44s both; }
  .ya-grid > :nth-child(13) { animation: fadeIn 0.4s ease-out 0.48s both; }

  /* ── Responsive breakpoints ────────────────── */
  @media (max-width: 1200px) {
    .ya-col-8 { grid-column: span 12; }
    .ya-col-4 { grid-column: span 6; }
    .ya-col-3 { grid-column: span 6; }
  }

  @media (max-width: 768px) {
    .ya-grid {
      gap: 14px;
    }

    .ya-col-3,
    .ya-col-4,
    .ya-col-6,
    .ya-col-8,
    .ya-col-12 {
      grid-column: span 12;
    }

    .home-header {
      flex-direction: column;
      align-items: flex-start;
    }

    .header-center {
      align-items: flex-start;
    }

    .header-right {
      justify-content: flex-start;
    }
  }
</style>
