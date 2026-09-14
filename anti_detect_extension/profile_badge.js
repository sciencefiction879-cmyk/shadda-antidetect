// profile_badge.js - Displays active profile name in window title & on-screen badge
(function() {
  if (typeof window === 'undefined') return;

  const profileName = window.__SHADDA_PROFILE_NAME__ || "Shadda Profile";
  const profileColor = window.__SHADDA_PROFILE_COLOR__ || "#0ea5e9";
  const proxyLabel = window.__SHADDA_PROXY_LABEL__ || "Direct";
  const suffix = ` — [${profileName}]`;

  // 1. Synchronize Window & Tab Title
  function updateTitle() {
    try {
      let cur = document.title || "";
      if (cur) {
        const clean = cur.replace(/\s*—\s*\[.*?\]\s*$/, '').trim();
        const formatted = clean ? `${clean}${suffix}` : profileName;
        if (document.title !== formatted) {
          document.title = formatted;
        }
      } else {
        document.title = profileName;
      }
    } catch (e) {}
  }

  try {
    const origDesc = Object.getOwnPropertyDescriptor(Document.prototype, 'title') || Object.getOwnPropertyDescriptor(HTMLDocument.prototype, 'title');
    if (origDesc && origDesc.set) {
      const nativeSet = origDesc.set;
      const nativeGet = origDesc.get;
      Object.defineProperty(document, 'title', {
        get: function() {
          return nativeGet ? nativeGet.call(document) : document.title;
        },
        set: function(val) {
          const raw = String(val || '');
          const clean = raw.replace(/\s*—\s*\[.*?\]\s*$/, '').trim();
          const formatted = clean ? `${clean}${suffix}` : profileName;
          return nativeSet.call(document, formatted);
        },
        configurable: true
      });
    }
  } catch (e) {}

  try {
    const observer = new MutationObserver(updateTitle);
    observer.observe(document.documentElement || document, { childList: true, subtree: true });
  } catch (e) {}
  updateTitle();
  setInterval(updateTitle, 1200);

  // 2. Render In-Browser Profile Header Pill (only top-level frame)
  if (window !== window.top) return;
  if (window.__SHADDA_PROFILE_BADGE_INJECTED__) return;
  window.__SHADDA_PROFILE_BADGE_INJECTED__ = true;

  function createBadgeDOM() {
    if (document.getElementById('shadda-profile-indicator')) return;

    const badge = document.createElement('div');
    badge.id = 'shadda-profile-indicator';
    badge.style.position = 'fixed';
    badge.style.top = '10px';
    badge.style.left = '14px';
    badge.style.zIndex = '2147483646';
    badge.style.display = 'flex';
    badge.style.alignItems = 'center';
    badge.style.gap = '8px';
    badge.style.background = 'rgba(15, 23, 42, 0.94)';
    badge.style.backdropFilter = 'blur(12px)';
    badge.style.webkitBackdropFilter = 'blur(12px)';
    badge.style.border = '1px solid rgba(255, 255, 255, 0.18)';
    badge.style.borderRadius = '9999px';
    badge.style.padding = '5px 12px 5px 10px';
    badge.style.fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";
    badge.style.fontSize = '12px';
    badge.style.fontWeight = '700';
    badge.style.color = '#f8fafc';
    badge.style.boxShadow = '0 4px 15px rgba(0, 0, 0, 0.45)';
    badge.style.userSelect = 'none';
    badge.style.transition = 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)';
    badge.style.cursor = 'grab';

    // Dot indicator with profile color
    const dot = document.createElement('span');
    dot.style.display = 'inline-block';
    dot.style.width = '9px';
    dot.style.height = '9px';
    dot.style.borderRadius = '50%';
    dot.style.background = profileColor;
    dot.style.boxShadow = `0 0 8px ${profileColor}`;
    dot.style.flexShrink = '0';
    badge.appendChild(dot);

    // Profile Name Label
    const nameSpan = document.createElement('span');
    nameSpan.id = 'shadda-badge-name-text';
    nameSpan.style.letterSpacing = '0.2px';
    nameSpan.style.maxWidth = '220px';
    nameSpan.style.overflow = 'hidden';
    nameSpan.style.textOverflow = 'ellipsis';
    nameSpan.style.whiteSpace = 'nowrap';
    nameSpan.style.color = '#ffffff';
    nameSpan.textContent = profileName;
    badge.appendChild(nameSpan);

    // Proxy Label
    const proxySpan = document.createElement('span');
    proxySpan.id = 'shadda-badge-proxy-text';
    proxySpan.style.fontSize = '10px';
    proxySpan.style.opacity = '0.85';
    proxySpan.style.color = '#38bdf8';
    proxySpan.style.paddingLeft = '4px';
    proxySpan.style.borderLeft = '1px solid rgba(255, 255, 255, 0.18)';
    proxySpan.style.whiteSpace = 'nowrap';
    proxySpan.textContent = proxyLabel;
    badge.appendChild(proxySpan);

    // Minimize Button
    const minBtn = document.createElement('button');
    minBtn.id = 'shadda-badge-min-btn';
    minBtn.type = 'button';
    minBtn.style.background = 'transparent';
    minBtn.style.border = 'none';
    minBtn.style.color = '#94a3b8';
    minBtn.style.cursor = 'pointer';
    minBtn.style.fontSize = '12px';
    minBtn.style.padding = '0 2px';
    minBtn.style.marginLeft = '4px';
    minBtn.style.lineHeight = '1';
    minBtn.title = 'Minimize / Expand badge';
    minBtn.textContent = '—';

    let isMin = false;
    minBtn.onclick = (e) => {
      e.stopPropagation();
      isMin = !isMin;
      if (isMin) {
        proxySpan.style.display = 'none';
        nameSpan.textContent = profileName.length > 10 ? (profileName.substring(0, 10) + '..') : profileName;
        badge.style.padding = '4px 8px';
        minBtn.textContent = '+';
      } else {
        proxySpan.style.display = 'inline';
        nameSpan.textContent = profileName;
        badge.style.padding = '5px 12px 5px 10px';
        minBtn.textContent = '—';
      }
    };
    badge.appendChild(minBtn);

    // Draggable behavior
    let isDragging = false, startX = 0, startY = 0, initialLeft = 0, initialTop = 0;
    badge.addEventListener('mousedown', (e) => {
      if (e.target === minBtn) return;
      isDragging = true;
      startX = e.clientX;
      startY = e.clientY;
      const rect = badge.getBoundingClientRect();
      initialLeft = rect.left;
      initialTop = rect.top;
      badge.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      badge.style.left = `${Math.max(4, initialLeft + e.clientX - startX)}px`;
      badge.style.top = `${Math.max(4, initialTop + e.clientY - startY)}px`;
      badge.style.right = 'auto';
    });

    window.addEventListener('mouseup', () => {
      if (isDragging) {
        isDragging = false;
        badge.style.cursor = 'grab';
      }
    });

    const root = document.body || document.documentElement;
    if (root) {
      root.appendChild(badge);
    }
  }

  function ensureInjected() {
    if (document.getElementById('shadda-profile-indicator')) return;
    createBadgeDOM();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureInjected);
  }
  window.addEventListener('load', ensureInjected);
  ensureInjected();

  // Fast initial checks
  let checks = 0;
  const initialTimer = setInterval(() => {
    checks++;
    ensureInjected();
    if (checks >= 15 || document.getElementById('shadda-profile-indicator')) {
      clearInterval(initialTimer);
    }
  }, 300);

  // Persistent background heartbeat to survive SPA full-page DOM rewrites
  setInterval(() => {
    if (!document.getElementById('shadda-profile-indicator')) {
      ensureInjected();
    }
  }, 2000);
})();
