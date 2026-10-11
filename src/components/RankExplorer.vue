<script setup>
import { computed, ref, shallowRef, watch, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { VAutocomplete } from 'vuetify/components';
import Plot from './Plot.vue';
import { loadData, numberText, downloadCsv, escapeHtml } from '../lib/data.js';
import { catalog, loadCatalog, snapshot, dirty, runState, resumeRun, chemicalName, matchesChemical } from '../lib/scenario.js';
import { currentRankRows, studyRankRows, cumulativeRankRows, rankCsvColumns } from '../lib/rankResults.js';
import { useViewportTable } from '../lib/useViewportTable.js';
import { rankLogAxis } from '../lib/rankAxis.js';

defineProps({ tab: { type: String, required: true } });
const route = useRoute(), router = useRouter();
const source = computed(() => route.query.source === 'reference' ? 'reference' : 'current');
const query = ref(''), scale = ref('log');
const selectedChemical = ref(null);
const searchQuery = computed(() => String(query.value || '').trim());
const rankElement = ref(null), tableRegion = ref(null);
const { tableMaxHeight } = useViewportTable(rankElement, tableRegion);
const reference = shallowRef([]), loading = ref(false), error = ref(''), exportError = ref('');
const chemicalById = computed(() => new Map((catalog.value?.chemicals || []).map(row => [row.id, row])));
const labelFor = id => chemicalName(chemicalById.value.get(id)) || id;
const shortLabelFor = id => {
  const name = labelFor(id);
  const abbreviation = name.match(/\(([A-Z][A-Z\d-]{1,11})\)$/)?.[1];
  return abbreviation || (name.length > 25 ? `${name.slice(0, 23)}…` : name);
};
const allRows = computed(() => source.value === 'current' ? currentRankRows(snapshot.value) : studyRankRows(reference.value));
const chemicalOptions = computed(() => allRows.value.map(row => ({
  title: labelFor(row.chemical), value: row.chemical,
  props: { subtitle: [chemicalById.value.get(row.chemical)?.cas, row.chemical].filter(Boolean).join(' · ') },
})));
const filterChemicalOption = (value, search, item) => matchesChemical(chemicalById.value.get(item?.raw?.value), search);
function selectChemical(value) { selectedChemical.value = value; query.value = ''; }
function clearSearch() { selectedChemical.value = null; query.value = ''; }
const rows = computed(() => allRows.value.filter(row => selectedChemical.value
  ? row.chemical === selectedChemical.value
  : !searchQuery.value || matchesChemical(chemicalById.value.get(row.chemical), searchQuery.value)));
const chartRows = computed(() => cumulativeRankRows(allRows.value));
const beqLabel = computed(() => source.value === 'reference' ? 'Mean BEQ' : 'BEQ');

const option = computed(() => {
  const points = chartRows.value;
  const logAxis = rankLogAxis(points.map(row => row.beq));
  const coordinateFactor = scale.value === 'log' ? logAxis.factor : 1;
  return {
    toolbox: { feature: { saveAsImage: { name: `WPN-${source.value === 'reference' ? 'study' : 'my'}-BEQ-ranking-${scale.value === 'log' ? 'log' : 'linear'}`, pixelRatio: 2 } } },
    grid: { left: 76, right: 68, top: 72, bottom: 220 },
    legend: { top: 0, data: [beqLabel.value, 'Cumulative contribution'], textStyle: { color: '#43526a', fontSize: 12 } },
    tooltip: {
      trigger: 'axis', confine: true, axisPointer: { type: 'shadow' },
      formatter: items => {
        const row = items.find(item => item.data?.record)?.data.record;
        if (!row) return '';
        return `<strong>${escapeHtml(labelFor(row.chemical))}</strong><br>Rank: ${row.rank}<br>${beqLabel.value}: ${numberText(row.beq, 7)} μg/L Narciclasine-EQ<br>WW ${source.value === 'reference' ? 'mean' : 'input'}: ${numberText(row.ww, 7)} nM<br>Contribution: ${numberText(row.contribution, 5)}%<br>Cumulative contribution: ${numberText(row.cumulative, 5)}%`;
      },
    },
    xAxis: {
      type: 'category', name: 'Chemical', nameLocation: 'middle', nameGap: 156,
      data: points.map(row => row.chemical),
      axisLabel: { interval: 'auto', rotate: 55, hideOverlap: true, fontSize: 11, width: 150, overflow: 'truncate', formatter: shortLabelFor },
      axisTick: { alignWithLabel: true }, axisLine: { lineStyle: { color: '#758499' } },
    },
    yAxis: [
      {
        type: scale.value, logBase: 10, min: scale.value === 'log' ? logAxis.min : 0,
        max: scale.value === 'log' ? logAxis.max : undefined,
        interval: scale.value === 'log' ? logAxis.interval : undefined,
        // ECharts otherwise starts log-axis bars at 1, reversing bars below 1.
        startValue: scale.value === 'log' ? logAxis.min : 0,
        name: `${beqLabel.value}\n(μg/L Narciclasine-EQ)`, nameGap: 18,
        nameTextStyle: { align: 'left', padding: [0, 0, 0, -48], color: '#43526a', lineHeight: 17 },
        splitLine: { lineStyle: { color: '#e8edf4' } },
        axisLabel: { color: '#526278', formatter: value => numberText(value / coordinateFactor, 2) },
      },
      {
        type: 'value', min: 0, max: 100, interval: 25, name: 'Cumulative\ncontribution (%)', nameGap: 18,
        nameTextStyle: { align: 'right', padding: [0, -40, 0, 0], color: '#43526a', lineHeight: 17 },
        splitLine: { show: false }, axisLabel: { formatter: '{value}%', color: '#526278' },
      },
    ],
    dataZoom: [{
      type: 'slider', xAxisIndex: 0, filterMode: 'none', start: 0, end: 100,
      left: 76, right: 68, bottom: 10, height: 26, minValueSpan: 0,
      showDetail: false, showDataShadow: false, brushSelect: false,
      borderColor: '#cbd9eb', backgroundColor: '#f5f8fc', fillerColor: 'rgba(36,99,223,.15)',
      handleStyle: { color: '#2463df', borderColor: '#2463df' },
    }],
    series: [
      {
        name: beqLabel.value, type: 'bar', yAxisIndex: 0, barMaxWidth: 46,
        itemStyle: { color: '#2463df', borderRadius: [2, 2, 0, 0] },
        data: points.map(row => ({ value: row.beq * coordinateFactor, record: row })),
      },
      {
        name: 'Cumulative contribution', type: 'line', yAxisIndex: 1,
        itemStyle: { color: '#e19a30' }, lineStyle: { width: 2.5 }, symbol: 'circle', symbolSize: 5,
        data: points.map(row => ({ value: row.cumulative, record: row })),
      },
    ],
  };
});

let loadSequence = 0;
let controller;
async function load(refresh = false) {
  const sequence = ++loadSequence;
  controller?.abort(); controller = new AbortController();
  loading.value = true; error.value = '';
  try {
    const tasks = [loadCatalog(refresh)];
    if (source.value === 'reference') tasks.push(loadData('ranks', { signal: controller.signal, refresh }));
    const values = await Promise.all(tasks);
    if (sequence !== loadSequence) return;
    if (values[1]) reference.value = values[1];
  } catch (cause) { if (sequence === loadSequence && cause.name !== 'AbortError') error.value = cause.message; }
  finally { if (sequence === loadSequence) loading.value = false; }
}
function setSource(value) { router.replace({ query: { ...route.query, source: value } }); }
function exportRows() {
  exportError.value = '';
  try {
    downloadCsv(`WPN-${source.value === 'current' ? 'My-results' : 'Study-results'}-BEQ.csv`, rankCsvColumns(labelFor), rows.value);
  } catch (cause) { exportError.value = cause.message; }
}
watch(source, () => { clearSearch(); load(); }, { immediate: true });
watch([source, query, selectedChemical], () => { exportError.value = ''; });
onBeforeUnmount(() => { ++loadSequence; controller?.abort(); });
</script>

<template>
  <section ref="rankElement" class="scenario rank-results" :class="{ 'rank-data': tab === 'Data' }" aria-label="Chemical rankings">
    <div class="switches result-sources" role="group" aria-label="Ranking source">
      <button :class="{active:source === 'current'}" :aria-pressed="source === 'current'" @click="setSource('current')">My results</button>
      <button :class="{active:source === 'reference'}" :aria-pressed="source === 'reference'" @click="setSource('reference')">Study results</button>
    </div>
    <div v-if="loading" class="state" role="status">Loading results…</div>
    <div v-else-if="error" class="state error" role="alert"><p>{{ error }}</p><button class="primary" @click="load(true)">Retry</button></div>
    <template v-else-if="source === 'current' && !snapshot">
      <div class="state empty-results">
        <h2>Your results will appear here</h2><p>Enter your WW concentrations and run WPN.</p>
        <router-link class="primary" to="/wpn/Data">Enter concentrations</router-link>
        <p v-if="runState.id" class="note" role="status">{{ runState.status === 'paused' ? 'Your calculation is waiting to reconnect.' : 'Your calculation is in progress.' }}</p>
        <button v-if="runState.status === 'paused'" class="link" @click="resumeRun">Reconnect calculation</button>
        <p v-if="runState.error" class="error-text" role="alert">{{ runState.error }}</p>
      </div>
    </template>
    <template v-else>
      <div class="result-heading">
        <h2>{{ source === 'current' ? 'Your chemical priorities' : 'Study chemical priorities' }} (BEQ ranking)</h2>
        <p v-if="tab === 'Figure'" class="result-summary">{{ allRows.length }} chemicals {{ source === 'current' ? 'evaluated' : '· Mean values across 117 cities' }}</p>
      </div>
      <p v-if="source === 'current' && dirty" class="notice">Inputs have changed. These are your previous results. <router-link class="link" to="/wpn/Data">Update results</router-link></p>
      <template v-if="tab === 'Data'">
        <div class="toolbar rank-table-tools">
          <div class="chemical-filter rank-chemical-filter"><label for="rank-chemical-filter">Chemical search</label><VAutocomplete id="rank-chemical-filter" :model-value="selectedChemical" v-model:search="query" :items="chemicalOptions" item-title="title" item-value="value" :custom-filter="filterChemicalOption" placeholder="All chemicals · Name, CAS or InChIKey" aria-label="Chemical search" clearable hide-details density="compact" variant="outlined" :menu-props="{maxHeight:300,contentClass:'chemical-filter-menu'}" no-data-text="No matching chemicals" @update:model-value="selectChemical" /></div>
          <div class="actions"><span>{{ rows.length }} {{ rows.length === 1 ? 'chemical' : 'chemicals' }}<template v-if="source === 'reference'"> · Mean values across 117 cities</template></span><button class="primary" :disabled="!rows.length" @click="exportRows"><v-icon icon="mdi-download" size="18" class="mr-2" aria-hidden="true" />Download CSV</button></div>
        </div>
        <p v-if="exportError" class="error-text" role="alert">{{ exportError }}</p>
        <div v-if="!rows.length" class="state">No chemicals match your search. <button class="link" @click="clearSearch">Clear search</button></div>
        <template v-else>
          <div ref="tableRegion" class="table-scroll" :style="{ maxHeight: tableMaxHeight }" role="region" tabindex="0" aria-label="Chemical priority ranking table">
            <table><thead><tr><th>Rank</th><th>Chemical</th><th class="number">WW input <small>(nM)</small></th><th class="number">BEQ <small>(μg/L Narciclasine-EQ)</small></th><th class="number">Contribution <small>(%)</small></th></tr></thead>
              <tbody><tr v-for="row in rows" :key="row.chemical"><td>{{ row.rank }}</td><td class="chem">{{ labelFor(row.chemical) }}</td><td class="number">{{ numberText(row.ww, 7) }}</td><td class="number">{{ numberText(row.beq, 7) }}</td><td class="number">{{ numberText(row.contribution, 6) }}</td></tr></tbody>
            </table>
          </div>
        </template>
      </template>
      <template v-else>
        <div class="rank-chart-shell"><Plot :option="option" :height="632" :show-number="false" aria-label="BEQ bars and cumulative contribution by chemical, in descending BEQ order">
          <template #controls><div class="switches axis-switches" role="group" aria-label="BEQ axis scale"><button :class="{active:scale === 'log'}" :aria-pressed="scale === 'log'" @click="scale = 'log'">Log scale</button><button :class="{active:scale === 'value'}" :aria-pressed="scale === 'value'" @click="scale = 'value'">Linear scale</button></div></template>
        </Plot></div>
      </template>
    </template>
  </section>
</template>

<style scoped src="./scenario.css"></style>
<style scoped>
.rank-results .result-sources {margin:0 0 24px;gap:10px;}
.rank-results .result-sources button {padding:10px 21px;font-weight:600;}
.rank-results .result-sources button.active {color:#fff;background:#2463df;border-color:#2463df;}
.rank-results .result-heading {display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 16px;margin-bottom:8px;}
.rank-results .result-heading h2 {margin:0;}
.rank-results .result-heading .result-summary {font-size:14px;font-weight:400;color:#627084;margin:0;}
.rank-results .empty-results {padding:28px;}
.rank-results .empty-results .primary {display:inline-block;text-decoration:none;}
.rank-results .axis-switches {margin:0;gap:5px;flex-wrap:nowrap;}
.rank-results .axis-switches button {font-size:13px;padding:6px 11px;}
.rank-results .rank-table-tools {align-items:flex-end;margin:20px 0;}
.rank-results .rank-chemical-filter {width:min(380px,100%);}
.rank-results table {min-width:680px;}
.rank-results th small {display:block;font-size:11px;font-weight:400;margin-top:3px;}
.rank-results .rank-chart-shell {min-width:0;}
.rank-results.rank-data .result-sources {margin-bottom:12px;}
.rank-results.rank-data .result-sources button {padding:8px 18px;}
.rank-results.rank-data .notice {margin:8px 0;padding:8px 12px;}
.rank-results.rank-data .rank-table-tools {margin:10px 0;}
.rank-results.rank-data .table-scroll {max-height:45dvh;scrollbar-gutter:stable;overscroll-behavior:contain;}
.rank-results.rank-data .table-scroll:focus-visible {outline:2px solid #2463df;outline-offset:3px;}
.rank-results.rank-data thead th {position:sticky;top:0;z-index:1;box-shadow:0 1px 0 #dce3ec;}
@media(max-width:620px){.rank-results .result-sources{gap:8px;}.rank-results .result-sources button{flex:1;padding:10px 12px;}.rank-results .rank-chemical-filter{width:100%;}.rank-results .rank-table-tools .actions{width:100%;justify-content:space-between;}.rank-results .empty-results{padding:20px;}.rank-results .rank-chart-shell{margin:0 -12px;}}
</style>
