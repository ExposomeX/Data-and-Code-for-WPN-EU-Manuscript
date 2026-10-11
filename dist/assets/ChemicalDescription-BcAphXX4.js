import { _ as _export_sfc, p as paper, r as resolveComponent, o as openBlock, c as createElementBlock, a as createBaseVNode, t as toDisplayString, u as unref, F as Fragment, b as renderList, d as createBlock, e as _sfc_main$1, f as createCommentVNode, g as createVNode, w as withCtx, h as createTextVNode } from './index-C6Zi8U9E.js';

const _hoisted_1 = { class: "description chemical-description" };
const _hoisted_2 = {
  id: "panel",
  class: "description-section",
  "aria-labelledby": "panel-heading"
};
const _hoisted_3 = { id: "panel-heading" };
const _hoisted_4 = {
  id: "ebio",
  class: "description-section",
  "aria-labelledby": "ebio-heading"
};
const _hoisted_5 = {
  id: "identity",
  class: "description-section",
  "aria-labelledby": "identity-heading"
};
const _hoisted_6 = { id: "identity-heading" };
const _hoisted_7 = { class: "workflow-links" };


const _sfc_main = {
  __name: 'ChemicalDescription',
  setup(__props) {

const description=paper.descriptions.chemical;
const panel=description.sections.find(section=>section.id==='panel');
const identity=description.sections.find(section=>section.id==='identity');
const biologicalFigure=paper.figures.find(figure=>figure.id==='Fig2');

return (_ctx, _cache) => {
  const _component_router_link = resolveComponent("router-link");

  return (openBlock(), createElementBlock("article", _hoisted_1, [
    createBaseVNode("h1", null, toDisplayString(unref(description).title), 1),
    (openBlock(true), createElementBlock(Fragment, null, renderList(unref(description).paragraphs, (paragraph) => {
      return (openBlock(), createElementBlock("p", { key: paragraph }, toDisplayString(paragraph), 1))
    }), 128)),
    createBaseVNode("section", _hoisted_2, [
      createBaseVNode("h2", _hoisted_3, toDisplayString(unref(panel).title), 1),
      (openBlock(true), createElementBlock(Fragment, null, renderList(unref(panel).paragraphs, (paragraph) => {
        return (openBlock(), createElementBlock("p", { key: paragraph }, toDisplayString(paragraph), 1))
      }), 128))
    ]),
    createBaseVNode("section", _hoisted_4, [
      _cache[0] || (_cache[0] = createBaseVNode("h2", { id: "ebio-heading" }, "Biological context from E-BIO", -1)),
      _cache[1] || (_cache[1] = createBaseVNode("p", null, "The ExposomeX E-BIO knowledge system connects chemicals to disease-related biology through two complementary networks. Exposure–Protein–Protein–Disease (EPPD) links chemicals to diseases through proteins and their interactions. Exposure–GO–Disease (EGoD) links chemicals to diseases through Gene Ontology (GO) terms describing biological processes.", -1)),
      _cache[2] || (_cache[2] = createBaseVNode("p", null, "The figure below shows the disease-associated protein and biological-process profiles of the 52 target chemicals. The heatmaps summarize their recorded coverage, while the layered networks show how chemicals connect to biological intermediates and representative neurobehavioral disorders.", -1)),
      (unref(biologicalFigure))
        ? (openBlock(), createBlock(_sfc_main$1, {
            key: 0,
            class: "biological-figure",
            figure: unref(biologicalFigure),
            "show-actions": false
          }, null, 8, ["figure"]))
        : createCommentVNode("", true)
    ]),
    createBaseVNode("section", _hoisted_5, [
      createBaseVNode("h2", _hoisted_6, toDisplayString(unref(identity).title), 1),
      (openBlock(true), createElementBlock(Fragment, null, renderList(unref(identity).paragraphs, (paragraph) => {
        return (openBlock(), createElementBlock("p", { key: paragraph }, toDisplayString(paragraph), 1))
      }), 128))
    ]),
    createBaseVNode("div", _hoisted_7, [
      createVNode(_component_router_link, { to: "/wpn/Data" }, {
        default: withCtx(() => [...(_cache[3] || (_cache[3] = [
          createTextVNode("Enter wastewater concentrations ", -1),
          createBaseVNode("span", { "aria-hidden": "true" }, "→", -1)
        ]))]),
        _: 1
      })
    ])
  ]))
}
}

};
const ChemicalDescription = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-78d7c315"]]);

export { ChemicalDescription as default };
