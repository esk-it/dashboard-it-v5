<script>
  import { currentPage } from '../stores/navigation.js';
  import { register } from '../stores/auth.js';
  import { UserPlus, Eye, EyeOff, Mail, Lock, User, AtSign } from 'lucide-svelte';

  let username = '';
  let email = '';
  let password = '';
  let confirmPassword = '';
  let displayName = '';
  let showPassword = false;
  let error = '';
  let loading = false;

  async function handleSubmit() {
    error = '';
    if (password !== confirmPassword) {
      error = 'Les mots de passe ne correspondent pas';
      return;
    }
    if (password.length < 4) {
      error = 'Le mot de passe doit contenir au moins 4 caracteres';
      return;
    }
    loading = true;
    try {
      await register(username, email, password, displayName);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
</script>

<div class="auth-page">
  <!-- Left panel: decorative (mirrored) -->
  <div class="auth-left">
    <div class="auth-left-content">
      <div class="deco-circles">
        <div class="deco-circle c1"></div>
        <div class="deco-circle c2"></div>
        <div class="deco-circle c3"></div>
        <div class="deco-circle c4"></div>
      </div>
      <div class="brand-block">
        <div class="brand-logo">IT</div>
        <h2>IT Manager</h2>
        <p>Creez votre compte et rejoignez la plateforme de gestion IT la plus complete.</p>
      </div>
      <div class="deco-dots">
        {#each Array(36) as _, i}
          <span class="dot"></span>
        {/each}
      </div>
    </div>
  </div>

  <!-- Right panel: form -->
  <div class="auth-right">
    <div class="auth-form-wrapper">
      <div class="auth-logo">
        <div class="logo-icon">IT</div>
        <span class="logo-label">Manager</span>
      </div>

      <h1 class="auth-title">Creer un compte</h1>
      <p class="auth-subtitle">Inscrivez-vous pour acceder au tableau de bord</p>

      {#if error}
        <div class="auth-error">{error}</div>
      {/if}

      <form on:submit|preventDefault={handleSubmit}>
        <div class="form-row">
          <div class="form-group">
            <label for="displayName">Nom complet</label>
            <div class="input-icon-wrap">
              <span class="input-icon"><User size={18} /></span>
              <input id="displayName" type="text" bind:value={displayName} placeholder="Jean Dupont" />
            </div>
          </div>
          <div class="form-group">
            <label for="username">Identifiant</label>
            <div class="input-icon-wrap">
              <span class="input-icon"><AtSign size={18} /></span>
              <input id="username" type="text" bind:value={username} placeholder="jdupont" required />
            </div>
          </div>
        </div>

        <div class="form-group">
          <label for="email">Email</label>
          <div class="input-icon-wrap">
            <span class="input-icon"><Mail size={18} /></span>
            <input id="email" type="email" bind:value={email} placeholder="jean@example.com" required />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="password">Mot de passe</label>
            <div class="input-icon-wrap">
              <span class="input-icon"><Lock size={18} /></span>
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                bind:value={password}
                placeholder="Mot de passe"
                required
              />
              <!-- svelte-ignore a11y_click_events_have_key_events -->
              <!-- svelte-ignore a11y_no_static_element_interactions -->
              <span class="password-toggle" on:click={() => showPassword = !showPassword}>
                {#if showPassword}<EyeOff size={16} />{:else}<Eye size={16} />{/if}
              </span>
            </div>
          </div>
          <div class="form-group">
            <label for="confirm">Confirmer</label>
            <div class="input-icon-wrap">
              <span class="input-icon"><Lock size={18} /></span>
              <input
                id="confirm"
                type={showPassword ? 'text' : 'password'}
                bind:value={confirmPassword}
                placeholder="Confirmer"
                required
              />
            </div>
          </div>
        </div>

        <button type="submit" class="auth-btn" disabled={loading}>
          {#if loading}
            <span class="spinner"></span>
          {:else}
            <UserPlus size={18} />
          {/if}
          Creer mon compte
        </button>
      </form>

      <p class="auth-link">
        Deja un compte ?
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <span on:click={() => currentPage.set('/login')}>Se connecter</span>
      </p>
    </div>
  </div>
</div>

<style>
  .auth-page {
    display: flex;
    height: 100vh;
    width: 100%;
    overflow: hidden;
    font-family: 'Poppins', sans-serif;
  }

  /* ── Left panel (decorative) ── */
  .auth-left {
    flex: 0 0 45%;
    background: linear-gradient(135deg, #452B90 0%, #6941C6 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
  }

  .auth-left-content {
    position: relative;
    z-index: 2;
    text-align: center;
    color: #fff;
    padding: 3rem;
  }

  .brand-block {
    position: relative;
    z-index: 2;
  }

  .brand-logo {
    width: 72px;
    height: 72px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.15);
    backdrop-filter: blur(10px);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
    font-weight: 700;
    color: #fff;
    margin: 0 auto 1.25rem;
    border: 1px solid rgba(255, 255, 255, 0.2);
  }

  .auth-left h2 {
    font-size: 2rem;
    font-weight: 700;
    margin: 0 0 0.75rem;
  }

  .auth-left p {
    font-size: 0.95rem;
    opacity: 0.8;
    max-width: 300px;
    margin: 0 auto;
    line-height: 1.6;
  }

  .deco-circles {
    position: absolute;
    inset: 0;
    z-index: 0;
    pointer-events: none;
  }

  .deco-circle {
    position: absolute;
    border-radius: 50%;
    border: 2px solid rgba(255, 255, 255, 0.08);
  }

  .c1 { width: 320px; height: 320px; top: -100px; left: -80px; }
  .c2 { width: 200px; height: 200px; bottom: -50px; right: -40px; background: rgba(255, 255, 255, 0.03); }
  .c3 { width: 140px; height: 140px; top: 40%; right: 10%; border-color: rgba(248, 185, 64, 0.15); }
  .c4 { width: 80px; height: 80px; bottom: 20%; left: 15%; background: rgba(255, 255, 255, 0.05); }

  .deco-dots {
    display: grid;
    grid-template-columns: repeat(6, 8px);
    gap: 12px;
    position: absolute;
    bottom: 60px;
    left: 60px;
    z-index: 1;
    opacity: 0.3;
  }

  .dot {
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: #fff;
  }

  /* ── Right panel (form) ── */
  .auth-right {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #ffffff;
    padding: 2rem;
    overflow-y: auto;
  }

  :global([data-theme="dark"]) .auth-right {
    background: #1a1a2e;
  }

  .auth-form-wrapper {
    width: 100%;
    max-width: 480px;
  }

  .auth-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 2rem;
  }

  .logo-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, #452B90, #6941C6);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 700;
  }

  .logo-label {
    font-size: 22px;
    font-weight: 700;
    color: var(--text-heading, #1e1e2d);
  }

  .auth-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--text-heading, #1e1e2d);
    margin: 0 0 0.5rem;
  }

  .auth-subtitle {
    color: var(--text-secondary, #6c7293);
    font-size: 0.9rem;
    margin: 0 0 1.5rem;
  }

  .auth-error {
    background: #fff5f5;
    color: #e53e3e;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    margin-bottom: 1.25rem;
    font-size: 0.875rem;
    border: 1px solid rgba(229, 62, 62, 0.2);
  }

  :global([data-theme="dark"]) .auth-error {
    background: rgba(229, 62, 62, 0.1);
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }

  .form-group {
    margin-bottom: 1.1rem;
  }

  .form-group label {
    display: block;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-secondary, #6c7293);
    margin-bottom: 0.4rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .input-icon-wrap {
    position: relative;
    display: flex;
    align-items: center;
  }

  .input-icon {
    position: absolute;
    left: 12px;
    color: var(--text-muted, #a2a5b9);
    display: flex;
    pointer-events: none;
    z-index: 1;
  }

  .input-icon-wrap input {
    width: 100%;
    padding: 0.7rem 1rem 0.7rem 2.5rem;
    font-size: 0.9rem;
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 8px;
    background: var(--bg-card, #fff);
    color: var(--text-heading, #1e1e2d);
    font-family: inherit;
    transition: border-color 0.2s, box-shadow 0.2s;
  }

  .input-icon-wrap input:focus {
    outline: none;
    border-color: #6941C6;
    box-shadow: 0 0 0 3px rgba(105, 65, 198, 0.12);
  }

  .password-toggle {
    position: absolute;
    right: 12px;
    cursor: pointer;
    color: var(--text-muted, #a2a5b9);
    display: flex;
    z-index: 1;
  }

  .password-toggle:hover {
    color: #6941C6;
  }

  .auth-btn {
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
    margin-top: 0.5rem;
    box-shadow: 0 4px 14px rgba(105, 65, 198, 0.3);
  }

  .auth-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(105, 65, 198, 0.45);
  }

  .auth-btn:disabled { opacity: 0.6; cursor: not-allowed; }

  .spinner {
    width: 18px; height: 18px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .auth-link {
    text-align: center;
    margin-top: 1.5rem;
    color: var(--text-secondary, #6c7293);
    font-size: 0.9rem;
  }

  .auth-link span {
    color: #6941C6;
    cursor: pointer;
    font-weight: 600;
  }

  .auth-link span:hover { text-decoration: underline; }

  @media (max-width: 768px) {
    .auth-page { flex-direction: column; }
    .auth-left { flex: 0 0 auto; min-height: 180px; }
    .auth-left-content { padding: 1.5rem; }
    .auth-left h2 { font-size: 1.5rem; }
    .deco-dots { display: none; }
  }
</style>
