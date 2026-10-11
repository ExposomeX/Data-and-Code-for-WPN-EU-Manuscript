// Real Explorer setup and frozen local data; no browser or model service required.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRenderer, h, nextTick, ref } from 'vue';
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc';
import * as realData from '../src/lib/data.js';
import * as echarts from 'echarts';

const root = new URL('../', import.meta.url);
const catalog = JSON.parse(fs.readFileSync(new URL('public/data/chemical-catalog.json', root), 'utf8'));
const paper = JSON.parse(fs.readFileSync(new URL('src/content/paper.json', root), 'utf8'));
const frozenConcentrations = JSON.parse(fs.readFileSync(new URL('public/data/concentrations.json', root), 'utf8'));
const BIT = 'DMSMPAJRVJJAGA-UHFFFAOYSA-N';
const ALL_CHEMICALS = 'all';
const expectedCitySums = new Map();
for (const row of frozenConcentrations) {
  if (!Number.isFinite(row.value)) continue;
  const total = expectedCitySums.get(row.city) || { value: 0, chemicalCount: 0, observedCount: 0, reconstructedCount: 0 };
  total.value += row.value; total.chemicalCount++;
  total[row.isObserved ? 'observedCount' : 'reconstructedCount']++;
  expectedCitySums.set(row.city, total);
}
function assertCitySums(rows) {
  assert.equal(new Set(rows.map(row => row.city)).size, rows.length);
  for (const row of rows) {
    const expected = expectedCitySums.get(row.city);
    assert.ok(expected);
    assert.ok(Math.abs(row.value - expected.value) <= Math.max(1, Math.abs(expected.value)) * 1e-12);
    assert.equal(row.chemical, ALL_CHEMICALS); assert.equal(row.isAggregate, true);
    assert.equal(row.chemicalCount, expected.chemicalCount);
    assert.equal(row.observedCount, expected.observedCount);
    assert.equal(row.reconstructedCount, expected.reconstructedCount);
  }
}
const savedFetch = globalThis.fetch;
let exported;
globalThis.fetch = async url => ({ ok: true, status: 200, headers: { get: () => 'application/json' },
  json: async () => JSON.parse(fs.readFileSync(new URL(`public${url}`, root), 'utf8')) });
globalThis.__referenceData = { ...realData, downloadCsv: (filename, columns, rows) => { exported = { filename, columns, rows }; } };
globalThis.__referencePaper = paper;
const filename = fileURLToPath(new URL('src/components/Explorer.vue', root));
const { descriptor, errors } = parse(fs.readFileSync(filename, 'utf8'), { filename });
assert.deepEqual(errors, []);
const compiled = compileScript(descriptor, { id: 'reference', genDefaultAs: 'component' });
assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename, id: 'reference', compilerOptions: { bindingMetadata: compiled.bindings } }).errors, []);
let code = compiled.content
  .replace(/import\s+\{([^}]+)\}\s+from\s+['"]\.\.\/lib\/data\.js['"];?/, 'const {$1} = globalThis.__referenceData;')
  .replace(/from\s+['"]\.\.\/lib\/useViewportTable\.js['"]/g, `from '${new URL('src/lib/useViewportTable.js', root).href}'`)
  .replace(/import\s+Plot\s+from\s+['"]\.\/Plot\.vue['"];?/, 'const Plot = { render: () => null };')
  .replace(/import\s+FigureCard\s+from\s+['"]\.\/FigureCard\.vue['"];?/, 'const FigureCard = { render: () => null };')
  .replace(/import\s+paper\s+from\s+['"]\.\.\/content\/paper\.json['"];?/, 'const paper = globalThis.__referencePaper;')
  .replace(/import\s+\{\s*VAutocomplete\s*\}\s+from\s+['"]vuetify\/components['"];?/, 'const VAutocomplete = { render: () => null };')
  .replace(/from\s+['"]vue['"]/g, `from '${import.meta.resolve('vue')}'`);
code += '\ncomponent.render = () => null; export default component;';
const Component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)).default;
const renderer = createRenderer({
  createElement: type => ({ type, children: [], props: {} }), createText: text => ({ text }), createComment: text => ({ text }),
  setText: (node, text) => { node.text = text; }, setElementText: (node, text) => { node.text = text; },
  patchProp: (node, key, previous, value) => { node.props[key] = value; },
  parentNode: node => node.parent, nextSibling: () => null,
  insert(node, parent) { node.parent = parent; parent.children.push(node); },
  remove(node) { const at = node.parent?.children.indexOf(node); if (at >= 0) node.parent.children.splice(at, 1); },
});
const tab = ref('Combined'), module = ref('ww');
const app = renderer.createApp({ setup: () => () => h(Component, { key: module.value, module: module.value, tab: tab.value }) });
const vm = app.mount({ children: [] });
const state = () => vm.$.subTree.component.setupState;
const settle = async () => {
  for (let n = 0; n < 100; n++) {
    await nextTick();
    if (!state().loading && state().chemicals.length) { assert.equal(state().error, ''); return; }
    await new Promise(resolve => setTimeout(resolve, 5));
  }
  throw new Error('Explorer did not finish loading.');
};
try {
  await settle();
  const s = state();
  assert.equal(s.chemical, 'all');
  assert.equal(s.chemicalOptions.length, 52);
  assert.equal(s.chartChemicalOptions.length, 664);
  assert.deepEqual(s.chartChemicalOptions[0], { title: 'All chemicals (sum)', value: ALL_CHEMICALS });
  assert.deepEqual(new Set(s.chartChemicalOptions.slice(1).map(option => option.value)), new Set(catalog.chemicals.map(item => item.id)));
  assert.equal(s.casOptions.length, 52);
  assert.equal(s.concentrationRows.length, 6084);
  assert.equal(s.showTable, true); assert.equal(s.showCharts, true); assert.ok(s.data.world);
  assert.equal(s.chartChemical, ALL_CHEMICALS); assert.equal(s.isChartSum, true);
  assert.equal(s.chartChemicalLabel, 'All chemicals (sum)'); assert.equal(s.mapRows.length, 117);
  assertCitySums(s.mapRows);
  assert.ok(s.mapRows.every(row => row.chemicalCount === 663));
  assert.equal(s.cityBars.length, 117);
  assert.ok(s.cityBars.every((row, index, rows) => index === 0 || row.value <= rows[index - 1].value));
  assert.equal(new Set(s.cityBarOption.series[0].data.map(point => point.itemStyle.color)).size, 1);
  const sumTooltip = s.concentrationTooltip(s.mapRows[0]);
  assert.match(sumTooltip, /sum|total/i); assert.match(sumTooltip, /663/); assert.match(sumTooltip, /nM/);
  assert.doesNotMatch(sumTooltip, /<br\s*\/?>(Observed|Reconstructed)\s*$/i);
  assert.equal(s.mapRows[0].isObserved, undefined);
  assert.equal(s.mapOption.tooltip.formatter({ data: { record: s.mapRows[0] } }), sumTooltip);
  assert.equal(s.cityBarOption.tooltip.formatter({ data: { record: s.mapRows[0] } }), sumTooltip);
  console.log('PASS default charts show independent 663-chemical city totals with 664 choices and truthful aggregate tooltips');

  assert.equal(s.perPage, 100); assert.equal(s.pageRows.length, 100); assert.equal(s.pageCount, 61);
  const firstPageKeys = new Set(s.pageRows.map(row => `${row.city}-${row.chemical}`));
  s.page = 2; await nextTick();
  assert.equal(s.pageRows.length, 100);
  assert.ok(s.pageRows.every(row => !firstPageKeys.has(`${row.city}-${row.chemical}`)));
  s.page = s.pageCount; await nextTick(); assert.equal(s.pageRows.length, 84);
  s.exportRows(); assert.equal(exported.rows.length, 6084);
  s.chemicalSelection = BIT; await nextTick();
  assert.equal(s.page, 1); assert.equal(s.pageCount, 2); assert.equal(s.pageRows.length, 100);
  s.page = 2; await nextTick(); assert.equal(s.pageRows.length, 17);
  s.resetFilters(); await nextTick(); assert.equal(s.page, 1);
  console.log('PASS 100-row pages cover all matches, filters reset pagination, and CSV exports every matching row');

  for (const field of ['chemicalSelection', 'casSelection']) {
    s[field] = BIT;
    await nextTick();
    assert.equal(s.chemicalSelection, BIT); assert.equal(s.casSelection, BIT);
    assert.equal(s.selectedChemical.cas, '2634-33-5');
    assert.equal(s.concentrationRows.length, 117);
    assert.ok(s.concentrationRows.every(row => row.chemical === BIT));
    assert.equal(s.chartChemical, ALL_CHEMICALS); assert.equal(s.mapRows.length, 117); assertCitySums(s.mapRows);
    s[field] = null; await nextTick();
    assert.equal(s.chemical, 'all'); assert.equal(s.casSelection, null);
  }
  console.log('PASS shared name/InChIKey and CAS selections synchronize by exact identity; clearing restores all');

  s.chemicalSelection = BIT; await nextTick();
  s.page = 2; await nextTick();
  s.chartChemicalSelection = BIT; await nextTick();
  assert.equal(s.isChartSum, false); assert.equal(s.chartChemical, BIT); assert.equal(s.mapRows.length, 117);
  const expectedBit = new Map(frozenConcentrations.filter(row => row.chemical === BIT).map(row => [row.city, row.value]));
  assert.ok(s.mapRows.every(row => row.chemical === BIT && row.value === expectedBit.get(row.city)));
  for (const observed of [true, false]) {
    const row = s.mapRows.find(item => item.isObserved === observed);
    assert.ok(row); assert.match(s.concentrationTooltip(row), new RegExp(`<br>${observed ? 'Observed' : 'Reconstructed'}$`));
  }
  s.chartSearch = 'not a chemical name'; await nextTick();
  assert.equal(s.chartChemical, BIT); assert.equal(s.mapRows.length, 117);
  assert.equal(s.chartChemicalOptions.length, 664);
  for (const cleared of [null, '']) {
    s.chartChemicalSelection = BIT; await nextTick();
    s.chartChemicalSelection = cleared; await nextTick();
    assert.equal(s.chartChemical, ALL_CHEMICALS); assert.equal(s.chartChemicalSelection, ALL_CHEMICALS);
    assert.equal(s.isChartSum, true); assert.equal(s.mapRows.length, 117); assertCitySums(s.mapRows);
    assert.equal(s.chemicalSelection, BIT); assert.equal(s.concentrationRows.length, 117); assert.equal(s.page, 2);
  }
  s.chartSearch = ''; s.resetFilters(); await nextTick();
  console.log('PASS chart search leaves values intact; selecting one chemical shows exact values and clearing restores totals without changing table filters/pages');

  const aggregateData = s.data, [firstCity, secondCity, emptyCity] = s.cities;
  const fixture = [
    { city: firstCity.id, chemical: BIT, value: 2, isObserved: true },
    { city: firstCity.id, chemical: catalog.chemicals[0].id, value: 3, isObserved: false },
    { city: firstCity.id, chemical: catalog.chemicals[1].id, value: null, isObserved: false },
    { city: secondCity.id, chemical: BIT, value: 0, isObserved: true },
    { city: secondCity.id, chemical: catalog.chemicals[0].id, value: Number.NaN, isObserved: false },
    { city: emptyCity.id, chemical: BIT, value: null, isObserved: false },
  ];
  try {
    s.data = { ...aggregateData, concentrations: fixture }; await nextTick();
    assert.equal(s.mapRows.length, 2);
    const first = s.mapRows.find(row => row.city === firstCity.id), second = s.mapRows.find(row => row.city === secondCity.id);
    assert.equal(first.value, 5); assert.equal(first.chemicalCount, 2); assert.equal(first.observedCount, 1); assert.equal(first.reconstructedCount, 1);
    assert.equal(second.value, 0); assert.equal(second.chemicalCount, 1); assert.equal(second.observedCount, 1); assert.equal(second.reconstructedCount, 0);
    assert.ok(!s.mapRows.some(row => row.city === emptyCity.id));
    assert.deepEqual(s.mapRange, { min: 0, max: 5 });
    s.data = { ...aggregateData, concentrations: fixture.map(row => ({ ...row, value: null })) }; await nextTick();
    assert.equal(s.mapRows.length, 0); assert.equal(s.mapRange, null);
  } finally { s.data = aggregateData; await nextTick(); }
  console.log('PASS city totals include measured zero, exclude non-finite values, report actual component counts and never invent zero for missing cities');

  s.country = s.countries[0]; await nextTick();
  assert.ok(s.mapRows.length > 0 && s.mapRows.length < 117);
  assertCitySums(s.mapRows);
  assert.ok(s.mapRows.every(row => s.cityById.get(row.city).country === s.country));
  s.focusCity(s.mapRows[0]); await nextTick();
  assert.equal(s.mapRows.length, 1); assertCitySums(s.mapRows);
  assert.equal(s.concentrationRows.length, 52);
  s.resetFilters(); await nextTick();
  assert.equal(s.chartChemical, ALL_CHEMICALS); assert.equal(s.mapRows.length, 117); assertCitySums(s.mapRows);
  console.log('PASS shared country/city filters select city totals without reducing the chemicals included in each sum');

  const chartChoice = catalog.chemicals.find(item => !item.nt52);
  s.page = 2; await nextTick();
  s.chartChemicalSelection = chartChoice.id; await nextTick();
  assert.equal(s.chemicalSelection, null); assert.equal(s.casSelection, null);
  assert.equal(s.page, 2); assert.equal(s.concentrationRows.length, 6084);
  assert.ok(s.mapRows.every(row => row.chemical === chartChoice.id));
  assert.equal(s.mapRows.length, 117);
  s.exportRows(); assert.equal(exported.rows.length, 6084);
  assert.ok(exported.rows.every(row => row.chemical !== chartChoice.id));
  s.chemicalSelection = BIT; await nextTick();
  assert.equal(s.concentrationRows.length, 117); assert.equal(s.chartChemical, chartChoice.id);
  assert.ok(s.mapRows.every(row => row.chemical === chartChoice.id));
  s.chemicalSelection = null; await nextTick();
  s.scope = 'all'; await nextTick();
  assert.equal(s.concentrationRows.length, 77571); assert.equal(s.chartChemical, chartChoice.id);
  s.scope = 'nt52'; await nextTick();
  assert.equal(s.concentrationRows.length, 6084); assert.equal(s.chartChemical, chartChoice.id);
  assert.equal(s.chartChemicalOptions.length, 664);
  s.country = s.countries[0]; await nextTick();
  assert.ok(s.mapRows.length > 0);
  assert.ok(s.mapRows.every(row => s.cityById.get(row.city).country === s.country));
  assert.ok(s.concentrationRows.every(row => s.cityById.get(row.city).country === s.country));
  s.focusCity(s.mapRows[0]); await nextTick();
  assert.equal(s.mapRows.length, 1); assert.equal(s.concentrationRows.length, 52);
  s.resetFilters(); await nextTick();
  assert.equal(s.chemical, 'all'); assert.equal(s.concentrationRows.length, 6084);
  assert.equal(s.chartChemical, chartChoice.id); assert.equal(s.mapRows.length, 117);
  console.log('PASS all 663 chart chemicals remain independent of table selection/scope/pagination/export/reset; city filters are shared');

  const values = s.mapRows.map(row => row.value);
  assert.deepEqual(s.mapRange, { min: Math.min(...values), max: Math.max(...values) });
  assert.equal(s.mapOption.visualMap.type, 'continuous'); assert.equal(s.mapOption.visualMap.dimension, 2);
  assert.equal(s.mapOption.visualMap.min, s.mapRange.min); assert.equal(s.mapOption.visualMap.max, s.mapRange.max);
  assert.ok(s.mapOption.visualMap.text.every(text => text.endsWith(' nM')));
  assert.equal(s.mapOption.legend, undefined); assert.equal(s.mapOption.series.length, 1);
  const plottedRecords = s.mapOption.series[0].data.map(point => point.record);
  assert.ok(plottedRecords.some(row => row.isObserved)); assert.ok(plottedRecords.some(row => !row.isObserved));
  echarts.registerMap('wpn-world', s.data.world);
  const map = echarts.init(null, null, { renderer: 'svg', ssr: true, width: 900, height: 520 });
  const originalData = s.data;
  try {
    map.setOption({ ...s.mapOption, animation: false });
    const minIndex = values.indexOf(s.mapRange.min), maxIndex = values.indexOf(s.mapRange.max);
    assert.notEqual(map.getVisual({ seriesIndex: 0, dataIndex: minIndex }, 'color'), map.getVisual({ seriesIndex: 0, dataIndex: maxIndex }, 'color'));
    assert.ok(map.renderToSVGString().includes('Concentration (nM)'));
    s.data = { ...originalData, concentrations: originalData.concentrations.map(row => row.chemical === chartChoice.id ? { ...row, value: 0 } : row) };
    await nextTick();
    assert.deepEqual(s.mapRange, { min: 0, max: 0 });
    assert.match(s.mapRangeText, /0 nM \(all displayed cities\)/);
    map.setOption({ ...s.mapOption, animation: false }, { notMerge: true });
    assert.equal(new Set(s.mapRows.map((row, index) => map.getVisual({ seriesIndex: 0, dataIndex: index }, 'color'))).size, 1);
    assert.ok(!map.renderToSVGString().includes('NaN'));
    s.data = { ...originalData, concentrations: originalData.concentrations.map(row => row.chemical === chartChoice.id ? { ...row, value: null } : row) };
    await nextTick();
    assert.equal(s.mapRows.length, 0); assert.equal(s.mapRange, null); assert.equal(s.mapOption.visualMap, undefined);
  } finally { s.data = originalData; await nextTick(); map.dispose(); }
  console.log('PASS continuous map colours use actual nM range, retain source tooltips and safely render equal-value/empty selections');

  s.chemicalSelection = BIT; await nextTick();
  s.nameSearch = 'a nonexistent name'; s.casSearch = 'not a CAS'; s.inchiKeySearch = 'unmatched';
  await nextTick();
  assert.equal(s.chemical, BIT); assert.equal(s.concentrationRows.length, 117);
  assert.equal(s.chemicalOptions.length, 52);
  s.exportRows(); assert.equal(exported.rows.length, 117);
  assert.ok(exported.rows.some(row => row.isObserved)); assert.ok(exported.rows.some(row => !row.isObserved));
  console.log('PASS typing only filters menu options; data/export retain chosen chemical and both statuses');

  s.scope = 'all'; s.chemicalSelection = null; await nextTick();
  assert.equal(s.chemicalOptions.length, 663); assert.equal(s.casOptions.length, 662);
  assert.equal(s.concentrationRows.length, 77571);
  const withoutCas = catalog.chemicals.find(item => !item.cas);
  s.chemicalSelection = withoutCas.id; await nextTick();
  assert.equal(s.selectedChemical.id, withoutCas.id); assert.equal(s.selectedChemical.cas, null);
  assert.equal(s.casSelection, null); assert.equal(s.concentrationRows.length, 117);
  s.scope = 'nt52'; await nextTick();
  assert.equal(s.chemical, 'all'); assert.equal(s.concentrationRows.length, 6084);
  console.log('PASS full catalog includes 663 identities and 662 real CAS values; missing CAS remains unavailable');

  tab.value = 'Figure'; await settle();
  assert.equal(s.chemical, 'all'); assert.equal(s.mapRows.length, 117);
  const other = catalog.chemicals.find(item => item.nt52 && item.id !== BIT);
  s.casSelection = other.id; await nextTick();
  assert.ok(s.mapRows.every(row => row.chemical === chartChoice.id));
  tab.value = 'Data'; await settle();
  assert.equal(s.chemical, other.id); assert.equal(s.concentrationRows.length, 117);
  s.resetFilters(); await nextTick(); assert.equal(s.chemical, 'all');
  tab.value = 'Figure'; await settle();
  s.chemicalSelection = null; await nextTick(); assert.equal(s.chemical, 'all');
  s.country = s.countries[0]; await nextTick();
  assert.ok(s.mapRows.every(row => s.cityById.get(row.city).country === s.country));
  s.resetFilters(); await nextTick();
  assert.equal(s.chemical, 'all'); assert.equal(s.chartChemical, chartChoice.id); assert.equal(s.country, 'all'); assert.equal(s.mapRows.length, 117);
  console.log('PASS presentation changes retain independent chemical selections and country filters still apply');

  module.value = 'imputation'; tab.value = 'Combined'; await settle();
  const v = state();
  assert.equal(v.showTable, true); assert.equal(v.showCharts, true);
  assert.equal(v.scope, 'all'); assert.equal(v.concentrationRows.length, 77571);
  assert.ok(v.validation.predictions.length > 0); assert.ok(v.validation.summary);
  const allValidationPredictions = v.validation.predictions.length;
  v.chemicalSelection = BIT; await nextTick();
  assert.equal(v.concentrationRows.length, 117);
  assert.equal(v.validation.predictions.length, allValidationPredictions);
  v.repeat = v.repeatOptions[0]; await nextTick();
  assert.ok(v.validation.predictions.length < allValidationPredictions);
  assert.ok(v.validation.predictions.every(row => String(row.repeat) === v.repeat));
  assert.equal(v.concentrationRows.length, 117);
  v.exportRows(); assert.equal(exported.rows.length, 117);
  assert.deepEqual(v.validationFigure, paper.figures.find(figure => figure.id === 'ED3'));
  assert.match(v.validationFigure.caption, /\(A, B\).*\(C\).*\(D\).*\(E\).*\(F\)/s);
  console.log('PASS combined validation loads table and validation chart; repeat and concentration filters retain separate meanings');
} finally {
  app.unmount();
  globalThis.fetch = savedFetch;
  delete globalThis.__referenceData;
  delete globalThis.__referencePaper;
}
