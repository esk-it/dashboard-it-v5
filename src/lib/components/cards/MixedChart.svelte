<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../../api/client.js';
  import GlassCard from '../GlassCard.svelte';
  import ApexCharts from 'apexcharts';

  let chartEl;
  let chart;
  let loading = true;

  let tasksSeries = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
  let docsSeries = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
  let activitySeries = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];

  const months = ['Jan', 'F\u00e9v', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Ao\u00fbt', 'Sep', 'Oct', 'Nov', 'D\u00e9c'];

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
      const data = await api.get('/api/dashboard/stats/weekly');
      if (data && data.tasks) tasksSeries = data.tasks;
      if (data && data.documents) docsSeries = data.documents;
      if (data && data.activity) activitySeries = data.activity;
    } catch (e) {
      // Use zeros as fallback
    }
    loading = false;
    renderChart();
  }

  function renderChart() {
    if (!chartEl) return;

    const seriesData = [
      {
        name: 'T\u00e2ches',
        type: 'column',
        data: tasksSeries
      },
      {
        name: 'Documents',
        type: 'column',
        data: docsSeries
      },
      {
        name: 'Activit\u00e9',
        type: 'line',
        data: activitySeries
      }
    ];

    if (chart) {
      chart.updateSeries(seriesData);
      return;
    }

    const options = {
      series: seriesData,
      chart: {
        type: 'line',
        height: 350,
        stacked: false,
        toolbar: {
          show: true,
          tools: {
            download: false,
            selection: true,
            zoom: true,
            zoomin: true,
            zoomout: true,
            pan: true,
            reset: true
          }
        },
        animations: {
          enabled: true,
          easing: 'easeinout',
          speed: 600
        }
      },
      colors: ['#452B90', '#F8B940', '#3A9B94'],
      stroke: {
        width: [0, 0, 3],
        curve: 'smooth'
      },
      plotOptions: {
        bar: {
          columnWidth: '50%',
          borderRadius: 4
        }
      },
      fill: {
        opacity: [1, 1, 1]
      },
      markers: {
        size: [0, 0, 4],
        strokeWidth: 0
      },
      xaxis: {
        categories: months,
        labels: {
          style: {
            colors: 'var(--text-muted)',
            fontSize: '12px'
          }
        },
        axisBorder: { show: false },
        axisTicks: { show: false }
      },
      yaxis: {
        labels: {
          style: {
            colors: 'var(--text-muted)',
            fontSize: '12px'
          }
        }
      },
      grid: {
        borderColor: 'rgba(var(--primary-rgb), 0.08)',
        strokeDashArray: 4,
        xaxis: { lines: { show: false } },
        yaxis: { lines: { show: true } }
      },
      legend: {
        position: 'top',
        horizontalAlign: 'left',
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
          horizontal: 12
        }
      },
      tooltip: {
        theme: 'dark',
        shared: true,
        intersect: false
      },
      responsive: [{
        breakpoint: 768,
        options: {
          chart: { height: 280 },
          legend: { position: 'bottom' }
        }
      }]
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
      <h3>Vue d'ensemble des projets</h3>
    </div>

    <div class="chart-container">
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

  .chart-container {
    padding: 12px 16px 16px;
  }

  .loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 350px;
    color: var(--text-muted);
    font-size: 13px;
  }
</style>
