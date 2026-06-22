// Shared Duolingo-style animation helpers

// Count a number up from 0 to its target. Reads the target from the
// element's text content (strips %, etc.) and re-applies the suffix.
export function countUp(el, duration = 900) {
  if (!el) return;
  const raw = el.textContent.trim();
  const match = raw.match(/^(\d+(?:\.\d+)?)(.*)$/);
  if (!match) return;
  const target = parseFloat(match[1]);
  const suffix = match[2] || '';
  const decimals = (match[1].split('.')[1] || '').length;
  const start = performance.now();
  function tick(now) {
    const p = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    const val = (target * eased).toFixed(decimals);
    el.textContent = val + suffix;
    if (p < 1) requestAnimationFrame(tick);
    else el.textContent = match[1] + suffix;
  }
  requestAnimationFrame(tick);
}

// Animate every .stat-value on the page once they're populated.
export function animateStats(selector = '.stat-value') {
  document.querySelectorAll(selector).forEach((el, i) => {
    setTimeout(() => countUp(el), i * 80);
  });
}

// Confetti burst from the top of the screen.
export function fireConfetti(count = 80) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const colors = ['#58cc02', '#4a7dff', '#f5a623', '#ff4b4b', '#a855f7', '#06b6d4'];
  for (let i = 0; i < count; i++) {
    const piece = document.createElement('div');
    piece.className = 'confetti-piece';
    piece.style.left = Math.random() * 100 + 'vw';
    piece.style.background = colors[Math.floor(Math.random() * colors.length)];
    piece.style.animationDuration = (1.8 + Math.random() * 1.4) + 's';
    piece.style.animationDelay = (Math.random() * 0.3) + 's';
    piece.style.width = piece.style.height = (7 + Math.random() * 8) + 'px';
    if (Math.random() > 0.5) piece.style.borderRadius = '50%';
    document.body.appendChild(piece);
    setTimeout(() => piece.remove(), 3600);
  }
}

// Add a one-shot CSS class then auto-remove it (re-triggerable).
export function pulse(el, className, ms = 800) {
  if (!el) return;
  el.classList.remove(className);
  void el.offsetWidth;
  el.classList.add(className);
  setTimeout(() => el.classList.remove(className), ms);
}
