// Toggle sidebar (mobile)
const sidebarToggle = document.getElementById('sidebarToggle');
const sidebar = document.getElementById('sidebar');

if (sidebarToggle && sidebar) {
  sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('open');
  });

  document.addEventListener('click', (e) => {
    if (window.innerWidth <= 768 && !sidebar.contains(e.target) && e.target !== sidebarToggle) {
      sidebar.classList.remove('open');
    }
  });
}

// Relógio de Brasília
function atualizarRelogio() {
  const el = document.getElementById('relogio');
  if (!el) return;
  const now = new Date();
  const options = {
    timeZone: 'America/Sao_Paulo',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  };
  const partes = new Intl.DateTimeFormat('pt-BR', options).formatToParts(now);
  const p = {};
  partes.forEach(x => { p[x.type] = x.value; });
  el.textContent = `${p.day}/${p.month}/${p.year} ${p.hour}:${p.minute}:${p.second} (Brasília)`;
}

atualizarRelogio();
setInterval(atualizarRelogio, 1000);

// Confirmação para ações destrutivas
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', (e) => {
    if (!confirm(el.dataset.confirm)) e.preventDefault();
  });
});

// Auto-dismiss alerts após 5s
setTimeout(() => {
  document.querySelectorAll('.alert-msg').forEach(el => {
    el.style.transition = 'opacity 0.5s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 500);
  });
}, 5000);
