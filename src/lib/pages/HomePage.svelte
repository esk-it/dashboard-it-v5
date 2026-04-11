<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../api/client.js';
  import { settings } from '../stores/settings.js';
  import { currentPage } from '../stores/navigation.js';
  import { success } from '../stores/toast.js';
  import SparklineChart from '../components/cards/SparklineChart.svelte';
  import DonutChart from '../components/cards/DonutChart.svelte';
  import EventsCard from '../components/cards/EventsCard.svelte';
  import ActiveProjectsCard from '../components/cards/ActiveProjectsCard.svelte';
  import SysMonCard from '../components/cards/SysMonCard.svelte';
  import ActivityCard from '../components/cards/ActivityCard.svelte';
  import GaugeChart from '../components/cards/GaugeChart.svelte';
  import ZabbixCard from '../components/cards/ZabbixCard.svelte';

  const JOURS = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'];
  const MOIS = ['janvier', 'f\u00e9vrier', 'mars', 'avril', 'mai', 'juin', 'juillet', 'ao\u00fbt', 'septembre', 'octobre', 'novembre', 'd\u00e9cembre'];

  let clockStr = '';
  let clockTimer;
  let refreshTimer;

  // KPI data
  let weatherData = null;
  let kpiTasks = 0;
  let kpiOverdue = 0;
  let kpiWeek = 0;
  let kpiDocs = 0;
  let kpiParc = 0;

  // Component refs
  let sparklineChart;
  let donutChart;
  let eventsCard;
  let activeProjectsCard;
  let sysMonCard;
  let activityCard;
  let gaugeChart;
  let zabbixCard;

  $: greeting = getGreeting();
  $: username = $settings.username || 'Utilisateur';
  $: dateStr = getDateStr();
  $: kpiWeekTotal = 28;
  $: kpiWeekPercent = kpiWeekTotal > 0 ? Math.round((kpiWeek / kpiWeekTotal) * 100) : 0;
  $: kpiOverduePercent = (kpiTasks + kpiOverdue) > 0 ? Math.round((kpiOverdue / (kpiTasks + kpiOverdue)) * 100) : 0;

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

  async function loadWeather() {
    try {
      const res = await fetch('http://localhost:8010/api/dashboard/weather');
      weatherData = await res.json();
      if (!weatherData.temperature && weatherData.temperature !== 0) weatherData = null;
    } catch { weatherData = null; }
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
    if (sparklineChart?.refresh) sparklineChart.refresh();
    if (donutChart?.refresh) donutChart.refresh();
    if (eventsCard?.refresh) eventsCard.refresh();
    if (activeProjectsCard?.refresh) activeProjectsCard.refresh();
    if (sysMonCard?.refresh) sysMonCard.refresh();
    if (activityCard?.refresh) activityCard.refresh();
    if (gaugeChart?.refresh) gaugeChart.refresh();
    if (zabbixCard?.refresh) zabbixCard.refresh();
    success('Donn\u00e9es actualis\u00e9es');
  }

  function goNewTask() {
    currentPage.set('/tasks');
  }

  onMount(async () => {
    updateClock();
    clockTimer = setInterval(updateClock, 1000);
    await fetchKpis();
    loadWeather();

    // Delayed refresh to ensure child components have mounted and backend is ready
    setTimeout(() => {
      if (sparklineChart?.refresh) sparklineChart.refresh();
      if (donutChart?.refresh) donutChart.refresh();
      if (eventsCard?.refresh) eventsCard.refresh();
      if (activeProjectsCard?.refresh) activeProjectsCard.refresh();
      if (activityCard?.refresh) activityCard.refresh();
      if (gaugeChart?.refresh) gaugeChart.refresh();
    }, 500);

    const mins = $settings.auto_refresh_minutes || 5;
    refreshTimer = setInterval(() => {
      fetchKpis();
      if (sparklineChart?.refresh) sparklineChart.refresh();
      if (activityCard?.refresh) activityCard.refresh();
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
      <div class="date-weather-row">
        <p class="date-str">{dateStr}</p>
        {#if weatherData}
          <span class="weather-inline">
            <span class="wi-emoji">{weatherData.emoji}</span>
            <span class="wi-temp">{Math.round(weatherData.temperature)}&deg;C</span>
            <span class="wi-desc">{weatherData.description}</span>
            <span class="wi-city">&mdash; {weatherData.city}</span>
          </span>
        {/if}
      </div>
    </div>
    <div class="header-right">
      <div class="clock-frame">
        <span class="clock">{clockStr}</span>
      </div>
      <button class="btn-ghost" on:click={refreshAll}>
        &#x21BB; Actualiser
      </button>
      <button class="btn-primary-action" on:click={goNewTask}>
        + T&acirc;che
      </button>
    </div>
  </header>

  <!-- ═══ ROW 1: 4 YashAdmin-style KPI cards ═══ -->
  <div class="row">
    <!-- Card 1: Purple — Taches en cours -->
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="col-3 ya-card ya-card--purple" on:click={() => currentPage.set('/tasks')}>
      <div class="ya-card__deco-circle ya-card__deco-circle--1"></div>
      <div class="ya-card__deco-circle ya-card__deco-circle--2"></div>
      <div class="ya-card__body">
        <span class="ya-card__label">Taches en cours</span>
        <span class="ya-card__value">{kpiTasks}</span>
        <div class="ya-card__bars">
          <svg viewBox="0 0 120 40" class="ya-bars-svg">
            <rect x="2"  y="22" width="10" height="18" rx="2" fill="rgba(255,255,255,0.25)" />
            <rect x="16" y="10" width="10" height="30" rx="2" fill="rgba(255,255,255,0.35)" />
            <rect x="30" y="16" width="10" height="24" rx="2" fill="rgba(255,255,255,0.25)" />
            <rect x="44" y="6"  width="10" height="34" rx="2" fill="rgba(255,255,255,0.45)" />
            <rect x="58" y="14" width="10" height="26" rx="2" fill="rgba(255,255,255,0.30)" />
            <rect x="72" y="20" width="10" height="20" rx="2" fill="rgba(255,255,255,0.20)" />
            <rect x="86" y="8"  width="10" height="32" rx="2" fill="rgba(255,255,255,0.40)" />
            <rect x="100" y="18" width="10" height="22" rx="2" fill="rgba(255,255,255,0.28)" />
          </svg>
        </div>
      </div>
      <div class="ya-card__footer">
        <div class="ya-card__avatars">
          <span class="ya-avatar" style="background:#7B5EC6;">IT</span>
          <span class="ya-avatar" style="background:#9B8AD8;">Eq</span>
        </div>
        <span class="ya-card__badge">{kpiTasks > 0 ? Math.min(Math.round((kpiTasks / (kpiTasks + kpiOverdue || 1)) * 100), 100) : 0}%</span>
      </div>
    </div>

    <!-- Card 2: Gold — En retard -->
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="col-3 ya-card ya-card--gold" on:click={() => currentPage.set('/tasks')}>
      <div class="ya-card__deco-circle ya-card__deco-circle--1"></div>
      <div class="ya-card__deco-circle ya-card__deco-circle--2"></div>
      <div class="ya-card__body">
        <span class="ya-card__label">En retard</span>
        <span class="ya-card__value">{kpiOverdue}</span>
        <div class="ya-card__bars">
          <svg viewBox="0 0 120 40" class="ya-bars-svg">
            <rect x="2"  y="18" width="10" height="22" rx="2" fill="rgba(255,255,255,0.30)" />
            <rect x="16" y="24" width="10" height="16" rx="2" fill="rgba(255,255,255,0.22)" />
            <rect x="30" y="8"  width="10" height="32" rx="2" fill="rgba(255,255,255,0.40)" />
            <rect x="44" y="14" width="10" height="26" rx="2" fill="rgba(255,255,255,0.30)" />
            <rect x="58" y="20" width="10" height="20" rx="2" fill="rgba(255,255,255,0.25)" />
            <rect x="72" y="4"  width="10" height="36" rx="2" fill="rgba(255,255,255,0.45)" />
            <rect x="86" y="16" width="10" height="24" rx="2" fill="rgba(255,255,255,0.28)" />
            <rect x="100" y="12" width="10" height="28" rx="2" fill="rgba(255,255,255,0.35)" />
          </svg>
        </div>
      </div>
      <div class="ya-card__footer">
        <span class="ya-card__hint">{kpiOverdue > 0 ? 'Action requise' : 'Tout est \u00e0 jour'}</span>
        <button class="ya-card__plus" on:click|stopPropagation={goNewTask}>+</button>
      </div>
    </div>

    <!-- Card 3: Teal gradient — Synthese IT -->
    <div class="col-3 ya-card ya-card--teal">
      <div class="ya-card__teal-deco">
        <svg viewBox="0 0 80 80" fill="none">
          <circle cx="40" cy="40" r="36" stroke="rgba(255,255,255,0.15)" stroke-width="2" fill="none" />
          <path d="M28 42 L36 50 L54 30" stroke="rgba(255,255,255,0.6)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none" />
          <circle cx="40" cy="40" r="26" stroke="rgba(255,255,255,0.08)" stroke-width="1.5" fill="none" />
        </svg>
      </div>
      <div class="ya-card__body ya-card__body--teal">
        <span class="ya-card__label ya-card__label--lg">Votre IT, securise et surveille</span>
        <p class="ya-card__desc">Parc informatique, taches et documents sous controle.</p>
        <div class="ya-card__avatars ya-card__avatars--row">
          <span class="ya-avatar" style="background:#2dd4bf;">P</span>
          <span class="ya-avatar" style="background:#14b8a6;">M</span>
          <span class="ya-avatar" style="background:#0d9488;">S</span>
        </div>
        <span class="ya-card__clients">{kpiParc}+ Equipements geres</span>
      </div>
    </div>

    <!-- Card 4: Radial progress — Ma Progression -->
    <div class="col-3 ya-card ya-card--progress">
      <div class="ya-card__body ya-card__body--center">
        <div class="ya-radial">
          <svg viewBox="0 0 120 120" class="ya-radial__svg">
            <circle cx="60" cy="60" r="52" fill="none" stroke="var(--border-subtle)" stroke-width="8" />
            <circle
              cx="60" cy="60" r="52"
              fill="none"
              stroke="var(--accent)"
              stroke-width="8"
              stroke-linecap="round"
              stroke-dasharray="{2 * Math.PI * 52}"
              stroke-dashoffset="{2 * Math.PI * 52 * (1 - (kpiWeekPercent / 100))}"
              transform="rotate(-90 60 60)"
              class="ya-radial__arc"
            />
            <text x="60" y="56" text-anchor="middle" class="ya-radial__text">{kpiWeekPercent}%</text>
            <text x="60" y="72" text-anchor="middle" class="ya-radial__sub">complete</text>
          </svg>
        </div>
        <span class="ya-card__label ya-card__label--center">Ma Progression</span>
        <p class="ya-card__desc ya-card__desc--sm">Suivi hebdomadaire des taches assignees.</p>
        <button class="ya-card__details-btn" on:click={() => currentPage.set('/tasks')}>Plus de details</button>
      </div>
    </div>
  </div>

  <!-- ═══ ROW 2: Projects Overview (col-8) + Events (col-4) ═══ -->
  <div class="row">
    <div class="col-8">
      <div class="w-card">
        <div class="w-card__header">
          <h4 class="w-card__title">Vue d'ensemble</h4>
          <div class="w-card__actions">
            <span class="w-card__period">7 derniers jours</span>
          </div>
        </div>
        <div class="w-card__body">
          <SparklineChart bind:this={sparklineChart} />
        </div>
        <div class="w-card__stats">
          <div class="w-stat">
            <span class="w-stat__val">{kpiTasks}</span>
            <span class="w-stat__label">Total taches</span>
          </div>
          <div class="w-stat">
            <span class="w-stat__val w-stat__val--primary">{kpiWeek}</span>
            <span class="w-stat__label">Cette semaine</span>
          </div>
          <div class="w-stat">
            <span class="w-stat__val">{kpiDocs}</span>
            <span class="w-stat__label">Documents</span>
          </div>
          <div class="w-stat">
            <span class="w-stat__val w-stat__val--success">{kpiParc}</span>
            <span class="w-stat__label">Equipements</span>
          </div>
        </div>
      </div>
    </div>
    <div class="col-4">
      <div class="w-card">
        <div class="w-card__header">
          <h4 class="w-card__title">Evenements</h4>
        </div>
        <div class="w-card__body w-card__body--flush">
          <EventsCard bind:this={eventsCard} />
        </div>
      </div>
    </div>
  </div>

  <!-- ═══ ROW 3: Active Projects (col-8) + Donut (col-4) ═══ -->
  <div class="row">
    <div class="col-8">
      <div class="w-card">
        <div class="w-card__header">
          <h4 class="w-card__title">Taches actives</h4>
          <div class="w-card__actions">
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <span class="w-link" on:click={() => currentPage.set('/tasks')}>Voir tout</span>
          </div>
        </div>
        <div class="w-card__body w-card__body--flush">
          <ActiveProjectsCard bind:this={activeProjectsCard} />
        </div>
      </div>
    </div>
    <div class="col-4">
      <div class="w-card">
        <div class="w-card__header">
          <h4 class="w-card__title">Repartition</h4>
        </div>
        <div class="w-card__body w-card__body--flush">
          <DonutChart bind:this={donutChart} />
        </div>
      </div>
    </div>
  </div>

  <!-- ═══ ROW 4: Systeme (col-4) + Zabbix (col-4) + Completion (col-4) ═══ -->
  <div class="row">
    <div class="col-4">
      <div class="w-card">
        <div class="w-card__header">
          <h4 class="w-card__title">Systeme</h4>
        </div>
        <div class="w-card__body w-card__body--flush">
          <SysMonCard bind:this={sysMonCard} />
        </div>
      </div>
    </div>
    <div class="col-4">
      <div class="w-card">
        <div class="w-card__header">
          <h4 class="w-card__title">Monitoring</h4>
        </div>
        <div class="w-card__body w-card__body--flush">
          <ZabbixCard bind:this={zabbixCard} />
        </div>
      </div>
    </div>
    <div class="col-4">
      <div class="w-card">
        <div class="w-card__header">
          <h4 class="w-card__title">Completion du mois</h4>
        </div>
        <div class="w-card__body" style="display:flex;justify-content:center;">
          <GaugeChart bind:this={gaugeChart} />
        </div>
      </div>
    </div>
  </div>

  <!-- ═══ ROW 5: Activite recente (col-12) ═══ -->
  <div class="row">
    <div class="col-12">
      <div class="w-card">
        <div class="w-card__header">
          <h4 class="w-card__title">Activite recente</h4>
        </div>
        <div class="w-card__body w-card__body--flush">
          <ActivityCard bind:this={activityCard} />
        </div>
      </div>
    </div>
  </div>

</div>

<style>
  .home-page {
    animation: fadeIn 0.35s ease-out;
  }

  /* ═══ Header ═══ */
  .home-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 1.75rem;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .header-left {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .greeting {
    font-size: 1.625rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
    letter-spacing: -0.3px;
  }

  .username {
    color: var(--accent);
  }

  .date-weather-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }
  .date-str {
    font-size: 0.875rem;
    color: var(--text-secondary);
    margin: 0;
  }
  .weather-inline {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 0.625rem;
    padding: 0.25rem 0.75rem;
  }
  .wi-emoji { font-size: 1.125rem; line-height: 1; }
  .wi-temp { font-size: 0.875rem; font-weight: 700; color: var(--text-primary); }
  .wi-desc { font-size: 0.75rem; color: var(--text-secondary); }
  .wi-city { font-size: 0.6875rem; color: var(--text-muted); }

  .header-right {
    display: flex;
    align-items: center;
    gap: 0.625rem;
  }

  .clock-frame {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 0.625rem;
    padding: 0.375rem 0.875rem;
  }

  .clock {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.5px;
  }

  .btn-ghost {
    background: transparent;
    border: 1px solid var(--border-subtle);
    border-radius: 0.625rem;
    color: var(--text-secondary);
    font-size: 0.8125rem;
    padding: 0.4375rem 0.875rem;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
  }

  .btn-ghost:hover {
    background: var(--bg-hover);
    border-color: var(--border-hover);
    color: var(--text-primary);
  }

  .btn-primary-action {
    background: var(--accent);
    border: none;
    border-radius: 0.625rem;
    color: #fff;
    font-size: 0.8125rem;
    font-weight: 600;
    padding: 0.5rem 1rem;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
    box-shadow: 0 2px 12px rgba(var(--accent-rgb), 0.3);
  }

  .btn-primary-action:hover {
    filter: brightness(1.15);
    box-shadow: 0 4px 20px rgba(var(--accent-rgb), 0.4);
  }

  /* ═══ 12-column Grid System ═══ */
  .row {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 1.563rem;
    margin-bottom: 1.563rem;
  }

  .row--sub {
    margin-top: -0.25rem;
  }

  .col-3 { grid-column: span 3; }
  .col-4 { grid-column: span 4; }
  .col-6 { grid-column: span 6; }
  .col-8 { grid-column: span 8; }
  .col-12 { grid-column: span 12; }

  @media (max-width: 1200px) {
    .col-3 { grid-column: span 6; }
    .col-4 { grid-column: span 6; }
    .col-8 { grid-column: span 12; }
    .col-12 { grid-column: span 12; }
  }

  @media (max-width: 768px) {
    .col-3 { grid-column: span 12; }
    .col-4 { grid-column: span 12; }
    .col-6 { grid-column: span 12; }
    .col-8 { grid-column: span 12; }
    .col-12 { grid-column: span 12; }
  }

  /* ═══ YashAdmin Card Base ═══ */
  .ya-card {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem;
    padding: 1.25rem;
    position: relative;
    overflow: hidden;
    transition: transform 0.2s, box-shadow 0.3s;
    cursor: default;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .ya-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.12);
  }

  .ya-card__deco-circle {
    position: absolute;
    border-radius: 50%;
    background: rgba(255,255,255,0.1);
    pointer-events: none;
    z-index: 0;
  }
  .ya-card__deco-circle--1 {
    width: 8rem;
    height: 8rem;
    top: -2.5rem;
    right: -2.5rem;
  }
  .ya-card__deco-circle--2 {
    width: 5rem;
    height: 5rem;
    bottom: -1.5rem;
    right: 2rem;
    background: rgba(255,255,255,0.06);
  }

  /* ═══ Purple Card ═══ */
  .ya-card--purple {
    background: linear-gradient(135deg, #452B90 0%, #7B5EC6 100%);
    border: none;
    color: #fff;
    cursor: pointer;
    box-shadow: 0 6px 20px rgba(69,43,144,0.3);
  }
  .ya-card--purple:hover {
    box-shadow: 0 10px 35px rgba(69,43,144,0.45);
  }

  /* ═══ Gold Card ═══ */
  .ya-card--gold {
    background: linear-gradient(135deg, #F8B940 0%, #FFD166 100%);
    border: none;
    color: #fff;
    cursor: pointer;
    box-shadow: 0 6px 20px rgba(248,185,64,0.3);
  }
  .ya-card--gold:hover {
    box-shadow: 0 10px 35px rgba(248,185,64,0.45);
  }

  /* ═══ Teal Gradient Card ═══ */
  .ya-card--teal {
    background: linear-gradient(135deg, #0d9488 0%, #2dd4bf 100%);
    border: none;
    color: #fff;
    box-shadow: 0 6px 20px rgba(13,148,136,0.3);
    position: relative;
  }
  .ya-card--teal:hover {
    box-shadow: 0 10px 35px rgba(13,148,136,0.45);
  }

  .ya-card__teal-deco {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    width: 5rem;
    height: 5rem;
    opacity: 0.7;
    pointer-events: none;
    z-index: 0;
  }

  /* ═══ Progress Card ═══ */
  .ya-card--progress {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
  }

  /* ═══ Flat sub-cards ═══ */
  .ya-card--flat {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    cursor: pointer;
  }

  /* ═══ Card Body & Elements ═══ */
  .ya-card__body {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    flex: 1;
  }

  .ya-card__body--teal {
    gap: 0.375rem;
  }

  .ya-card__body--center {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 0.375rem;
    flex: 1;
  }

  .ya-card__label {
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    opacity: 0.85;
  }

  .ya-card__label--lg {
    font-size: 0.9375rem;
    font-weight: 700;
    text-transform: none;
    letter-spacing: 0;
    opacity: 1;
    line-height: 1.3;
  }

  .ya-card__label--center {
    font-size: 0.8125rem;
    font-weight: 600;
    text-transform: none;
    letter-spacing: 0;
    opacity: 1;
    color: var(--text-primary);
    margin-top: 0.25rem;
  }

  .ya-card__value {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.1;
    letter-spacing: -0.02em;
  }

  .ya-card__value--md {
    font-size: 1.5rem;
    color: var(--text-heading);
  }

  .ya-card__desc {
    font-size: 0.75rem;
    opacity: 0.8;
    line-height: 1.4;
    margin: 0;
  }

  .ya-card__desc--sm {
    font-size: 0.6875rem;
    color: var(--text-secondary);
    opacity: 1;
    margin: 0;
  }

  .ya-card__clients {
    font-size: 0.75rem;
    font-weight: 600;
    opacity: 0.9;
    margin-top: 0.25rem;
  }

  /* ═══ SVG Bar Charts ═══ */
  .ya-card__bars {
    margin-top: 0.5rem;
    flex: 1;
    min-height: 2.5rem;
  }

  .ya-bars-svg {
    width: 100%;
    height: 2.5rem;
    display: block;
  }

  /* ═══ Card Footer ═══ */
  .ya-card__footer {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 0.75rem;
  }

  .ya-card__hint {
    font-size: 0.6875rem;
    font-weight: 500;
    opacity: 0.85;
  }

  /* ═══ Avatars ═══ */
  .ya-card__avatars {
    display: flex;
    align-items: center;
  }

  .ya-card__avatars--row {
    margin-top: 0.375rem;
  }

  .ya-avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.75rem;
    height: 1.75rem;
    border-radius: 50%;
    font-size: 0.625rem;
    font-weight: 700;
    color: #fff;
    border: 2px solid rgba(255,255,255,0.3);
    margin-right: -0.375rem;
  }

  .ya-card__badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.25rem;
    height: 2.25rem;
    border-radius: 50%;
    background: rgba(255,255,255,0.2);
    font-size: 0.625rem;
    font-weight: 700;
    color: #fff;
    border: 2px solid rgba(255,255,255,0.3);
  }

  .ya-card__plus {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    background: rgba(255,255,255,0.25);
    border: 2px solid rgba(255,255,255,0.35);
    color: #fff;
    font-size: 1.25rem;
    font-weight: 300;
    cursor: pointer;
    transition: all 0.15s;
    line-height: 1;
    font-family: inherit;
  }
  .ya-card__plus:hover {
    background: rgba(255,255,255,0.35);
    transform: scale(1.1);
  }

  /* ═══ Radial Progress ═══ */
  .ya-radial {
    width: 7.5rem;
    height: 7.5rem;
    margin-bottom: 0.25rem;
  }

  .ya-radial__svg {
    width: 100%;
    height: 100%;
  }

  .ya-radial__arc {
    transition: stroke-dashoffset 0.8s ease-out;
  }

  .ya-radial__text {
    font-size: 1.5rem;
    font-weight: 700;
    fill: var(--text-heading);
  }

  .ya-radial__sub {
    font-size: 0.625rem;
    fill: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .ya-card__details-btn {
    margin-top: 0.5rem;
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 0.375rem;
    padding: 0.375rem 1rem;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
  }
  .ya-card__details-btn:hover {
    filter: brightness(1.15);
    box-shadow: 0 4px 16px rgba(var(--accent-rgb), 0.3);
  }

  /* ═══ Progress Bar ═══ */
  .ya-progress {
    margin-top: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .ya-progress__bar {
    width: 100%;
    height: 0.5rem;
    background: rgba(var(--accent-rgb), 0.15);
    border-radius: 1rem;
    overflow: hidden;
  }

  .ya-progress__fill {
    height: 100%;
    background: var(--accent);
    border-radius: 1rem;
    transition: width 0.6s ease-out;
    min-width: 0.25rem;
  }

  .ya-progress__text {
    font-size: 0.6875rem;
    color: var(--text-secondary);
  }

  /* ═══ Inline Sparkline ═══ */
  .ya-sparkline-inline {
    margin-top: 0.5rem;
    height: 2.25rem;
  }

  .ya-sparkline-svg {
    width: 100%;
    height: 100%;
    display: block;
  }

  /* ═══ Widget Cards — YashAdmin style ═══ */
  .w-card {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem;
    box-shadow: var(--shadow-card);
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .w-card__header {
    padding: 1.25rem 1.25rem 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .w-card__title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-heading);
    margin: 0;
  }

  .w-card__actions {
    display: flex;
    gap: 0.75rem;
    align-items: center;
  }

  .w-card__period {
    font-size: 0.75rem;
    color: var(--text-muted);
    background: var(--bg-badge);
    padding: 0.25rem 0.75rem;
    border-radius: 1rem;
  }

  .w-link {
    font-size: 0.8125rem;
    color: var(--primary);
    cursor: pointer;
    font-weight: 500;
    transition: opacity 0.15s;
  }
  .w-link:hover { opacity: 0.8; }

  .w-card__body {
    padding: 1.25rem;
    flex: 1;
    min-height: 0;
  }

  .w-card__body--flush {
    padding: 0;
  }

  .w-card__body--flush > :global(*) {
    border: none;
    box-shadow: none;
    border-radius: 0;
    background: transparent;
  }

  /* Stats row below chart */
  .w-card__stats {
    display: flex;
    border-top: 1px solid var(--border-subtle);
  }

  .w-stat {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0.875rem 0.5rem;
    border-right: 1px solid var(--border-subtle);
  }
  .w-stat:last-child { border-right: none; }

  .w-stat__val {
    font-size: 1.0625rem;
    font-weight: 700;
    color: var(--text-heading);
  }
  .w-stat__val--primary { color: var(--primary); }
  .w-stat__val--success { color: var(--success); }

  .w-stat__label {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 0.125rem;
  }
</style>
