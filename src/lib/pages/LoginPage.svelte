<script>
  import { currentPage } from '../stores/navigation.js';
  import { login } from '../stores/auth.js';
  import { LogIn, Eye, EyeOff, Mail, Lock } from 'lucide-svelte';
  import logoUrl from '../../assets/ESKlogoN.png';
  import eskLogoBUrl from '../../assets/ESKlogoB.png';

  let username = '';
  let password = '';
  let showPassword = false;
  let rememberMe = false;
  let error = '';
  let loading = false;
  let showForgotInfo = false;

  async function handleSubmit() {
    error = '';
    loading = true;
    try {
      await login(username, password);
      if (rememberMe) {
        // Remember for 7 days
        localStorage.setItem('auth_remember_until', String(Date.now() + 7 * 24 * 60 * 60 * 1000));
      } else {
        localStorage.removeItem('auth_remember_until');
      }
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
</script>

<div class="auth-page">
  <!-- Left panel: form -->
  <div class="auth-left">
    <div class="auth-form-wrapper">
      <div class="auth-logo">
        <img src={logoUrl} alt="ESK-IT" class="logo-img-wide" />
      </div>

      <h1 class="auth-title">Bienvenue !</h1>
      <p class="auth-subtitle">Connectez-vous pour acceder a votre espace</p>

      {#if error}
        <div class="auth-error">{error}</div>
      {/if}

      <form on:submit|preventDefault={handleSubmit}>
        <div class="form-group">
          <label for="username">Nom d'utilisateur</label>
          <div class="input-icon-wrap">
            <span class="input-icon"><Mail size={18} /></span>
            <input
              id="username"
              type="text"
              bind:value={username}
              placeholder="Entrez votre identifiant"
              required
              autocomplete="username"
            />
          </div>
        </div>

        <div class="form-group">
          <label for="password">Mot de passe</label>
          <div class="input-icon-wrap">
            <span class="input-icon"><Lock size={18} /></span>
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              bind:value={password}
              placeholder="Entrez votre mot de passe"
              required
              autocomplete="current-password"
            />
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <span class="password-toggle" on:click={() => showPassword = !showPassword}>
              {#if showPassword}
                <EyeOff size={18} />
              {:else}
                <Eye size={18} />
              {/if}
            </span>
          </div>
        </div>

        <div class="form-options">
          <label class="checkbox-wrap">
            <input type="checkbox" bind:checked={rememberMe} />
            <span class="checkmark"></span>
            Se souvenir (7 jours)
          </label>
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <span class="forgot-link" on:click={() => showForgotInfo = !showForgotInfo}>Mot de passe oublie ?</span>
        </div>
        {#if showForgotInfo}
          <div class="forgot-info">
            <p><strong>Mot de passe oublie ?</strong></p>
            <p>Contactez un administrateur pour reinitialiser votre mot de passe.</p>
            <p>Si vous etes l'administrateur, supprimez le fichier <code>dashboard.db</code> dans le repertoire de l'application pour repartir de zero.</p>
            <p style="margin-top:0.5rem;opacity:0.7">Identifiants par defaut : <code>admin</code> / <code>admin123</code></p>
          </div>
        {/if}

        <button type="submit" class="auth-btn" disabled={loading}>
          {#if loading}
            <span class="spinner"></span>
          {:else}
            <LogIn size={18} />
          {/if}
          Connexion
        </button>
      </form>

      <p class="auth-link">
        Pas de compte ?
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <span on:click={() => currentPage.set('/register')}>Creer un compte</span>
      </p>

      <p class="auth-hint">Premiere installation ? Identifiant : admin / admin123</p>
    </div>
  </div>

  <!-- Right panel: decorative -->
  <div class="auth-right">
    <div class="auth-right-content">
      <div class="deco-circles">
        <div class="deco-circle c1"></div>
        <div class="deco-circle c2"></div>
        <div class="deco-circle c3"></div>
        <div class="deco-circle c4"></div>
      </div>
      <div class="brand-block">
        <img src={eskLogoBUrl} alt="ESK" class="brand-esk-logo" />
        <p>Tableau de bord IT de l'Ensemble Scolaire du Kreisker</p>
        <div class="brand-features">
          <span>Parc informatique</span>
          <span>Monitoring</span>
          <span>Securite</span>
          <span>Messagerie</span>
          <span>Planning</span>
        </div>
      </div>
      <div class="deco-dots">
        {#each Array(36) as _, i}
          <span class="dot"></span>
        {/each}
      </div>
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

  /* ── Left panel ── */
  .auth-left {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #ffffff;
    padding: 2rem;
  }

  :global([data-theme="dark"]) .auth-left {
    background: #1a1a2e;
  }

  .auth-form-wrapper {
    width: 100%;
    max-width: 420px;
  }

  .auth-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 2.5rem;
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

  .logo-img-wide {
    max-width: 280px;
    max-height: 80px;
    object-fit: contain;
  }

  .logo-label {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-heading, #1e1e2d);
  }

  .auth-title {
    font-size: 1.85rem;
    font-weight: 700;
    color: var(--text-heading, #1e1e2d);
    margin: 0 0 0.5rem;
  }

  .auth-subtitle {
    color: var(--text-secondary, #6c7293);
    font-size: 0.9rem;
    margin: 0 0 1.75rem;
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

  .form-group {
    margin-bottom: 1.25rem;
  }

  .form-group label {
    display: block;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-secondary, #6c7293);
    margin-bottom: 0.5rem;
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
    left: 14px;
    color: var(--text-muted, #a2a5b9);
    display: flex;
    pointer-events: none;
    z-index: 1;
  }

  .input-icon-wrap input {
    width: 100%;
    padding: 0.75rem 1rem 0.75rem 2.75rem;
    font-size: 0.95rem;
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
    right: 14px;
    cursor: pointer;
    color: var(--text-muted, #a2a5b9);
    display: flex;
    z-index: 1;
  }

  .password-toggle:hover {
    color: #6941C6;
  }

  .form-options {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.5rem;
  }

  .checkbox-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.85rem;
    color: var(--text-secondary, #6c7293);
    cursor: pointer;
    user-select: none;
  }

  .checkbox-wrap input[type="checkbox"] {
    width: 16px;
    height: 16px;
    accent-color: #6941C6;
    cursor: pointer;
  }

  .auth-btn {
    width: 100%;
    padding: 0.85rem;
    background: linear-gradient(135deg, #452B90, #6941C6);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
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

  .auth-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(105, 65, 198, 0.45);
  }

  .auth-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .spinner {
    width: 18px;
    height: 18px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .auth-link {
    text-align: center;
    margin-top: 1.75rem;
    color: var(--text-secondary, #6c7293);
    font-size: 0.9rem;
  }

  .auth-link span {
    color: #6941C6;
    cursor: pointer;
    font-weight: 600;
  }

  .auth-link span:hover {
    text-decoration: underline;
  }

  .forgot-link {
    font-size: 0.8125rem;
    color: var(--primary, #452B90);
    cursor: pointer;
    font-weight: 500;
  }
  .forgot-link:hover { text-decoration: underline; }

  .forgot-info {
    background: rgba(69,43,144,0.06);
    border: 1px solid rgba(69,43,144,0.15);
    border-radius: 0.5rem;
    padding: 0.75rem;
    font-size: 0.75rem;
    color: var(--text-muted, #a2a5b9);
    margin-bottom: 0.5rem;
    line-height: 1.5;
  }
  .forgot-info code {
    background: rgba(0,0,0,0.08);
    padding: 0.125rem 0.375rem;
    border-radius: 0.25rem;
    font-size: 0.7rem;
  }

  .auth-hint {
    text-align: center;
    margin-top: 0.75rem;
    color: var(--text-muted, #a2a5b9);
    font-size: 0.8rem;
    font-style: italic;
  }

  /* ── Right panel ── */
  .auth-right {
    flex: 0 0 45%;
    background: linear-gradient(135deg, #452B90 0%, #6941C6 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
  }

  .auth-right-content {
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

  .brand-esk-logo {
    max-width: 260px;
    max-height: 80px;
    object-fit: contain;
    margin: 0 auto 1.5rem;
    display: block;
  }

  .brand-features {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    justify-content: center;
    margin-top: 1.25rem;
  }
  .brand-features span {
    padding: 0.375rem 0.875rem;
    border-radius: 2rem;
    background: rgba(255,255,255,0.12);
    color: rgba(255,255,255,0.9);
    font-size: 0.75rem;
    font-weight: 500;
    backdrop-filter: blur(5px);
    border: 1px solid rgba(255,255,255,0.15);
  }

  .auth-right h2 {
    font-size: 2rem;
    font-weight: 700;
    margin: 0 0 0.75rem;
  }

  .auth-right p {
    font-size: 0.95rem;
    opacity: 0.8;
    max-width: 300px;
    margin: 0 auto;
    line-height: 1.6;
  }

  /* Decorative circles */
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

  .c1 { width: 320px; height: 320px; top: -100px; right: -80px; }
  .c2 { width: 200px; height: 200px; bottom: -50px; left: -40px; background: rgba(255, 255, 255, 0.03); }
  .c3 { width: 140px; height: 140px; top: 40%; left: 10%; border-color: rgba(248, 185, 64, 0.15); }
  .c4 { width: 80px; height: 80px; bottom: 20%; right: 15%; background: rgba(255, 255, 255, 0.05); }

  /* Dot grid */
  .deco-dots {
    display: grid;
    grid-template-columns: repeat(6, 8px);
    gap: 12px;
    position: absolute;
    bottom: 60px;
    right: 60px;
    z-index: 1;
    opacity: 0.3;
  }

  .dot {
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: #fff;
  }

  @media (max-width: 768px) {
    .auth-page { flex-direction: column; }
    .auth-right { flex: 0 0 auto; min-height: 180px; }
    .auth-right-content { padding: 1.5rem; }
    .auth-right h2 { font-size: 1.5rem; }
    .deco-dots { display: none; }
  }
</style>
