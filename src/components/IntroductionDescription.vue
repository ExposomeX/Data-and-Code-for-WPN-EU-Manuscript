<template>
 <article class="description introduction-description">
  <h1>{{introduction.title}}</h1>
  <p v-for="paragraph in introduction.overview" :key="paragraph">{{paragraph}}</p>

  <FigureCard v-if="frameworkFigure" class="framework-figure" :figure="frameworkFigure" :show-actions="false" />

  <section class="methods" aria-labelledby="methods-heading">
   <h2 id="methods-heading">Methods</h2>
   <section v-for="section in methods" :id="section.id" :key="section.id" class="method-section" :aria-labelledby="`${section.id}-heading`">
    <h3 :id="`${section.id}-heading`">{{section.title}}</h3>
    <template v-for="(block,index) in section.blocks" :key="index">
     <p v-if="block.type==='paragraph'">{{block.text}}</p>
     <div v-else-if="block.type==='equation'" class="method-equation" role="group" :aria-label="block.label" tabindex="0" v-html="block.html"></div>
    </template>
   </section>
  </section>
  <div class="workflow-links"><router-link to="/chemical/Data">Explore the chemical panel <span aria-hidden="true">→</span></router-link></div>
 </article>
</template>

<script setup>
import katex from 'katex';
import 'katex/dist/katex.min.css';
import FigureCard from './FigureCard.vue';
import paper from '../content/paper.json';
import introduction from '../content/introduction.js';

const sourceFigure=paper.figures.find(figure=>figure.id==='Fig1');
const frameworkFigure=sourceFigure?{
 ...sourceFigure,
 title:sourceFigure.title.replace(' | ','. '),
 caption:sourceFigure.caption.split('\n').slice(1).join('\n')
}:undefined;
// Equations are authored locally with the manuscript content; no page or user input is rendered as HTML.
const methods=introduction.methods.map(section=>({...section,blocks:section.blocks.map(block=>block.type==='equation'
 ?{...block,html:katex.renderToString(block.tex,{displayMode:true,throwOnError:true,strict:'error',trust:false})}
 :block)}));
</script>

<style scoped>
.introduction-description{max-width:1150px;min-width:0;margin:0 auto}
.introduction-description h1{font-size:22px;margin-bottom:18px}
.introduction-description>p{margin-bottom:18px}
.framework-figure{max-width:980px;margin:30px auto 38px}
.framework-figure :deep(figcaption){font-size:16px;line-height:1.65}
.methods>h2{font-size:22px;text-transform:uppercase;letter-spacing:.3px;margin:0 0 24px}
.method-section{margin:0 0 30px;scroll-margin-top:90px;min-width:0}
.method-section h3{font-size:19px;line-height:1.5;margin:0 0 14px}
.method-equation{box-sizing:border-box;max-width:100%;overflow-x:auto;overflow-y:hidden;border:1px solid #d9d9d9;background:#fafafa;padding:14px;margin:8px 0 14px}
.method-equation :deep(.katex-display){margin:.6em 0;text-align:center}
.method-equation :deep(.katex-display>.katex){display:block;width:max-content;min-width:100%;font-size:1.06em}
@media(max-width:600px){
 .introduction-description h1,.methods>h2{font-size:21px}
 .method-section h3{font-size:18px}
 .method-equation{padding-inline:10px}
 .framework-figure{margin-block:24px 30px}
}
</style>
