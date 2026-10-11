// Run: node tests/frontend-contract.test.mjs
// Uses existing Vue/compiler/Papa Parse/ECharts packages and Node built-ins. All HTTP is mocked.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRenderer, h, nextTick } from 'vue';
import { createRouter, createMemoryHistory, useRoute } from 'vue-router';
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc';
import * as realData from '../src/lib/data.js';
import * as echarts from 'echarts';
import { parsePastedData, rowsToDraft, evaluateDraft } from '../src/lib/input-data.js';

const root = new URL('../', import.meta.url);
const reportUrl = new URL('.runtime/checks/frontend-contract.json', root);
const startedAt = new Date().toISOString();
const checks = [];
const originals = { fetch: globalThis.fetch, localStorage: globalThis.localStorage };
const catalog = JSON.parse(fs.readFileSync(new URL('public/data/chemical-catalog.json', root), 'utf8'));
const targets = catalog.chemicals.filter(row => row.nt52);
const storage = new Map(), jobs = new Map();
let posts = 0, mode = 'success', resultGate = null, exported = null, componentCounter = 0;
const mountedApps = [];

async function check(name, fn) {
  try { await fn(); checks.push({ name, passed: true }); console.log(`PASS ${name}`); }
  catch (error) { checks.push({ name, passed: false, error: error.message }); throw error; }
}
function fixtureRows(values) {
  const total = values.reduce((sum, row) => sum + row.ww, 0);
  return [...values].sort((a,b) => b.ww-a.ww).map((row, index) => ({ chemical:row.chemical, ww:row.ww, beq:row.ww / 100,
    beqRank:index+1, beqContribution:row.ww / total * 100 }));
}
function fixtureResult(id, inputs) {
  const rows = fixtureRows(inputs);
  const totals = records => Object.fromEntries(['ww', 'beq'].map(key => [key, records.reduce((sum, row) => sum + row[key], 0)]));
  return { id, createdAt: '2026-10-08T00:00:00Z', modelVersion: 'test-fixture-not-scientific', dataVersion: catalog.version,
    rows, totals: totals(rows), inputs };
}
const response = (data, status = 200) => ({ ok: status < 400, status, headers: { get: () => 'application/json' }, json: async () => data });
globalThis.localStorage = { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value) };
globalThis.fetch = async (url, options = {}) => {
  if (url === '/data/chemical-catalog.json') return response(catalog);
  if (url === '/data/ranks.json') return response(JSON.parse(fs.readFileSync(new URL('public/data/ranks.json', root), 'utf8')));
  if (url === '/api/health') return response({ status: 'ready', modelVersion: 'test-fixture-not-scientific', message: 'Fixture is ready.' });
  if (url === '/api/import') return response({ rows:[['Chemical','WW (nM)'],['BIT',2],['Unknown chemical',3]] });
  if (url === '/api/runs' && options.method === 'POST') {
    const id = `contract-test-${++posts}`;
    jobs.set(id, JSON.parse(options.body).inputs);
    return response({ id, status: 'queued' });
  }
  if (url.startsWith('/api/runs/')) {
    if (mode === 'network') throw new TypeError('Simulated network interruption');
    if (mode === '404') return response({ message: 'Task not found' }, 404);
    const id = url.split('/').at(-1);
    const result = () => response({ id, status: 'succeeded', result: fixtureResult(id, jobs.get(id)) });
    if (mode === 'hold') return new Promise(resolve => { resultGate = () => resolve(result()); });
    return result();
  }
  throw new Error(`Unexpected mocked request: ${url}`);
};

// Real Vue component setup/lifecycle, using an in-memory renderer and router.
// Charts/image components are stubbed; DOM layout and live model accuracy are separate checks.
const renderer = createRenderer({
  createElement: type => ({ type, children: [], props: {} }), createText: text => ({ text }), createComment: text => ({ text }),
  setText: (node, text) => { node.text = text; }, setElementText: (node, text) => { node.text = text; },
  patchProp: (node, key, previous, value) => { node.props[key] = value; },
  parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
  insert(node, parent, anchor = null) { if (node.parent) { const old = node.parent.children.indexOf(node); if (old >= 0) node.parent.children.splice(old, 1); } node.parent = parent; const at = anchor ? parent.children.indexOf(anchor) : -1; if (at >= 0) parent.children.splice(at, 0, node); else parent.children.push(node); },
  remove(node) { const at = node.parent?.children.indexOf(node); if (at >= 0) node.parent.children.splice(at, 1); },
});
async function compileSetup(file, scenario) {
  const filename = fileURLToPath(new URL(`src/components/${file}`, root));
  const { descriptor } = parse(fs.readFileSync(filename, 'utf8'), { filename });
  let code = compileScript(descriptor, { id: file, genDefaultAs: 'component' }).content;
  globalThis.__wpnContract = { scenario, data: { ...realData, downloadCsv: (filename, columns, rows) => { exported = { filename, columns, rows }; } }, paper: JSON.parse(fs.readFileSync(new URL('src/content/paper.json', root), 'utf8')) };
  code = code.replace(/import\s+\{([^}]+)\}\s+from\s+['"]\.\.\/lib\/scenario\.js['"];?/g, 'const {$1} = globalThis.__wpnContract.scenario;');
  code = code.replace(/import\s+\{([^}]+)\}\s+from\s+['"]\.\.\/lib\/data\.js['"];?/g, 'const {$1} = globalThis.__wpnContract.data;');
  code = code.replace(/from\s+['"]\.\.\/lib\/(input-data|rankResults|useViewportTable|rankAxis)\.js['"]/g, (all, name) => `from '${new URL(`src/lib/${name}.js`, root).href}'`);
  code = code.replace(/import\s+paper\s+from\s+['"]\.\.\/content\/paper\.json['"];?/, 'const paper = globalThis.__wpnContract.paper;');
  code = code.replace(/import\s+(\w+)\s+from\s+['"]\.\/(?:Plot|FigureCard)\.vue['"];?/g, 'const $1 = {render:()=>null};');
  code = code.replace(/import\s+\{\s*VAutocomplete\s*\}\s+from\s+['"]vuetify\/components['"];?/g, 'const VAutocomplete = {render:()=>null};');
  code = code.replace(/from\s+['"](vue|vue-router)['"]/g, (all, pkg) => `from '${import.meta.resolve(pkg)}'`);
  code += `\ncomponent.render = () => null; export default component; // ${++componentCounter}`;
  return (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)).default;
}
async function mountPage(file, module, address, scenario) {
  const Component = await compileSetup(file, scenario);
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:module/:tab', component: { render: () => null } }] });
  await router.push(address); await router.isReady();
  const app = renderer.createApp({ setup() { const route = useRoute(); return () => route.params.module === module && route.params.tab !== 'Description' ? h(Component, { tab: route.params.tab }) : h('div'); } });
  app.use(router); const host = { children: [] }; const vm = app.mount(host);
  mountedApps.push(app); await nextTick();
  return { app, router, instance: () => vm.$.subTree.component, state: () => vm.$.subTree.component?.setupState };
}
async function until(predicate) { for (let i = 0; i < 100; i++) { if (predicate()) return; await new Promise(resolve => setTimeout(resolve, 5)); await nextTick(); } throw new Error('Component contract did not settle.'); }

try {
  const s = await import('../src/lib/scenario.js?frontend-contract=initial');
  const id = targets[0].id, secondId=targets[1].id;
  let first;
  const setSubset = () => s.replaceDraft([{identifier:id,ww:'2'},{identifier:secondId,ww:'4'}]);
  await check('01 Vue scripts and templates compile', () => {
    for (const file of ['ChemicalExplorer.vue', 'WpnWorkspace.vue', 'RankExplorer.vue']) {
      const filename = fileURLToPath(new URL(`src/components/${file}`, root));
      const { descriptor, errors } = parse(fs.readFileSync(filename, 'utf8'), { filename }); assert.deepEqual(errors, []);
      const compiled = compileScript(descriptor, { id: file });
      assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename, id: file, compilerOptions: { bindingMetadata: compiled.bindings } }).errors, []);
    }
  });
  await check('02 Fresh workspace is blank and only the 52 calculable chemicals are exposed', async () => {
    await s.loadCatalog(); assert.equal(s.catalog.value.chemicals.length,52); assert.equal(s.panel.value.length,52);
    assert.equal(s.draftRows.length,0); assert.equal(s.validInputs.value.length,0); assert.equal(s.snapshot.value,null);
  });
  await check('03 Strict positive finite WW values and no API submission when nothing valid', async () => {
    for(const value of ['', ' ', '0', '-1', 'Infinity', 'NaN', '1e309', '0x12', 'abc']) assert.equal(s.parsePositiveWW(value),null,value);
    for(const value of ['1','+1.5','1e-9','.5','1.']) assert.ok(s.parsePositiveWW(value)>0,value);
    await assert.rejects(s.startRun(),/at least one valid/); s.addDraftRow(id,'0'); await assert.rejects(s.startRun(),/at least one valid/); assert.equal(posts,0);
  });
  await check('04 Excel paste resolves names, CAS and InChIKey and flags both duplicate identities', () => {
    const pasted=`Chemical\tWW (nM)\nBIT\t1\n${targets[0].cas}\t2\n${secondId}\t3\nUnknown chemical\t4\n${targets[2].id}\t-1`;
    const evaluated=evaluateDraft(parsePastedData(pasted),targets);
    assert.equal(evaluated.length,5); assert.equal(evaluated.filter(row=>row.valid).length,1);
    assert.match(evaluated[0].reason,/Duplicate/); assert.match(evaluated[1].reason,/Duplicate/);
    assert.equal(evaluated[2].chemical.id,secondId); assert.match(evaluated[3].reason,/Not recognized/); assert.match(evaluated[4].reason,/positive/);
    const quoted=parsePastedData(`Chemical,WW (nM)\n"${targets[0].name}",1.25`); assert.equal(quoted[0].identifier,targets[0].name); assert.equal(quoted[0].ww,'1.25');
  });
  await check('05 Import recognizes reversed headers, empty input and a header-only file', () => {
    assert.deepEqual(rowsToDraft([['WW (nM)','InChIKey'],[2,id]])[0],{identifier:id,ww:'2',origin:'user'});
    assert.throws(()=>parsePastedData(''),/No data/); assert.throws(()=>parsePastedData('Chemical\tWW (nM)'),/headers but no/);
    assert.throws(()=>rowsToDraft([['Chemical','Not a concentration'],[id,2]]),/Use columns/);
    for(const unit of ['µM','μM','mM','ng/L','mg/L']) assert.throws(()=>rowsToDraft([['Chemical',`WW (${unit})`],[id,2]]),/WW \(nM\)/,unit);
    for(const header of ['Unit','Units','WW unit','WW units','concentration unit']) {
      for(const unit of ['µM','μM','mM','ng/L','mg/L']) assert.throws(()=>rowsToDraft([['Chemical','WW',header],[id,'2',unit]]),/must be in nM/,`${header}: ${unit}`);
      const accepted=rowsToDraft([['Chemical','WW',header],[id,'1.23e-5','nM'],[secondId,'4','nmol/L'],[targets[2].id,'5','nanomolar'],[targets[3].id,'6','']]);
      assert.equal(accepted.length,4); assert.deepEqual(accepted.map(row=>row.ww),['1.23e-5','4','5','6']); assert.equal(accepted[0].identifier,id);
      assert.throws(()=>rowsToDraft([['Chemical','WW',header],[id,'1','nM'],[secondId,'2','µM']]),/must be in nM/);
    }
  });
  await check('06 Example data is opt-in; user entries equal to examples still have user provenance', () => {
    s.loadExample(); assert.equal(s.draftRows.length,52); assert.ok(s.validInputs.value.every(row=>row.origin==='example'));
    const firstRow=s.draftRows[0]; s.updateDraftRow(firstRow.key,'ww',String(Number(firstRow.originalWW)*2));
    assert.equal(s.validInputs.value.find(row=>row.chemical===id).origin,'user');
    s.updateDraftRow(firstRow.key,'ww',firstRow.originalWW); assert.equal(s.validInputs.value.find(row=>row.chemical===id).origin,'example');
    s.replaceDraft([{identifier:id,ww:targets[0].defaultWW}]); assert.equal(s.validInputs.value[0].origin,'user');
  });
  await check('07 Mixed-validity data submits only the valid subset and duplicate Run posts once', async () => {
    setSubset(); s.addDraftRow('Unknown chemical','5'); s.addDraftRow(targets[2].id,'0');
    const values=await Promise.all([s.startRun(),s.startRun()]); first=values[0]; assert.ok(first); assert.equal(values[1],null); assert.equal(posts,1);
    assert.deepEqual(jobs.get(first.id).map(row=>row.chemical),[id,secondId]); assert.equal(first.rows.length,2); assert.equal(s.dirty.value,false);
    assert.ok(Math.abs(first.rows.reduce((sum,row)=>sum+row.beqContribution,0)-100)<1e-9);
  });
  await check('08 Successful subset result and input snapshot are immutable', () => {
    assert.ok(Object.isFrozen(s.snapshot.value)); assert.ok(Object.isFrozen(s.snapshot.value.rows)); assert.ok(Object.isFrozen(s.snapshot.value.inputs));
    assert.throws(()=>{s.snapshot.value.rows[0].ww=100;}); assert.equal('baseline' in s.snapshot.value,false); assert.equal('de' in s.snapshot.value.rows[0],false); assert.equal('cb' in s.snapshot.value.rows[0],false);
  });
  await check('09 Editing inputs preserves the previous successful result and marks it stale', () => {
    s.updateDraftRow(s.draftRows[0].key,'ww','9'); assert.equal(s.dirty.value,true);
    assert.equal(s.snapshot.value.rows.find(row=>row.chemical===id).ww,2); assert.equal(s.snapshot.value.id,first.id);
  });
  await check('10 Network interruption pauses one task and locks input mutations', async () => {
    mode='network'; await s.startRun(); assert.equal(s.runState.status,'paused'); assert.equal(s.locked.value,true); assert.equal(posts,2);
    const before=JSON.stringify(s.draftRows); s.updateDraftRow(s.draftRows[0].key,'ww','99'); s.replaceDraft([]); s.addDraftRow(targets[4].id,12); s.removeDraftRow(s.draftRows[0].key);
    assert.equal(JSON.stringify(s.draftRows),before); assert.equal(s.snapshot.value.id,first.id);
  });
  await check('11 An expired task unlocks drafts without losing earlier successful results', async () => {
    mode='404'; await s.resumeRun(); assert.equal(s.runState.status,'failed'); assert.equal(s.locked.value,false); assert.equal(s.snapshot.value.id,first.id); assert.equal(posts,2);
    await nextTick(); assert.equal(JSON.parse(storage.get('wpn-workspace-v2')).pendingRun,null);
  });
  await check('12 Refresh restores draft, preview step, input method and successful snapshot', async () => {
    s.workspaceStep.value='preview'; s.inputMethod.value='paste'; s.pastedText.value='BIT\t9'; await nextTick();
    const fresh=await import('../src/lib/scenario.js?frontend-contract=restore'); await fresh.loadCatalog();
    assert.deepEqual(fresh.draftRows.map(({identifier,ww})=>({identifier,ww})),s.draftRows.map(({identifier,ww})=>({identifier,ww})));
    assert.equal(fresh.snapshot.value.id,first.id); assert.equal(fresh.workspaceStep.value,'preview'); assert.equal(fresh.inputMethod.value,'paste'); assert.equal(fresh.pastedText.value,'BIT\t9'); assert.equal(fresh.dirty.value,true);
  });
  await check('13 Mismatched concentrations, duplicate identities, contributions and ranks are rejected', () => {
    const ids=[id,secondId];
    const corrupt=()=>JSON.parse(JSON.stringify(first));
    let value=corrupt(); value.rows[0].ww=999; assert.throws(()=>s.validateResult(value,ids),/input snapshot/);
    value=corrupt(); value.rows[1].chemical=value.rows[0].chemical; assert.throws(()=>s.validateResult(value,ids),/incomplete/);
    value=corrupt(); value.rows[0].beqContribution=17; assert.throws(()=>s.validateResult(value,ids),/contributions/);
    value=corrupt(); value.rows[1].beqRank=value.rows[0].beqRank; assert.throws(()=>s.validateResult(value,ids),/ranks/);
    value=corrupt(); value.totals.ww=999; assert.throws(()=>s.validateResult(value,ids),/WW total/);
    value=corrupt(); [value.rows[0].beqRank,value.rows[1].beqRank]=[value.rows[1].beqRank,value.rows[0].beqRank]; assert.throws(()=>s.validateResult(value,ids),/BEQ order/);
    assert.throws(()=>s.validateResult(first,[id]),/incomplete/);
  });
  await check('14 Chemical shows all 52 rows, identity filters stay linked and CSV contains all matching rows', async () => {
    const view=await mountPage('ChemicalExplorer.vue','chemical','/chemical/Data',s), state=view.state();
    assert.equal(state.rows.length,52); state.exportRows(); assert.equal(exported.rows.length,52);
    state.identityFilter=id; await nextTick(); assert.equal(state.casFilter,id); assert.equal(state.selectedIdentity.id,id); state.exportRows(); assert.equal(exported.rows.length,1); assert.equal(exported.rows[0].id,id);
    state.casFilter=secondId; await nextTick(); assert.equal(state.identityFilter,secondId); assert.equal(state.rows[0].id,secondId); state.resetFilters(); await nextTick(); assert.equal(state.rows.length,52); view.app.unmount();
  });
  await check('15 Rank starts with My results and retains axis/source when moving between Data and Figure', async () => {
    const view=await mountPage('RankExplorer.vue','rank','/rank/Data',s); await until(()=>!view.state().loading);
    const uid=view.instance().uid; assert.equal(view.state().source,'current'); assert.equal(view.state().allRows.length,2); view.state().scale='value';
    await view.router.push('/rank/Figure'); await nextTick(); assert.equal(view.instance().uid,uid); assert.equal(view.state().scale,'value');
    await view.state().setSource('reference'); await until(()=>!view.state().loading&&view.state().allRows.length===52);
    await view.router.push('/rank/Data?source=reference'); await nextTick(); assert.equal(view.state().source,'reference'); assert.equal(view.state().allRows[0].chemical,id);
    view.app.unmount();
  });
  await check('16 Ranking search never changes global ranks, chart denominator or CSV field set', async () => {
    const view=await mountPage('RankExplorer.vue','rank','/rank/Data?source=reference',s); await until(()=>!view.state().loading);
    const state=view.state(), firstContribution=state.allRows[0].contribution; state.query='BIT'; await nextTick();
    assert.equal(state.rows.length,1); assert.equal(state.rows[0].rank,1); assert.equal(state.rows[0].contribution,firstContribution); assert.equal(state.chartRows.length,52); assert.equal(state.chartRows.at(-1).cumulative,100);
    state.exportRows(); assert.equal(exported.rows.length,1); assert.deepEqual(exported.columns.map(column=>column.header),['Rank','Chemical','WW input (nM)','BEQ (μg/L Narciclasine-EQ)','Contribution (%)']);
    assert.equal(state.chemicalOptions.length,52);
    state.selectChemical(secondId); await nextTick();
    const selectedReference = state.allRows.find(row=>row.chemical===secondId);
    assert.equal(state.rows.length,1); assert.equal(state.rows[0].rank,selectedReference.rank); assert.equal(state.rows[0].contribution,selectedReference.contribution);
    assert.equal(state.chartRows.length,52); state.exportRows(); assert.equal(exported.rows[0].chemical,secondId);
    state.clearSearch(); await nextTick(); assert.equal(state.rows.length,52);
    assert.equal(state.option.series[0].type,'bar'); assert.equal(state.option.series[1].type,'line'); assert.equal(state.option.yAxis[0].type,'log'); assert.equal(state.option.yAxis[1].max,100); assert.equal(state.option.dataZoom[0].filterMode,'none');
    view.app.unmount();
  });
  await check('17 Finishing after leaving WPN preserves the current page', async () => {
    setSubset(); mode='hold'; resultGate=null; const view=await mountPage('WpnWorkspace.vue','wpn','/wpn/Data',s); await nextTick();
    const running=view.state().run(); await until(()=>typeof resultGate==='function'); await view.router.push('/chemical/Data'); await nextTick(); resultGate(); await running;
    assert.equal(view.router.currentRoute.value.path,'/chemical/Data'); assert.equal(s.snapshot.value.id,'contract-test-3'); view.app.unmount();
  });
  await check('18 Finishing inside WPN opens My results Figure', async () => {
    mode='success'; const view=await mountPage('WpnWorkspace.vue','wpn','/wpn/Data',s); await nextTick(); await view.state().run();
    assert.equal(view.router.currentRoute.value.path,'/rank/Figure'); assert.equal(view.router.currentRoute.value.query.source,'current'); view.app.unmount();
  });
  await check('19 Refreshed pending task reconnects without another POST', async () => {
    mode='network'; await s.startRun(); assert.equal(s.runState.status,'paused'); await nextTick(); const submittedCount=posts;
    const fresh=await import('../src/lib/scenario.js?frontend-contract=pending'); await fresh.loadCatalog(); assert.equal(fresh.runState.status,'paused');
    mode='success'; const view=await mountPage('WpnWorkspace.vue','wpn','/wpn/Data',fresh);
    await until(()=>view.router.currentRoute.value.path==='/rank/Figure'); assert.equal(posts,submittedCount); assert.equal(fresh.snapshot.value.id,fresh.runState.id); view.app.unmount();
  });
  await check('20 Legacy saved inputs and snapshot migrate without exposing intermediate results', async () => {
    const legacyInputs=targets.map(row=>({chemical:row.id,ww:row.defaultWW})), previous=fixtureResult('legacy-example',legacyInputs);
    previous.baseline={rows:[]}; previous.rows.forEach(row=>{row.de=1;row.cb=2;});
    storage.delete('wpn-workspace-v2'); storage.set('wpn-scenario-v1',JSON.stringify({dataVersion:catalog.version,inputs:Object.fromEntries(legacyInputs.map(row=>[row.chemical,row.ww])),inputSources:Object.fromEntries(legacyInputs.map(row=>[row.chemical,'default'])),snapshot:previous}));
    const fresh=await import('../src/lib/scenario.js?frontend-contract=legacy'); await fresh.loadCatalog();
    assert.equal(fresh.validInputs.value.length,52); assert.ok(fresh.validInputs.value.every(row=>row.origin==='example')); assert.equal(fresh.snapshot.value.id,'legacy-example'); assert.equal('baseline' in fresh.snapshot.value,false); assert.equal('de' in fresh.snapshot.value.rows[0],false); assert.equal('cb' in fresh.snapshot.value.rows[0],false); assert.equal(JSON.parse(storage.get('wpn-workspace-v2')).schema,2);
  });
  await check('21 Paste preview exposes valid and invalid rows; Back retains data for correction', async () => {
    const fresh=await import('../src/lib/scenario.js?frontend-contract=preview'); await fresh.loadCatalog();
    const view=await mountPage('WpnWorkspace.vue','wpn','/wpn/Data',fresh); await nextTick();
    fresh.pastedText.value=`Chemical\tWW (nM)\nBIT\t2\nUnknown\t3`; view.state().usePaste(); await nextTick();
    assert.equal(fresh.workspaceStep.value,'preview'); assert.equal(fresh.validInputs.value.length,1); assert.equal(fresh.invalidInputs.value.length,1);
    assert.equal(view.state().previewRows.length,2); assert.equal(view.state().previewRows[0].valid,true); assert.equal(view.state().previewRows[1].valid,false); assert.match(view.state().previewRows[1].reason,/Not recognized/);
    view.state().back(); assert.equal(fresh.workspaceStep.value,'input'); assert.equal(fresh.draftRows.length,2);
    fresh.updateDraftRow(fresh.draftRows[1].key,'identifier',secondId); view.state().preview(); assert.equal(fresh.validInputs.value.length,2); view.app.unmount();
  });
  await check('22 Excel upload uses the same preview and clears the file chooser for re-upload', async () => {
    const fresh=await import('../src/lib/scenario.js?frontend-contract=upload'); await fresh.loadCatalog();
    const view=await mountPage('WpnWorkspace.vue','wpn','/wpn/Data',fresh); await nextTick();
    assert.equal(view.state().selectedFileName,'');
    const event={target:{files:[{name:'my-inputs.xlsx',size:200}],value:'my-inputs.xlsx'}};
    await view.state().importFile(event); assert.equal(fresh.workspaceStep.value,'preview'); assert.equal(fresh.validInputs.value.length,1); assert.equal(fresh.invalidInputs.value.length,1); assert.equal(event.target.value,''); assert.equal(view.state().importing,false);
    assert.equal(view.state().selectedFileName,'my-inputs.xlsx');
    const importedRows=JSON.stringify(fresh.draftRows);
    await view.state().importFile({target:{files:[],value:''}});
    assert.equal(view.state().selectedFileName,'my-inputs.xlsx'); assert.equal(JSON.stringify(fresh.draftRows),importedRows); view.app.unmount();
  });
  await check('23 One chemical can run independently with a 100% contribution', async () => {
    const fresh=await import('../src/lib/scenario.js?frontend-contract=single'); await fresh.loadCatalog(); fresh.replaceDraft([{identifier:'BIT',ww:'1'}]); mode='success';
    const result=await fresh.startRun(); assert.equal(result.rows.length,1); assert.equal(result.rows[0].beqRank,1); assert.equal(result.rows[0].beqContribution,100); assert.equal(result.inputs[0].chemical,id);
  });
  await check('24 Invalid saved draft records are skipped without blocking valid inputs or the catalog', async () => {
    storage.set('wpn-workspace-v2',JSON.stringify({schema:2,dataVersion:catalog.version,draftRows:[null,[],123,'damaged row',true,{identifier:id,ww:'1.25'},{identifier:secondId,ww:'2'}],workspaceStep:'preview'}));
    const fresh=await import('../src/lib/scenario.js?frontend-contract=damaged-draft'); await fresh.loadCatalog();
    assert.equal(fresh.catalog.value.chemicals.length,52); assert.equal(fresh.catalogError.value,''); assert.equal(fresh.draftRows.length,2);
    assert.deepEqual(fresh.draftRows.map(({identifier,ww})=>({identifier,ww})),[{identifier:id,ww:'1.25'},{identifier:secondId,ww:'2'}]);
    assert.equal(fresh.validInputs.value.length,2); assert.equal(fresh.workspaceStep.value,'preview'); assert.match(fresh.storageNotice.value,/saved input rows were skipped/);
    assert.equal(JSON.parse(storage.get('wpn-workspace-v2')).draftRows.length,2);
  });
  await check('25 Actual ECharts bars grow upwards from the log minimum or linear zero for WW and BEQ', async () => {
    const fresh=await import('../src/lib/scenario.js?frontend-contract=log-bars'); await fresh.loadCatalog();
    const wpnView=await mountPage('WpnWorkspace.vue','wpn','/wpn/Figure',fresh);
    const rankView=await mountPage('RankExplorer.vue','rank','/rank/Figure?source=current',fresh); await until(()=>!rankView.state().loading);
    for(const concentrations of [[0.01,0.2],[200,1200],[0.01,1200],[1e-10,1e-7]]) {
      fresh.replaceDraft([{identifier:id,ww:concentrations[0]},{identifier:secondId,ww:concentrations[1]}]);
      fresh.snapshot.value=fixtureResult('geometry-fixture',fresh.validInputs.value);
      for(const view of [wpnView,rankView]) for(const scale of ['log','value']) {
        view.state().scale=scale; await nextTick(); const option=view.state().option;
        const seriesValues=option.series[0].data.map(row=>row.value);
        const axis=Array.isArray(option.yAxis)?option.yAxis[0]:option.yAxis;
        const chart=echarts.init(null,null,{renderer:'svg',ssr:true,width:1200,height:580});
        try {
          chart.setOption({animation:false,...option});
          if(view===rankView&&scale==='log') {
            const ticks=chart.getModel().getComponent('yAxis',0).axis.scale.getTicks();
            assert.ok(ticks.every(tick=>Number.isFinite(tick.value)&&tick.value>0),'all BEQ logarithmic ticks remain finite and positive');
            assert.ok(ticks.length>=2);
            const displayed=option.series[0].data.map(point=>axis.axisLabel.formatter(point.value));
            assert.deepEqual(displayed,option.series[0].data.map(point=>realData.numberText(point.record.beq,2)),'labels retain original BEQ units');
          }
          const data=chart.getModel().getSeriesByIndex(0).getData();
          const baseline=chart.convertToPixel({yAxisIndex:0},scale==='log'?axis.min:0);
          const heights=[];
          for(let index=0;index<data.count();index++) {
            const layout=data.getItemLayout(index),top=chart.convertToPixel({yAxisIndex:0},seriesValues[index]);
            assert.ok(layout.height<0,`${view===wpnView?'WW':'BEQ'} ${scale}: positive bar grows upward`);
            assert.ok(Math.abs(layout.y-baseline)<1e-6,'bar starts at the displayed minimum or zero');
            assert.ok(Math.abs(layout.y+layout.height-top)<1e-6,'bar endpoint represents the unmodified value');
            heights.push(Math.abs(layout.height));
          }
          assert.ok(heights[0]>heights[1],'larger value has the longer bar in descending order');
          assert.deepEqual(option.series[0].data.map(row=>row.value),seriesValues);
        } finally { chart.dispose(); }
      }
    }
    wpnView.app.unmount(); rankView.app.unmount();
  });
} catch (error) {
  console.error(error.stack); process.exitCode = 1;
} finally {
  for (const app of mountedApps) { if (app._container?._vnode) app.unmount(); }
  globalThis.fetch = originals.fetch;
  if (originals.localStorage === undefined) delete globalThis.localStorage; else globalThis.localStorage = originals.localStorage;
  delete globalThis.__wpnContract;
  const report = { startedAt, completedAt: new Date().toISOString(), passed: checks.length === 25 && checks.every(row => row.passed), checks,
    testCommand: 'node tests/frontend-contract.test.mjs', dependencies: 'Node built-ins and existing Vue, vue-router, @vue/compiler-sfc, papaparse and echarts packages only',
    scope: 'Mock API/state contracts, actual component setup/lifecycle with an in-memory Vue renderer and memory router, and real ECharts SSR bar geometry. No real prediction request, browser layout test, or scientific-model accuracy claim.', simulatedPosts: posts };
  fs.mkdirSync(new URL('.runtime/checks/', root), { recursive: true }); fs.writeFileSync(reportUrl, JSON.stringify(report, null, 2) + '\n');
  console.log(`${report.passed ? 'PASS' : 'FAIL'} ${checks.filter(row => row.passed).length}/${checks.length}; report: ${fileURLToPath(reportUrl)}`);
}
