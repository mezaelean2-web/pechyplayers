(() => {
  const filter = document.getElementById('wallet-movement-filter');
  if (!filter) return;
  const rows = [...document.querySelectorAll('[data-movement-type]')];
  const empty = document.querySelector('.reseller-wallet-filter-empty');
  filter.addEventListener('change', () => {
    let visible = 0;
    rows.forEach((row) => {
      const show = filter.value === 'all' || row.dataset.movementType === filter.value;
      row.hidden = !show;
      if (show) visible += 1;
    });
    if (empty) empty.hidden = visible !== 0;
  });
})();
