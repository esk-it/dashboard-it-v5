<script>
  import { currentUser, login, logout } from '../stores/auth.js';
  import { Lock, LogOut } from 'lucide-svelte';

  let password = '';
  let error = '';
  let loading = false;

  $: initials = $currentUser
    ? ($currentUser.display_name || $currentUser.username).split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
    : '?';

  $: displayName = $currentUser?.display_name || $currentUser?.username || 'Utilisateur';

  async function handleUnlock() {
    error = '';
    loading = true;
    try {
      await login($currentUser.username, password);
    } catch (e) {
      error = 'Mot de passe incorrect';
    } finally {
      loading = false;
    }
  }
</script>

<div class="lock-container">
  <div class="lock-card">
    <div class="avatar">{initials}</div>
    <h2>{displayName}</h2>
    <p class="lock-subtitle">Session verrouillée</p>

    {#if error}
      <div class="lock-error">{error}</div>
    {/if}

    <form on:submit|preventDefault={handleUnlock}>
      <div class="form-group">
        <input
          type="password"
          bind:value={password}
          placeholder="Mot de passe"
          required
          autocomplete="current-password"
        />
      </div>

      <button type="submit" class="lock-btn" disabled={loading}>
        {#if loading}
          <span class="spinner"></span>
        {:else}
          <Lock size={18} />
        {/if}
        Déverrouiller
      </button>
    </form>

    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <p class="lock-link" on:click={logout}>
      <LogOut size={14} />
      Se déconnecter
    </p>
  </div>
</div>

<style>
  .lock-container {
    min-height: 100vh;
    width: 100%;
    background: linear-gradient(135deg, #452B90 0%, #7C3AED 50%, #452B90 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
  }

  .lock-card {
    background: var(--bg-card);
    border-radius: var(--radius-lg);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    padding: 3rem 2.5rem;
    text-align: center;
    width: 100%;
    max-width: 360px;
  }

  .avatar {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    background: linear-gradient(135deg, #452B90, #7C3AED);
    color: #FFFFFF;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.75rem;
    font-weight: 700;
    margin: 0 auto 1rem;
    box-shadow: 0 4px 20px rgba(69, 43, 144, 0.4);
  }

  h2 {
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--text-heading);
    margin-bottom: 0.25rem;
  }

  .lock-subtitle {
    color: var(--text-muted);
    font-size: 0.85rem;
    margin-bottom: 1.5rem;
  }

  .lock-error {
    background: var(--danger-light);
    color: var(--danger);
    padding: 0.6rem 0.8rem;
    border-radius: var(--radius-sm);
    margin-bottom: 1rem;
    font-size: 0.85rem;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-group input {
    width: 100%;
    padding: 0.75rem 1rem;
    font-size: 0.95rem;
    text-align: center;
    border-radius: var(--radius-sm);
  }

  .lock-btn {
    width: 100%;
    padding: 0.75rem;
    background: var(--primary);
    color: #FFFFFF;
    border: none;
    border-radius: var(--radius-sm);
    font-size: 0.95rem;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    transition: all 0.2s ease;
  }

  .lock-btn:hover:not(:disabled) {
    background: var(--primary-hover);
    box-shadow: 0 4px 16px rgba(var(--primary-rgb), 0.4);
  }

  .lock-btn:disabled { opacity: 0.6; cursor: not-allowed; }

  .spinner {
    width: 18px; height: 18px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #FFF;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .lock-link {
    margin-top: 1.5rem;
    color: var(--text-muted);
    font-size: 0.85rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    transition: color 0.2s;
  }

  .lock-link:hover { color: var(--danger); }
</style>
