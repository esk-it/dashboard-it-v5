<script>
  import { currentPage } from '../stores/navigation.js';
  import { login } from '../stores/auth.js';
  import { LogIn, Eye, EyeOff } from 'lucide-svelte';

  let username = '';
  let password = '';
  let showPassword = false;
  let error = '';
  let loading = false;

  async function handleSubmit() {
    error = '';
    loading = true;
    try {
      await login(username, password);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
</script>

<div class="auth-container">
  <!-- Left panel – gradient branding -->
  <div class="auth-left">
    <div class="auth-left-content">
      <div class="auth-logo">
        <div class="logo-circle">IT</div>
        <span class="logo-text">Manager</span>
      </div>
      <h1>Bienvenue</h1>
      <p>Votre tableau de bord IT centralisé pour gérer vos équipements, tâches et sécurité.</p>
      <div class="auth-decoration">
        <div class="deco-circle deco-1"></div>
        <div class="deco-circle deco-2"></div>
        <div class="deco-circle deco-3"></div>
      </div>
    </div>
  </div>

  <!-- Right panel – login form -->
  <div class="auth-right">
    <div class="auth-form-wrapper">
      <h2>Connexion</h2>
      <p class="auth-subtitle">Connectez-vous à votre compte</p>

      {#if error}
        <div class="auth-error">{error}</div>
      {/if}

      <form on:submit|preventDefault={handleSubmit}>
        <div class="form-group">
          <label for="username">Nom d'utilisateur</label>
          <input
            id="username"
            type="text"
            bind:value={username}
            placeholder="admin"
            required
            autocomplete="username"
          />
        </div>

        <div class="form-group">
          <label for="password">Mot de passe</label>
          <div class="password-input">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              bind:value={password}
              placeholder="••••••••"
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

        <button type="submit" class="auth-btn" disabled={loading}>
          {#if loading}
            <span class="spinner"></span>
          {:else}
            <LogIn size={18} />
          {/if}
          Se connecter
        </button>
      </form>

      <p class="auth-link">
        Pas de compte ?
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <span on:click={() => currentPage.set('/register')}>Créer un compte</span>
      </p>

      <p class="auth-hint">Compte par défaut : admin / admin123</p>
    </div>
  </div>
</div>

<style>
  .auth-container {
    display: flex;
    min-height: 100vh;
    width: 100%;
    background: var(--bg-base);
  }

  /* Left panel */
  .auth-left {
    flex: 0 0 45%;
    background: linear-gradient(135deg, #452B90 0%, #7C3AED 50%, #452B90 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
  }

  .auth-left-content {
    color: #FFFFFF;
    text-align: center;
    padding: 3rem;
    position: relative;
    z-index: 2;
  }

  .auth-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-bottom: 2rem;
  }

  .logo-circle {
    width: 52px;
    height: 52px;
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.2);
    backdrop-filter: blur(10px);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: 700;
    color: #FFFFFF;
  }

  .logo-text {
    font-size: 28px;
    font-weight: 600;
    color: #FFFFFF;
  }

  .auth-left h1 {
    font-size: 2.5rem;
    font-weight: 700;
    margin-bottom: 1rem;
  }

  .auth-left p {
    font-size: 1rem;
    opacity: 0.85;
    max-width: 320px;
    margin: 0 auto;
    line-height: 1.6;
  }

  /* Decorative circles */
  .deco-circle {
    position: absolute;
    border-radius: 50%;
    border: 2px solid rgba(255, 255, 255, 0.1);
  }

  .deco-1 {
    width: 300px; height: 300px;
    top: -80px; left: -60px;
  }

  .deco-2 {
    width: 200px; height: 200px;
    bottom: -40px; right: -30px;
    background: rgba(248, 185, 64, 0.1);
  }

  .deco-3 {
    width: 120px; height: 120px;
    top: 50%; left: 75%;
    background: rgba(255, 255, 255, 0.05);
  }

  /* Right panel */
  .auth-right {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
  }

  .auth-form-wrapper {
    width: 100%;
    max-width: 400px;
  }

  .auth-form-wrapper h2 {
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--text-heading);
    margin-bottom: 0.5rem;
  }

  .auth-subtitle {
    color: var(--text-secondary);
    margin-bottom: 2rem;
    font-size: 0.9rem;
  }

  .auth-error {
    background: var(--danger-light);
    color: var(--danger);
    padding: 0.75rem 1rem;
    border-radius: var(--radius-sm);
    margin-bottom: 1.25rem;
    font-size: 0.875rem;
    border: 1px solid rgba(255, 94, 94, 0.2);
  }

  .form-group {
    margin-bottom: 1.25rem;
  }

  .form-group label {
    display: block;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .form-group input {
    width: 100%;
    padding: 0.75rem 1rem;
    font-size: 0.95rem;
    border-radius: var(--radius-sm);
  }

  .password-input {
    position: relative;
  }

  .password-input input {
    width: 100%;
    padding-right: 3rem;
  }

  .password-toggle {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    cursor: pointer;
    color: var(--text-muted);
    display: flex;
  }

  .password-toggle:hover {
    color: var(--primary);
  }

  .auth-btn {
    width: 100%;
    padding: 0.8rem;
    background: var(--primary);
    color: #FFFFFF;
    border: none;
    border-radius: var(--radius-sm);
    font-size: 1rem;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    transition: all 0.2s ease;
    margin-top: 0.5rem;
  }

  .auth-btn:hover:not(:disabled) {
    background: var(--primary-hover);
    box-shadow: 0 4px 16px rgba(var(--primary-rgb), 0.4);
    transform: translateY(-1px);
  }

  .auth-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .spinner {
    width: 18px;
    height: 18px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: #FFFFFF;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .auth-link {
    text-align: center;
    margin-top: 1.5rem;
    color: var(--text-secondary);
    font-size: 0.9rem;
  }

  .auth-link span {
    color: var(--primary);
    cursor: pointer;
    font-weight: 600;
  }

  .auth-link span:hover {
    text-decoration: underline;
  }

  .auth-hint {
    text-align: center;
    margin-top: 1rem;
    color: var(--text-muted);
    font-size: 0.8rem;
    font-style: italic;
  }

  @media (max-width: 768px) {
    .auth-container { flex-direction: column; }
    .auth-left { flex: 0 0 auto; min-height: 200px; }
  }
</style>
