/* init.js — clock bar and timestamp popovers
 * Timezone list is injected server-side via #app-config (application/json).
 */
(function () {
  var configEl = document.getElementById('app-config');
  if (!configEl) return;
  var _TZ;
  try { _TZ = JSON.parse(configEl.textContent); } catch (e) { return; }
  if (!Array.isArray(_TZ) || _TZ.length === 0) return;

  /* ── helpers ── */
  function _fmt(date, tz) {
    try {
      return new Intl.DateTimeFormat('en-GB', {
        timeZone: tz,
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false
      }).format(date).replace(',', '');
    } catch (e) { return '—'; }
  }

  function _fmtTooltip(date, tz) {
    try {
      return new Intl.DateTimeFormat('en-GB', {
        timeZone: tz,
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false, timeZoneName: 'short'
      }).format(date).replace(',', '');
    } catch (e) { return '—'; }
  }

  function _label(tz) {
    return tz === 'UTC' ? 'UTC' : tz.split('/').pop().replace(/_/g, '\u00a0');
  }

  /* ── live clock ── */
  var _bar = document.getElementById('clock-bar');
  function _tick() {
    if (!_bar) return;
    var now = new Date();
    var frag = document.createDocumentFragment();
    _TZ.forEach(function (tz, i) {
      if (i > 0) {
        var sep = document.createElement('span');
        sep.style.cssText = 'color:#6c757d;margin:0 .6rem;';
        sep.textContent = '|';
        frag.appendChild(sep);
      }
      var lbl = document.createElement('span');
      lbl.style.color = '#6c757d';
      lbl.className = 'me-1';
      lbl.textContent = _label(tz) + ':';
      frag.appendChild(lbl);
      var val = document.createElement('span');
      val.className = 'font-monospace';
      val.style.color = '#0dcaf0';
      val.textContent = _fmt(now, tz);
      frag.appendChild(val);
    });
    _bar.textContent = '';
    _bar.appendChild(frag);
  }
  _tick();
  setInterval(_tick, 1000);

  /* ── timestamp popovers (click to expand) ── */
  function _initPopovers() {
    var _allPopovers = [];

    document.querySelectorAll('[data-utc]').forEach(function (el) {
      var raw = el.getAttribute('data-utc');
      if (!raw) return;
      var iso = (raw.endsWith('Z') || raw.includes('+')) ? raw : raw + 'Z';
      var date = new Date(iso);
      if (isNaN(date.getTime())) return;

      // Build popover content: one row per configured TZ
      var content = _TZ.map(function (tz) {
        return '<div style="white-space:nowrap;font-family:monospace">' +
               '<span style="color:#6c757d;display:inline-block;min-width:7rem">' +
               tz.split('/').pop().replace(/_/g, '\u00a0') + '</span>' +
               _fmtTooltip(date, tz) +
               '</div>';
      }).join('');

      el.style.cursor = 'pointer';
      el.style.borderBottom = '1px dotted rgba(255,255,255,0.35)';

      // Extend Bootstrap's default allowList to permit inline styles on div/span
      // so we can remove the unsafe sanitize:false option.
      var customAllowList = Object.assign({}, bootstrap.Popover.Default.allowList);
      customAllowList['div']  = (customAllowList['div']  || []).concat(['style']);
      customAllowList['span'] = (customAllowList['span'] || []).concat(['style']);

      var pop = new bootstrap.Popover(el, {
        trigger: 'manual',
        html: true,
        allowList: customAllowList,
        container: 'body',
        placement: 'top',
        title: '<i class="bi bi-clock me-1"></i>Timezones',
        content: content
      });

      el.addEventListener('click', function (e) {
        e.stopPropagation();
        e.preventDefault();
        var isVisible = el.getAttribute('aria-describedby');
        // Close all others first
        _allPopovers.forEach(function (p) {
          if (p._element !== el) p.hide();
        });
        if (isVisible) {
          pop.hide();
        } else {
          pop.show();
        }
      });

      _allPopovers.push(pop);
    });

    // Click outside → close all
    document.addEventListener('click', function () {
      _allPopovers.forEach(function (p) { p.hide(); });
    });
  }

  /* Run after page settles so dynamically-added elements are in DOM */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _initPopovers);
  } else {
    _initPopovers();
  }
})();
