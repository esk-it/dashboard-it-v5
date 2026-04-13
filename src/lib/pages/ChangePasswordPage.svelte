<script>
  import { currentUser } from '../stores/auth.js';
  import { currentPage } from '../stores/navigation.js';
  import { Lock } from 'lucide-svelte';

  let newPassword = '';
  let confirmPassword = '';
  let error = '';
  let saving = false;

  async function changePassword() {
    error = '';
    if (newPassword.length < 4) { error = 'Le mot de passe doit contenir au moins 4 caracteres'; return; }
    if (newPassword === 'admin123') { error = 'Choisissez un mot de passe different du mot de passe par defaut'; return; }
    if (newPassword !== confirmPassword) { error = 'Les mots de passe ne correspondent pas'; return; }

    saving = true;
    try {
      const res = await fetch('http://localhost:8010/api/auth/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: $currentUser.id, new_password: newPassword }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Erreur');
      }
      currentPage.set('/');
    } catch (e) {
      error = e.message;
    }
    saving = false;
  }
</script>

<div class="change-pw-page">
  <div class="change-pw-card">
    <div class="change-pw-icon">
      <Lock size={32} />
    </div>
    <h2>Changement de mot de passe requis</h2>
    <p>Pour des raisons de securite, vous devez changer le mot de passe par defaut avant de continuer.</p>

    {#if error}
      <div class="change-pw-error">{error}</div>
    {/if}

    <form on:submit|preventDefault={changePassword}>
      <label>
        Nouveau mot de passe
        <input type="password" bind:value={newPassword} placeholder="Minimum 4 caracteres" required />
      </label>
      <label>
        Confirmer le mot de passe
        <input type="password" bind:value={confirmPassword} placeholder="Repetez le mot de passe" required />
      </label>
      <button type="submit" class="change-pw-btn" disabled={saving}>
        {saving ? 'Enregistrement...' : 'Enregistrer et continuer'}
      </button>
    </form>
  </div>
</div>

<style>
  .change-pw-page {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
  }
  .change-pw-card {
    background: var(--bg-card, #1a1a2e);
    border: 1px solid var(--border-card, rgba(255,255,255,0.08));
    border-radius: 1rem;
    padding: 2.5rem;
    width: 90vw;
    max-width: 420px;
    text-align: center;
  }
  .change-pw-icon {
    width: 64px; height: 64px; border-radius: 50%;
    background: linear-gradient(135deg, #452B90, #6941C6);
    color: #fff; display: flex; align-items: center; justify-content: center;
    margin: 0 auto 1.25rem;
  }
  .change-pw-card h2 {
    font-size: 1.25rem; font-weight: 700; color: var(--text-heading, #fff);
    margin: 0 0 0.5rem;
  }
  .change-pw-card p {
    font-size: 0.8125rem; color: var(--text-muted, #a2a5b9);
    margin: 0 0 1.5rem; line-height: 1.5;
  }
  .change-pw-error {
    background: rgba(239,68,68,0.1); color: #EF4444;
    padding: 0.5rem 0.75rem; border-radius: 0.5rem;
    font-size: 0.8125rem; margin-bottom: 1rem;
  }
  label {
    display: flex; flex-direction: column; gap: 0.25rem;
    text-align: left; font-size: 0.8125rem; font-weight: 600;
    color: var(--text-secondary, #a2a5b9); margin-bottom: 1rem;
  }
  input {
    padding: 0.625rem 0.875rem; background: var(--bg-base, #16162a);
    border: 1px solid var(--border-subtle, rgba(255,255,255,0.1));
    border-radius: 0.5rem; color: var(--text-heading, #fff);
    font-size: 0.875rem; font-family: inherit;
  }
  input:focus { outline: none; border-color: #452B90; }
  .change-pw-btn {
    width: 100%; padding: 0.75rem; border: none; border-radius: 0.5rem;
    background: linear-gradient(135deg, #452B90, #6941C6); color: #fff;
    font-size: 0.9375rem; font-weight: 600; cursor: pointer; font-family: inherit;
    transition: filter 0.15s;
  }
  .change-pw-btn:hover { filter: brightness(1.1); }
  .change-pw-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
