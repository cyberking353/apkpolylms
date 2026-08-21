/* ══════════════════════════════════════
   Al-Hikma LMS — main.js
   Each feature block is wrapped independently so a failure in one
   (e.g. mobile sidebar setup on a page with unusual markup) can never
   prevent another feature (e.g. the confirm modal) from initializing.
   ══════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {

  /* ── Custom confirm modal (replaces native confirm()) ── */
  /* This runs FIRST and is the most critical piece, so it's isolated
     and guaranteed to set up regardless of what else is on the page. */
  try {
    const overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';
    overlay.id = 'confirmOverlay';
    overlay.innerHTML =
      '<div class="confirm-box">' +
        '<div class="confirm-icon" id="confirmIcon"><i data-lucide="triangle-alert"></i></div>' +
        '<div class="confirm-msg" id="confirmMsg"></div>' +
        '<div class="confirm-acts">' +
          '<button type="button" class="btn btn-ghost btn-sm" id="confirmCancel">Cancel</button>' +
          '<button type="button" class="btn btn-danger btn-sm" id="confirmOk">Confirm</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);
    if (window.lucide) lucide.createIcons();

    const msgEl     = document.getElementById('confirmMsg');
    const okBtn     = document.getElementById('confirmOk');
    const cancelBtn = document.getElementById('confirmCancel');
    const iconEl    = document.getElementById('confirmIcon');
    let pendingAction = null;

    function closeModal() {
      overlay.classList.remove('open');
      pendingAction = null;
    }
    function openModal(message, onConfirm) {
      msgEl.textContent = message;
      pendingAction = onConfirm;
      overlay.classList.add('open');
    }
    okBtn.addEventListener('click', () => {
      const action = pendingAction;
      closeModal();
      if (action) action();
    });
    cancelBtn.addEventListener('click', closeModal);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

    // Intercept any element with data-confirm="message" — works for
    // <a href> links and <button> elements inside (or referencing) a <form>.
    // Delegated on document so it also works for HTMX-swapped content.
    document.addEventListener('click', function (e) {
      const el = e.target.closest('[data-confirm]');
      if (!el) return;
      e.preventDefault();
      const message = el.getAttribute('data-confirm');
      const isDestructive = el.classList.contains('btn-danger');

      if (isDestructive) {
        iconEl.innerHTML = '<i data-lucide="triangle-alert"></i>';
        iconEl.style.background = 'var(--rose-bg)';
        iconEl.style.color = 'var(--rose)';
        okBtn.className = 'btn btn-danger btn-sm';
        okBtn.textContent = 'Delete';
      } else {
        iconEl.innerHTML = '<i data-lucide="check"></i>';
        iconEl.style.background = 'var(--green-bg)';
        iconEl.style.color = 'var(--green)';
        okBtn.className = 'btn btn-teal btn-sm';
        okBtn.textContent = 'Confirm';
      }
      if (window.lucide) lucide.createIcons();

      openModal(message, () => {
        // Temporarily remove data-confirm so the re-triggered click
        // passes through without being intercepted again.
        el.removeAttribute('data-confirm');
        el.click();
        // Restore it after a tick so the button remains protected
        // if the modal is dismissed and the user clicks again.
        setTimeout(() => el.setAttribute('data-confirm', message), 100);
      });
    });
  } catch (err) {
    console.error('Confirm modal setup failed:', err);
  }

  /* ── Mobile nav toggle ── */
  try {
    const hamburger = document.getElementById('hamburger');
    const navLinks  = document.querySelector('.nav-links');
    if (hamburger && navLinks) {
      hamburger.addEventListener('click', () => navLinks.classList.toggle('open'));
      navLinks.querySelectorAll('a').forEach(a =>
        a.addEventListener('click', () => navLinks.classList.remove('open'))
      );
    }
  } catch (err) { console.error('Mobile nav setup failed:', err); }

  /* ── Mobile dashboard sidebar toggle ── */
  try {
    const sb = document.getElementById('sidebar');
    if (sb) {
      const btn = document.createElement('button');
      btn.className = 'mob-sb-toggle';
      btn.setAttribute('aria-label', 'Open menu');
      document.body.appendChild(btn);

      const overlay = document.createElement('div');
      overlay.className = 'mob-sb-overlay';
      document.body.appendChild(overlay);

      function setSbIcon(name) {
        btn.innerHTML = '<i data-lucide="' + name + '"></i>';
        if (window.lucide) lucide.createIcons();
      }
      function openSb() {
        sb.classList.add('mob-open');
        overlay.classList.add('open');
        setSbIcon('x');
      }
      function closeSb() {
        sb.classList.remove('mob-open');
        overlay.classList.remove('open');
        setSbIcon('menu');
      }
      setSbIcon('menu');
      btn.addEventListener('click', () => sb.classList.contains('mob-open') ? closeSb() : openSb());
      overlay.addEventListener('click', closeSb);
      sb.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
        if (window.innerWidth <= 900) closeSb();
      }));
    }
  } catch (err) { console.error('Mobile sidebar setup failed:', err); }

  /* ── User dropdown ── */
  try {
    const avTrigger = document.getElementById('av-trigger');
    const dropdown  = document.getElementById('user-dropdown');
    if (avTrigger && dropdown) {
      avTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdown.classList.toggle('open');
      });
      document.addEventListener('click', () => dropdown.classList.remove('open'));
    }
  } catch (err) { console.error('User dropdown setup failed:', err); }

  /* ── Department pill checkboxes — visual toggle ── */
  try {
    document.querySelectorAll('.dept-pill').forEach(label => {
      const cb = label.querySelector('input[type=checkbox]');
      if (!cb) return;
      function updatePill() {
        if (cb.checked) {
          label.classList.add('selected');
          label.style.borderColor = 'var(--teal)';
          label.style.background  = 'var(--teal-bg)';
        } else {
          label.classList.remove('selected');
          label.style.borderColor = '';
          label.style.background  = '';
        }
      }
      updatePill();
      cb.addEventListener('change', updatePill);
    });
  } catch (err) { console.error('Department pill setup failed:', err); }

  /* ── Password eye toggle ── */
  try {
    document.querySelectorAll('.pw-eye').forEach(btn => {
      btn.addEventListener('click', () => {
        const input = btn.previousElementSibling;
        if (!input) return;
        input.type = input.type === 'password' ? 'text' : 'password';
        btn.innerHTML = '<i data-lucide="' + (input.type === 'password' ? 'eye' : 'eye-off') + '"></i>';
        if (window.lucide) lucide.createIcons();
      });
    });
  } catch (err) { console.error('Password eye toggle setup failed:', err); }

  /* ── Flash message auto-dismiss ── */
  try {
    document.querySelectorAll('.flash').forEach(flash => {
      setTimeout(() => {
        flash.style.opacity = '0';
        flash.style.transform = 'translateX(20px)';
        flash.style.transition = '.3s';
        setTimeout(() => flash.remove(), 300);
      }, 4000);
    });
  } catch (err) { console.error('Flash auto-dismiss setup failed:', err); }

  /* ── Re-render Lucide icons after HTMX swaps ── */
  try {
    document.body.addEventListener('htmx:afterSwap', () => { if (window.lucide) lucide.createIcons(); });
    document.body.addEventListener('htmx:afterSettle', () => { if (window.lucide) lucide.createIcons(); });
  } catch (err) { console.error('Lucide htmx re-render setup failed:', err); }

  /* ── Scroll animations ── */
  try {
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(e => {
          if (e.isIntersecting) {
            e.target.style.opacity = '1';
            e.target.style.transform = 'translateY(0)';
          }
        });
      }, { threshold: 0.08 });

      document.querySelectorAll('.card, .step, .bi, .stb').forEach(el => {
        if (window.innerWidth > 600) {
          el.style.opacity = '0';
          el.style.transform = 'translateY(18px)';
          el.style.transition = 'opacity .45s ease, transform .45s ease';
          observer.observe(el);
        }
      });
    }
  } catch (err) { console.error('Scroll animation setup failed:', err); }

  /* ── Progress bar animation ── */
  try {
    document.querySelectorAll('.prog-fill[data-width]').forEach(bar => {
      const target = bar.dataset.width;
      bar.style.width = '0%';
      setTimeout(() => { bar.style.width = target; }, 100);
    });
  } catch (err) { console.error('Progress bar animation setup failed:', err); }

  /* ── Navbar scroll effect ── */
  try {
    const nav = document.querySelector('.nav');
    if (nav) {
      const updateNav = () => {
        nav.style.boxShadow = window.scrollY > 20 ? '0 4px 20px rgba(13,15,26,.12)' : '';
      };
      window.addEventListener('scroll', updateNav, { passive: true });
      updateNav();
    }
  } catch (err) { console.error('Navbar scroll effect setup failed:', err); }

});
