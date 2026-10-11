import { _ as _export_sfc, y as onMounted, r as resolveComponent, o as openBlock, c as createElementBlock, a as createBaseVNode, g as createVNode, h as createTextVNode, t as toDisplayString, f as createCommentVNode, G as createStaticVNode, m as ref, q as computed } from './index-C6Zi8U9E.js';

const _hoisted_1 = {
  class: "code-download",
  "aria-labelledby": "code-heading"
};
const _hoisted_2 = { class: "code-intro" };
const _hoisted_3 = { class: "code-download-action" };
const _hoisted_4 = {
  key: 0,
  href: "/downloads/WPN-local-code.zip",
  download: "WPN-local-code.zip",
  class: "code-download-button"
};
const _hoisted_5 = {
  key: 1,
  role: "status"
};
const _hoisted_6 = {
  key: 2,
  role: "alert"
};
const _hoisted_7 = {
  key: 3,
  class: "code-download-meta"
};
const _hoisted_8 = { class: "code-outputs" };


const _sfc_main = {
  __name: 'CodeDownload',
  setup(__props) {

const bundle = ref(null), loading = ref(true), error = ref('');
const sizeLabel = computed(() => bundle.value ? `${(bundle.value.bytes / 1024 / 1024).toFixed(1)} MB` : '');
async function loadBundle() {
  loading.value = true;
  error.value = '';
  try {
    const response = await fetch('/downloads/WPN-local-code.manifest.json');
    if (!response.ok || !response.headers.get('content-type')?.includes('json')) throw new Error('Package unavailable');
    const value = await response.json();
    if (value.filename !== 'WPN-local-code.zip' || !Number.isFinite(value.bytes) || value.bytes <= 0) throw new Error('Invalid package information');
    bundle.value = value;
  } catch {
    error.value = 'The download package could not be loaded.';
  } finally { loading.value = false; }
}
onMounted(loadBundle);

return (_ctx, _cache) => {
  const _component_v_icon = resolveComponent("v-icon");

  return (openBlock(), createElementBlock("section", _hoisted_1, [
    createBaseVNode("div", _hoisted_2, [
      _cache[1] || (_cache[1] = createBaseVNode("div", { class: "code-intro-heading" }, [
        createBaseVNode("p", { class: "code-eyebrow" }, "WPN LOCAL CODE"),
        createBaseVNode("h1", { id: "code-heading" }, "Run WPN on your computer")
      ], -1)),
      createBaseVNode("div", _hoisted_3, [
        (bundle.value && !error.value)
          ? (openBlock(), createElementBlock("a", _hoisted_4, [
              createVNode(_component_v_icon, {
                icon: "mdi-download",
                "aria-hidden": "true"
              }),
              _cache[0] || (_cache[0] = createTextVNode(" Download WPN Code", -1))
            ]))
          : (loading.value)
            ? (openBlock(), createElementBlock("span", _hoisted_5, "Preparing download…"))
            : (openBlock(), createElementBlock("div", _hoisted_6, [
                createBaseVNode("p", null, toDisplayString(error.value), 1),
                createBaseVNode("button", { onClick: loadBundle }, "Retry")
              ])),
        (bundle.value && !error.value)
          ? (openBlock(), createElementBlock("span", _hoisted_7, "ZIP · " + toDisplayString(sizeLabel.value), 1))
          : createCommentVNode("", true)
      ]),
      _cache[2] || (_cache[2] = createBaseVNode("p", { class: "code-lead" }, "Enter WW concentrations to generate chemical rankings, a results table and a BEQ plot.", -1))
    ]),
    _cache[5] || (_cache[5] = createStaticVNode("<ol class=\"code-steps\" aria-label=\"Local WPN instructions\" data-v-c3a72758><li data-v-c3a72758><span class=\"code-step-number\" aria-hidden=\"true\" data-v-c3a72758>1</span><div data-v-c3a72758><h2 data-v-c3a72758>Download and unzip</h2><p data-v-c3a72758>Extract the complete package to a folder on your computer.</p></div></li><li data-v-c3a72758><span class=\"code-step-number\" aria-hidden=\"true\" data-v-c3a72758>2</span><div data-v-c3a72758><h2 data-v-c3a72758>Set up once</h2><p data-v-c3a72758>Install <a href=\"https://www.python.org/downloads/release/python-31210/\" target=\"_blank\" rel=\"noopener\" data-v-c3a72758>Python 3.12 (64-bit)</a>, then double-click <code data-v-c3a72758>Setup_WPN.bat</code>. This first setup downloads the required libraries.</p></div></li><li data-v-c3a72758><span class=\"code-step-number\" aria-hidden=\"true\" data-v-c3a72758>3</span><div data-v-c3a72758><h2 data-v-c3a72758>Fill in your concentrations</h2><p data-v-c3a72758>Open <code data-v-c3a72758>inputs/concentrations.xlsx</code> and enter WW concentrations in nM. Leave unused chemicals blank. CSV input and example data are also included.</p></div></li><li data-v-c3a72758><span class=\"code-step-number\" aria-hidden=\"true\" data-v-c3a72758>4</span><div data-v-c3a72758><h2 data-v-c3a72758>Run and view your results</h2><p data-v-c3a72758>Double-click <code data-v-c3a72758>Run_WPN.bat</code> or run <code data-v-c3a72758>run.py</code> to calculate locally on <span class=\"cpu-badge\" data-v-c3a72758>CPU</span>. Find your ranking table and BEQ plot in <code data-v-c3a72758>results</code>.</p></div></li></ol>", 1)),
    createBaseVNode("div", _hoisted_8, [
      createBaseVNode("div", null, [
        createVNode(_component_v_icon, {
          icon: "mdi-table",
          "aria-hidden": "true"
        }),
        _cache[3] || (_cache[3] = createBaseVNode("div", null, [
          createBaseVNode("h2", null, "Results table"),
          createBaseVNode("p", null, "Rank · Chemical · WW input · BEQ · Contribution (%)")
        ], -1))
      ]),
      createBaseVNode("div", null, [
        createVNode(_component_v_icon, {
          icon: "mdi-chart-bar",
          "aria-hidden": "true"
        }),
        _cache[4] || (_cache[4] = createBaseVNode("div", null, [
          createBaseVNode("h2", null, "BEQ plot"),
          createBaseVNode("p", null, "All evaluated chemicals, a logarithmic BEQ axis and cumulative contribution.")
        ], -1))
      ])
    ]),
    _cache[6] || (_cache[6] = createBaseVNode("p", { class: "code-footnote" }, [
      createTextVNode("Built with PriorLabs-TabPFN · "),
      createBaseVNode("a", {
        href: "/notices/TabPFN-2.6-LICENSE.txt",
        target: "_blank",
        rel: "noopener"
      }, "Model license")
    ], -1))
  ]))
}
}

};
const CodeDownload = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-c3a72758"]]);

export { CodeDownload as default };
