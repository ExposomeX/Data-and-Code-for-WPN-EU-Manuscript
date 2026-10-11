<template>
 <article class="description chemical-description">
  <h1>{{description.title}}</h1>
  <p v-for="paragraph in description.paragraphs" :key="paragraph">{{paragraph}}</p>

  <section id="panel" class="description-section" aria-labelledby="panel-heading">
   <h2 id="panel-heading">{{panel.title}}</h2>
   <p v-for="paragraph in panel.paragraphs" :key="paragraph">{{paragraph}}</p>
  </section>

  <section id="ebio" class="description-section" aria-labelledby="ebio-heading">
   <h2 id="ebio-heading">Biological context from E-BIO</h2>
   <p>The ExposomeX E-BIO knowledge system connects chemicals to disease-related biology through two complementary networks. Exposure–Protein–Protein–Disease (EPPD) links chemicals to diseases through proteins and their interactions. Exposure–GO–Disease (EGoD) links chemicals to diseases through Gene Ontology (GO) terms describing biological processes.</p>
   <p>The figure below shows the disease-associated protein and biological-process profiles of the 52 target chemicals. The heatmaps summarize their recorded coverage, while the layered networks show how chemicals connect to biological intermediates and representative neurobehavioral disorders.</p>
   <FigureCard v-if="biologicalFigure" class="biological-figure" :figure="biologicalFigure" :show-actions="false" />
  </section>

  <section id="identity" class="description-section" aria-labelledby="identity-heading">
   <h2 id="identity-heading">{{identity.title}}</h2>
   <p v-for="paragraph in identity.paragraphs" :key="paragraph">{{paragraph}}</p>
  </section>
  <div class="workflow-links"><router-link to="/wpn/Data">Enter wastewater concentrations <span aria-hidden="true">→</span></router-link></div>
 </article>
</template>

<script setup>
import FigureCard from './FigureCard.vue';
import paper from '../content/paper.json';

const description=paper.descriptions.chemical;
const panel=description.sections.find(section=>section.id==='panel');
const identity=description.sections.find(section=>section.id==='identity');
const biologicalFigure=paper.figures.find(figure=>figure.id==='Fig2');
</script>

<style scoped>
.chemical-description{max-width:1150px;min-width:0;margin:0 auto}
.biological-figure{max-width:1050px;margin:26px auto 30px}
.biological-figure :deep(figcaption){font-size:16px;line-height:1.65}
</style>
