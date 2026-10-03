    const search = document.getElementById('claim-search');
    const statusFilter = document.getElementById('status-filter');
    const predicateFilter = document.getElementById('predicate-filter');
    const roleFilter = document.getElementById('role-filter');
    const note = document.getElementById('filter-note');
    const cards = Array.from(document.querySelectorAll('[data-claim-card]'));
    const details = Array.from(document.querySelectorAll('[data-claim-detail]'));
    const emptyHint = document.getElementById('claim-empty');
    let stage = '';

    function applyFilter() {
      const q = (search.value || '').toLowerCase();
      const s = statusFilter.value;
      const p = predicateFilter.value;
      const r = roleFilter.value;
      let shown = 0;
      for (const card of cards) {
        const d = card.dataset;
        const visible =
          (!q || (d.search || '').includes(q)) &&
          (!s || d.status === s) &&
          (!p || d.predicate === p) &&
          (!r || d.role === r) &&
          (!stage || (d.stage === stage) || (stage === 'executed' && d.executed === 'yes'));
        card.style.display = visible ? '' : 'none';
        if (visible) shown++;
      }
      note.textContent = shown + ' of ' + cards.length + ' claims shown'
        + (stage ? ' · funnel: ' + stage : '');
    }

    function setStage(value) {
      stage = (stage === value) ? '' : value;
      for (const chip of document.querySelectorAll('[data-stage-chip]')) {
        chip.classList.toggle('active', chip.dataset.stageChip === stage);
      }
      applyFilter();
    }

    function showClaim(id) {
      let found = false;
      for (const section of details) {
        const match = section.id === 'claim-' + id;
        section.style.display = match ? 'block' : 'none';
        found = found || match;
      }
      if (emptyHint) emptyHint.style.display = found ? 'none' : '';
    }

    function reveal(hash) {
      const target = document.getElementById(hash);
      if (!target) return;
      const section = target.closest('[data-claim-detail]');
      if (section) showClaim(section.dataset.claimId);
      for (let el = target.parentElement; el; el = el.parentElement) {
        if (el.tagName === 'DETAILS') el.open = true;
      }
      target.scrollIntoView({block: 'start'});
    }

    search.addEventListener('input', applyFilter);
    for (const select of [statusFilter, predicateFilter, roleFilter]) {
      select.addEventListener('change', applyFilter);
    }
    for (const chip of document.querySelectorAll('[data-stage-chip]')) {
      chip.addEventListener('click', () => {
        const value = chip.dataset.stageChip;
        if (chip.dataset.status) {
          statusFilter.value = chip.dataset.status;
          stage = '';
          for (const other of document.querySelectorAll('[data-stage-chip]')) {
            other.classList.remove('active');
          }
          applyFilter();
        } else {
          setStage(value);
        }
      });
    }
    window.addEventListener('hashchange', () => reveal(location.hash.slice(1)));
    showClaim(null);
    if (location.hash) reveal(location.hash.slice(1));
    applyFilter();
