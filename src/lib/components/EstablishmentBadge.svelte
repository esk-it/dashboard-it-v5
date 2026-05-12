<script>
  // Reusable badge for displaying an establishment (NDK / SU / NDE). Renders
  // the uploaded logo when present, otherwise falls back to a colored chip
  // with the establishment's code. Used in Tasks (site tag), Planning
  // (event row), Projects (detail header + Running Projects card), and the
  // per-site cards on the Home page.
  //
  // Props:
  //   code        : establishment code (NDK / SU / NDE). If unknown, renders
  //                 a discreet grey "?" badge so unknown values don't break
  //                 the layout (useful for migrated rows still empty).
  //   size        : 'xs' | 'sm' | 'md' | 'lg' — controls overall dimensions.
  //   showLabel   : when true, the code text appears next to the logo.
  //                 Default true at sm+, false at xs.
  //   titleOverride: custom tooltip (defaults to establishment.name).

  import { establishmentsByCode, logoUrl } from '../stores/establishments.js';

  export let code = '';
  export let size = 'sm';
  export let showLabel = null;
  export let titleOverride = null;

  $: establishment = code ? $establishmentsByCode[code] : null;
  $: url = logoUrl(establishment);
  $: effectiveShowLabel = showLabel === null ? (size !== 'xs') : showLabel;

  $: dim = ({ xs: 16, sm: 20, md: 28, lg: 40 })[size] || 20;
  $: textSize = ({ xs: 9, sm: 11, md: 13, lg: 15 })[size] || 11;
</script>

{#if establishment}
  <span
    class="eb eb--{size}"
    title={titleOverride || establishment.name}
    style:--eb-color={establishment.color}
  >
    {#if url}
      <img class="eb-logo" src={url} alt={establishment.code} width={dim} height={dim} />
    {:else}
      <span class="eb-fallback" style:width="{dim}px" style:height="{dim}px" style:font-size="{textSize}px">
        {establishment.code.slice(0, 3)}
      </span>
    {/if}
    {#if effectiveShowLabel}
      <span class="eb-code" style:font-size="{textSize}px">{establishment.code}</span>
    {/if}
  </span>
{:else if code}
  <!-- Code present but not matched in the store — show a discreet placeholder
       so the user notices it's not configured properly (without crashing). -->
  <span class="eb eb--{size} eb--unknown" title="Établissement inconnu : {code}">
    <span class="eb-fallback eb-fallback--unknown" style:width="{dim}px" style:height="{dim}px" style:font-size="{textSize}px">?</span>
    {#if effectiveShowLabel}
      <span class="eb-code eb-code--unknown" style:font-size="{textSize}px">{code}</span>
    {/if}
  </span>
{/if}

<style>
  .eb {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    vertical-align: middle;
    line-height: 1;
    white-space: nowrap;
  }
  .eb-logo {
    object-fit: contain;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.04);
    flex-shrink: 0;
  }
  .eb-fallback {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    font-weight: 700;
    color: #fff;
    background: var(--eb-color, var(--primary));
    flex-shrink: 0;
    letter-spacing: 0.02em;
  }
  .eb-fallback--unknown {
    background: rgba(148, 163, 184, 0.35);
    color: #475569;
  }
  .eb-code {
    font-weight: 600;
    color: var(--eb-color, var(--text-heading));
    letter-spacing: 0.04em;
  }
  .eb-code--unknown {
    color: var(--text-muted);
    font-weight: 500;
    font-style: italic;
  }

  /* Slight tweak for the xs variant — sits on a row with text, no extra gap */
  .eb--xs { gap: 0.25rem; }
  .eb--xs .eb-logo { border-radius: 3px; }
</style>
