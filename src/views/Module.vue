<template>
 <div class="module-layout" :class="{'wpn-data-layout':module==='wpn'&&tab==='Data','table-data-layout':['chemical','rank'].includes(module)&&tab==='Data'}">
  <nav class="sub-navigation" :class="{'has-code':module==='rank'}" aria-label="Section navigation"><router-link v-for="t in tabs" :key="t" :to="{path:`/${module}/${t}`,query:t==='Code'?{}:route.query}" :class="['sub-tab',{active:tab===t}]" :aria-current="tab===t?'page':undefined"><v-icon :icon="tabIcons[t]" class="sub-tab-icon" aria-hidden="true" /><span class="sub-tab-copy"><strong>{{t}}</strong><span>{{tabDescriptions[module]?.[t]}}</span></span></router-link></nav>
  <div class="module-content" :key="module">
   <IntroductionDescription v-if="module==='introduction'&&tab==='Description'" />
   <ChemicalDescription v-else-if="module==='chemical'&&tab==='Description'" />
   <article v-else-if="tab==='Description'" class="description">
    <h1>{{description.title}}</h1><p v-for="paragraph in description.paragraphs" :key="paragraph">{{paragraph}}</p>
    <section v-for="s in description.sections" :key="s.id" :id="s.id" class="description-section"><h2>{{s.title}}</h2><p v-for="p in s.paragraphs" :key="p">{{p}}</p><div v-if="studyFigureLinks(s.figureIds).length" class="description-figure-links"><router-link v-for="id in studyFigureLinks(s.figureIds)" :key="id" to="/introduction/Figure">{{studyFigure.title}}</router-link></div></section>
    <div class="workflow-links"><router-link :to="nextStep.path">{{nextStep.label}} <span aria-hidden="true">→</span></router-link></div>
   </article>
   <template v-if="module==='introduction'">
    <IntroductionData v-if="tab==='Data'" />
    <div v-else-if="tab==='Figure'" class="intro-figure">
     <FigureCard v-if="studyFigure" :figure="studyFigure" :show-actions="false" />
    </div>
   </template>
   <ChemicalExplorer v-else-if="module==='chemical'&&tab!=='Description'" :tab="tab" />
   <WpnWorkspace v-else-if="module==='wpn'&&tab!=='Description'" :tab="tab" />
   <CodeDownload v-else-if="module==='rank'&&tab==='Code'" />
   <RankExplorer v-else-if="module==='rank'&&tab!=='Description'" :tab="tab" />
  </div>
 </div>
</template>
<script setup>
import {computed,defineAsyncComponent} from 'vue';
import {useRoute} from 'vue-router';
import paper from '../content/paper.json';
import FigureCard from '../components/FigureCard.vue';
import {unnumberedFigureText} from '../lib/figureText.js';
import IntroductionData from '../components/IntroductionData.vue';
const IntroductionDescription=defineAsyncComponent(()=>import('../components/IntroductionDescription.vue'));
const ChemicalDescription=defineAsyncComponent(()=>import('../components/ChemicalDescription.vue'));
const ChemicalExplorer=defineAsyncComponent(()=>import('../components/ChemicalExplorer.vue'));
const WpnWorkspace=defineAsyncComponent(()=>import('../components/WpnWorkspace.vue'));
const RankExplorer=defineAsyncComponent(()=>import('../components/RankExplorer.vue'));
const CodeDownload=defineAsyncComponent(()=>import('../components/CodeDownload.vue'));
const route=useRoute();
const tabs=computed(()=>module.value==='rank'?['Description','Data','Figure','Code']:['Description','Data','Figure']);
const tabIcons={Description:'mdi-file-document-outline',Data:'mdi-database',Figure:'mdi-chart-box-outline',Code:'mdi-code-braces'};
const tabDescriptions={
 introduction:{Description:'Study design and methods',Data:'Study datasets and downloads',Figure:'BEQ priority rankings'},
 chemical:{Description:'The 52 target chemicals',Data:'Names, identifiers and categories',Figure:'How the panel was selected'},
 wpn:{Description:'How to use WPN',Data:'Enter wastewater concentrations',Figure:'Explore your input concentrations'},
 rank:{Description:'Understanding the results',Data:'Rankings, values and downloads',Figure:'BEQ and cumulative contribution',Code:'Run WPN on your computer'}
};
const module=computed(()=>route.params.module),tab=computed(()=>route.params.tab||({wpn:'Data',rank:'Figure'}[module.value]||'Description'));
const description=computed(()=>paper.descriptions[module.value]||{title:'WPN',paragraphs:[]});
const sourceStudyFigure=paper.figures.find(f=>f.id==='Fig4');
const studyFigure=sourceStudyFigure?{...sourceStudyFigure,title:unnumberedFigureText(sourceStudyFigure.title),caption:unnumberedFigureText(sourceStudyFigure.caption)}:undefined;
const studyFigureLinks=ids=>(ids||[]).filter(id=>id.toLowerCase()==='fig4');
const nextStep=computed(()=>({introduction:{path:'/chemical/Data',label:'Explore the chemical panel'},chemical:{path:'/wpn/Data',label:'Enter wastewater concentrations'},wpn:{path:'/wpn/Data',label:'Enter concentrations'},rank:{path:'/rank/Figure?source=current',label:'View your results'}}[module.value]));
</script>
