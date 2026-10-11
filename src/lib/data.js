const cache = new Map();
const pending = new Map();
const allowed = new Set(['cities', 'chemicals', 'chemical-catalog', 'concentrations', 'ranks', 'city-metrics', 'validation', 'world', 'manifest']);

function validate(name, value) {
  if (name === 'validation') {
    if (!Array.isArray(value?.predictions) || !value.predictions.length || !Array.isArray(value?.summary) || !value.summary.length) throw new Error('Validation data are incomplete.');
  } else if (name === 'world') {
    if (value?.type !== 'FeatureCollection' || !Array.isArray(value.features) || !value.features.length) throw new Error('The local map is incomplete.');
  } else if (name === 'chemical-catalog') {
    if (!Array.isArray(value?.chemicals) || !value.chemicals.length) throw new Error('The local chemical catalog is empty or invalid.');
  } else if (name !== 'manifest' && (!Array.isArray(value) || !value.length)) {
    throw new Error(`The ${name} dataset is empty or invalid.`);
  }
  return value;
}

// Shared requests keep their cache even if one view is abandoned. Each caller
// can abort its own subscription; the shared request has a separate timeout.
function abortable(promise, signal) {
  if (!signal) return promise;
  if (signal.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  return new Promise((resolve, reject) => {
    const abort = () => { cleanup(); reject(new DOMException('Aborted', 'AbortError')); };
    const cleanup = () => signal.removeEventListener('abort', abort);
    signal.addEventListener('abort', abort, { once: true });
    promise.then(value => { cleanup(); resolve(value); }, error => { cleanup(); reject(error); });
  });
}

export function loadData(name, { signal, refresh = false } = {}) {
  if (!allowed.has(name)) return Promise.reject(new Error('Unknown local dataset.'));
  if (refresh) cache.delete(name);
  if (cache.has(name)) return abortable(Promise.resolve(cache.get(name)), signal);
  if (!pending.has(name)) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 45000);
    const request = fetch(`/data/${name}.json`, { signal: controller.signal }).then(async response => {
      const type = response.headers.get('content-type') || '';
      if (!response.ok || type.includes('text/html')) throw new Error(`The local ${name} dataset could not be loaded (${response.status}).`);
      const value = validate(name, await response.json());
      cache.set(name, value);
      return value;
    }).catch(error => {
      if (error.name === 'AbortError') throw new Error(`Loading ${name} timed out. Please retry.`);
      throw error;
    }).finally(() => { clearTimeout(timer); pending.delete(name); });
    pending.set(name, request);
  }
  return abortable(pending.get(name), signal);
}

export function numberText(value, digits = 4) {
  if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value))) return '—';
  const n = Number(value);
  if (n === 0) return '0';
  if (Math.abs(n) < 0.001 || Math.abs(n) >= 100000) return n.toExponential(Math.max(1, digits - 1));
  return Number(n.toPrecision(digits)).toLocaleString('en-US', { maximumFractionDigits: 8 });
}

export function csvText(columns, rows) {
  const cell = value => value === null || value === undefined ? '' : `"${String(value).replaceAll('"', '""')}"`;
  const lines = [columns.map(column => cell(column.header)).join(',')];
  for (const row of rows) lines.push(columns.map(column => cell(typeof column.value === 'function' ? column.value(row) : row[column.value])).join(','));
  return '\ufeff' + lines.join('\r\n');
}

export function downloadCsv(filename, columns, rows) {
  if (!rows.length) throw new Error('There are no matching rows to export.');
  const blob = new Blob([csvText(columns, rows)], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
}

export function selectConcentrations(rows, { cityIds, chemicalIds, status = 'all' }) {
  return rows.filter(row => cityIds.has(row.city) && chemicalIds.has(row.chemical)
    && (status === 'all' || (status === 'observed' ? row.isObserved === true : row.isObserved === false)));
}

export function selectRanks(rows, { metric = 'BEQ_ugL', statistic = 'mean', chemicalIds }) {
  const key = statistic === 'median' ? 'medianRank' : 'meanRank';
  return rows.filter(row => row.metric === metric && chemicalIds.has(row.chemical))
    .slice().sort((a, b) => a[key] - b[key]);
}

export function selectValidation(validation, repeat = 'all') {
  const key = repeat === 'all' ? 'overall' : String(repeat);
  return {
    predictions: validation.predictions.filter(row => repeat === 'all' || String(row.repeat) === key),
    summary: validation.summary.find(row => String(row.validation_repeat) === key) || null,
  };
}
