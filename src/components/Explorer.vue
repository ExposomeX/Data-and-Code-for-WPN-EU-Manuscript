<script setup>
import { computed, ref, shallowRef, watch, onBeforeUnmount } from 'vue';
import { VAutocomplete } from 'vuetify/components';
import Plot from './Plot.vue';
import FigureCard from './FigureCard.vue';
import paper from '../content/paper.json';
import { loadData, numberText, downloadCsv, escapeHtml, selectConcentrations, selectRanks, selectValidation } from '../lib/data.js';
import { useViewportTable } from '../lib/useViewportTable.js';

const props = defineProps({ module: { type: String, required: true }, tab: { type: String, required: true } });
const showTable = computed(() => props.tab !== 'Figure');
const showCharts = computed(() => props.tab !== 'Data');
const explorerElement = ref(null), tableRegion = ref(null);
const { tableMaxHeight } = useViewportTable(explorerElement, tableRegion);
const data = shallowRef({});
const loading = ref(false);
const error = ref('');
const exportError = ref('');
let sequence = 0;
let controller;
const scope = ref(props.module === 'ww' ? 'nt52' : 'all');
const country = ref('all');
const city = ref('all');
const chemicalQuery = ref('');
const chemical = ref('all');
const nameSearch = ref(''), casSearch = ref(''), inchiKeySearch = ref('');
const category = ref('all');
const metric = ref('BEQ_ugL');
const statistic = ref('mean');
const topN = ref(10);
const repeat = ref('all');
const page = ref(1);
const perPage = 100;
const sortKey = ref('city');
const sortDirection = ref('asc');
const BIT = 'DMSMPAJRVJJAGA-UHFFFAOYSA-N';
const ALL_CHEMICALS = 'all';
const chartChemical = ref(ALL_CHEMICALS);
const chartSearch = ref('');
const chartChemicalSelection = computed({
  get: () => chartChemical.value,
  set: value => { chartChemical.value = value || ALL_CHEMICALS; chartSearch.value = ''; },
});
const isChartSum = computed(() => chartChemical.value === ALL_CHEMICALS);
const chartChemicalLabel = computed(() => isChartSum.value ? 'All chemicals (sum)' : chemicalName(chartChemical.value));
const validationFigure = paper.figures.find(figure => figure.id === 'ED3');
function matchesChemical(item, query) {
  if (query === 'bit') return item.id === BIT;
  return !query || `${item.name} ${item.id}`.toLocaleLowerCase().includes(query);
}
const collator = new Intl.Collator('en', { numeric: true, sensitivity: 'base' });
const units = { WW_nM: 'nM', DE_umol_day: 'μmol/day', BEQ_ugL: 'μg/L narciclasine-EQ' };
const metricLabels = { WW_nM: 'Wastewater concentration', DE_umol_day: 'Daily exposure', BEQ_ugL: 'Bioanalytical equivalent concentration' };
const cities = computed(() => data.value.cities || []);
const catalogById = computed(() => new Map((data.value['chemical-catalog']?.chemicals || []).map(item => [item.id, item])));
const chemicals = computed(() => (data.value.chemicals || []).map(item => ({ ...item, cas: catalogById.value.get(item.id)?.cas || null })));
const cityById = computed(() => new Map(cities.value.map(item => [item.id, item])));
const chemicalById = computed(() => new Map(chemicals.value.map(item => [item.id, item])));
const countries = computed(() => [...new Set(cities.value.map(item => item.country))].sort(collator.compare));
const cityOptions = computed(() => cities.value.filter(item => country.value === 'all' || item.country === country.value).slice().sort((a, b) => collator.compare(a.name, b.name)));
// All three selectors share the exact InChIKey. Search text only narrows the
// open menu; it does not change the selected chemical or the displayed data.
const chemicalOptions = computed(() => chemicals.value.filter(item => scope.value === 'all' || item.nt52)
  .slice().sort((a, b) => collator.compare(a.name, b.name)));
const chartChemicalOptions = computed(() => [
  { title: 'All chemicals (sum)', value: ALL_CHEMICALS },
  ...chemicals.value.slice().sort((a, b) => collator.compare(a.name, b.name))
    .map(item => ({ title: chemicalName(item.id), value: item.id })),
]);
const chemicalSelection = computed({
  get: () => chemical.value === 'all' ? null : chemical.value,
  set: value => {
    chemical.value = value || 'all';
    normalizeChemical();
  },
});
const selectedChemical = computed(() => chemicalById.value.get(chemical.value));
const casSelection = computed({
  get: () => selectedChemical.value?.cas ? chemicalSelection.value : null,
  set: value => { chemicalSelection.value = value; },
});
const nameOptions = computed(() => chemicalOptions.value.map(item => ({ title: chemicalName(item.id), value: item.id })));
const casOptions = computed(() => chemicalOptions.value.filter(item => item.cas)
  .map(item => ({ title: item.cas, value: item.id, props: { subtitle: chemicalName(item.id) } }))
  .sort((a, b) => collator.compare(a.title, b.title)));
const inchiKeyOptions = computed(() => chemicalOptions.value.map(item => item.id).sort(collator.compare));
const filterMenuProps = { maxHeight: 300, contentClass: 'chemical-filter-menu' };
const filterOption = (value, query) => String(value).toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
const categories = computed(() => [...new Set(chemicals.value.filter(item => item.nt52 && item.category).map(item => item.category))].sort(collator.compare));
const allowedCities = computed(() => new Set(cityOptions.value.filter(item => city.value === 'all' || item.id === city.value).map(item => item.id)));
const allowedChemicals = computed(() => new Set(chemicalOptions.value.filter(item => chemical.value === 'all' || item.id === chemical.value).map(item => item.id)));
const concentrationRows = computed(() => selectConcentrations(data.value.concentrations || [], { cityIds: allowedCities.value, chemicalIds: allowedChemicals.value }));
const rankRows = computed(() => {
  const q = chemicalQuery.value.trim().toLocaleLowerCase();
  const ids = new Set(chemicals.value.filter(item => (category.value === 'all' || item.category === category.value) && matchesChemical(item, q)).map(item => item.id));
  return selectRanks(data.value.ranks || [], { metric: metric.value, statistic: statistic.value, chemicalIds: ids });
});
function sortValue(row, key) {
  if (key === 'city') return cityById.value.get(row.city)?.name || row.city;
  if (key === 'country') return cityById.value.get(row.city)?.country || '';
  if (key === 'chemical') return chemicalById.value.get(row.chemical)?.name || row.chemical;
  return row[key];
}
const tableRows = computed(() => {
  if (props.module === 'rank') return rankRows.value;
  const direction = sortDirection.value === 'asc' ? 1 : -1;
  return concentrationRows.value.slice().sort((a, b) => {
    const left = sortValue(a, sortKey.value), right = sortValue(b, sortKey.value);
    if (left == null) return right == null ? 0 : 1;
    if (right == null) return -1;
    return direction * (typeof left === 'number' && typeof right === 'number' ? left - right : collator.compare(String(left), String(right)));
  });
});
const pageCount = computed(() => Math.max(1, Math.ceil(tableRows.value.length / perPage)));
const pageRows = computed(() => tableRows.value.slice((page.value - 1) * perPage, page.value * perPage));
const observedCount = computed(() => concentrationRows.value.reduce((count, row) => count + Number(row.isObserved), 0));
const validation = computed(() => selectValidation(data.value.validation || { predictions: [], summary: [] }, repeat.value));
const repeatOptions = computed(() => [...new Set((data.value.validation?.predictions || []).map(item => String(item.repeat)))].filter(value => /^\d+$/.test(value)).sort((a, b) => Number(a) - Number(b)));
const rankField = computed(() => statistic.value === 'median' ? 'medianRank' : 'meanRank');
const unit = computed(() => units[metric.value]);
const chemicalName = id => {
  const name = chemicalById.value.get(id)?.name || id;
  return id === BIT ? `${name} (BIT)` : name;
};
const cityName = id => cityById.value.get(id)?.name || id;
const chartToolbox = { right: 8, feature: { saveAsImage: { title: 'Download PNG', pixelRatio: 2, name: 'WPN-figure' } } };

async function load(refresh = false) {
  const request = ++sequence;
  controller?.abort();
  controller = new AbortController();
  error.value = '';
  const names = props.module === 'rank' ? ['chemicals', 'ranks']
    : ['cities', 'chemicals',
      ...(showTable.value || props.module === 'ww' ? ['chemical-catalog', 'concentrations'] : []),
      ...(props.module === 'ww' && showCharts.value ? ['world'] : []),
      ...(props.module === 'imputation' && showCharts.value ? ['validation'] : [])];
  const needed = names.filter(name => refresh || !data.value[name]);
  if (!needed.length) { loading.value = false; normalizeChemical(); return; }
  loading.value = true;
  try {
    const values = await Promise.all(needed.map(name => loadData(name, { signal: controller.signal, refresh })));
    if (request !== sequence) return;
    data.value = { ...data.value, ...Object.fromEntries(needed.map((name, i) => [name, values[i]])) };
    normalizeChemical();
  } catch (cause) {
    if (request !== sequence || cause.name === 'AbortError') return;
    error.value = cause.message || 'The local data could not be loaded. Please retry.';
  } finally { if (request === sequence) loading.value = false; }
}
function normalizeChemical() {
  if (props.module === 'rank' || !chemicals.value.length) return;
  const options = chemicalOptions.value;
  if (chemical.value !== 'all' && !options.some(item => item.id === chemical.value)) chemical.value = 'all';
}
watch(() => [props.module, props.tab], () => load(), { immediate: true });
watch(chemicalOptions, normalizeChemical);
watch(chartChemicalOptions, options => {
  if (!options.some(item => item.value === chartChemical.value)) chartChemicalSelection.value = ALL_CHEMICALS;
});
watch(country, () => { if (!cityOptions.value.some(item => item.id === city.value)) city.value = 'all'; });
watch([scope, country, city, chemicalQuery, chemical, category, metric, statistic], () => { page.value = 1; exportError.value = ''; });
watch(pageCount, count => { if (page.value > count) page.value = count; });
watch(pageRows, () => { if (tableRegion.value) tableRegion.value.scrollTop = 0; }, { flush: 'post' });
onBeforeUnmount(() => { ++sequence; controller?.abort(); });
function resetFilters() {
  scope.value = props.module === 'ww' ? 'nt52' : 'all'; country.value = 'all'; city.value = 'all'; chemicalQuery.value = ''; chemical.value = 'all'; category.value = 'all'; page.value = 1;
  nameSearch.value = ''; casSearch.value = ''; inchiKeySearch.value = '';
  normalizeChemical();
}
function focusCity(record) {
  if (record?.city && cityById.value.has(record.city)) city.value = record.city;
}
function sortBy(key) {
  if (sortKey.value === key) sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc';
  else { sortKey.value = key; sortDirection.value = ['observed', 'value'].includes(key) ? 'desc' : 'asc'; }
  page.value = 1;
}
function sortMark(key) { return sortKey.value === key ? (sortDirection.value === 'asc' ? ' ↑' : ' ↓') : ' ↕'; }
function exportRows() {
  exportError.value = '';
  try {
    if (props.module === 'rank') {
      downloadCsv(`WPN-Rank-${metric.value}-${statistic.value}.csv`, [
        { header: 'StdInChIKey', value: 'chemical' }, { header: 'Chemical', value: row => chemicalById.value.get(row.chemical)?.name || row.chemical },
        { header: 'Category', value: row => chemicalById.value.get(row.chemical)?.category || '' },
        { header: 'Metric', value: () => metric.value }, { header: 'Statistic', value: () => statistic.value },
        { header: 'Global_rank', value: row => row[rankField.value] }, { header: 'Value', value: row => row[statistic.value] },
        { header: 'Unit', value: () => unit.value }, { header: 'Mean_based_contribution_percent', value: 'contribution' },
      ], tableRows.value);
    } else {
      downloadCsv(`WPN-${props.module}-${scope.value}-filtered.csv`, [
        { header: 'GUB_city_unit', value: 'city' }, { header: 'City', value: row => cityName(row.city) },
        { header: 'Country', value: row => cityById.value.get(row.city)?.country },
        { header: 'StdInChIKey', value: 'chemical' }, { header: 'Chemical', value: row => chemicalById.value.get(row.chemical)?.name || row.chemical },
        { header: 'Observed_concentration_nM', value: 'observed' }, { header: 'Final_concentration_nM', value: 'value' },
        { header: 'Deterministic_concentration_nM', value: 'deterministic' }, { header: 'Unit', value: () => 'nM' },
        { header: 'Status', value: row => row.isObserved ? 'Observed' : 'Reconstructed' }, { header: 'Is_observed', value: 'isObserved' },
      ], tableRows.value);
    }
  } catch (cause) { exportError.value = cause.message; }
}

// Chart identity is independent of every chemical filter used by the table.
// Country and city remain shared so a spatial selection can focus both views.
const chartConcentrationRows = computed(() => {
  const rows = selectConcentrations(data.value.concentrations || [], {
    cityIds: allowedCities.value,
    chemicalIds: new Set(isChartSum.value ? chemicals.value.map(item => item.id) : [chartChemical.value]),
  });
  if (!isChartSum.value) return rows;
  const totals = new Map();
  for (const row of rows) {
    if (!Number.isFinite(row.value)) continue;
    let total = totals.get(row.city);
    if (!total) {
      total = { city: row.city, chemical: ALL_CHEMICALS, value: 0, isAggregate: true, chemicalCount: 0, observedCount: 0, reconstructedCount: 0 };
      totals.set(row.city, total);
    }
    total.value += row.value;
    total.chemicalCount += 1;
    if (row.isObserved) total.observedCount += 1;
    else total.reconstructedCount += 1;
  }
  return [...totals.values()];
});
const mapRows = computed(() => chartConcentrationRows.value.filter(row => {
  const location = cityById.value.get(row.city);
  return row.value != null && Number.isFinite(row.value) && location && Number.isFinite(location.lon) && Number.isFinite(location.lat);
}));
const mapRange = computed(() => {
  if (!mapRows.value.length) return null;
  const values = mapRows.value.map(row => row.value);
  return { min: Math.min(...values), max: Math.max(...values) };
});
const mapRangeText = computed(() => !mapRange.value ? 'No concentration data'
  : mapRange.value.min === mapRange.value.max ? `Concentration: ${numberText(mapRange.value.min, 6)} nM (all displayed cities)`
  : `Concentration range: ${numberText(mapRange.value.min, 6)}–${numberText(mapRange.value.max, 6)} nM`);
const cityBars = computed(() => mapRows.value.slice().sort((a, b) => b.value - a.value));
function concentrationTooltip(row) {
  const location = cityById.value.get(row.city);
  if (row.isAggregate) return `<strong>${escapeHtml(location?.name)}</strong> · ${escapeHtml(location?.country)}<br>All chemicals (sum)<br>${escapeHtml(numberText(row.value, 6))} nM<br>Sum of ${row.chemicalCount} of ${chemicals.value.length} chemicals<br>${row.observedCount} observed; ${row.reconstructedCount} reconstructed`;
  return `<strong>${escapeHtml(location?.name)}</strong> · ${escapeHtml(location?.country)}<br>${escapeHtml(chemicalName(row.chemical))}<br>${escapeHtml(numberText(row.value, 6))} nM<br>${row.isObserved ? 'Observed' : 'Reconstructed'}`;
}
const mapOption = computed(() => ({
  toolbox: chartToolbox,
  tooltip: { trigger: 'item', formatter: params => params.data?.record ? concentrationTooltip(params.data.record) : escapeHtml(params.name) },
  visualMap: mapRange.value ? {
    type: 'continuous', dimension: 2, seriesIndex: 0,
    min: mapRange.value.min, max: mapRange.value.max,
    orient: 'horizontal', left: 'center', bottom: 6, itemWidth: 14, itemHeight: 150,
    calculable: false, hoverLink: false,
    text: [`${numberText(mapRange.value.max, 6)} nM`, `${numberText(mapRange.value.min, 6)} nM`],
    textGap: 8, textStyle: { color: '#43526a', fontSize: 11 },
    inRange: { color: mapRange.value.min === mapRange.value.max ? ['#21918c', '#21918c'] : ['#440154', '#3b528b', '#21918c', '#5ec962', '#fde725'] },
    ...(mapRange.value.min === mapRange.value.max ? { outOfRange: { color: ['#21918c', '#21918c'] } } : {}),
  } : undefined,
  graphic: [{ type: 'text', left: 'center', bottom: 35, style: { text: 'Concentration (nM)', fill: '#43526a', fontSize: 12 } }],
  geo: { map: 'wpn-world', boundingCoords: [[-27, 73], [48, 32]], roam: true, scaleLimit: { min: 1, max: 10 }, top: 28, bottom: 70, left: 8, right: 8,
    itemStyle: { areaColor: '#eef2f6', borderColor: '#a7b5c5', borderWidth: 0.65 }, emphasis: { disabled: true } },
  series: [{ name: 'Concentration (nM)', type: 'scatter', coordinateSystem: 'geo', symbolSize: 10,
    itemStyle: { opacity: 0.9, borderColor: '#fff', borderWidth: 0.8 },
    data: mapRows.value.map(row => { const location = cityById.value.get(row.city); return { name: location.name, value: [location.lon, location.lat, row.value], record: row }; }),
  }],
}));
const cityBarOption = computed(() => ({
  toolbox: chartToolbox, grid: { left: 120, right: cityBars.value.length > 20 ? 62 : 30, top: 35, bottom: 55 },
  tooltip: { trigger: 'item', formatter: params => concentrationTooltip(params.data.record) },
  xAxis: { type: 'value', splitNumber: 3, name: 'Concentration (nM)', nameLocation: 'middle', nameGap: 34, axisLabel: { hideOverlap: true, formatter: value => numberText(value, 3) } },
  yAxis: { type: 'category', inverse: true, data: cityBars.value.map(row => cityName(row.city)), axisLabel: { width: 105, overflow: 'truncate' } },
  dataZoom: cityBars.value.length > 20 ? [{ type: 'slider', yAxisIndex: 0, right: 6, width: 15, start: 0, end: Math.min(100, 2000 / cityBars.value.length), filterMode: 'none' }, { type: 'inside', yAxisIndex: 0, start: 0, end: Math.min(100, 2000 / cityBars.value.length), filterMode: 'none' }] : [],
  series: [{ type: 'bar', data: cityBars.value.map(row => ({ value: row.value, record: row, itemStyle: { color: row.isAggregate || row.isObserved ? '#2463df' : '#1a9c8f' } })), barMaxWidth: 20 }],
}));
const validationOption = computed(() => {
  const points = validation.value.predictions.filter(row => Number.isFinite(row.trueLog10) && Number.isFinite(row.predictedLog10));
  const extrema = points.flatMap(row => [row.trueLog10, row.predictedLog10]);
  let min = extrema.length ? Math.floor(Math.min(...extrema)) : -1;
  let max = extrema.length ? Math.ceil(Math.max(...extrema)) : 1;
  if (min === max) { min -= 1; max += 1; }
  return { toolbox: chartToolbox, grid: { left: 66, right: 28, top: 30, bottom: 65 },
    tooltip: { trigger: 'item', formatter: params => { const row = params.data?.record; return row ? `${escapeHtml(cityName(row.city))}<br>${escapeHtml(chemicalName(row.chemical))}<br>Repeat ${row.repeat}<br>True: ${numberText(row.trueLog10)}<br>Predicted: ${numberText(row.predictedLog10)}` : ''; } },
    xAxis: { type: 'value', min, max, name: 'True log10 concentration (nM)', nameLocation: 'middle', nameGap: 42, axisLabel: { hideOverlap: true } },
    yAxis: { type: 'value', min, max, name: 'Predicted log10 concentration (nM)', nameLocation: 'middle', nameGap: 46, axisLabel: { hideOverlap: true } },
    series: [{ type: 'scatter', symbolSize: 4, progressive: 3000, itemStyle: { color: '#2463df', opacity: 0.28 },
      data: points.map(row => ({ value: [row.trueLog10, row.predictedLog10], record: row })),
      markLine: { silent: true, symbol: 'none', lineStyle: { color: '#db795a', type: 'dashed', width: 2 }, label: { formatter: '1:1', position: 'insideEndTop' }, data: [[{ coord: [min, min] }, { coord: [max, max] }]] },
    }],
  };
});
const topRankRows = computed(() => rankRows.value.slice(0, Number(topN.value)));
const rankOption = computed(() => ({
  toolbox: chartToolbox, grid: { left: 190, right: 35, top: 30, bottom: 66 },
  tooltip: { trigger: 'item', formatter: params => { const row = params.data.record; return `<strong>${escapeHtml(chemicalName(row.chemical))}</strong><br>Global ${statistic.value} rank: ${row[rankField.value]}<br>${escapeHtml(numberText(row[statistic.value], 6))} ${escapeHtml(unit.value)}<br>Mean-based contribution: ${numberText(row.contribution, 5)}%`; } },
  xAxis: { type: 'value', splitNumber: 3, name: `${statistic.value === 'mean' ? 'Mean' : 'Median'} (${unit.value})`, nameLocation: 'middle', nameGap: 42, axisLabel: { hideOverlap: true, formatter: value => numberText(value, 3) } },
  yAxis: { type: 'category', inverse: true, data: topRankRows.value.map(row => `${row[rankField.value]}. ${chemicalName(row.chemical)}`), axisLabel: { width: 175, overflow: 'truncate', fontSize: 12 } },
  series: [{ type: 'bar', barMaxWidth: 28, itemStyle: { color: '#2463df', borderRadius: [0, 3, 3, 0] }, data: topRankRows.value.map(row => ({ value: row[statistic.value], record: row })) }],
}));
</script>

<template>
  <section ref="explorerElement" class="wpn-explorer" :aria-label="`${module} ${tab}`">
    <div v-if="loading" class="state-panel" role="status">Loading local research data…</div>
    <div v-else-if="error" class="state-panel error" role="alert"><p>{{ error }}</p><button class="primary" @click="load(true)">Retry</button></div>
    <template v-else>
      <template v-if="module === 'rank'">
        <div class="filter-grid rank-filters">
          <label>Metric<select v-model="metric"><option value="BEQ_ugL">BEQ — effect-based priority</option><option value="WW_nM">WW — wastewater concentration</option><option value="DE_umol_day">DE — daily exposure</option></select></label>
          <label>Statistic<select v-model="statistic"><option value="mean">Mean</option><option value="median">Median</option></select></label>
          <label>Chemical search<input v-model="chemicalQuery" placeholder="Name or InChIKey" type="search"></label>
          <label>Category<select v-model="category"><option value="all">All categories</option><option v-for="item in categories" :key="item" :value="item">{{ item }}</option></select></label>
          <label v-if="tab === 'Figure'">Number of chemicals<select v-model.number="topN"><option :value="10">Top 10</option><option :value="20">Top 20</option><option :value="52">All 52</option></select></label>
        </div>
        <p class="data-note">{{ metricLabels[metric] }} · {{ unit }}. Global {{ statistic }} ranks use the frozen 117-city dataset. Searching and category filters hide rows without recalculating ranks. Contribution always means <strong>mean-based contribution</strong>.</p>
      </template>
      <template v-else-if="module !== 'imputation' || showTable">
        <div class="filter-grid">
          <label>Chemical scope<select v-model="scope"><option value="nt52">52 target chemicals (NT52)</option><option value="all">All 663 chemicals</option></select></label>
          <label>Country<select v-model="country"><option value="all">All countries</option><option v-for="item in countries" :key="item" :value="item">{{ item }}</option></select></label>
          <label>City<select v-model="city"><option value="all">All cities</option><option v-for="item in cityOptions" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
          <div class="chemical-filter"><label for="reference-chemical-name">Chemical Name</label><VAutocomplete id="reference-chemical-name" v-model="chemicalSelection" v-model:search="nameSearch" :items="nameOptions" item-title="title" item-value="value" placeholder="All chemical names" aria-label="Chemical Name" clearable hide-details density="compact" variant="outlined" :menu-props="filterMenuProps" :custom-filter="filterOption" no-data-text="No matching chemical names" /></div>
          <div class="chemical-filter"><label for="reference-chemical-cas">CAS number</label><VAutocomplete id="reference-chemical-cas" v-model="casSelection" v-model:search="casSearch" :items="casOptions" item-title="title" item-value="value" :placeholder="selectedChemical &amp;&amp; !selectedChemical.cas ? 'CAS unavailable' : 'All CAS numbers'" aria-label="CAS number" clearable hide-details density="compact" variant="outlined" :menu-props="filterMenuProps" :custom-filter="filterOption" no-data-text="No matching CAS numbers" /></div>
          <div class="chemical-filter"><label for="reference-chemical-inchikey">InChIKey</label><VAutocomplete id="reference-chemical-inchikey" v-model="chemicalSelection" v-model:search="inchiKeySearch" :items="inchiKeyOptions" placeholder="All InChIKeys" aria-label="InChIKey" clearable hide-details density="compact" variant="outlined" :menu-props="filterMenuProps" :custom-filter="filterOption" no-data-text="No matching InChIKeys" /></div>
        </div>
        <div class="filter-summary"><p class="data-note">Concentration unit: <strong>nM</strong> · {{ concentrationRows.length.toLocaleString() }} matching records · {{ observedCount.toLocaleString() }} observed · {{ (concentrationRows.length - observedCount).toLocaleString() }} reconstructed</p><button class="text-button" @click="resetFilters">Reset filters</button></div>
      </template>

      <template v-if="showTable">
        <div class="table-toolbar"><span>{{ tableRows.length.toLocaleString() }} matching rows</span><button class="primary csv-download" :disabled="!tableRows.length" @click="exportRows"><v-icon icon="mdi-download" size="18" aria-hidden="true" />Download filtered CSV</button></div>
        <p v-if="exportError" class="error-text" role="alert">{{ exportError }}</p>
        <div v-if="!tableRows.length" class="state-panel">No records match the current filters. <button class="text-button" @click="resetFilters">Reset filters</button></div>
        <template v-else>
          <div ref="tableRegion" class="table-scroll" :style="{ maxHeight: tab === 'Combined' ? 'max(300px, 45dvh)' : tableMaxHeight ? `max(300px, ${tableMaxHeight})` : null }" tabindex="0" role="region" aria-label="Research data table, scroll within this table for all rows and columns">
            <table v-if="module === 'rank'">
              <thead><tr><th>Global {{ statistic }} rank</th><th>Chemical</th><th>Category</th><th class="numeric">{{ statistic === 'mean' ? 'Mean' : 'Median' }} ({{ unit }})</th><th class="numeric">Mean-based contribution (%)</th></tr></thead>
              <tbody><tr v-for="row in pageRows" :key="`${row.chemical}-${row.metric}`"><td>{{ row[rankField] }}</td><td class="chemical-cell">{{ chemicalName(row.chemical) }}<small>{{ row.chemical }}</small></td><td>{{ chemicalById.get(row.chemical)?.category || '—' }}</td><td class="numeric">{{ numberText(row[statistic], 6) }}</td><td class="numeric">{{ numberText(row.contribution, 5) }}</td></tr></tbody>
            </table>
            <table v-else>
              <thead><tr>
                <th :aria-sort="sortKey === 'city' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'"><button @click="sortBy('city')">City{{ sortMark('city') }}</button></th>
                <th><button @click="sortBy('country')">Country{{ sortMark('country') }}</button></th>
                <th><button @click="sortBy('chemical')">Chemical{{ sortMark('chemical') }}</button></th>
                <th v-if="module === 'imputation'" class="numeric"><button @click="sortBy('observed')">Observed (nM){{ sortMark('observed') }}</button></th>
                <th class="numeric"><button @click="sortBy('value')">{{ module === 'imputation' ? 'Final value' : 'Concentration' }} (nM){{ sortMark('value') }}</button></th><th>Status</th>
              </tr></thead>
              <tbody><tr v-for="row in pageRows" :key="`${row.city}-${row.chemical}`"><td>{{ cityName(row.city) }}</td><td>{{ cityById.get(row.city)?.country }}</td><td class="chemical-cell">{{ chemicalName(row.chemical) }}<small>{{ row.chemical }}</small></td><td v-if="module === 'imputation'" class="numeric">{{ numberText(row.observed, 6) }}</td><td class="numeric">{{ numberText(row.value, 6) }}</td><td><span class="status" :class="row.isObserved ? 'observed' : 'reconstructed'">{{ row.isObserved ? 'Observed' : 'Reconstructed' }}</span></td></tr></tbody>
            </table>
          </div>
          <nav class="pagination" aria-label="Table pages"><span>{{ ((page - 1) * perPage + 1).toLocaleString() }}–{{ Math.min(page * perPage, tableRows.length).toLocaleString() }} of {{ tableRows.length.toLocaleString() }} · {{ perPage }} per page</span><div><button :disabled="page === 1" @click="page = 1" aria-label="First page">«</button><button :disabled="page === 1" @click="page--" aria-label="Previous page">‹</button><span>Page {{ page }} / {{ pageCount }}</span><button :disabled="page === pageCount" @click="page++" aria-label="Next page">›</button><button :disabled="page === pageCount" @click="page = pageCount" aria-label="Last page">»</button></div></nav>
        </template>
      </template>

      <section v-if="showCharts && module === 'ww'" class="concentration-charts" aria-label="Wastewater map and chart">
        <div class="chemical-filter chart-chemical-selector"><label for="chart-chemical">Chemical shown in map &amp; chart</label><VAutocomplete id="chart-chemical" v-model="chartChemicalSelection" v-model:search="chartSearch" :items="chartChemicalOptions" item-title="title" item-value="value" placeholder="All chemicals (sum)" aria-label="Chemical shown in map &amp; chart" clearable hide-details density="compact" variant="outlined" :menu-props="filterMenuProps" :custom-filter="filterOption" no-data-text="No matching chemicals" /></div>
        <div v-if="!mapRows.length" class="state-panel">No mapped concentrations match these filters. <button class="text-button" @click="resetFilters">Reset filters</button></div>
        <template v-else><h3 class="plot-heading">{{ chartChemicalLabel }}</h3><div class="plots-grid"><Plot :option="mapOption" :map-data="data.world" :height="520" :figure-number="1" aria-label="European city wastewater concentration map" @point-select="focusCity" :caption="`${mapRows.length} cities. ${isChartSum ? `Sum of all ${chemicals.length} chemical concentrations, including observed and reconstructed values` : chemicalName(chartChemical)}. ${mapRangeText}. Colour follows the continuous concentration scale. Click a marker to focus that city in the table and charts; Reset filters restores all cities.`" /><Plot :option="cityBarOption" :height="520" :figure-number="2" aria-label="City concentrations in descending order" @point-select="focusCity" :caption="`The same ${cityBars.length} cities, ordered by ${isChartSum ? 'total ' : ''}concentration in nM. ${isChartSum ? `Each bar sums all ${chemicals.length} chemicals, including observed and reconstructed values.` : 'Blue: observed; green: reconstructed.'} Click a bar to focus that city in the table and charts; Reset filters restores all cities. ${cityBars.length > 20 ? 'Use the vertical slider to inspect all cities.' : ''}`" /></div></template>
      </section>

      <section v-else-if="showCharts && module === 'imputation'" class="validation-charts" aria-label="Reconstruction validation charts">
        <div class="validation-toolbar"><label>Validation repeat<select v-model="repeat"><option value="all">All 10 repeats</option><option v-for="value in repeatOptions" :key="value" :value="value">Repeat {{ value }}</option></select></label><span>Held-out predictions from the frozen validation output.</span></div>
        <div v-if="validation.summary" class="metric-cards"><div><span>R² (log10)</span><strong>{{ numberText(validation.summary.r2_log10, 4) }}</strong></div><div><span>RMSE (log10)</span><strong>{{ numberText(validation.summary.rmse_log10, 4) }}</strong></div><div><span>MAE (log10)</span><strong>{{ numberText(validation.summary.mae_log10, 4) }}</strong></div><div><span>Pearson r (log10)</span><strong>{{ numberText(validation.summary.pearson_r_log10, 4) }}</strong></div></div>
        <p v-else class="error-text">A frozen validation summary is unavailable for this repeat.</p>
        <Plot v-if="validation.predictions.length" :option="validationOption" :height="520" aria-label="True versus predicted log10 concentration validation scatter plot" :caption="`${validation.predictions.length.toLocaleString()} held-out predictions. Both axes are log10 concentration (nM); the dashed line is 1:1. Metrics come from the frozen ${repeat === 'all' ? 'overall summary across 10 repeats' : `repeat ${repeat} summary`}, without recalculation. The concentration filters above do not alter this validation chart.`" />
        <div v-else class="state-panel">No validation predictions are available for this repeat.</div>
        <FigureCard :figure="validationFigure" :figure-number="2" :show-actions="false" />
      </section>

      <template v-else-if="showCharts && module === 'rank'">
        <Plot v-if="topRankRows.length" :option="rankOption" :height="Math.max(430, topRankRows.length * 26 + 100)" aria-label="Global chemical priority ranking" :caption="`${topRankRows.length} displayed chemicals from ${rankRows.length} matching rows. Labels retain the original global ${statistic} rank across 117 cities. Values are in ${unit}; mean-based contribution remains a separate statistic.`" />
        <div v-else class="state-panel">No chemicals match the search and category. <button class="text-button" @click="resetFilters">Reset filters</button></div>
        <figure class="paper-figure"><a href="/figures/Fig3.png" target="_blank" rel="noopener"><img src="/figures/Fig3.png" :alt="`Fig ${topRankRows.length ? 2 : 1}. Chemical exposure and effect-based prioritization`" loading="lazy"></a><figcaption><strong class="figure-number">Fig {{ topRankRows.length ? 2 : 1 }}.</strong> Chemical exposure and effect-based prioritization. Select the image to view it at full resolution.</figcaption></figure>
      </template>
    </template>
  </section>
</template>

<style scoped>
.wpn-explorer { width: 100%; color: #29313d; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; }
.filter-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px 22px; margin-bottom: 16px; }
.filter-grid.rank-filters { grid-template-columns: repeat(4, minmax(0, 1fr)); }
label { display: flex; flex-direction: column; gap: 7px; font-size: 14px; font-weight: 600; color: #334155; min-width: 0; }
input, select { box-sizing: border-box; width: 100%; min-width: 0; height: 40px; padding: 7px 10px; border: 1px solid #cbd3df; border-radius: 5px; background: #fff; color: #29313d; font: 14px Arial, sans-serif; }
input:focus, select:focus { outline: 2px solid #bfd2fb; border-color: #2463df; outline-offset: 1px; }
button { font: inherit; cursor: pointer; }
button:disabled { cursor: default; opacity: 0.45; }
button:focus-visible, a:focus-visible { outline: 2px solid #2463df; outline-offset: 3px; }
.primary { border: 1px solid #2463df; border-radius: 5px; background: #2463df; color: #fff; padding: 9px 16px; font-size: 14px; font-weight: 600; }
.primary:hover:not(:disabled) { background: #1c51bf; }
.text-button { color: #2463df; background: transparent; border: 0; padding: 3px 0; font-size: 14px; }
.text-button:hover { text-decoration: underline; }
.data-note { color: #5f6c7b; margin: 12px 0 16px; font-size: 14px; line-height: 1.7; }
.filter-summary, .table-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin: 14px 0; font-size: 14px; color: #516071; }
.filter-summary .data-note { margin: 0; }
.filter-summary .text-button { flex-shrink: 0; }
.table-toolbar { border-top: 1px solid #e7ecf2; padding-top: 16px; }
.table-scroll { width: 100%; max-height: 45dvh; overflow: auto; scrollbar-gutter: stable; overscroll-behavior: contain; border: 1px solid #dce3ec; border-radius: 6px; }
.table-scroll:focus-visible { outline: 2px solid #2463df; outline-offset: 3px; }
table { width: 100%; min-width: 760px; border-collapse: collapse; background: #fff; font-size: 14px; }
th, td { padding: 11px 12px; text-align: left; border-bottom: 1px solid #e6ebf1; vertical-align: top; }
th { position: sticky; top: 0; z-index: 1; background: #f4f7fb; box-shadow: 0 1px 0 #dce3ec; font-size: 13px; color: #334155; white-space: nowrap; }
th button { border: 0; padding: 0; background: none; color: inherit; font-weight: 600; font-size: inherit; }
tbody tr:nth-child(even) { background: #fbfcfe; }
tbody tr:hover { background: #f0f5ff; }
tbody tr:last-child td { border-bottom: 0; }
.numeric { text-align: right; font-variant-numeric: tabular-nums; }
.chemical-cell { min-width: 240px; max-width: 400px; overflow-wrap: anywhere; }
.chemical-cell small { display: block; margin-top: 3px; color: #7a8797; font-size: 11px; }
.status { display: inline-block; border-radius: 4px; padding: 2px 7px; font-size: 12px; white-space: nowrap; }
.status.observed { background: #edf3ff; color: #215bc2; }
.status.reconstructed { background: #e9f6f1; color: #237763; }
.pagination { display: flex; justify-content: space-between; align-items: center; gap: 14px; flex-wrap: wrap; margin: 16px 0; color: #66758a; font-size: 13px; }
.pagination div { display: flex; align-items: center; gap: 8px; }
.pagination button { min-width: 30px; height: 30px; border: 1px solid #d4dce7; border-radius: 4px; background: #fff; color: #2463df; font-size: 18px; }
.pagination div span { margin: 0 4px; }
.state-panel { padding: 30px 22px; background: #f7f9fc; border: 1px solid #e0e6ef; border-radius: 7px; line-height: 1.7; }
.state-panel p { margin-top: 0; }
.state-panel.error { border-color: #edc7c1; background: #fff7f5; }
.error-text { color: #ae372c; font-size: 14px; }
.plots-grid { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); gap: 20px; }
.plot-heading { font-size: 18px; margin: 24px 0 12px; }
.concentration-charts, .validation-charts { margin-top: 28px; }
.chart-chemical-selector { max-width: 560px; margin-bottom: 18px; }
.validation-toolbar { display: flex; align-items: flex-end; flex-wrap: wrap; gap: 18px; margin-bottom: 20px; }
.validation-toolbar label { min-width: 210px; }
.validation-toolbar span { font-size: 14px; color: #66758a; padding-bottom: 10px; }
.metric-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 18px; }
.metric-cards div { padding: 14px 18px; border: 1px solid #e1e7f0; border-radius: 6px; }
.metric-cards span { display: block; color: #68788c; font-size: 13px; }
.metric-cards strong { display: block; color: #2463df; font-size: 24px; font-weight: 600; margin-top: 4px; }
.paper-figure { margin: 38px 0 8px; border-top: 1px solid #e4eaf2; padding-top: 26px; }
.paper-figure img { display: block; max-width: 100%; width: 100%; height: auto; margin: 0 auto; }
.paper-figure figcaption { color: #66758a; font-size: 14px; line-height: 1.6; margin-top: 14px; }
@media (max-width: 1100px) { .filter-grid.rank-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); } .plots-grid { grid-template-columns: 1fr; } }
@media (max-width: 700px) {
  .filter-grid, .filter-grid.rank-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 13px; }
  .metric-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .pagination { align-items: flex-start; flex-direction: column; }
  .pagination div { gap: 6px; }
}
@media (max-width: 420px) { .filter-grid, .filter-grid.rank-filters { grid-template-columns: 1fr; } }
</style>
