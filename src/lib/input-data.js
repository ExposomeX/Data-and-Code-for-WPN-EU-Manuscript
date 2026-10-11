import Papa from 'papaparse';

export function parsePositiveWW(value) {
  const text = String(value ?? '').trim();
  if (!text || !/^[+]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/.test(text)) return null;
  const valueNumber = Number(text);
  return Number.isFinite(valueNumber) && valueNumber > 0 ? valueNumber : null;
}
export const normalizeIdentity = value => String(value ?? '').normalize('NFKC').trim().toLowerCase().replace(/[’‘]/g, "'").replace(/\s+/g, ' ');
export function identityIndex(chemicals) {
  const index = new Map();
  const add = (name, item) => {
    const key = normalizeIdentity(name);
    if (!key) return;
    if (!index.has(key)) index.set(key, new Set());
    index.get(key).add(item.id);
  };
  for (const item of chemicals) {
    [item.id, item.name, item.cas, ...(Array.isArray(item.synonyms) ? item.synonyms : [])].forEach(name => add(name, item));
    if (item.id === 'DMSMPAJRVJJAGA-UHFFFAOYSA-N') add('BIT', item);
  }
  return index;
}
export function evaluateDraft(records, chemicals) {
  const index = identityIndex(chemicals), byId = new Map(chemicals.map(item => [item.id, item]));
  const counts = new Map();
  const mapped = records.map((record, position) => {
    const found = [...(index.get(normalizeIdentity(record.identifier)) || [])];
    const chemical = found.length === 1 ? byId.get(found[0]) : null;
    if (chemical) counts.set(chemical.id, (counts.get(chemical.id) || 0) + 1);
    const ww = parsePositiveWW(record.ww);
    const reason = !String(record.identifier || '').trim() ? 'Choose a chemical.'
      : found.length > 1 ? 'Name matches multiple chemicals. Use CAS or InChIKey.'
      : !chemical ? 'Not recognized in the 52-chemical panel.'
      : ww === null ? 'Enter a positive, finite WW concentration in nM.' : '';
    return { ...record, position: position + 1, chemical, value: ww, reason };
  });
  return mapped.map(row => {
    const reason = row.chemical && counts.get(row.chemical.id) > 1 ? 'Duplicate chemical. Keep one concentration.' : row.reason;
    return { ...row, reason, valid: !reason };
  });
}
const headerKey = value => String(value ?? '').replace(/^\uFEFF/, '').toLowerCase().replace(/[^a-z0-9]/g, '');
const identityHeaders = new Set(['chemical', 'chemicalname', 'name', 'identifier', 'chemicalidentifier', 'cas', 'casnumber', 'casrn', 'inchikey', 'stdinchikey']);
const valueHeaders = new Set(['ww', 'wwnm', 'wwinput', 'wwinputnm', 'concentration', 'concentrationnm', 'wwconcentrationnm']);
export function rowsToDraft(matrix) {
  const rows = matrix.filter(row => Array.isArray(row) && row.some(cell => String(cell ?? '').trim()));
  if (!rows.length) throw new Error('No data found. Add a chemical and its WW concentration.');
  if (rows.length > 5000) throw new Error('Please use a file with at most 5,000 rows.');
  let identifierColumn = 0, valueColumn = 1, offset = 0;
  const headers = rows[0].map(headerKey);
  const idIndex = headers.findIndex(header => identityHeaders.has(header));
  const wwIndex = headers.findIndex(header => valueHeaders.has(header));
  if (idIndex >= 0 || wwIndex >= 0) {
    if (idIndex < 0 || wwIndex < 0) throw new Error('Use columns Chemical (name, CAS or InChIKey) and WW (nM).');
    identifierColumn = idIndex; valueColumn = wwIndex; offset = 1;
  }
  const data = rows.slice(offset);
  if (!data.length) throw new Error('The file contains headers but no concentrations.');
  const unitColumn = offset ? headers.findIndex(header => ['unit','units','wwunit','wwunits','concentrationunit'].includes(header)) : -1;
  if (unitColumn >= 0 && data.some(row => String(row[unitColumn] ?? '').trim() && !['nm','nmoll','nanomolar'].includes(headerKey(row[unitColumn])))) throw new Error('All WW concentrations must be in nM. Convert other units before importing.');
  return data.map(row => ({ identifier: String(row[identifierColumn] ?? '').trim(), ww: String(row[valueColumn] ?? '').trim(), origin: 'user' }));
}
export function parsePastedData(text) {
  if (String(text).length > 5 * 1024 * 1024) throw new Error('Please use a file smaller than 5 MB.');
  const result = Papa.parse(String(text).replace(/^\uFEFF/, ''), { skipEmptyLines: 'greedy', delimitersToGuess: ['\t', ',', ';'] });
  const error = result.errors.find(item => item.code !== 'UndetectableDelimiter');
  if (error) throw new Error(`Unable to read the table: ${error.message}`);
  return rowsToDraft(result.data);
}
