<script>
  import { onMount } from 'svelte';
  import { api } from '../api/client.js';
  import { success, error as toastError } from '../stores/toast.js';

  // ── State ──────────────────────────────────────────────────
  let equipment = [];
  let sites = [];
  let buildings = {};   // { site_id: [...] }
  let rooms = {};       // { building_id: [...] }
  let stats = { total: 0, by_type: {}, by_site: {}, by_source: {} };
  let loading = true;

  // Filters
  let searchQuery = '';
  let filterType = '';
  let filterSource = '';
  let selectedSiteId = null;
  let selectedBuildingId = null;
  let selectedRoomId = null;

  // Sidebar expand state
  let expandedSites = {};
  let expandedBuildings = {};

  // Tab: 'inventory' or 'audit'
  let activeTab = 'inventory';

  // Audit data (smart)
  let auditData = null;  // { rules, issues, summary }
  let auditLoaded = false;
  let showRulesPanel = false;
  let auditRules = {};
  let savingRules = false;
  let auditFilterType = '';
  let auditFilterSeverity = '';

  // Equipment dialog
  let showDialog = false;
  let editingEquipment = null;
  let form = defaultForm();
  let saving = false;

  // Delete
  let confirmDelete = null;
  let deleting = false;

  // Row selection
  let selectedEquipIds = new Set();
  $: selectAllChecked = filteredEquipment.length > 0 && filteredEquipment.every(e => selectedEquipIds.has(e.id));

  function toggleSelectEquip(id) {
    if (selectedEquipIds.has(id)) selectedEquipIds.delete(id);
    else selectedEquipIds.add(id);
    selectedEquipIds = selectedEquipIds;
  }

  function toggleSelectAllEquip() {
    if (selectAllChecked) {
      selectedEquipIds = new Set();
    } else {
      selectedEquipIds = new Set(filteredEquipment.map(e => e.id));
    }
  }

  $: selectedEquipment = equipment.filter(e => selectedEquipIds.has(e.id));

  // GLPI integration
  let glpiConfig = null;
  let glpiSyncing = false;
  let glpiStats = null;

  // Derived
  $: typeList = [...new Set(equipment.map(e => e.equip_type).filter(Boolean))].sort();
  $: sourceList = [...new Set(equipment.map(e => e.source).filter(Boolean))].sort();

  $: filteredEquipment = equipment.filter(e => {
    if (filterType && e.equip_type !== filterType) return false;
    if (filterSource && e.source !== filterSource) return false;
    if (selectedSiteId && e.site_id !== selectedSiteId) return false;
    if (selectedBuildingId && e.building_id !== selectedBuildingId) return false;
    if (selectedRoomId && e.room_id !== selectedRoomId) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      if (!(e.hostname || '').toLowerCase().includes(q) &&
          !(e.serial_number || '').toLowerCase().includes(q) &&
          !(e.brand || '').toLowerCase().includes(q) &&
          !(e.model || '').toLowerCase().includes(q) &&
          !(e.os || '').toLowerCase().includes(q)) return false;
    }
    return true;
  });

  // Cascading selects for dialog
  $: dialogBuildings = form.site_id ? (buildings[form.site_id] || []) : [];
  $: dialogRooms = form.building_id ? (rooms[form.building_id] || []) : [];

  function defaultForm() {
    return {
      hostname: '', equip_type: 'PC', os: '', serial_number: '',
      brand: '', model: '', site_id: null, building_id: null, room_id: null,
      source: 'manual', notes: '', warranty_end: '', purchase_date: '',
    };
  }

  // ── Load ───────────────────────────────────────────────────
  onMount(() => { loadAll(); loadGlpiConfig(); });

  async function loadAll() {
    loading = true;
    try {
      const [eq, st, siteList] = await Promise.all([
        api.get('/api/parc/equipment'),
        api.get('/api/parc/stats'),
        api.get('/api/parc/sites'),
      ]);
      equipment = eq;
      stats = st;
      sites = siteList;

      // Load buildings for each site
      for (const site of siteList) {
        const bl = await api.get(`/api/parc/sites/${site.id}/buildings`);
        buildings[site.id] = bl;
        buildings = buildings; // trigger reactivity
        for (const b of bl) {
          const rm = await api.get(`/api/parc/buildings/${b.id}/rooms`);
          rooms[b.id] = rm;
        }
        rooms = rooms;
      }
    } catch (e) {
      toastError('Erreur chargement parc : ' + e.message);
    }
    loading = false;
  }

  // Audit derived filters
  $: filteredAuditIssues = (auditData?.issues || []).filter(i => {
    if (auditFilterType && i.equip_type !== auditFilterType) return false;
    if (auditFilterSeverity && i.severity !== auditFilterSeverity) return false;
    return true;
  });

  $: auditEquipTypes = auditData ? Object.keys(auditData.summary?.by_type || {}).sort() : [];

  async function loadAudit() {
    try {
      auditData = await api.get('/api/parc/audit');
      auditRules = auditData.rules || {};
      auditLoaded = true;
    } catch (e) {
      toastError('Erreur chargement audit : ' + e.message);
    }
  }

  function switchTab(tab) {
    activeTab = tab;
    if (tab === 'audit' && !auditLoaded) loadAudit();
  }

  async function saveAuditRules() {
    savingRules = true;
    try {
      await api.put('/api/parc/audit/rules', auditRules);
      // Reload audit with new rules
      auditLoaded = false;
      await loadAudit();
      success('R\u00e8gles d\u2019audit sauvegard\u00e9es');
    } catch (e) {
      toastError('Erreur sauvegarde r\u00e8gles');
    }
    savingRules = false;
  }

  function resetAuditRules() {
    auditRules = {
      "PC":          {"site": true, "building": true, "room": true, "os": true, "user": false},
      "Portable":    {"site": true, "building": true, "room": true, "os": true, "user": false},
      "Chromebook":  {"site": true, "building": false, "room_or_user": true, "os": false, "user": false},
      "Imprimante":  {"site": true, "building": true, "room": false, "os": false, "user": false},
      "Switch":      {"site": true, "building": true, "room": false, "os": false, "user": false},
      "AP Wi-Fi":    {"site": true, "building": true, "room": false, "os": false, "user": false},
      "Serveur":     {"site": true, "building": true, "room": true, "os": true, "user": false},
      "_default":    {"site": true, "building": false, "room": false, "os": false, "user": false},
    };
  }

  function missingLabel(key) {
    const labels = { site: 'Site', building: 'B\u00e2timent', room: 'Salle', os: 'OS', user: 'Utilisateur', room_or_user: 'Salle ou Utilisateur' };
    return labels[key] || key;
  }

  // ── Export PDF helpers ──────────────────────────────────────
  import logoUrl from '../../assets/logo.png';

  async function savePdfWithDialog(doc, defaultName) {
    try {
      const { save } = await import('@tauri-apps/plugin-dialog');
      // Use Documents folder as default directory
      let defaultPath = defaultName;
      try {
        const { documentDir, join } = await import('@tauri-apps/api/path');
        const docsDir = await documentDir();
        defaultPath = await join(docsDir, defaultName);
      } catch { /* keep just filename if path API unavailable */ }

      const path = await save({
        defaultPath,
        filters: [{ name: 'PDF', extensions: ['pdf'] }],
      });
      if (!path) return; // user cancelled
      const { writeFile } = await import('@tauri-apps/plugin-fs');
      const pdfBytes = doc.output('arraybuffer');
      await writeFile(path, new Uint8Array(pdfBytes));
      success(`PDF enregistre : ${path.split(/[\\/]/).pop()}`);
    } catch (e) {
      console.error('Tauri PDF save failed, using browser fallback:', e);
      doc.save(defaultName);
      success('PDF exporte');
    }
  }

  function addPdfHeader(doc, title, subtitle) {
    // Try to add logo
    try {
      doc.addImage(logoUrl, 'PNG', 14, 8, 18, 18);
      doc.setFontSize(16);
      doc.text(title, 36, 18);
      doc.setFontSize(9);
      doc.text(subtitle, 36, 24);
      return 30;
    } catch {
      doc.setFontSize(16);
      doc.text(title, 14, 16);
      doc.setFontSize(9);
      doc.text(subtitle, 14, 23);
      return 28;
    }
  }

  // ── Export PDF ─────────────────────────────────────────────
  async function exportInventoryPdf() {
    const { default: jsPDF } = await import('jspdf');
    await import('jspdf-autotable');
    const doc = new jsPDF('landscape');
    const items = selectedEquipment.length > 0 ? selectedEquipment : filteredEquipment;
    const startY = addPdfHeader(doc, 'Inventaire du Parc Informatique',
      `Export\u00e9 le ${new Date().toLocaleDateString('fr-FR')} \u2014 ${items.length} \u00e9quipements`);

    const headers = [['Hostname', 'Type', 'OS', 'N\u00b0 S\u00e9rie', 'Marque/Mod\u00e8le', 'Site', 'B\u00e2timent', 'Salle', 'Source', 'Utilisateur']];
    const rows = items.map(e => [
      e.hostname, e.equip_type, e.os, e.serial_number,
      [e.brand, e.model].filter(Boolean).join(' '),
      e.site_name || '', e.building_name || '', e.room_name || '',
      e.source, e.last_user || '',
    ]);

    doc.autoTable({ head: headers, body: rows, startY, styles: { fontSize: 7, cellPadding: 2 }, headStyles: { fillColor: [6, 166, 201] } });
    await savePdfWithDialog(doc, `inventaire_parc_${new Date().toISOString().slice(0,10)}.pdf`);
  }

  async function exportAuditPdf() {
    if (!auditData) return;
    const { default: jsPDF } = await import('jspdf');
    await import('jspdf-autotable');
    const doc = new jsPDF('landscape');
    const startY = addPdfHeader(doc, 'Audit Parc Informatique',
      `Conformit\u00e9 : ${auditData.summary.compliance_percent}% \u2014 ${auditData.summary.critical} critiques, ${auditData.summary.warnings} avertissements`);

    const headers = [['Hostname', 'Type', 'S\u00e9v\u00e9rit\u00e9', 'Champs manquants', 'Site', 'B\u00e2timent', 'Salle', 'Utilisateur']];
    const rows = auditData.issues.map(i => [
      i.hostname, i.equip_type, i.severity === 'critical' ? 'Critique' : 'Avertissement',
      i.missing.map(m => missingLabel(m)).join(', '),
      i.site_name || '', i.building_name || '', i.room_name || '', i.last_user || '',
    ]);

    doc.autoTable({ head: headers, body: rows, startY, styles: { fontSize: 7, cellPadding: 2 }, headStyles: { fillColor: [239, 68, 68] } });
    await savePdfWithDialog(doc, `audit_parc_${new Date().toISOString().slice(0,10)}.pdf`);
  }

  // ── QR Labels ─────────────────────────────────────────────
  let showQrDialog = false;
  let qrEquipments = [];
  let qrGenerating = false;

  function openQrLabels() {
    // Use selected items if any, otherwise filtered items
    qrEquipments = selectedEquipment.length > 0 ? selectedEquipment.slice(0, 50) : filteredEquipment.slice(0, 50);
    showQrDialog = true;
  }

  // Color per equipment type for labels
  const TYPE_COLORS = {
    'PC': [69, 43, 144],        // Purple
    'Portable': [59, 130, 246], // Blue
    'Moniteur': [34, 197, 94],  // Green
    'Imprimante': [245, 158, 11], // Amber
    'Switch': [6, 166, 201],    // Cyan
    'Serveur': [239, 68, 68],   // Red
    'AP Wi-Fi': [139, 92, 246], // Violet
    'Chromebook': [16, 185, 129], // Emerald
  };

  function truncPdf(text, maxLen) {
    if (!text) return '';
    return text.length > maxLen ? text.slice(0, maxLen - 2) + '..' : text;
  }

  async function generateQrLabels() {
    qrGenerating = true;
    try {
      const QRCode = (await import('qrcode')).default;
      const { default: jsPDF } = await import('jspdf');
      const doc = new jsPDF('portrait');

      const perRow = 3;
      const labelW = 62;
      const labelH = 38;
      const marginX = 8;
      const marginY = 8;
      const gapX = 3;
      const gapY = 3;
      const labelsPerPage = perRow * 7; // 21

      // Try to add logo
      let logoImg = null;
      try {
        const img = new Image();
        img.src = logoUrl;
        await new Promise((res, rej) => { img.onload = res; img.onerror = rej; });
        const canvas = document.createElement('canvas');
        canvas.width = img.width; canvas.height = img.height;
        canvas.getContext('2d').drawImage(img, 0, 0);
        logoImg = canvas.toDataURL('image/png');
      } catch { /* no logo fallback */ }

      for (let i = 0; i < qrEquipments.length; i++) {
        const eq = qrEquipments[i];
        const posOnPage = i % labelsPerPage;
        const col = posOnPage % perRow;
        const row = Math.floor(posOnPage / perRow);

        if (i > 0 && posOnPage === 0) doc.addPage();

        const x = marginX + col * (labelW + gapX);
        const y = marginY + row * (labelH + gapY);

        // Color stripe on left (by equipment type)
        const typeColor = TYPE_COLORS[eq.equip_type] || [100, 116, 139];
        doc.setFillColor(...typeColor);
        doc.rect(x, y, 2.5, labelH, 'F');

        // Background
        doc.setFillColor(252, 252, 253);
        doc.rect(x + 2.5, y, labelW - 2.5, labelH, 'F');

        // Border
        doc.setDrawColor(220, 220, 225);
        doc.setLineWidth(0.3);
        doc.rect(x, y, labelW, labelH);

        // QR code
        const qrData = [eq.hostname, eq.equip_type, eq.serial_number || '', eq.site_name || ''].join(' | ');
        const qrDataUrl = await QRCode.toDataURL(qrData, { width: 100, margin: 1, color: { dark: '#1a1a2e' } });
        doc.addImage(qrDataUrl, 'PNG', x + 4, y + 2, 16, 16);

        // Logo (top right, small)
        if (logoImg) {
          try { doc.addImage(logoImg, 'PNG', x + labelW - 10, y + 1.5, 7, 7); } catch {}
        }

        // Hostname (bold, prominent)
        doc.setTextColor(26, 26, 46);
        doc.setFontSize(8);
        doc.setFont(undefined, 'bold');
        doc.text(truncPdf(eq.hostname || '', 22), x + 22, y + 6);

        // Type badge
        doc.setFontSize(5.5);
        doc.setFont(undefined, 'normal');
        doc.setTextColor(...typeColor);
        doc.text(eq.equip_type || '', x + 22, y + 10);

        // Details
        doc.setTextColor(100, 116, 139);
        doc.setFontSize(5.5);
        const details = [
          eq.serial_number ? `SN: ${truncPdf(eq.serial_number, 20)}` : '',
          eq.site_name ? `${truncPdf(eq.site_name, 15)}` : '',
          eq.building_name ? `${truncPdf(eq.building_name, 12)}${eq.room_name ? ' > ' + truncPdf(eq.room_name, 10) : ''}` : '',
        ].filter(Boolean);

        details.forEach((line, idx) => {
          doc.text(line, x + 22, y + 14 + idx * 3.5);
        });

        // Separator line
        doc.setDrawColor(230, 230, 235);
        doc.setLineWidth(0.2);
        doc.line(x + 4, y + 19, x + labelW - 4, y + 19);

        // Footer: date
        doc.setFontSize(4.5);
        doc.setTextColor(160, 165, 185);
        doc.text(new Date().toLocaleDateString('fr-FR'), x + 4, y + labelH - 2);

        // Footer: brand
        doc.setFontSize(4.5);
        doc.text('ITManager', x + labelW - 16, y + labelH - 2);
      }

      await savePdfWithDialog(doc, `etiquettes_qr_parc_${new Date().toISOString().slice(0,10)}.pdf`);
      showQrDialog = false;
      success(`${qrEquipments.length} etiquettes generees`);
    } catch (e) {
      toastError('Erreur : ' + e.message);
    }
    qrGenerating = false;
  }

  // ── Sidebar ────────────────────────────────────────────────
  function toggleSite(siteId) {
    expandedSites[siteId] = !expandedSites[siteId];
    expandedSites = expandedSites;
  }
  function toggleBuilding(buildingId) {
    expandedBuildings[buildingId] = !expandedBuildings[buildingId];
    expandedBuildings = expandedBuildings;
  }
  function selectSite(siteId) {
    selectedSiteId = selectedSiteId === siteId ? null : siteId;
    selectedBuildingId = null;
    selectedRoomId = null;
  }
  function selectBuilding(buildingId) {
    selectedBuildingId = selectedBuildingId === buildingId ? null : buildingId;
    selectedRoomId = null;
  }
  function selectRoom(roomId) {
    selectedRoomId = selectedRoomId === roomId ? null : roomId;
  }
  function clearTreeFilter() {
    selectedSiteId = null;
    selectedBuildingId = null;
    selectedRoomId = null;
  }

  // ── Equipment count per node ───────────────────────────────
  function countBySite(siteId) { return equipment.filter(e => e.site_id === siteId).length; }
  function countByBuilding(bId) { return equipment.filter(e => e.building_id === bId).length; }
  function countByRoom(rId) { return equipment.filter(e => e.room_id === rId).length; }

  // ── CRUD ───────────────────────────────────────────────────
  function openNew() {
    editingEquipment = null;
    form = defaultForm();
    showDialog = true;
  }
  function openEdit(eq) {
    editingEquipment = eq;
    form = {
      hostname: eq.hostname, equip_type: eq.equip_type, os: eq.os,
      serial_number: eq.serial_number, brand: eq.brand, model: eq.model,
      site_id: eq.site_id, building_id: eq.building_id, room_id: eq.room_id,
      source: eq.source, notes: eq.notes,
      warranty_end: eq.warranty_end || '', purchase_date: eq.purchase_date || '',
    };
    showDialog = true;
  }

  async function saveEquipment() {
    saving = true;
    try {
      const payload = {
        ...form,
        site_id: form.site_id || null,
        building_id: form.building_id || null,
        room_id: form.room_id || null,
        warranty_end: form.warranty_end || null,
        purchase_date: form.purchase_date || null,
      };
      if (editingEquipment) {
        await api.put(`/api/parc/equipment/${editingEquipment.id}`, payload);
        success('Équipement modifié');
      } else {
        await api.post('/api/parc/equipment', payload);
        success('Équipement ajouté');
      }
      showDialog = false;
      await loadAll();
    } catch (e) {
      toastError('Erreur : ' + e.message);
    }
    saving = false;
  }

  async function deleteEquipment() {
    if (!confirmDelete) return;
    deleting = true;
    try {
      await api.delete(`/api/parc/equipment/${confirmDelete.id}`);
      success('Équipement supprimé');
      confirmDelete = null;
      await loadAll();
    } catch (e) {
      toastError('Erreur : ' + e.message);
    }
    deleting = false;
  }

  // Cascading selects handlers
  async function onSiteChange() {
    form.building_id = null;
    form.room_id = null;
    if (form.site_id && !buildings[form.site_id]) {
      buildings[form.site_id] = await api.get(`/api/parc/sites/${form.site_id}/buildings`);
      buildings = buildings;
    }
  }
  async function onBuildingChange() {
    form.room_id = null;
    if (form.building_id && !rooms[form.building_id]) {
      rooms[form.building_id] = await api.get(`/api/parc/buildings/${form.building_id}/rooms`);
      rooms = rooms;
    }
  }

  // ── GLPI ─────────────────────────────────────────────────
  async function loadGlpiConfig() {
    try {
      const cfg = await api.get('/api/glpi/config');
      glpiConfig = cfg.configured ? cfg : null;
      if (glpiConfig) {
        const st = await api.get('/api/glpi/stats');
        glpiStats = st;
      }
    } catch (e) {
      glpiConfig = null;
    }
  }

  async function triggerGlpiSync() {
    glpiSyncing = true;
    try {
      const result = await api.post('/api/glpi/sync');
      success(`Sync GLPI : ${result.created} créés, ${result.updated} mis à jour, ${result.unchanged} inchangés`);
      await loadGlpiConfig();
      await loadAll();
    } catch (e) {
      toastError('Erreur sync GLPI : ' + e.message);
    }
    glpiSyncing = false;
  }
</script>

<!-- ── KPI Stats ──────────────────────────────────────────── -->
<div class="page-header">
  <div class="title-row">
    <h1>Parc Informatique</h1>
    <div class="header-actions">
      {#if glpiConfig}
        <button class="ya-btn btn-sync" on:click={triggerGlpiSync} disabled={glpiSyncing} title="Synchroniser avec GLPI">
          {glpiSyncing ? '⏳ Sync…' : '🔄 Sync GLPI'}
        </button>
        {#if glpiStats?.last_sync}
          <span class="sync-info">Dernière sync : {new Date(glpiStats.last_sync).toLocaleString('fr-FR')}</span>
        {/if}
      {/if}
      <button class="ya-btn ya-btn--ghost" on:click={exportInventoryPdf} title="Exporter en PDF">
        {'\u{1F4C4}'} Export PDF{selectedEquipIds.size > 0 ? ` (${selectedEquipIds.size})` : ''}
      </button>
      <button class="ya-btn ya-btn--ghost" on:click={openQrLabels} title="Generer des etiquettes QR">
        {'\u{1F3F7}\uFE0F'} Etiquettes QR{selectedEquipIds.size > 0 ? ` (${selectedEquipIds.size})` : ''}
      </button>
      <button class="ya-btn ya-btn--primary" on:click={openNew}>+ Ajouter</button>
    </div>
  </div>

  <div class="ya-kpi-row">
    <div class="ya-kpi ya-kpi--primary">
      <span class="ya-kpi__value">{stats.total}</span>
      <span class="ya-kpi__label">Total</span>
    </div>
    {#each Object.entries(stats.by_type) as [type, count], i}
      <div class="ya-kpi {['ya-kpi--info', 'ya-kpi--warning', 'ya-kpi--success', 'ya-kpi--danger', 'ya-kpi--secondary'][i % 5]}">
        <span class="ya-kpi__value">{count}</span>
        <span class="ya-kpi__label">{type}</span>
      </div>
    {/each}
  </div>
</div>

<!-- ── Tabs ────────────────────────────────────────────────── -->
<div class="ya-tabs ya-tabs--boxed">
  <button class="ya-tab" class:ya-tab--active={activeTab === 'inventory'} on:click={() => switchTab('inventory')}>
    Inventaire
  </button>
  <button class="ya-tab" class:ya-tab--active={activeTab === 'audit'} on:click={() => switchTab('audit')}>
    Audit
    {#if auditLoaded && auditData}
      <span class="ya-badge ya-badge--danger">{auditData.issues.length}</span>
    {/if}
  </button>
</div>

{#if activeTab === 'inventory'}
<!-- ── Inventory Tab ──────────────────────────────────────── -->
<div class="inventory-layout">
  <!-- Sidebar Tree -->
  <aside class="tree-sidebar">
    <div class="tree-header">
      <span class="tree-header-icon">{'\u{1F5C2}\uFE0F'}</span>
      <strong>Sites</strong>
      {#if selectedSiteId || selectedBuildingId || selectedRoomId}
        <button class="btn-clear" on:click={clearTreeFilter}>Effacer</button>
      {/if}
    </div>
    <div class="tree-list">
      {#each sites as site}
        <div class="tree-node">
          <button class="tree-item site-level"
                  class:selected={selectedSiteId === site.id}
                  on:click={() => selectSite(site.id)}>
            <span class="tree-toggle" on:click|stopPropagation={() => toggleSite(site.id)}>
              <svg class="chevron" class:open={expandedSites[site.id]} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
            </span>
            <span class="tree-ico">{'\u{1F3E2}'}</span>
            <span class="tree-label">{site.name || site.code}</span>
            <span class="tree-count">{countBySite(site.id)}</span>
          </button>
          {#if expandedSites[site.id] && buildings[site.id]}
            <div class="tree-children">
              {#each buildings[site.id] as building}
                <div class="tree-node">
                  <button class="tree-item building-level"
                          class:selected={selectedBuildingId === building.id}
                          on:click={() => selectBuilding(building.id)}>
                    <span class="tree-toggle" on:click|stopPropagation={() => toggleBuilding(building.id)}>
                      <svg class="chevron" class:open={expandedBuildings[building.id]} width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
                    </span>
                    <span class="tree-ico">{'\u{1F3D7}\uFE0F'}</span>
                    <span class="tree-label">{building.name}</span>
                    <span class="tree-count">{countByBuilding(building.id)}</span>
                  </button>
                  {#if expandedBuildings[building.id] && rooms[building.id]}
                    <div class="tree-children">
                      {#each rooms[building.id] as room}
                        <div class="tree-node">
                          <button class="tree-item room-level"
                                  class:selected={selectedRoomId === room.id}
                                  on:click={() => selectRoom(room.id)}>
                            <span class="tree-ico">{'\u{1F6AA}'}</span>
                            <span class="tree-label">{room.name}</span>
                            <span class="tree-count">{countByRoom(room.id)}</span>
                          </button>
                        </div>
                      {/each}
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  </aside>

  <!-- Main Content -->
  <div class="main-content">
    <!-- Filters -->
    <div class="ya-toolbar">
      <div class="ya-toolbar__search">
        <input type="text" placeholder="Rechercher hostname, SN, marque…"
               bind:value={searchQuery} />
      </div>
      <select class="filter-select" bind:value={filterType}>
        <option value="">— Type —</option>
        {#each typeList as t}<option value={t}>{t}</option>{/each}
      </select>
      <select class="filter-select" bind:value={filterSource}>
        <option value="">— Source —</option>
        {#each sourceList as s}<option value={s}>{s}</option>{/each}
      </select>
      <span class="result-count">{filteredEquipment.length} résultat{filteredEquipment.length !== 1 ? 's' : ''}</span>
    </div>

    <!-- Equipment Table -->
    {#if loading}
      <div class="loading">Chargement…</div>
    {:else}
      <div class="ya-page-card">
        <div class="ya-page-card__body" style="padding:0">
          <div class="ya-table-wrap">
            <table class="ya-table">
              <thead>
                <tr>
                  <th style="width:40px"><input type="checkbox" checked={selectAllChecked} on:change={toggleSelectAllEquip} /></th>
                  <th>Hostname</th>
                  <th>Type</th>
                  <th>OS</th>
                  <th>N° Série</th>
                  <th>Marque / Modèle</th>
                  <th>Localisation</th>
                  <th>Source</th>
                  <th>Dernier utilisateur</th>
                  <th class="actions-col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {#each filteredEquipment as eq}
                  <tr class:row-selected={selectedEquipIds.has(eq.id)}>
                    <td><input type="checkbox" checked={selectedEquipIds.has(eq.id)} on:change={() => toggleSelectEquip(eq.id)} /></td>
                    <td class="hostname">{eq.hostname}</td>
                    <td><span class="ya-badge ya-badge--primary">{eq.equip_type}</span></td>
                    <td class="os-cell">{eq.os}</td>
                    <td>{eq.serial_number || '—'}</td>
                    <td>{[eq.brand, eq.model].filter(Boolean).join(' ') || '—'}</td>
                    <td class="loc-cell">
                      {#if eq.site_name}
                        <span class="loc-part">{eq.site_name}</span>
                        {#if eq.building_name}<span class="loc-sep">›</span><span class="loc-part">{eq.building_name}</span>{/if}
                        {#if eq.room_name}<span class="loc-sep">›</span><span class="loc-part">{eq.room_name}</span>{/if}
                      {:else}
                        <span class="muted">—</span>
                      {/if}
                    </td>
                    <td><span class="ya-badge ya-badge--secondary">{eq.source}</span></td>
                    <td>{eq.last_user || '—'}</td>
                    <td class="actions-col">
                      <button class="btn-icon" title="Modifier" on:click={() => openEdit(eq)}>✏️</button>
                      <button class="btn-icon danger" title="Supprimer" on:click={() => confirmDelete = eq}>🗑️</button>
                    </td>
                  </tr>
                {/each}
                {#if filteredEquipment.length === 0}
                  <tr><td colspan="10" class="empty-row">Aucun équipement trouvé</td></tr>
                {/if}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    {/if}
  </div>
</div>

{:else}
<!-- ── Audit Tab (Smart) ──────────────────────────────────── -->
<div class="audit-section">
  {#if !auditLoaded}
    <div class="loading">Chargement audit…</div>
  {:else if auditData}
    <!-- Summary bar -->
    <div class="ya-kpi-row audit-summary">
      <div class="ya-kpi ya-kpi--success compliance">
        <div class="audit-pct">{auditData.summary.compliance_percent}%</div>
        <div class="ya-progress-bar"><div class="ya-progress-bar__fill" style="width:{auditData.summary.compliance_percent}%"></div></div>
        <span class="ya-kpi__label">Conformit{'\u00e9'}</span>
      </div>
      <div class="ya-kpi ya-kpi--info">
        <span class="ya-kpi__value">{auditData.summary.total_checked}</span>
        <span class="ya-kpi__label">V{'\u00e9'}rifi{'\u00e9'}s</span>
      </div>
      <div class="ya-kpi ya-kpi--success">
        <span class="ya-kpi__value">{auditData.summary.compliant}</span>
        <span class="ya-kpi__label">Conformes</span>
      </div>
      <div class="ya-kpi ya-kpi--warning" class:has-issues={auditData.summary.warnings > 0}>
        <span class="ya-kpi__value">{auditData.summary.warnings}</span>
        <span class="ya-kpi__label">Avertissements</span>
      </div>
      <div class="ya-kpi ya-kpi--danger" class:has-issues={auditData.summary.critical > 0}>
        <span class="ya-kpi__value">{auditData.summary.critical}</span>
        <span class="ya-kpi__label">Critiques</span>
      </div>
      <button class="ya-btn ya-btn--ghost" on:click={() => showRulesPanel = !showRulesPanel}>
        {'\u2699\uFE0F'} R{'\u00e8'}gles
      </button>
      <button class="ya-btn ya-btn--ghost" on:click={exportAuditPdf}>
        {'\u{1F4C4}'} Export PDF
      </button>
    </div>

    <!-- Rules panel (collapsible) -->
    {#if showRulesPanel}
      <div class="rules-panel">
        <h3>{'\u{1F4CB}'} R{'\u00e8'}gles d'audit par type</h3>
        <p class="rules-help">Cochez les champs obligatoires pour chaque type d'{'\u00e9'}quipement. L'audit v{'\u00e9'}rifiera que ces champs sont renseign{'\u00e9'}s.</p>
        <div class="rules-table-wrap">
          <table class="rules-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Site</th>
                <th>B{'\u00e2'}timent</th>
                <th>Salle</th>
                <th>OS</th>
                <th>Utilisateur</th>
                <th title="Salle OU Utilisateur (au moins un)">Salle/User</th>
              </tr>
            </thead>
            <tbody>
              {#each Object.keys(auditRules).filter(k => k !== '_default') as type}
                <tr>
                  <td class="rule-type">{type}</td>
                  <td><input type="checkbox" bind:checked={auditRules[type].site} /></td>
                  <td><input type="checkbox" bind:checked={auditRules[type].building} /></td>
                  <td><input type="checkbox" bind:checked={auditRules[type].room} /></td>
                  <td><input type="checkbox" bind:checked={auditRules[type].os} /></td>
                  <td><input type="checkbox" bind:checked={auditRules[type].user} /></td>
                  <td><input type="checkbox" bind:checked={auditRules[type].room_or_user} /></td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <div class="rules-actions">
          <button class="btn-secondary" on:click={resetAuditRules}>R{'\u00e9'}initialiser</button>
          <button class="btn-primary" on:click={saveAuditRules} disabled={savingRules}>
            {savingRules ? 'Sauvegarde...' : 'Sauvegarder'}
          </button>
        </div>
      </div>
    {/if}

    <!-- Issues list -->
    {#if auditData.issues.length === 0}
      <div class="audit-all-ok">
        <span class="audit-ok-icon">{'\u2705'}</span>
        <h3>Tous les {'\u00e9'}quipements sont conformes !</h3>
        <p>Aucune anomalie d{'\u00e9'}tect{'\u00e9'}e selon vos r{'\u00e8'}gles d'audit.</p>
      </div>
    {:else}
      <div class="filters-bar" style="margin-top:16px">
        <select class="filter-select" bind:value={auditFilterType}>
          <option value="">— Tous les types —</option>
          {#each auditEquipTypes as t}<option value={t}>{t}</option>{/each}
        </select>
        <select class="filter-select" bind:value={auditFilterSeverity}>
          <option value="">— Toutes s{'\u00e9'}v{'\u00e9'}rit{'\u00e9'}s —</option>
          <option value="critical">{'\u{1F534}'} Critique</option>
          <option value="warning">{'\u{1F7E1}'} Avertissement</option>
        </select>
        <span class="result-count">{filteredAuditIssues.length} probl{'\u00e8'}me{filteredAuditIssues.length !== 1 ? 's' : ''}</span>
      </div>

      <div class="table-wrapper" style="margin-top:8px">
        <table>
          <thead>
            <tr>
              <th>S{'\u00e9'}v{'\u00e9'}rit{'\u00e9'}</th>
              <th>Hostname</th>
              <th>Type</th>
              <th>Champs manquants</th>
              <th>Localisation actuelle</th>
              <th>Utilisateur</th>
              <th class="actions-col">Action</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredAuditIssues as issue}
              <tr>
                <td>
                  {#if issue.severity === 'critical'}
                    <span class="severity-badge critical">{'\u{1F534}'} Critique</span>
                  {:else}
                    <span class="severity-badge warning">{'\u{1F7E1}'} Avertissement</span>
                  {/if}
                </td>
                <td class="hostname">{issue.hostname}</td>
                <td><span class="type-badge">{issue.equip_type}</span></td>
                <td>
                  <div class="missing-tags">
                    {#each issue.missing as m}
                      <span class="missing-tag">{missingLabel(m)}</span>
                    {/each}
                  </div>
                </td>
                <td class="loc-cell">
                  {#if issue.site_name}
                    {issue.site_name}
                    {#if issue.building_name} › {issue.building_name}{/if}
                    {#if issue.room_name} › {issue.room_name}{/if}
                  {:else}
                    <span class="muted">—</span>
                  {/if}
                </td>
                <td>{issue.last_user || '—'}</td>
                <td class="actions-col">
                  <button class="btn-icon" title="Modifier"
                    on:click={() => { const eq = equipment.find(e => e.id === issue.id); if (eq) openEdit(eq); }}>
                    {'\u270F\uFE0F'}
                  </button>
                </td>
              </tr>
            {/each}
            {#if filteredAuditIssues.length === 0}
              <tr><td colspan="7" class="empty-row">Aucun probl{'\u00e8'}me avec ces filtres</td></tr>
            {/if}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</div>
{/if}

<!-- ── Equipment Dialog ───────────────────────────────────── -->
{#if showDialog}
<div class="ya-dialog-overlay" on:click|self={() => showDialog = false}>
  <div class="ya-dialog">
    <div class="ya-dialog__header">
      <h3 class="ya-dialog__title">{editingEquipment ? 'Modifier' : 'Ajouter'} un équipement</h3>
      <button class="ya-dialog__close" on:click={() => showDialog = false}>×</button>
    </div>
    <div class="ya-dialog__body">
      <div class="form-row">
        <label>Hostname<input type="text" bind:value={form.hostname} /></label>
        <label>Type
          <select bind:value={form.equip_type}>
            <option value="PC">PC</option>
            <option value="Portable">Portable</option>
            <option value="Imprimante">Imprimante</option>
            <option value="Switch">Switch</option>
            <option value="AP Wi-Fi">AP Wi-Fi</option>
            <option value="Serveur">Serveur</option>
            <option value="Écran">Écran</option>
            <option value="Autre">Autre</option>
          </select>
        </label>
      </div>
      <div class="form-row">
        <label>OS<input type="text" bind:value={form.os} /></label>
        <label>N° Série<input type="text" bind:value={form.serial_number} /></label>
      </div>
      <div class="form-row">
        <label>Marque<input type="text" bind:value={form.brand} /></label>
        <label>Modèle<input type="text" bind:value={form.model} /></label>
      </div>
      <div class="form-row triple">
        <label>Site
          <select bind:value={form.site_id} on:change={onSiteChange}>
            <option value={null}>— Aucun —</option>
            {#each sites as s}<option value={s.id}>{s.code || s.name}</option>{/each}
          </select>
        </label>
        <label>Bâtiment
          <select bind:value={form.building_id} on:change={onBuildingChange} disabled={!form.site_id}>
            <option value={null}>— Aucun —</option>
            {#each dialogBuildings as b}<option value={b.id}>{b.name}</option>{/each}
          </select>
        </label>
        <label>Salle
          <select bind:value={form.room_id} disabled={!form.building_id}>
            <option value={null}>— Aucune —</option>
            {#each dialogRooms as r}<option value={r.id}>{r.name}</option>{/each}
          </select>
        </label>
      </div>
      <div class="form-row">
        <label>Source
          <select bind:value={form.source}>
            <option value="manual">Manuel</option>
            <option value="glpi">GLPI</option>
            <option value="ad_admin">AD Admin</option>
            <option value="ad_pedago_ndk">AD Pédago NDK</option>
            <option value="ad_pedago_su">AD Pédago SU</option>
          </select>
        </label>
      </div>
      <div class="form-row">
        <label>Date d'achat<input type="date" bind:value={form.purchase_date} /></label>
        <label>Fin garantie<input type="date" bind:value={form.warranty_end} /></label>
      </div>
      <label class="full-width">Notes<textarea bind:value={form.notes} rows="3"></textarea></label>
    </div>
    <div class="ya-dialog__footer">
      <button class="ya-btn ya-btn--ghost" on:click={() => showDialog = false}>Annuler</button>
      <button class="ya-btn ya-btn--primary" on:click={saveEquipment} disabled={saving || !form.hostname}>
        {saving ? 'Enregistrement…' : 'Enregistrer'}
      </button>
    </div>
  </div>
</div>
{/if}

<!-- ── Delete Confirm ─────────────────────────────────────── -->
{#if confirmDelete}
<div class="ya-dialog-overlay" on:click|self={() => confirmDelete = null}>
  <div class="ya-dialog small">
    <div class="ya-dialog__header">
      <h3 class="ya-dialog__title">Supprimer</h3>
      <button class="ya-dialog__close" on:click={() => confirmDelete = null}>×</button>
    </div>
    <div class="ya-dialog__body">
      <p>Supprimer <strong>{confirmDelete.hostname}</strong> ?</p>
    </div>
    <div class="ya-dialog__footer">
      <button class="ya-btn ya-btn--ghost" on:click={() => confirmDelete = null}>Annuler</button>
      <button class="ya-btn" style="background:var(--danger);color:#fff" on:click={deleteEquipment} disabled={deleting}>
        {deleting ? 'Suppression…' : 'Supprimer'}
      </button>
    </div>
  </div>
</div>
{/if}

<!-- ── QR Labels Dialog ───────────────────────────────────── -->
{#if showQrDialog}
<div class="ya-dialog-overlay" on:click|self={() => showQrDialog = false}>
  <div class="ya-dialog">
    <div class="ya-dialog__header">
      <h3 class="ya-dialog__title">{'\u{1F3F7}\uFE0F'} {'\u00C9'}tiquettes QR</h3>
      <button class="ya-dialog__close" on:click={() => showQrDialog = false}>{'\u00D7'}</button>
    </div>
    <div class="ya-dialog__body">
      <p style="font-size:0.85rem;color:rgba(255,255,255,0.6);margin-bottom:12px">
        G{'\u00e9'}n{'\u00e9'}rer des {'\u00e9'}tiquettes QR code pour coller sur les {'\u00e9'}quipements.
        Chaque {'\u00e9'}tiquette contient le hostname, type, n{'\u00b0'} de s{'\u00e9'}rie et site.
      </p>
      <p style="font-size:0.9rem;margin-bottom:8px">
        <strong>{qrEquipments.length}</strong> {'\u00e9'}quipements s{'\u00e9'}lectionn{'\u00e9'}s (filtre actuel, max 50)
      </p>
    </div>
    <div class="ya-dialog__footer">
      <button class="ya-btn ya-btn--ghost" on:click={() => showQrDialog = false}>Annuler</button>
      <button class="ya-btn ya-btn--primary" on:click={generateQrLabels} disabled={qrGenerating}>
        {qrGenerating ? 'G\u00e9n\u00e9ration...' : `G\u00e9n\u00e9rer ${qrEquipments.length} \u00e9tiquettes`}
      </button>
    </div>
  </div>
</div>
{/if}

<style>
  /* ── Layout ─────────────────────────────────────────────── */
  .page-header { margin-bottom: 20px; }
  .title-row {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 16px;
  }
  .title-row h1 { font-size: 1.5rem; font-weight: 700; color: #fff; margin: 0; }

  /* old .stats-row / .stat-card / .tabs / .badge removed — now global ya-kpi-row + ya-tabs */

  /* ── Inventory layout ───────────────────────────────────── */
  .inventory-layout { display: flex; gap: 16px; min-height: 500px; }

  /* ── Tree Sidebar ───────────────────────────────────────── */
  .tree-sidebar {
    width: 260px; min-width: 260px;
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem; padding: 14px;
    backdrop-filter: blur(16px); overflow-y: auto; max-height: 70vh;
    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
  }
  .tree-header {
    display: flex; align-items: center; gap: 6px;
    margin-bottom: 12px; padding-bottom: 10px;
    border-bottom: 1px solid var(--border-subtle);
    font-size: 0.9rem; color: rgba(255,255,255,0.7);
  }
  .tree-header-icon { font-size: 1rem; }
  .tree-header strong { flex: 1; letter-spacing: 0.3px; }
  .btn-clear {
    background: none; border: none; color: var(--accent, #6C63FF);
    cursor: pointer; font-size: 0.75rem; opacity: 0.8;
  }
  .btn-clear:hover { opacity: 1; text-decoration: underline; }
  .tree-list { display: flex; flex-direction: column; gap: 2px; }
  .tree-item {
    display: flex; align-items: center; gap: 6px; width: 100%;
    background: none; border: none; color: rgba(255,255,255,0.75);
    padding: 6px 8px; border-radius: 0.625rem; cursor: pointer;
    font-size: 0.8125rem; text-align: left; transition: all 0.15s;
    border: 1px solid transparent; font-family: inherit;
  }
  .tree-item:hover {
    background: rgba(255,255,255,0.05);
    border-color: rgba(255,255,255,0.06);
  }
  .tree-item.selected {
    background: rgba(108,99,255,0.15); color: #fff;
    border-color: rgba(108,99,255,0.3);
    box-shadow: 0 0 8px rgba(108,99,255,0.1);
  }
  .tree-toggle {
    width: 16px; display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; color: rgba(255,255,255,0.35);
  }
  .chevron { transition: transform 0.2s ease; }
  .chevron.open { transform: rotate(90deg); }
  .tree-ico { font-size: 0.85rem; flex-shrink: 0; line-height: 1; }
  .tree-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; }
  .tree-count {
    font-size: 0.6875rem; color: rgba(var(--accent-rgb, 108,99,255), 0.8);
    background: rgba(var(--accent-rgb, 108,99,255), 0.1);
    border-radius: 0.625rem; padding: 2px 7px; font-weight: 600;
    min-width: 22px; text-align: center;
  }
  .site-level { font-weight: 600; }
  .tree-children {
    margin-left: 12px; padding-left: 10px;
    border-left: 1px solid var(--border-subtle);
  }
  .building-level .tree-label { font-weight: 500; }
  .room-level { padding-left: 24px; }
  .room-level .tree-label { font-weight: 400; color: rgba(255,255,255,0.65); }

  /* ── Main content ───────────────────────────────────────── */
  .main-content { flex: 1; min-width: 0; }

  .filters-bar {
    display: flex; gap: 10px; align-items: center; margin-bottom: 12px; flex-wrap: wrap;
  }
  .search-input {
    flex: 1; min-width: 200px; padding: 8px 14px;
    background: var(--bg-card); border: 1px solid var(--border-subtle);
    border-radius: 0.625rem; color: #fff; font-size: 0.875rem;
  }
  .search-input::placeholder { color: rgba(255,255,255,0.3); }
  .filter-select {
    padding: 8px 12px;
    background: var(--bg-card); border: 1px solid var(--border-subtle);
    border-radius: 0.625rem; color: #fff; font-size: 0.875rem;
  }
  .filter-select option { background: var(--bg-card); color: #fff; }
  .result-count { font-size: 0.75rem; color: rgba(255,255,255,0.4); white-space: nowrap; }

  /* ── Table ──────────────────────────────────────────────── */
  .table-wrapper {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem; overflow: auto; max-height: 60vh;
    backdrop-filter: blur(12px);
  }
  table { width: 100%; border-collapse: collapse; font-size: 0.8125rem; }
  thead { position: sticky; top: 0; z-index: 2; }
  th {
    background: rgba(255,255,255,0.04); color: rgba(255,255,255,0.6);
    padding: 10px 12px; text-align: left; font-weight: 600; white-space: nowrap;
    border-bottom: 1px solid var(--border-subtle);
  }
  td {
    padding: 8px 12px; border-bottom: 1px solid var(--border-subtle);
    color: rgba(255,255,255,0.85); white-space: nowrap;
  }
  tr:hover td { background: rgba(255,255,255,0.03); }
  .hostname { font-weight: 600; color: #fff; }
  .os-cell { max-width: 160px; overflow: hidden; text-overflow: ellipsis; }
  .type-badge {
    background: rgba(108,99,255,0.2); color: var(--accent, #6C63FF);
    border-radius: 0.625rem; padding: 2px 8px; font-size: 0.75rem; font-weight: 600;
  }
  .source-tag {
    background: var(--bg-card); border-radius: 0.625rem;
    padding: 2px 8px; font-size: 0.75rem;
  }
  .loc-cell { max-width: 220px; overflow: hidden; text-overflow: ellipsis; }
  .loc-sep { color: rgba(255,255,255,0.3); margin: 0 2px; }
  .loc-part { }
  .muted { color: rgba(255,255,255,0.3); }
  .actions-col { width: 80px; text-align: center; }
  .empty-row { text-align: center; color: rgba(255,255,255,0.3); padding: 32px !important; }
  .loading { text-align: center; color: rgba(255,255,255,0.4); padding: 40px; }

  .btn-icon {
    background: none; border: none; cursor: pointer; font-size: 0.9rem;
    padding: 4px; border-radius: 0.625rem; transition: background 0.15s;
  }
  .btn-icon:hover { background: rgba(255,255,255,0.08); }

  /* ── Audit (Smart) ──────────────────────────────────────── */
  .audit-summary {
    display: flex; gap: 10px; align-items: stretch; flex-wrap: wrap; margin-bottom: 16px;
  }
  /* old .audit-stat-card removed — now global ya-kpi */
  .audit-pct { font-size: 1.6rem; font-weight: 800; color: #22C55E; }

  /* Rules panel */
  .rules-panel {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem; padding: 20px; margin-bottom: 16px;
    backdrop-filter: blur(12px);
  }
  .rules-panel h3 { margin: 0 0 6px; font-size: 1rem; color: #fff; }
  .rules-help { font-size: 0.75rem; color: rgba(255,255,255,0.45); margin: 0 0 14px; }
  .rules-table-wrap { overflow-x: auto; }
  .rules-table { width: 100%; border-collapse: collapse; font-size: 0.8125rem; }
  .rules-table th {
    padding: 8px 10px; text-align: center; color: rgba(255,255,255,0.5);
    font-weight: 600; font-size: 0.75rem; text-transform: uppercase;
    border-bottom: 1px solid var(--border-subtle);
  }
  .rules-table th:first-child { text-align: left; }
  .rules-table td { padding: 6px 10px; text-align: center; border-bottom: 1px solid var(--border-subtle); }
  .rules-table td:first-child { text-align: left; }
  .rule-type { font-weight: 600; color: #fff; }
  .rules-table input[type="checkbox"] { width: 16px; height: 16px; accent-color: var(--accent, #6C63FF); cursor: pointer; }
  .rules-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 14px; }

  /* Severity badges */
  .severity-badge {
    border-radius: 0.625rem; padding: 3px 8px; font-size: 0.75rem; font-weight: 600;
  }
  .severity-badge.critical { background: rgba(239,68,68,0.15); color: #EF4444; }
  .severity-badge.warning { background: rgba(245,158,11,0.15); color: #F59E0B; }

  /* Missing tags */
  .missing-tags { display: flex; gap: 4px; flex-wrap: wrap; }
  .missing-tag {
    background: rgba(239,68,68,0.1); color: #F87171;
    border-radius: 0.625rem; padding: 2px 7px; font-size: 0.6875rem; font-weight: 500;
    white-space: nowrap;
  }

  /* All OK state */
  .audit-all-ok {
    text-align: center; padding: 60px 20px;
    color: rgba(255,255,255,0.6);
  }
  .audit-ok-icon { font-size: 3rem; display: block; margin-bottom: 12px; }
  .audit-all-ok h3 { color: #22C55E; margin: 0 0 8px; font-size: 1.2rem; }
  .audit-all-ok p { margin: 0; font-size: 0.9rem; }

  /* old .dialog-overlay / .dialog / .dialog-header / .dialog-body / .dialog-footer / .btn-close removed — now global ya-dialog */

  .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
  .form-row.triple { grid-template-columns: 1fr 1fr 1fr; }
  .full-width { display: block; margin-bottom: 12px; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 0.8125rem; color: rgba(255,255,255,0.6); }
  input, select, textarea {
    padding: 8px 12px; background: var(--bg-card);
    border: 1px solid var(--border-subtle); border-radius: 0.625rem;
    color: #fff; font-size: 0.875rem; font-family: inherit;
  }
  input:focus, select:focus, textarea:focus {
    outline: none; border-color: var(--accent, #6C63FF);
  }
  select option { background: var(--bg-card); color: #fff; }
  textarea { resize: vertical; }

  /* old .btn-primary / .btn-secondary / .btn-danger removed — now global ya-btn */

  /* ── Header actions ──────────────────────────────────────── */
  .header-actions {
    display: flex; gap: 8px; align-items: center;
  }
  .btn-sync {
    background: rgba(34,197,94,0.15); color: #22C55E;
    border: 1px solid rgba(34,197,94,0.3); border-radius: 0.625rem;
    padding: 8px 14px; cursor: pointer; font-size: 0.8125rem;
    font-weight: 600; transition: all 0.2s;
  }
  .btn-sync:hover { background: rgba(34,197,94,0.25); }
  .btn-sync:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-export {
    background: rgba(108,99,255,0.1); color: var(--accent, #6C63FF);
    border: 1px solid rgba(108,99,255,0.25); border-radius: 0.625rem;
    padding: 7px 12px; cursor: pointer; font-size: 0.75rem;
    font-weight: 600; transition: all 0.2s; font-family: inherit;
  }
  .btn-export:hover { background: rgba(108,99,255,0.2); }
  .sync-info {
    font-size: 0.75rem; color: rgba(255,255,255,0.4);
    white-space: nowrap;
  }
</style>
