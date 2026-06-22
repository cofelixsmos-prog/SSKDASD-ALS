export function initTheme() {
  const saved = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
}

export function toggleTheme() {
  const html = document.documentElement;
  const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
}

export function bindThemeToggle(btnId) {
  initTheme();
  const btn = document.getElementById(btnId);
  if (btn) btn.addEventListener('click', toggleTheme);
}
