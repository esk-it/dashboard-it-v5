<script>
  import { currentPage } from '../stores/navigation.js';
  import { register } from '../stores/auth.js';
  import { UserPlus, Eye, EyeOff } from 'lucide-svelte';

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
      error = 'Le mot de passe doit contenir au moins 4 caractères';
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

<div class="auth-container">
  <div class="auth-card-wrapper">
    <div class="auth-card">
      <div class="auth-logo">
        <div class="logo-circle">IT</div>
        <span class="logo-text">Manager</span>
      </div>

      <h2>Créer un compte</h2>
      <p class="auth-subtitle">Inscrivez-vous pour accéder au tableau de bord</p>

      {#if error}
        <div class="auth-error">{error}</div>
      {/if}

      <form on:submit|preventDefault={handleSubmit}>
        <div class="form-row">
          <div class="form-group">
            <label for="displayName">Nom complet</label>
            <input id="displayName" type="text" bind:value={displayName} placeholder="Jean Dupont" />
          </div>
          <div class="form-group">
            <label for="username">Identifiant</label>
            <input id="username" type="text" bind:value={username} placeholder="jdupont" required />
          </div>
        </div>

        <div class="form-group">
          <label for="email">Email</label>
          <input id="email" type="email" bind:value={email} placeholder="jean@example.com" required />
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="password">Mot de passe</label>
            <div class="password-input">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                bind:value={password}
                placeholder="••••••••"
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
            <input
              id="confirm"
              type={showPassword ? 'text' : 'password'}
              bind:value={confirmPassword}
              placeholder="••••••••"
              required
            />
          </div>
        </div>

        <button type="submit" class="auth-btn" disabled={loading}>
          {#if loading}
            <span class="spinner"></span>
          {:else}
            <UserPlus size={18} />
          {/if}
          Créer mon compte
        </button>
      </form>

      <p class="auth-link">
        Déjà un compte ?
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <span on:click={() => currentPage.set('/login')}>Se connecter</span>
      </p>
    </div>
  </div>
</div>

<style>
  .auth-container {
    min-height: 100vh;
    width: 100%;
    background: linear-gradient(135deg, rgba(69,43,144,0.05) 0%, rgba(248,185,64,0.05) 100%);
    background-color: var(--bg-base);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
  }

  .auth-card-wrapper {
    width: 100%;
    max-width: 520px;
  }

  .auth-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-card);
    padding: 2.5rem;
  }

  .auth-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin-bottom: 1.5rem;
  }

  .logo-circle {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: var(--primary);
    color: #FFFFFF;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    font-weight: 700;
  }

  .logo-text {
    font-size: 22px;
    font-weight: 600;
    color: var(--text-heading);
  }

  h2 {
    text-align: center;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-heading);
    margin-bottom: 0.25rem;
  }

  .auth-subtitle {
    text-align: center;
    color: var(--text-secondary);
    margin-bottom: 1.75rem;
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

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-group label {
    display: block;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 0.4rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .form-group input {
    width: 100%;
    padding: 0.65rem 0.85rem;
    font-size: 0.9rem;
  }

  .password-input {
    position: relative;
  }

  .password-input input {
    padding-right: 2.5rem;
  }

  .password-toggle {
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    cursor: pointer;
    color: var(--text-muted);
    display: flex;
  }

  .auth-btn {
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
    margin-top: 0.5rem;
  }

  .auth-btn:hover:not(:disabled) {
    background: var(--primary-hover);
    box-shadow: 0 4px 16px rgba(var(--primary-rgb), 0.4);
  }

  .auth-btn:disabled { opacity: 0.6; cursor: not-allowed; }

  .spinner {
    width: 18px; height: 18px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #FFF;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

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

  .auth-link span:hover { text-decoration: underline; }
</style>
