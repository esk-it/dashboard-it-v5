<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../../api/client.js';
  import GlassCard from '../GlassCard.svelte';
  import ApexCharts from 'apexcharts';

  let categories = [];
  let loading = true;
  let chartEl;
  let chart;

  const colors = ['#452B90', '#F8B940', '#3A9B94', '#FF5E5E', '#58bad7', '#BB6BD9'];

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
      const data = await api.get('/api/dashboard/stats/categories');
      categories = data.categories || data || [];
    } catch (e) {
      categories = [];
    }
    loading = false;
    renderChart();
  }

  function renderChart() {
    if (!chartEl || categories.length === 0) return;

    const labels = categories.map(c => c.name || c.label || '');
    const series = categories.map(c => c.count || c.value || 0);
    const total = series.reduce((a, b) => a + b, 0);

    if (chart) {
      chart.updateOptions({
        labels,
        series
      });
      return;
    }

    const options = {
      series,
      labels,
      chart: {
        type: 'donut',
        height: 280,
        animations: {
          enabled: true,
          easing: 'easeinout',
          speed: 600
        }
      },
      colors: colors.slice(0, categories.length),
      stroke: {
        width: 0
      },
      dataLabels: {
        enabled: false
      },
      legend: {
        position: 'bottom',
        fontSize: '12px',
        labels: {
          colors: 'var(--text-secondary)'
        },
        markers: {
          width: 10,
          height: 10,
          radius: 3
        },
        itemMargin: {
          horizontal: 8,
          vertical: 4
        }
      },
      plotOptions: {
        pie: {
          donut: {
            size: '65%',
            labels: {
              show: true,
              name: {
                show: true,
                fontSize: '13px',
                color: 'var(--text-secondary)',
                offsetY: -4
              },
              value: {
                show: true,
                fontSize: '22px',
                fontWeight: 700,
                color: 'var(--text-primary)',
                offsetY: 4,
                formatter: (val) => val
              },
              total: {
                show: true,
                showAlways: true,
                label: 'Total',
                fontSize: '13px',
                color: 'var(--text-secondary)',
                formatter: () => total
              }
            }
          }
        }
      },
      tooltip: {
        enabled: true,
        theme: 'dark',
        y: {
          formatter: (val) => val + ' items'
        }
      },
      responsive: [{
        breakpoint: 480,
        options: {
          chart: { height: 240 },
          legend: { position: 'bottom' }
        }
      }]
    };

    chart = new ApexCharts(chartEl, options);
    chart.render();
  }

  $: if (!loading && chartEl && !chart && categories.length > 0) {
    renderChart();
  }
</script>

<GlassCard padding="0">
  <div class="card-inner">
    <div class="card-header">
      <h3>R&eacute;partition par cat&eacute;gorie</h3>
    </div>

    <div class="chart-wrap">
      {#if !loading && categories.length > 0}
        <div bind:this={chartEl}></div>
      {:else if loading}
        <div class="empty">Chargement...</div>
      {:else}
        <div class="empty">Aucune donn&eacute;e</div>
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

  .chart-wrap {
    padding: 12px 16px 16px;
  }

  .empty {
    padding: 40px;
    text-align: center;
    color: var(--text-muted);
    font-size: 13px;
  }
</style>
