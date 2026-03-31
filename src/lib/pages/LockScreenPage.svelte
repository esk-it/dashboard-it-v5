<script>
  import { currentUser, login, logout } from '../stores/auth.js';
  import { Lock, LogOut, Eye, EyeOff } from 'lucide-svelte';

  let password = '';
  let showPassword = false;
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

<div class="lock-page">
  <div class="lock-bg-shapes">
    <div class="shape s1"></div>
    <div class="shape s2"></div>
    <div class="shape s3"></div>
    <div class="shape s4"></div>
  </div>

  <div class="lock-card">
    <div class="avatar-ring">
      <div class="avatar">{initials}</div>
    </div>

    <h2 class="user-name">{displayName}</h2>
    <p class="lock-subtitle">Session verrouill&eacute;e</p>

    {#if error}
      <div class="lock-error">{error}</div>
    {/if}

    <form on:submit|preventDefault={handleUnlock}>
      <div class="form-group">
        <div class="input-wrap">
          <span class="input-icon"><Lock size={18} /></span>
          <input
            type={showPassword ? 'text' : 'password'}
            bind:value={password}
            placeholder="Mot de passe"
            required
            autocomplete="current-password"
          />
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <span class="toggle-pwd" on:click={() => showPassword = !showPassword}>
            {#if showPassword}<EyeOff size={16} />{:else}<Eye size={16} />{/if}
          </span>
        </div>
      </div>

      <button type="submit" class="lock-btn" disabled={loading}>
        {#if loading}
          <span class="spinner"></span>
        {:else}
          <Lock size={18} />
        {/if}
        Deverrouiller
      </button>
    </form>

    <div class="lock-footer">
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <p class="lock-link" on:click={logout}>
        <LogOut size={14} />
        Changer d'utilisateur
      </p>
    </div>
  </div>
</div>

<style>
  .lock-page {
    min-height: 100vh;
    width: 100%;
    background: linear-gradient(135deg, #1a1035 0%, #2d1b69 40%, #452B90 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    position: relative;
    overflow: hidden;
    font-family: 'Poppins', sans-serif;
  }

  /* Background shapes */
  .lock-bg-shapes {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 0;
  }

  .shape {
    position: absolute;
    border-radius: 50%;
  }

  .s1 {
    width: 400px; height: 400px;
    top: -120px; right: -100px;
    background: radial-gradient(circle, rgba(105, 65, 198, 0.3) 0%, transparent 70%);
  }

  .s2 {
    width: 300px; height: 300px;
    bottom: -80px; left: -60px;
    background: radial-gradient(circle, rgba(124, 58, 237, 0.25) 0%, transparent 70%);
  }

  .s3 {
    width: 150px; height: 150px;
    top: 30%; left: 20%;
    border: 2px solid rgba(255, 255, 255, 0.05);
  }

  .s4 {
    width: 80px; height: 80px;
    bottom: 25%; right: 25%;
    background: rgba(248, 185, 64, 0.08);
  }

  /* Card */
  .lock-card {
    background: var(--bg-card, #ffffff);
    border-radius: 16px;
    box-shadow: 0 25px 80px rgba(0, 0, 0, 0.35);
    padding: 2.5rem 2.5rem 2rem;
    text-align: center;
    width: 100%;
    max-width: 380px;
    position: relative;
    z-index: 1;
  }

  :global([data-theme="dark"]) .lock-card {
    background: #1e1e2d;
    border: 1px solid rgba(255, 255, 255, 0.06);
  }

  /* Avatar */
  .avatar-ring {
    width: 100px;
    height: 100px;
    border-radius: 50%;
    background: linear-gradient(135deg, #452B90, #6941C6);
    padding: 4px;
    margin: 0 auto 1rem;
    box-shadow: 0 8px 30px rgba(105, 65, 198, 0.35);
  }

  .avatar {
    width: 100%;
    height: 100%;
    border-radius: 50%;
    background: linear-gradient(135deg, #5b3cc4, #7c4dff);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    font-weight: 700;
    border: 3px solid var(--bg-card, #fff);
  }

  :global([data-theme="dark"]) .avatar {
    border-color: #1e1e2d;
  }

  .user-name {
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--text-heading, #1e1e2d);
    margin: 0 0 0.25rem;
  }

  .lock-subtitle {
    color: var(--text-muted, #a2a5b9);
    font-size: 0.85rem;
    margin: 0 0 1.5rem;
  }

  .lock-error {
    background: #fff5f5;
    color: #e53e3e;
    padding: 0.65rem 0.85rem;
    border-radius: 8px;
    margin-bottom: 1rem;
    font-size: 0.85rem;
    border: 1px solid rgba(229, 62, 62, 0.2);
  }

  :global([data-theme="dark"]) .lock-error {
    background: rgba(229, 62, 62, 0.1);
  }

  .form-group {
    margin-bottom: 1.25rem;
  }

  .input-wrap {
    position: relative;
    display: flex;
    align-items: center;
  }

  .input-icon {
    position: absolute;
    left: 14px;
    color: var(--text-muted, #a2a5b9);
    display: flex;
    pointer-events: none;
    z-index: 1;
  }

  .input-wrap input {
    width: 100%;
    padding: 0.75rem 2.75rem 0.75rem 2.75rem;
    font-size: 0.95rem;
    text-align: center;
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 8px;
    background: var(--bg-card, #fff);
    color: var(--text-heading, #1e1e2d);
    font-family: inherit;
    transition: border-color 0.2s, box-shadow 0.2s;
  }

  .input-wrap input:focus {
    outline: none;
    border-color: #6941C6;
    box-shadow: 0 0 0 3px rgba(105, 65, 198, 0.12);
  }

  .toggle-pwd {
    position: absolute;
    right: 14px;
    cursor: pointer;
    color: var(--text-muted, #a2a5b9);
    display: flex;
  }

  .toggle-pwd:hover { color: #6941C6; }

  .lock-btn {
    width: 100%;
    padding: 0.8rem;
    background: linear-gradient(135deg, #452B90, #6941C6);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 0.95rem;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    transition: all 0.2s ease;
    box-shadow: 0 4px 14px rgba(105, 65, 198, 0.3);
  }

  .lock-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(105, 65, 198, 0.45);
  }

  .lock-btn:disabled { opacity: 0.6; cursor: not-allowed; }

  .spinner {
    width: 18px; height: 18px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .lock-footer {
    margin-top: 1.5rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-subtle, #e4e6ef);
  }

  .lock-link {
    color: var(--text-muted, #a2a5b9);
    font-size: 0.85rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    transition: color 0.2s;
    margin: 0;
  }

  .lock-link:hover { color: #e53e3e; }
</style>
