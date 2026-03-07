'use strict';

// ── Utilities ──────────────────────────────────────────────────────────────

function copyField(elementId, btn) {
  const text = document.getElementById(elementId).innerText;
  navigator.clipboard.writeText(text).then(() => {
    const icon = btn.querySelector('i');
    icon.className = 'bi bi-clipboard-check text-success';
    setTimeout(() => { icon.className = 'bi bi-clipboard'; }, 2000);
  });
}

function debounce(fn, delay) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

// ── Live search ────────────────────────────────────────────────────────────

const searchInput = document.getElementById('search-input');
const artifactGrid = document.getElementById('artifact-grid');

function buildCard(a) {
  const tagsHtml = (a.tags || []).map(tag =>
    `<a href="/?tag=${encodeURIComponent(tag)}"
        class="badge bg-secondary text-decoration-none tag-pill"
        style="position:relative;z-index:1;">${escapeHtml(tag)}</a>`
  ).join(' ');

  const locationSnippet = a.location.length > 80
    ? a.location.slice(0, 80) + '…'
    : a.location;

  return `
    <div class="col">
      <div class="card h-100 border-secondary bg-dark card-hover">
        <div class="card-body">
          <h6 class="card-title text-light mb-1">
            <a href="/artifact/${a.id}"
               class="text-decoration-none text-light stretched-link artifact-link">
              ${escapeHtml(a.name)}
            </a>
          </h6>
          <p class="card-text font-monospace text-success small mb-2 location-snippet">
            ${escapeHtml(locationSnippet)}
          </p>
          <div class="d-flex flex-wrap gap-1 mt-auto">${tagsHtml}</div>
        </div>
        <div class="card-footer text-secondary small border-secondary">
          <i class="bi bi-clock me-1"></i>${escapeHtml(a.updated_at.slice(0, 19) + 'Z')}
          &nbsp;·&nbsp;
          <i class="bi bi-person me-1"></i>${escapeHtml(a.updated_by)}
        </div>
      </div>
    </div>`;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function emptyState(search) {
  return `
    <div class="col-12">
      <div class="text-center text-secondary py-5">
        <i class="bi bi-inbox display-4"></i>
        <p class="mt-3">No artifacts found for <em>${escapeHtml(search)}</em>.
          <a href="/">Clear search</a>
        </p>
      </div>
    </div>`;
}

async function liveSearch(query) {
  const activeTag = new URLSearchParams(window.location.search).get('tag') || '';
  const params = new URLSearchParams({ q: query });
  if (activeTag) params.set('tag', activeTag);

  try {
    const resp = await fetch(`/api/artifacts?${params}`);
    if (!resp.ok) return;
    const artifacts = await resp.json();

    if (!artifactGrid) return;
    if (artifacts.length === 0) {
      artifactGrid.innerHTML = emptyState(query);
    } else {
      artifactGrid.innerHTML = artifacts.map(buildCard).join('');
    }

    // Update browser URL without reload
    const newUrl = query
      ? `/?q=${encodeURIComponent(query)}${activeTag ? '&tag=' + encodeURIComponent(activeTag) : ''}`
      : `/${activeTag ? '?tag=' + encodeURIComponent(activeTag) : ''}`;
    history.replaceState(null, '', newUrl);
  } catch (_) {
    // Network error — fall back gracefully (form still works)
  }
}

if (searchInput && artifactGrid) {
  searchInput.addEventListener('input', debounce(function () {
    const q = this.value.trim();
    if (q.length === 0) {
      // Reload to restore full list
      const activeTag = new URLSearchParams(window.location.search).get('tag') || '';
      window.location.href = activeTag ? `/?tag=${encodeURIComponent(activeTag)}` : '/';
      return;
    }
    liveSearch(q);
  }, 350));
}

// ── Tag autocomplete ───────────────────────────────────────────────────────

let allTags = [];

async function fetchTags() {
  try {
    const resp = await fetch('/api/tags');
    if (resp.ok) allTags = await resp.json();
  } catch (_) {}
}

function autocompleteTag(e) {
  const input = e.target;
  const val = input.value;
  const lastComma = val.lastIndexOf(',');
  const current = val.slice(lastComma + 1).trimStart().toLowerCase();

  removeDropdown();
  if (!current || allTags.length === 0) return;

  const matches = allTags
    .filter(t => t.name.toLowerCase().includes(current) &&
                 !val.toLowerCase().split(',').map(s => s.trim()).includes(t.name.toLowerCase()))
    .slice(0, 8);

  if (matches.length === 0) return;

  const dropdown = document.createElement('ul');
  dropdown.className = 'list-group position-absolute shadow z-3';
  dropdown.id = 'tag-dropdown';
  dropdown.style.cssText = 'max-width:300px;cursor:pointer;';

  matches.forEach(tag => {
    const li = document.createElement('li');
    li.className = 'list-group-item list-group-item-action bg-dark text-light border-secondary small py-1';
    li.textContent = tag.name;
    li.addEventListener('mousedown', (ev) => {
      ev.preventDefault();
      const prefix = lastComma >= 0 ? val.slice(0, lastComma + 1) + ' ' : '';
      input.value = prefix + tag.name + ', ';
      removeDropdown();
      input.focus();
    });
    dropdown.appendChild(li);
  });

  input.parentNode.style.position = 'relative';
  input.insertAdjacentElement('afterend', dropdown);
}

function removeDropdown() {
  const existing = document.getElementById('tag-dropdown');
  if (existing) existing.remove();
}

document.addEventListener('click', (e) => {
  if (!e.target.closest('#tag-dropdown') &&
      e.target.id !== 'tags-input' &&
      e.target.id !== 'ioc-tags-input' &&
      e.target.id !== 'event-tags-input') {
    removeDropdown();
  }
});

const tagsInputEl = document.getElementById('tags-input');
if (tagsInputEl) {
  fetchTags();
}

// ── IOC live search ─────────────────────────────────────────────────────────

const iocSearchInput = document.getElementById('ioc-search-input');
const iocGrid = document.getElementById('ioc-grid');

const SEV_BADGE = {
  Low:      'bg-secondary',
  Medium:   'bg-warning text-dark',
  High:     'bg-danger',
  Critical: 'bg-danger',
};

function buildIocCard(ioc) {
  const tagsHtml = (ioc.tags || []).map(tag =>
    `<a href="/iocs/?tag=${encodeURIComponent(tag)}"
        class="badge bg-secondary text-decoration-none tag-pill"
        style="position:relative;z-index:1;">${escapeHtml(tag)}</a>`
  ).join(' ');

  const badgeClass = SEV_BADGE[ioc.severity] || 'bg-secondary';
  const caseHtml = ioc.category
    ? `<span class="badge bg-dark border border-secondary text-secondary small font-monospace">
         ${escapeHtml(ioc.category.slice(0, 30))}${ioc.category.length > 30 ? '…' : ''}
       </span>`
    : '';
  const borderClass = ioc.severity === 'Critical' ? 'border-danger' : 'border-secondary';
  const indicator = escapeHtml(ioc.primary_indicator || '');

  return `
    <div class="col">
      <div class="card h-100 bg-dark card-hover ${borderClass}">
        <div class="card-body">
          <div class="d-flex justify-content-between align-items-start mb-2">
            <span class="badge ${badgeClass}">${escapeHtml(ioc.severity)}</span>
            ${caseHtml}
          </div>
          <p class="card-text font-monospace text-success small mb-2 text-break">
            <a href="/iocs/${ioc.id}"
               class="text-decoration-none text-success stretched-link">
              ${indicator}
            </a>
          </p>
          <div class="d-flex flex-wrap gap-1 mt-auto">${tagsHtml}</div>
        </div>
        <div class="card-footer text-secondary small border-secondary">
          <i class="bi bi-clock me-1"></i>${escapeHtml(ioc.updated_at.slice(0, 19) + 'Z')}
          &nbsp;·&nbsp;
          <i class="bi bi-person me-1"></i>${escapeHtml(ioc.updated_by)}
        </div>
      </div>
    </div>`;
}

function iocEmptyState(search) {
  return `
    <div class="col-12">
      <div class="text-center text-secondary py-5">
        <i class="bi bi-shield display-4"></i>
        <p class="mt-3">No IOCs found for <em>${escapeHtml(search)}</em>.
          <a href="/iocs/">Clear search</a>
        </p>
      </div>
    </div>`;
}

async function liveSearchIocs(query) {
  const params = new URLSearchParams(window.location.search);
  // Rename legacy 'case' param to 'category' for the API call
  if (params.has('case')) { params.set('category', params.get('case')); params.delete('case'); }
  params.set('q', query);

  try {
    const resp = await fetch(`/api/iocs?${params}`);
    if (!resp.ok) return;
    const iocs = await resp.json();

    if (!iocGrid) return;
    iocGrid.innerHTML = iocs.length === 0
      ? iocEmptyState(query)
      : iocs.map(buildIocCard).join('');

    // Update URL
    const newParams = new URLSearchParams(window.location.search);
    if (query) {
      newParams.set('q', query);
    } else {
      newParams.delete('q');
    }
    history.replaceState(null, '', `/iocs/?${newParams}`);
  } catch (_) {}
}

if (iocSearchInput && iocGrid) {
  iocSearchInput.addEventListener('input', debounce(function () {
    const q = this.value.trim();
    if (q.length === 0) {
      const params = new URLSearchParams(window.location.search);
      params.delete('q');
      window.location.href = `/iocs/?${params}`;
      return;
    }
    liveSearchIocs(q);
  }, 350));
}

// ── IOC tag autocomplete ─────────────────────────────────────────────────────

let allIocTags = [];

async function fetchIocTags() {
  try {
    const resp = await fetch('/api/ioc-tags');
    if (resp.ok) allIocTags = await resp.json();
  } catch (_) {}
}

function autocompleteIocTag(e) {
  const input = e.target;
  const val = input.value;
  const lastComma = val.lastIndexOf(',');
  const current = val.slice(lastComma + 1).trimStart().toLowerCase();

  removeDropdown();
  if (!current || allIocTags.length === 0) return;

  const matches = allIocTags
    .filter(t => t.name.toLowerCase().includes(current) &&
                 !val.toLowerCase().split(',').map(s => s.trim()).includes(t.name.toLowerCase()))
    .slice(0, 8);

  if (matches.length === 0) return;

  const dropdown = document.createElement('ul');
  dropdown.className = 'list-group position-absolute shadow z-3';
  dropdown.id = 'tag-dropdown';
  dropdown.style.cssText = 'max-width:300px;cursor:pointer;';

  matches.forEach(tag => {
    const li = document.createElement('li');
    li.className = 'list-group-item list-group-item-action bg-dark text-light border-secondary small py-1';
    li.textContent = tag.name;
    li.addEventListener('mousedown', (ev) => {
      ev.preventDefault();
      const prefix = lastComma >= 0 ? val.slice(0, lastComma + 1) + ' ' : '';
      input.value = prefix + tag.name + ', ';
      removeDropdown();
      input.focus();
    });
    dropdown.appendChild(li);
  });

  input.parentNode.style.position = 'relative';
  input.insertAdjacentElement('afterend', dropdown);
}

const iocTagsInputEl = document.getElementById('ioc-tags-input');
if (iocTagsInputEl) {
  fetchIocTags();
}

// ── Event live search ─────────────────────────────────────────────────────────

const eventSearchInput = document.getElementById('event-search-input');
const eventGrid = document.getElementById('event-grid');

function buildEventCard(ev) {
  const tagsHtml = (ev.tags || []).map(tag =>
    `<span class="badge bg-secondary">${escapeHtml(tag)}</span>`
  ).join(' ');

  const datetimeHtml = ev.event_datetime
    ? `<i class="bi bi-clock me-1"></i>${escapeHtml(ev.event_datetime.slice(0, 19) + 'Z')}`
    : '<span class="fst-italic">no date</span>';

  const systemHtml = ev.system
    ? `<span class="font-monospace text-success">${escapeHtml(ev.system.slice(0, 60))}${ev.system.length > 60 ? '…' : ''}</span>`
    : `<span class="text-secondary fst-italic small">Event #${ev.id}</span>`;

  const accountHtml = ev.account
    ? `<span class="text-secondary small ms-1">/ ${escapeHtml(ev.account.slice(0, 40))}</span>`
    : '';

  const sourceHtml = ev.high_level_source
    ? `<span class="badge bg-dark border border-secondary text-secondary small font-monospace">${escapeHtml(ev.high_level_source.slice(0, 20))}</span>`
    : '';

  const categoryHtml = ev.event_category
    ? `<span class="badge bg-secondary small">${escapeHtml(ev.event_category)}</span>`
    : '';

  const iocHtml = ev.ioc_id
    ? `<span class="badge bg-dark border border-warning text-warning small"><i class="bi bi-shield-exclamation me-1"></i>IOC #${ev.ioc_id}</span>`
    : '';

  const timelineHtml = ev.show_on_timeline
    ? `<span class="text-secondary" title="On timeline"><i class="bi bi-calendar-check"></i></span>`
    : '';

  return `
    <a href="/events/${ev.id}"
       class="list-group-item list-group-item-action bg-dark border-secondary text-decoration-none py-2 px-3">
      <div class="d-flex align-items-center gap-3 flex-wrap">
        <span class="font-monospace text-info small text-nowrap" style="min-width:11rem;">${datetimeHtml}</span>
        <span class="flex-grow-1" style="min-width:8rem;">${systemHtml}${accountHtml}</span>
        <span class="d-flex gap-1 align-items-center flex-wrap">${sourceHtml}${categoryHtml}${iocHtml}${timelineHtml}</span>
        <span class="d-flex flex-wrap gap-1">${tagsHtml}</span>
      </div>
    </a>`;
}

function eventEmptyState(search) {
  return `
    <div class="text-center text-secondary py-5">
      <i class="bi bi-calendar-x display-4"></i>
      <p class="mt-3">No events found for <em>${escapeHtml(search)}</em>.
        <a href="/events/">Clear search</a>
      </p>
    </div>`;
}

async function liveSearchEvents(query) {
  const params = new URLSearchParams(window.location.search);
  params.set('q', query);

  try {
    const resp = await fetch(`/api/events?${params}`);
    if (!resp.ok) return;
    const events = await resp.json();

    if (!eventGrid) return;
    eventGrid.innerHTML = events.length === 0
      ? eventEmptyState(query)
      : events.map(buildEventCard).join('');

    const newParams = new URLSearchParams(window.location.search);
    if (query) { newParams.set('q', query); } else { newParams.delete('q'); }
    history.replaceState(null, '', `/events/?${newParams}`);
  } catch (_) {}
}

if (eventSearchInput && eventGrid) {
  eventSearchInput.addEventListener('input', debounce(function () {
    const q = this.value.trim();
    if (q.length === 0) {
      const params = new URLSearchParams(window.location.search);
      params.delete('q');
      window.location.href = `/events/?${params}`;
      return;
    }
    liveSearchEvents(q);
  }, 350));
}
