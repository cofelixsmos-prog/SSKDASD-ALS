// Glass distortion + 3D tilt effect
// Auto-applies to cards, stat cards, buttons and other interactive elements.
// Injected globally via guard.js.

if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  // Respect user preference — bail out entirely
} else {
  const TILT_SEL = [
    '.card', '.stat-card', '.quiz-hist-card', '.prestart-card',
    '.result-card', '.monitor-header-card', '.batch-card',
    '.review-q-card', '.ai-review-card', '.score-box',
    '.btn-primary', '.btn-secondary', '.btn-danger',
    '.login-btn', '.nav-item',
  ].join(',');

  const MAX_TILT = 10;    // degrees
  const LENS_R  = 90;     // glass lens radius px

  // ── Glass lens (backdrop-filter circle that follows cursor) ──────────────
  const lens = document.createElement('div');
  lens.id = '__glass_lens__';
  Object.assign(lens.style, {
    position: 'fixed',
    pointerEvents: 'none',
    zIndex: '9998',
    width: LENS_R * 2 + 'px',
    height: LENS_R * 2 + 'px',
    borderRadius: '50%',
    backdropFilter: 'blur(3px) saturate(1.6) brightness(1.08)',
    WebkitBackdropFilter: 'blur(3px) saturate(1.6) brightness(1.08)',
    border: '1.5px solid rgba(255,255,255,0.22)',
    boxShadow: '0 2px 20px rgba(0,0,0,0.08), inset 0 1.5px 0 rgba(255,255,255,0.35), inset 0 -1px 0 rgba(0,0,0,0.05)',
    transform: 'translate(-50%,-50%) scale(0)',
    transition: 'transform 0.25s cubic-bezier(0.34,1.56,0.64,1), opacity 0.2s',
    opacity: '0',
    left: '-200px',
    top: '-200px',
    willChange: 'transform, left, top',
  });
  document.body.appendChild(lens);

  let lensRaf = null;
  let lensVis = false;

  function showLens(x, y) {
    if (!lensVis) {
      lensVis = true;
      lens.style.transform = 'translate(-50%,-50%) scale(1)';
      lens.style.opacity = '1';
    }
    if (lensRaf) return;
    lensRaf = requestAnimationFrame(() => {
      lens.style.left = x + 'px';
      lens.style.top  = y + 'px';
      lensRaf = null;
    });
  }

  function hideLens() {
    lensVis = false;
    lens.style.transform = 'translate(-50%,-50%) scale(0)';
    lens.style.opacity = '0';
  }

  // ── Per-element tilt + shine ─────────────────────────────────────────────
  function addShine(el) {
    if (el._glassShine) return el._glassShine;
    const s = document.createElement('div');
    s.className = '__glass_shine__';
    Object.assign(s.style, {
      position: 'absolute',
      inset: '0',
      borderRadius: 'inherit',
      pointerEvents: 'none',
      zIndex: '2',
      opacity: '0',
      transition: 'opacity 0.18s',
      background: 'radial-gradient(circle at 50% 50%, rgba(255,255,255,0.22) 0%, transparent 60%)',
      mixBlendMode: 'overlay',
    });
    // only add to positioned elements (cards etc.) not buttons
    const tag = el.tagName.toLowerCase();
    if (tag !== 'button') {
      const pos = getComputedStyle(el).position;
      if (pos === 'static') el.style.position = 'relative';
      el.style.overflow = 'hidden';
      el.appendChild(s);
    }
    el._glassShine = s;
    return s;
  }

  function onMove(el, e) {
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width  / 2;
    const cy = rect.top  + rect.height / 2;
    const dx = (e.clientX - cx) / (rect.width  / 2);
    const dy = (e.clientY - cy) / (rect.height / 2);

    // Clamp to ±1
    const rx = Math.max(-1, Math.min(1, dx));
    const ry = Math.max(-1, Math.min(1, dy));

    const rotY =  rx * MAX_TILT;
    const rotX = -ry * MAX_TILT;
    const zShift = 6;

    el.style.transform = `perspective(700px) rotateX(${rotX}deg) rotateY(${rotY}deg) translateZ(${zShift}px)`;
    el.style.transition = 'transform 0.04s linear, box-shadow 0.04s linear';
    el.style.boxShadow = `${-rotY * 0.6}px ${rotX * 0.6}px 24px rgba(0,0,0,0.18)`;

    const shine = el._glassShine;
    if (shine) {
      const px = ((e.clientX - rect.left) / rect.width)  * 100;
      const py = ((e.clientY - rect.top)  / rect.height) * 100;
      shine.style.background = `radial-gradient(circle at ${px}% ${py}%, rgba(255,255,255,0.26) 0%, transparent 58%)`;
      shine.style.opacity = '1';
    }

    showLens(e.clientX, e.clientY);
  }

  function onLeave(el) {
    el.style.transform = '';
    el.style.boxShadow = '';
    el.style.transition = 'transform 0.5s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.4s ease';
    const shine = el._glassShine;
    if (shine) shine.style.opacity = '0';
    hideLens();
  }

  function initEl(el) {
    if (el._glassInit) return;
    el._glassInit = true;
    addShine(el);
    el.addEventListener('mousemove',  e => onMove(el, e), { passive: true });
    el.addEventListener('mouseleave', () => onLeave(el));
  }

  function initAll() {
    try {
      document.querySelectorAll(TILT_SEL).forEach(el => {
        // skip elements inside the glass lens itself
        if (el.closest('#__glass_lens__')) return;
        initEl(el);
      });
    } catch {}
  }

  // Init after DOM is ready + watch for dynamically added elements
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

  // Re-init whenever new nodes appear (quiz results, modals, etc.)
  new MutationObserver(mutations => {
    let changed = false;
    for (const m of mutations) {
      if (m.addedNodes.length) { changed = true; break; }
    }
    if (changed) initAll();
  }).observe(document.body, { childList: true, subtree: true });
}
