import { _ as _export_sfc, i as watch, j as onBeforeUnmount, r as resolveComponent, o as openBlock, c as createElementBlock, u as unref, a as createBaseVNode, t as toDisplayString, F as Fragment, g as createVNode, h as createTextVNode, f as createCommentVNode, n as normalizeStyle, b as renderList, d as createBlock, k as withModifiers, T as Teleport, e as _sfc_main$1, l as normalizeClass, m as ref, q as computed, s as nextTick, p as paper } from './index-C6Zi8U9E.js';
import { V as VAutocomplete, d as downloadCsv } from './data-B_ATQ81f.js';
import { u as useViewportTable } from './useViewportTable-nDS-iF5F.js';
import { l as loadCatalog, c as catalogLoading, a as catalog, b as catalogError, d as chemicalName, e as detailText } from './scenario-D5uTaS2J.js';

const _hoisted_1 = {
  key: 0,
  class: "state",
  role: "status"
};
const _hoisted_2 = {
  key: 1,
  class: "state error",
  role: "alert"
};
const _hoisted_3 = { class: "filters chemical-filters" };
const _hoisted_4 = { class: "chemical-filter" };
const _hoisted_5 = { class: "chemical-filter" };
const _hoisted_6 = { class: "chemical-filter" };
const _hoisted_7 = { class: "toolbar" };
const _hoisted_8 = { class: "actions" };
const _hoisted_9 = ["disabled"];
const _hoisted_10 = {
  key: 0,
  class: "error-text",
  role: "alert"
};
const _hoisted_11 = {
  key: 1,
  class: "state"
};
const _hoisted_12 = { class: "chem" };
const _hoisted_13 = { class: "chemical-key" };
const _hoisted_14 = ["aria-label", "onClick"];
const _hoisted_15 = { class: "dialog-shell" };
const _hoisted_16 = { class: "dialog-header" };
const _hoisted_17 = { id: "chemical-dialog-title" };
const _hoisted_18 = { class: "dialog-content" };
const _hoisted_19 = { class: "note" };
const _hoisted_20 = {
  key: 1,
  class: "state"
};

const _sfc_main = {
  __name: 'ChemicalExplorer',
  props: { tab: { type: String, required: true } },
  setup(__props) {

const props = __props;
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

return (_ctx, _cache) => {
  const _component_v_icon = resolveComponent("v-icon");

  return (openBlock(), createElementBlock("section", {
    ref_key: "catalogElement",
    ref: catalogElement,
    class: normalizeClass(["scenario", {'chemical-data':__props.tab==='Data'}]),
    "aria-label": "Chemical catalog"
  }, [
    (unref(catalogLoading) && !unref(catalog))
      ? (openBlock(), createElementBlock("div", _hoisted_1, "Loading the local chemical catalog…"))
      : (unref(catalogError))
        ? (openBlock(), createElementBlock("div", _hoisted_2, [
            createBaseVNode("p", null, toDisplayString(unref(catalogError)), 1),
            createBaseVNode("button", {
              class: "primary",
              onClick: retry
            }, "Retry catalog")
          ]))
        : (unref(catalog))
          ? (openBlock(), createElementBlock(Fragment, { key: 2 }, [
              (__props.tab === 'Data')
                ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                    _cache[18] || (_cache[18] = createBaseVNode("h2", null, "Chemical catalog", -1)),
                    createBaseVNode("div", _hoisted_3, [
                      createBaseVNode("div", _hoisted_4, [
                        _cache[11] || (_cache[11] = createBaseVNode("label", { for: "chemical-name-filter" }, "Chemical name", -1)),
                        createVNode(unref(VAutocomplete), {
                          id: "chemical-name-filter",
                          modelValue: identityFilter.value,
                          "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((identityFilter).value = $event)),
                          search: nameSearch.value,
                          "onUpdate:search": _cache[1] || (_cache[1] = $event => ((nameSearch).value = $event)),
                          items: nameOptions.value,
                          "item-title": "title",
                          "item-value": "value",
                          placeholder: "All chemical names",
                          "aria-label": "Chemical name",
                          clearable: "",
                          "hide-details": "",
                          density: "compact",
                          variant: "outlined",
                          "menu-props": filterMenuProps,
                          "custom-filter": filterOption,
                          "no-data-text": "No matching chemical names"
                        }, null, 8, ["modelValue", "search", "items"])
                      ]),
                      createBaseVNode("div", _hoisted_5, [
                        _cache[12] || (_cache[12] = createBaseVNode("label", { for: "chemical-cas-filter" }, "CAS number", -1)),
                        createVNode(unref(VAutocomplete), {
                          id: "chemical-cas-filter",
                          modelValue: casFilter.value,
                          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((casFilter).value = $event)),
                          search: casSearch.value,
                          "onUpdate:search": _cache[3] || (_cache[3] = $event => ((casSearch).value = $event)),
                          items: casOptions.value,
                          "item-title": "title",
                          "item-value": "value",
                          placeholder: selectedIdentity.value && !selectedIdentity.value.cas ? 'CAS unavailable' : 'All CAS numbers',
                          "aria-label": "CAS number",
                          clearable: "",
                          "hide-details": "",
                          density: "compact",
                          variant: "outlined",
                          "menu-props": filterMenuProps,
                          "custom-filter": filterOption,
                          "no-data-text": "No matching CAS numbers"
                        }, null, 8, ["modelValue", "search", "items", "placeholder"])
                      ]),
                      createBaseVNode("div", _hoisted_6, [
                        _cache[13] || (_cache[13] = createBaseVNode("label", { for: "chemical-inchikey-filter" }, "InChIKey", -1)),
                        createVNode(unref(VAutocomplete), {
                          id: "chemical-inchikey-filter",
                          modelValue: identityFilter.value,
                          "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((identityFilter).value = $event)),
                          search: inchiKeySearch.value,
                          "onUpdate:search": _cache[5] || (_cache[5] = $event => ((inchiKeySearch).value = $event)),
                          items: inchiKeyOptions.value,
                          placeholder: "All InChIKeys",
                          "aria-label": "InChIKey",
                          clearable: "",
                          "hide-details": "",
                          density: "compact",
                          variant: "outlined",
                          "menu-props": filterMenuProps,
                          "custom-filter": filterOption,
                          "no-data-text": "No matching InChIKeys"
                        }, null, 8, ["modelValue", "search", "items"])
                      ])
                    ]),
                    createBaseVNode("div", _hoisted_7, [
                      createBaseVNode("span", null, toDisplayString(rows.value.length) + " " + toDisplayString(rows.value.length === 1 ? 'chemical' : 'chemicals'), 1),
                      createBaseVNode("div", _hoisted_8, [
                        createBaseVNode("button", {
                          class: "link",
                          onClick: resetFilters
                        }, "Reset filters"),
                        createBaseVNode("button", {
                          class: "primary csv-download",
                          disabled: !rows.value.length,
                          onClick: exportRows
                        }, [
                          createVNode(_component_v_icon, {
                            icon: "mdi-download",
                            size: "18",
                            "aria-hidden": "true"
                          }),
                          _cache[14] || (_cache[14] = createTextVNode("Download CSV", -1))
                        ], 8, _hoisted_9)
                      ])
                    ]),
                    (exportError.value)
                      ? (openBlock(), createElementBlock("p", _hoisted_10, toDisplayString(exportError.value), 1))
                      : createCommentVNode("", true),
                    (!rows.value.length)
                      ? (openBlock(), createElementBlock("div", _hoisted_11, [
                          _cache[15] || (_cache[15] = createTextVNode("No chemicals match these filters. ", -1)),
                          createBaseVNode("button", {
                            class: "link",
                            onClick: resetFilters
                          }, "Reset filters")
                        ]))
                      : (openBlock(), createElementBlock("div", {
                          key: 2,
                          ref_key: "tableRegion",
                          ref: tableRegion,
                          class: "table-scroll chemical-table-scroll",
                          style: normalizeStyle({maxHeight:unref(tableMaxHeight)}),
                          tabindex: "0",
                          role: "region",
                          "aria-label": "All matching chemicals, scroll within this table"
                        }, [
                          createBaseVNode("table", null, [
                            createBaseVNode("thead", null, [
                              createBaseVNode("tr", null, [
                                createBaseVNode("th", null, [
                                  createBaseVNode("button", {
                                    onClick: _cache[6] || (_cache[6] = $event => (sortBy('name')))
                                  }, "Chemical name" + toDisplayString(mark('name')), 1)
                                ]),
                                createBaseVNode("th", null, [
                                  createBaseVNode("button", {
                                    onClick: _cache[7] || (_cache[7] = $event => (sortBy('cas')))
                                  }, "CAS number" + toDisplayString(mark('cas')), 1)
                                ]),
                                createBaseVNode("th", null, [
                                  createBaseVNode("button", {
                                    onClick: _cache[8] || (_cache[8] = $event => (sortBy('id')))
                                  }, "InChIKey" + toDisplayString(mark('id')), 1)
                                ]),
                                createBaseVNode("th", null, [
                                  createBaseVNode("button", {
                                    onClick: _cache[9] || (_cache[9] = $event => (sortBy('category')))
                                  }, "Category" + toDisplayString(mark('category')), 1)
                                ]),
                                _cache[16] || (_cache[16] = createBaseVNode("th", null, "Details", -1))
                              ])
                            ]),
                            createBaseVNode("tbody", null, [
                              (openBlock(true), createElementBlock(Fragment, null, renderList(rows.value, (row) => {
                                return (openBlock(), createElementBlock("tr", {
                                  key: row.id
                                }, [
                                  createBaseVNode("td", _hoisted_12, toDisplayString(unref(chemicalName)(row)), 1),
                                  createBaseVNode("td", null, toDisplayString(unref(detailText)(row.cas)), 1),
                                  createBaseVNode("td", _hoisted_13, toDisplayString(row.id), 1),
                                  createBaseVNode("td", null, toDisplayString(row.category || '—'), 1),
                                  createBaseVNode("td", null, [
                                    createBaseVNode("button", {
                                      class: "link",
                                      "aria-haspopup": "dialog",
                                      "aria-label": `Details for ${unref(chemicalName)(row)}`,
                                      onClick: $event => (openDetails(row, $event))
                                    }, "Details", 8, _hoisted_14)
                                  ])
                                ]))
                              }), 128))
                            ])
                          ])
                        ], 4)),
                    (openBlock(), createBlock(Teleport, { to: "body" }, [
                      (detail.value)
                        ? (openBlock(), createElementBlock("dialog", {
                            key: 0,
                            ref_key: "detailDialog",
                            ref: detailDialog,
                            class: "scenario chemical-dialog",
                            "aria-labelledby": "chemical-dialog-title",
                            onClose: onDetailsClosed,
                            onCancel: withModifiers(closeDetails, ["prevent"]),
                            onClick: _cache[10] || (_cache[10] = event => { if (event.target === detailDialog.value) closeDetails(); })
                          }, [
                            createBaseVNode("div", _hoisted_15, [
                              createBaseVNode("header", _hoisted_16, [
                                createBaseVNode("h2", _hoisted_17, toDisplayString(unref(chemicalName)(detail.value)), 1),
                                createBaseVNode("button", {
                                  class: "secondary",
                                  autofocus: "",
                                  "aria-label": "Close chemical details",
                                  onClick: closeDetails
                                }, [...(_cache[17] || (_cache[17] = [
                                  createTextVNode("Close ", -1),
                                  createBaseVNode("span", { "aria-hidden": "true" }, "×", -1)
                                ]))])
                              ]),
                              createBaseVNode("div", _hoisted_18, [
                                createBaseVNode("dl", null, [
                                  (openBlock(true), createElementBlock(Fragment, null, renderList(detailFields.value, ([label, value]) => {
                                    return (openBlock(), createElementBlock(Fragment, { key: label }, [
                                      createBaseVNode("dt", null, toDisplayString(label), 1),
                                      createBaseVNode("dd", null, toDisplayString(unref(detailText)(value)), 1)
                                    ], 64))
                                  }), 128))
                                ])
                              ])
                            ])
                          ], 544))
                        : createCommentVNode("", true)
                    ]))
                  ], 64))
                : (openBlock(), createElementBlock(Fragment, { key: 1 }, [
                    _cache[19] || (_cache[19] = createBaseVNode("h2", null, "How the target panel was selected", -1)),
                    createBaseVNode("p", _hoisted_19, toDisplayString(figure.value?.id.toLowerCase() === 'ed1' ? 'The selection of 52 target chemicals and their eight categories.' : 'The study framework and chemical-selection evidence.'), 1),
                    (figure.value)
                      ? (openBlock(), createBlock(_sfc_main$1, {
                          key: 0,
                          figure: figure.value,
                          "show-actions": false
                        }, null, 8, ["figure"]))
                      : (openBlock(), createElementBlock("div", _hoisted_20, "The chemical-selection figure is unavailable."))
                  ], 64))
            ], 64))
          : createCommentVNode("", true)
  ], 2))
}
}

};
const ChemicalExplorer = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-a45c7b26"]]);

export { ChemicalExplorer as default };
