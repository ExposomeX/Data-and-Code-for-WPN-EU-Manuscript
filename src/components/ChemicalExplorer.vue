<script setup>
import { computed, ref, watch, nextTick, onBeforeUnmount } from 'vue';
import { VAutocomplete } from 'vuetify/components';
import FigureCard from './FigureCard.vue';
import paper from '../content/paper.json';
import { downloadCsv } from '../lib/data.js';
import { useViewportTable } from '../lib/useViewportTable.js';
import { catalog, catalogLoading, catalogError, loadCatalog, chemicalName, detailText } from '../lib/scenario.js';
const props = defineProps({ tab: { type: String, required: true } });
const identityFilter = ref(null);
const nameSearch = ref(''), casSearch = ref(''), inchiKeySearch = ref('');
const sort = ref('name'), direction = ref(1), detailId = ref(''), exportError = ref('');
const detailDialog = ref(null);
const catalogElement = ref(null), tableRegion = ref(null);
const { tableMaxHeight } = useViewportTable(catalogElement, tableRegion);
let detailTrigger = null;
const collator = new Intl.Collator('en', { numeric: true, sensitivity: 'base' });
const chemicals = computed(() => (catalog.value?.chemicals || []).filter(row => row.nt52));
const scopedChemicals = chemicals;
const selectedIdentity = computed(() => scopedChemicals.value.find(row => row.id === identityFilter.value));
const casFilter = computed({ get: () => selectedIdentity.value?.cas ? identityFilter.value : null, set: value => { identityFilter.value = value; } });
const nameOptions = computed(() => scopedChemicals.value.map(row => ({ title: chemicalName(row), value: row.id })).sort((a, b) => collator.compare(a.title, b.title)));
const casOptions = computed(() => scopedChemicals.value.filter(row => row.cas).map(row => ({ title: row.cas, value: row.id, props: { subtitle: chemicalName(row) } })).sort((a, b) => collator.compare(a.title, b.title)));
const inchiKeyOptions = computed(() => scopedChemicals.value.map(row => row.id).sort(collator.compare));
const filterMenuProps = { maxHeight: 300, contentClass: 'chemical-filter-menu' };
const filterOption = (value, query) => String(value).toLowerCase().includes(query.trim().toLowerCase());
const rows = computed(() => scopedChemicals.value.filter(row =>
  !identityFilter.value || row.id === identityFilter.value).slice().sort((a, b) => {
    const x = a[sort.value], y = b[sort.value];
    if (x == null || x === '') return y == null || y === '' ? 0 : 1;
    if (y == null || y === '') return -1;
    return direction.value * (typeof x === 'number' && typeof y === 'number' ? x - y : collator.compare(String(x), String(y)));
  }));
const detail = computed(() => chemicals.value.find(row => row.id === detailId.value));
const figure = computed(() => paper.figures?.find(item => item.id.toLowerCase() === 'ed1') || paper.figures?.find(item => item.id.toLowerCase() === 'fig1'));
// Retain the source metadata, but omit this redundant block from the record dialog.
const hiddenDetailFields = new Set(['trainingMember', 'trainingMembershipBasis', 'structureIdentityStatus', 'computedStructureInChIKey', 'structureNote', 'formulaIdentityStatus', 'selectionReason', 'evidence', 'literatureMember', 'positiveREPMember', 'identitySource', 'identityFieldSources', 'identityCorrections', 'casSourceValue', 'categorySource', 'categoryLLMStatus', 'categoryNote', 'useSourceNote']);
const detailLabels = {
  name: 'Chemical name', synonyms: 'Synonyms', id: 'InChIKey', cas: 'CAS number', dtxsid: 'DTXSID', smiles: 'SMILES', formula: 'Molecular formula', molecularWeight: 'Molecular weight (g/mol)',
  category: 'Category', rep: 'Relative effect potency (REP)',
};
const detailFields = computed(() => {
  if (!detail.value) return [];
  const keys = Object.keys(detailLabels).filter(key => key in detail.value && !hiddenDetailFields.has(key));
  return keys.map(key => {
    const value = detail.value[key];
    let display = key === 'synonyms' && Array.isArray(value) && !value.length ? null : value;
    if (typeof value === 'boolean') display = value ? 'Yes' : 'No';
    else if (key === 'descriptorImputed' && value == null) display = 'Unknown';
    return [detailLabels[key] || key, display];
  });
});
async function openDetails(row, event) {
  detailTrigger = event.currentTarget;
  detailId.value = row.id;
  await nextTick();
  if (detailDialog.value && !detailDialog.value.open) detailDialog.value.showModal();
}
function closeDetails() { detailDialog.value?.close(); }
async function onDetailsClosed() {
  const trigger = detailTrigger;
  detailTrigger = null;
  detailId.value = '';
  await nextTick();
  if (trigger?.isConnected) trigger.focus();
}
watch(() => props.tab, () => { closeDetails(); detailId.value = ''; detailTrigger = null; });
onBeforeUnmount(() => { detailTrigger = null; closeDetails(); });
watch([identityFilter, sort, direction], () => { exportError.value = ''; });
function clearIdentityFilters() {
  identityFilter.value = null;
  nameSearch.value = ''; casSearch.value = ''; inchiKeySearch.value = '';
}
function sortBy(key) { if (sort.value === key) direction.value *= -1; else { sort.value = key; direction.value = 1; } }
const mark = key => sort.value === key ? direction.value === 1 ? ' ↑' : ' ↓' : ' ↕';
function resetFilters() { clearIdentityFilters(); }
function exportRows() {
  exportError.value = '';
  try {
    const fields = ['name','cas','id','category','synonyms','formula','molecularWeight','dtxsid','smiles','rep'];
    downloadCsv('WPN-Chemicals.csv', fields.map(key => ({ header: detailLabels[key] || key, value: row => Array.isArray(row[key]) ? row[key].join('; ') : row[key] })), rows.value);
  } catch (error) { exportError.value = error.message; }
}
async function retry() { try { await loadCatalog(true); } catch { /* shown in the shared error panel */ } }
loadCatalog().catch(() => {});
</script>

<template>
  <section ref="catalogElement" class="scenario" :class="{'chemical-data':tab==='Data'}" aria-label="Chemical catalog">
    <div v-if="catalogLoading && !catalog" class="state" role="status">Loading the local chemical catalog…</div>
    <div v-else-if="catalogError" class="state error" role="alert"><p>{{ catalogError }}</p><button class="primary" @click="retry">Retry catalog</button></div>
    <template v-else-if="catalog">
      <template v-if="tab === 'Data'">
        <h2>Chemical catalog</h2>
        <div class="filters chemical-filters">
          <div class="chemical-filter"><label for="chemical-name-filter">Chemical name</label><VAutocomplete id="chemical-name-filter" v-model="identityFilter" v-model:search="nameSearch" :items="nameOptions" item-title="title" item-value="value" placeholder="All chemical names" aria-label="Chemical name" clearable hide-details density="compact" variant="outlined" :menu-props="filterMenuProps" :custom-filter="filterOption" no-data-text="No matching chemical names" /></div>
          <div class="chemical-filter"><label for="chemical-cas-filter">CAS number</label><VAutocomplete id="chemical-cas-filter" v-model="casFilter" v-model:search="casSearch" :items="casOptions" item-title="title" item-value="value" :placeholder="selectedIdentity &amp;&amp; !selectedIdentity.cas ? 'CAS unavailable' : 'All CAS numbers'" aria-label="CAS number" clearable hide-details density="compact" variant="outlined" :menu-props="filterMenuProps" :custom-filter="filterOption" no-data-text="No matching CAS numbers" /></div>
          <div class="chemical-filter"><label for="chemical-inchikey-filter">InChIKey</label><VAutocomplete id="chemical-inchikey-filter" v-model="identityFilter" v-model:search="inchiKeySearch" :items="inchiKeyOptions" placeholder="All InChIKeys" aria-label="InChIKey" clearable hide-details density="compact" variant="outlined" :menu-props="filterMenuProps" :custom-filter="filterOption" no-data-text="No matching InChIKeys" /></div>
        </div>
        <div class="toolbar"><span>{{ rows.length }} {{ rows.length === 1 ? 'chemical' : 'chemicals' }}</span><div class="actions"><button class="link" @click="resetFilters">Reset filters</button><button class="primary csv-download" :disabled="!rows.length" @click="exportRows"><v-icon icon="mdi-download" size="18" aria-hidden="true" />Download CSV</button></div></div>
        <p v-if="exportError" class="error-text" role="alert">{{ exportError }}</p>
        <div v-if="!rows.length" class="state">No chemicals match these filters. <button class="link" @click="resetFilters">Reset filters</button></div>
        <template v-else>
          <div ref="tableRegion" class="table-scroll chemical-table-scroll" :style="{maxHeight:tableMaxHeight}" tabindex="0" role="region" aria-label="All matching chemicals, scroll within this table">
            <table><thead><tr>
              <th><button @click="sortBy('name')">Chemical name{{ mark('name') }}</button></th><th><button @click="sortBy('cas')">CAS number{{ mark('cas') }}</button></th><th><button @click="sortBy('id')">InChIKey{{ mark('id') }}</button></th><th><button @click="sortBy('category')">Category{{ mark('category') }}</button></th><th>Details</th>
            </tr></thead><tbody><tr v-for="row in rows" :key="row.id">
              <td class="chem">{{ chemicalName(row) }}</td><td>{{ detailText(row.cas) }}</td><td class="chemical-key">{{ row.id }}</td><td>{{ row.category || '—' }}</td><td><button class="link" aria-haspopup="dialog" :aria-label="`Details for ${chemicalName(row)}`" @click="openDetails(row, $event)">Details</button></td>
            </tr></tbody></table>
          </div>
        </template>
        <Teleport to="body">
          <dialog v-if="detail" ref="detailDialog" class="scenario chemical-dialog" aria-labelledby="chemical-dialog-title" @close="onDetailsClosed" @cancel.prevent="closeDetails" @click="event => { if (event.target === detailDialog) closeDetails(); }">
            <div class="dialog-shell">
              <header class="dialog-header"><h2 id="chemical-dialog-title">{{ chemicalName(detail) }}</h2><button class="secondary" autofocus aria-label="Close chemical details" @click="closeDetails">Close <span aria-hidden="true">×</span></button></header>
              <div class="dialog-content"><dl><template v-for="[label, value] in detailFields" :key="label"><dt>{{ label }}</dt><dd>{{ detailText(value) }}</dd></template></dl></div>
            </div>
          </dialog>
        </Teleport>
      </template>
      <template v-else>
        <h2>How the target panel was selected</h2><p class="note">{{ figure?.id.toLowerCase() === 'ed1' ? 'The selection of 52 target chemicals and their eight categories.' : 'The study framework and chemical-selection evidence.' }}</p><FigureCard v-if="figure" :figure="figure" :show-actions="false" /><div v-else class="state">The chemical-selection figure is unavailable.</div>
      </template>
    </template>
  </section>
</template>
<style scoped src="./scenario.css"></style>
<style scoped>
.chemical-data h2{margin-bottom:8px}.chemical-data .note{margin:8px 0 12px}.chemical-data .filters{margin:14px 0 12px}.chemical-data .toolbar{margin:12px 0}
.chemical-table-scroll{max-height:45dvh;scrollbar-gutter:stable;overscroll-behavior:contain}
.chemical-table-scroll th{position:sticky;top:0;z-index:1;box-shadow:0 1px 0 #dce3ec}
.chemical-table-scroll:focus-visible{outline:2px solid #2463df;outline-offset:3px}
@media(max-width:620px),(max-height:639px){.chemical-table-scroll{max-height:45dvh}}
</style>
