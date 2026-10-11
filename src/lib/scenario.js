import { computed, reactive, ref, shallowRef, watch } from 'vue';
import { parsePositiveWW, evaluateDraft } from './input-data.js';
export { parsePositiveWW } from './input-data.js';

const STORAGE_KEY = 'wpn-workspace-v2';
const BIT = 'DMSMPAJRVJJAGA-UHFFFAOYSA-N';
export const catalog = shallowRef(null);
export const catalogLoading = ref(false);
export const catalogError = ref('');
export const storageNotice = ref('');
export const draftRows = reactive([]);
export const workspaceStep = ref('input');
export const inputMethod = ref('manual');
export const pastedText = ref('');
export const draftLabel = ref('My data');
let draftSequence = 0;
export const selectedChemicalIds = shallowRef(new Set());
export const snapshot = shallowRef(null);
export const health = reactive({ status: 'loading', message: 'Checking the local prediction service…', modelVersion: '' });
export const runState = reactive({ status: 'idle', id: '', message: '', error: '', submittedInputs: null });
let catalogPromise;
let pollingPromise;
let restored = null;
let selectionInitialized = false;
let healthTimer;
let healthSubscribers = 0;
let healthRequest;

export const chemicalName = item => item ? `${item.name}${item.id === BIT ? ' (BIT)' : ''}` : '';
export function detailText(value) {
  if (value === null || value === undefined || value === '') return '—';
  if (Array.isArray(value)) return value.map(detailText).join('; ');
  if (typeof value === 'object') return Object.entries(value).map(([key, entry]) => `${key}: ${detailText(entry)}`).join('; ');
  return String(value);
}
export function matchesChemical(item, query) {
  const q = query.trim().toLocaleLowerCase();
  if (!q) return true;
  if (q === 'bit') return item.id === BIT;
  return [item.name, item.id, item.cas, item.dtxsid, item.smiles, item.formula].some(value => detailText(value).toLocaleLowerCase().includes(q));
}
export const panel = computed(() => (catalog.value?.chemicals || []).filter(item => item.nt52));
export const evaluatedDraft = computed(() => evaluateDraft(draftRows, panel.value));
export const validInputs = computed(() => evaluatedDraft.value.filter(item => item.valid).map(item => ({ chemical: item.chemical.id, ww: item.value, origin: item.origin === 'example' && Number(item.ww) === Number(item.originalWW) ? 'example' : 'user' })));
export const invalidInputs = computed(() => evaluatedDraft.value.filter(item => !item.valid));
export const locked = computed(() => ['checking', 'submitting', 'queued', 'running', 'reconnecting', 'paused'].includes(runState.status));
export const dirty = computed(() => {
  if (!snapshot.value) return false;
  const submitted = new Map(snapshot.value.inputs.map(item => [item.chemical, item.ww]));
  return validInputs.value.length !== submitted.size || validInputs.value.some(item => item.ww !== submitted.get(item.chemical));
});

async function jsonRequest(url, options = {}, timeoutMs = 20000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal, headers: { Accept: 'application/json', ...options.headers } });
    const type = response.headers.get('content-type') || '';
    if (!type.includes('json')) {
      const error = new Error(`The local service returned an unexpected response (${response.status}).`);
      error.status = response.status;
      throw error;
    }
    const value = await response.json();
    if (!response.ok) {
      const error = new Error(value.message || value.error || value.detail || `Request failed (${response.status}).`);
      error.status = response.status;
      throw error;
    }
    return value;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The local service did not respond in time. Please retry the connection.');
    throw error;
  } finally { clearTimeout(timer); }
}
function freezeDeep(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    Object.values(value).forEach(freezeDeep);
    Object.freeze(value);
  }
  return value;
}
export function validateResult(result, expectedIds) {
  if (!result || typeof result.id !== 'string' || !result.id || !result.createdAt || !result.modelVersion || !result.dataVersion) throw new Error('The result snapshot is missing its run or version information.');
  const ids = new Set(expectedIds);
  if (ids.size < 1 || ids.size > 52) throw new Error('The result must contain 1–52 chemicals.');
  const validRows = rows => Array.isArray(rows) && rows.length === ids.size && new Set(rows.map(row => row.chemical)).size === ids.size && rows.every(row => ids.has(row.chemical)
    && ['ww', 'beq', 'beqContribution'].every(key => typeof row[key] === 'number' && Number.isFinite(row[key]) && row[key] >= 0)
    && row.ww > 0 && Number.isInteger(row.beqRank) && row.beqRank >= 1 && row.beqRank <= ids.size);
  const validTotals = totals => totals && ['ww', 'beq'].every(key => typeof totals[key] === 'number' && Number.isFinite(totals[key]) && totals[key] > 0);
  if (!validRows(result.rows) || !validTotals(result.totals)) throw new Error('The result is incomplete. Please run again.');
  if (!Array.isArray(result.inputs) || result.inputs.length !== ids.size || new Set(result.inputs.map(row => row.chemical)).size !== ids.size || result.inputs.some(row => !ids.has(row.chemical) || parsePositiveWW(row.ww) === null)) throw new Error('The result does not match the submitted chemicals.');
  const submitted = new Map(result.inputs.map(row => [row.chemical, Number(row.ww)]));
  if (result.rows.some(row => row.ww !== submitted.get(row.chemical))) throw new Error('The result values do not match the returned input snapshot.');
  const total = result.rows.reduce((sum, row) => sum + row.beq, 0);
  if (Math.abs(total - result.totals.beq) > Math.abs(total) * 1e-9 || result.rows.some(row => Math.abs(row.beqContribution - row.beq / total * 100) > 1e-7)) throw new Error('The result contributions do not match the submitted chemicals.');
  const totalWW = result.rows.reduce((sum, row) => sum + row.ww, 0);
  if (Math.abs(totalWW - result.totals.ww) > Math.abs(totalWW) * 1e-9) throw new Error('The WW total does not match the submitted inputs.');
  const ranks = new Set(result.rows.map(row => row.beqRank));
  if (ranks.size !== ids.size) throw new Error('The returned ranks are incomplete.');
  const ordered = result.rows.slice().sort((a,b)=>a.beqRank-b.beqRank);
  if (ordered.some((row,index)=>index>0&&row.beq>ordered[index-1].beq)) throw new Error('The ranks do not follow BEQ order.');
  return result;
}
function restoreStorage() {
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY);
    if (raw) {
      const value = JSON.parse(raw);
      if (value.schema !== 2) throw new Error('Unknown stored format');
      restored = value;
    } else {
      const legacy = globalThis.localStorage?.getItem('wpn-scenario-v1');
      if (legacy) {
        const old = JSON.parse(legacy);
        restored = { schema: 2, dataVersion: old.dataVersion, draftRows: Object.entries(old.inputs || {}).map(([identifier, ww]) => ({ identifier, ww, originalWW: ww, origin: old.inputSources?.[identifier] === 'default' ? 'example' : 'user' })), draftLabel: 'Saved inputs', selected: old.selected };
        if (old.snapshot) {
          const r = old.snapshot;
          restored.snapshot = { id:r.id, createdAt:r.createdAt, modelVersion:r.modelVersion, dataVersion:r.dataVersion, inputs:r.inputs, rows:r.rows.map(({chemical,ww,beq,beqRank,beqContribution}) => ({chemical,ww,beq,beqRank,beqContribution})), totals:{ww:r.totals.ww,beq:r.totals.beq} };
        }
      }
    }
  } catch { storageNotice.value = 'Saved inputs could not be restored. Please enter your data again.'; }
}
restoreStorage();
function persist() {
  if (!catalog.value) return;
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify({ schema: 2, dataVersion: catalog.value.version,
      draftRows: [...draftRows], workspaceStep: workspaceStep.value, inputMethod:inputMethod.value, pastedText:pastedText.value, draftLabel:draftLabel.value, selected: [...selectedChemicalIds.value], snapshot: snapshot.value,
      pendingRun: locked.value && runState.id ? { id: runState.id, inputs: runState.submittedInputs } : null }));
  } catch { storageNotice.value = 'Browser storage is unavailable or full. Keep this page open to retain this session; CSV downloads still work.'; }
}
watch([draftRows, workspaceStep, inputMethod, pastedText, draftLabel, selectedChemicalIds, snapshot, () => [runState.id, runState.status]], persist, { deep: true });
export async function loadCatalog(refresh = false) {
  if (catalog.value && !refresh) return catalog.value;
  if (catalogPromise) return catalogPromise;
  catalogLoading.value = true;
  catalogError.value = '';
  catalogPromise = (async () => {
    try {
      const value = await jsonRequest('/data/chemical-catalog.json');
      if (!value.version || !Array.isArray(value.chemicals) || new Set(value.chemicals.map(item => item.id)).size !== value.chemicals.length) throw new Error('The local chemical catalog is incomplete.');
      const target = value.chemicals.filter(item => item.nt52);
      if (target.length !== 52 || target.some(item => parsePositiveWW(item.defaultWW) === null)) throw new Error('The fixed NT52 panel or its default concentrations are incomplete.');
      const previous = restored;
      if (previous && !draftRows.length && Array.isArray(previous.draftRows)) {
        const savedRows = previous.draftRows.filter(row => row !== null && typeof row === 'object' && !Array.isArray(row));
        if (savedRows.length !== previous.draftRows.length) storageNotice.value = 'Some invalid saved input rows were skipped.';
        draftRows.push(...savedRows.map(makeDraftRow));
        workspaceStep.value = previous.workspaceStep === 'preview' ? 'preview' : 'input';
        inputMethod.value = ['manual','paste','upload'].includes(previous.inputMethod) ? previous.inputMethod : 'manual';
        pastedText.value = String(previous.pastedText || '');
        draftLabel.value = previous.draftLabel || 'My data';
      }
      if (!selectionInitialized) {
        const valid = new Set(target.map(item => item.id));
        selectedChemicalIds.value = new Set(Array.isArray(previous?.selected) ? previous.selected.filter(id => valid.has(id)) : target.map(item => item.id));
        selectionInitialized = true;
      }
      if (!snapshot.value && previous?.snapshot) {
        try {
          const allowed = new Set(target.map(item => item.id)), ids = previous.snapshot.inputs.map(row => row.chemical);
          if (ids.some(id => !allowed.has(id))) throw new Error('Unknown chemical');
          snapshot.value = freezeDeep(validateResult(previous.snapshot, ids));
        }
        catch { storageNotice.value = 'A saved result was incomplete and has been ignored. Inputs remain available for a new run.'; }
      }
      if (previous?.pendingRun?.id && !runState.id) {
        runState.id = previous.pendingRun.id;
        runState.submittedInputs = previous.pendingRun.inputs;
        runState.status = 'paused';
        runState.message = 'A saved task is available. Reconnect to check its progress without submitting again.';
      }
      catalog.value = freezeDeep({ ...value, chemicals: target });
      restored = null;
      persist();
      return value;
    } catch (error) { catalogError.value = error.message; throw error; }
    finally { catalogLoading.value = false; catalogPromise = null; }
  })();
  return catalogPromise;
}
function makeDraftRow(row) { return { key: `input-${++draftSequence}`, identifier: String(row.identifier ?? ''), ww: String(row.ww ?? ''), originalWW: String(row.originalWW ?? row.ww ?? ''), origin: row.origin === 'example' ? 'example' : 'user' }; }
export function replaceDraft(rows, label = 'My data') {
  if (locked.value) return;
  draftRows.splice(0, draftRows.length, ...rows.map(makeDraftRow)); draftLabel.value = label; workspaceStep.value = 'input';
}
export function addDraftRow(identifier, ww = '') { if (!locked.value) draftRows.push(makeDraftRow({ identifier, ww, origin:'user' })); }
export function updateDraftRow(key, field, value) { if (!locked.value && ['identifier','ww'].includes(field)) { const row=draftRows.find(item=>item.key===key); if(row) row[field]=String(value); } }
export function removeDraftRow(key) { if (!locked.value) { const index=draftRows.findIndex(row=>row.key===key); if(index>=0) draftRows.splice(index,1); } }
export function loadExample() { replaceDraft(panel.value.map(row=>({identifier:row.id,ww:row.defaultWW,origin:'example'})), 'Example data'); inputMethod.value='manual'; pastedText.value=''; }
export function clearDraft() { replaceDraft([]); pastedText.value=''; }
export function setChemicalSelection(ids, selected) {
  const next = new Set(selectedChemicalIds.value);
  ids.forEach(id => selected ? next.add(id) : next.delete(id));
  selectedChemicalIds.value = next;
}
export async function refreshHealth() {
  if (healthRequest) return healthRequest;
  healthRequest = jsonRequest('/api/health').then(value => {
    if (!['loading', 'ready', 'error'].includes(value.status)) throw new Error('The prediction service returned an unknown health status.');
    Object.assign(health, { status: value.status, message: value.message || (value.status === 'ready' ? 'Prediction service is ready.' : 'Preparing the prediction service…'), modelVersion: value.modelVersion || '' });
    return value;
  }).catch(error => { Object.assign(health, { status: 'error', message: error.message }); return { status: 'error', message: error.message }; }).finally(() => { healthRequest = null; });
  return healthRequest;
}
export function subscribeHealth() {
  healthSubscribers++;
  if (healthSubscribers === 1) {
    const tick = async () => { await refreshHealth(); if (healthSubscribers) healthTimer = setTimeout(tick, health.status === 'loading' ? 2500 : 10000); };
    tick();
  }
  return () => { healthSubscribers = Math.max(0, healthSubscribers - 1); if (!healthSubscribers) clearTimeout(healthTimer); };
}
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
export async function resumeRun() {
  if (pollingPromise) return pollingPromise;
  if (!runState.id || !locked.value) return null;
  runState.error = '';
  runState.status = 'reconnecting';
  const id = runState.id;
  pollingPromise = (async () => {
    try {
      while (runState.id === id) {
        const task = await jsonRequest(`/api/runs/${encodeURIComponent(id)}`);
        if (task.id !== id || !['queued', 'running', 'succeeded', 'failed'].includes(task.status)) throw new Error('The returned task identity or status is invalid.');
        runState.status = task.status;
        runState.message = task.message || `Task ${task.status}.`;
        if (task.status === 'failed') { runState.error = task.message || 'Prediction failed. The previous successful result is unchanged.'; persist(); return null; }
        if (task.status === 'succeeded') {
          let result;
          try {
            result = validateResult(task.result, (runState.submittedInputs || []).map(item => item.chemical));
            if (result.id !== id) throw new Error('The returned result belongs to a different task.');
            const expected = new Map((runState.submittedInputs || []).map(row => [row.chemical, row.ww]));
            if (expected.size !== result.inputs.length || result.inputs.some(row => expected.get(row.chemical) !== row.ww)) throw new Error('The result does not match the submitted concentrations.');
          } catch (error) { runState.status = 'failed'; runState.error = error.message; persist(); return null; }
          snapshot.value = freezeDeep(JSON.parse(JSON.stringify(result)));
          runState.message = 'Prediction completed. The submitted inputs and results were saved together.';
          persist();
          return snapshot.value;
        }
        await delay(1800);
      }
      return null;
    } catch (error) {
      const expired = error.status === 404 || error.status === 410;
      runState.status = expired ? 'failed' : 'paused';
      runState.error = error.message;
      runState.message = expired
        ? 'This task is no longer available, for example after a service restart. Inputs are unlocked for a new run. The previous successful result is unchanged.'
        : 'Connection interrupted. Reconnect to this task; a second prediction has not been submitted.';
      persist();
      return null;
    } finally { pollingPromise = null; }
  })();
  return pollingPromise;
}
export async function startRun() {
  if (locked.value) return null;
  if (!catalog.value || panel.value.length !== 52) throw new Error('Load the complete NT52 catalog before running WPN.');
  if (!validInputs.value.length) throw new Error('Add at least one valid chemical and WW concentration.');
  const submitted = validInputs.value.map(row => ({ ...row }));
  runState.id = ''; runState.submittedInputs = null;
  runState.status = 'checking'; runState.error = ''; runState.message = 'Checking the prediction service…';
  try {
    const currentHealth = await refreshHealth();
    if (currentHealth.status !== 'ready') throw new Error(currentHealth.message || 'The prediction service is not ready.');
    runState.status = 'submitting'; runState.message = `Submitting ${submitted.length} chemicals…`;
    const task = await jsonRequest('/api/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ inputs: submitted }) }, 30000);
    if (typeof task.id !== 'string' || !task.id) throw new Error('The service did not return a task ID.');
    runState.id = task.id; runState.submittedInputs = submitted; runState.status = 'queued';
    persist();
    return await resumeRun();
  } catch (error) { runState.status = 'failed'; runState.error = error.message; runState.message = 'The run did not complete. Previous results were retained.'; persist(); throw error; }
}
