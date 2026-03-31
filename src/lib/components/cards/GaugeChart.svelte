<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../../api/client.js';
  import GlassCard from '../GlassCard.svelte';
  import ApexCharts from 'apexcharts';

  let percent = 0;
  let loading = true;
  let chartEl;
  let chart;

  export function refresh() {
    fetchData();
  }

  onMount(() => {
    fetchData();
  });

  onDestroy(() => {
    if (chart) chart.destroy();
  });

  async function fetchData() {
    loading = true;
    try {
      const data = await api.get('/api/dashboard/stats/completion');
      percent = data.percent || data.completion || 0;
    } catch (e) {
      percent = 0;
    }
    loading = false;
    renderChart();
  }

  function renderChart() {
    if (!chartEl) return;

    if (chart) {
      chart.updateSeries([Math.round(percent)]);
      return;
    }

    const options = {
      series: [Math.round(percent)],
      chart: {
        type: 'radialBar',
        height: 220,
        animations: {
          enabled: true,
          easing: 'easeinout',
          speed: 800
        }
      },
      colors: ['#452B90'],
      plotOptions: {
        radialBar: {
          hollow: {
            size: '60%',
            background: 'transparent'
          },
          track: {
            background: 'rgba(var(--primary-rgb), 0.1)',
            strokeWidth: '100%'
          },
          dataLabels: {
            show: true,
            name: {
              show: true,
              fontSize: '13px',
              color: 'var(--text-secondary)',
              offsetY: -8
            },
            value: {
              show: true,
              fontSize: '28px',
              fontWeight: 700,
              color: 'var(--text-primary)',
              offsetY: 4,
              formatter: (val) => val + '%'
            }
          }
        }
      },
      labels: ['Completion'],
      stroke: {
        lineCap: 'round'
      }
    };

    chart = new ApexCharts(chartEl, options);
    chart.render();
  }

  $: if (!loading && chartEl && !chart) {
    renderChart();
  }
</script>

<GlassCard padding="0">
  <div class="card-inner">
    <div class="card-header">
      <h3>Compl&eacute;tion du mois</h3>
    </div>

    <div class="gauge-container">
      {#if !loading}
        <div bind:this={chartEl}></div>
      {:else}
        <div class="loading">Chargement...</div>
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
    padding: 16px 20px 0;
  }

  .card-header h3 {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  .gauge-container {
    padding: 8px 20px 16px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .gauge-container > div {
    width: 100%;
    max-width: 280px;
  }

  .loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: var(--text-muted);
    font-size: 13px;
  }
</style>
