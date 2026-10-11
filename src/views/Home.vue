<template>
 <div class="cover-wrapper"><div class="cover-inner">
  <section class="platform-intro"><h1 class="home-framework-name">WPN <span aria-hidden="true">·</span> {{paper.longName}}</h1><div class="home-intro-details"><p class="home-framework-summary">From chemical concentrations to neurotoxicity priorities</p><div class="home-actions"><router-link to="/introduction/Description">Explore the study</router-link><router-link class="primary-link" to="/wpn/Data">Run WPN <span aria-hidden="true">→</span></router-link></div></div></section>
  <FigureCard :figure="paper.figures.find(f=>f.id.toLowerCase()==='fig1')" :show-number="false" :show-caption="false" :show-actions="false" />
  <div class="welcome-info">
   <section class="info-block"><v-icon class="info-icon" icon="mdi-account-group" /><div><h2>Team</h2><p class="authors"><template v-for="(author,i) in authors" :key="author.name">{{author.name}}<sup>{{author.units}}</sup><span v-if="i<authors.length-1">, </span></template></p><details><summary>Affiliations</summary><p v-for="a in paper.team.affiliations" :key="a" class="affiliation">{{a}}</p></details><p v-for="contact in paper.team.correspondence" :key="contact">{{contact}}</p></div></section>
   <section class="info-block"><v-icon class="info-icon" icon="mdi-license" /><div><h2>License &amp; Attribution</h2><p v-for="p in paper.license.paragraphs" :key="p">{{p}}</p><details v-if="paper.license.modelNotice"><summary>TabPFN attribution</summary><p>{{paper.license.modelNotice}}</p></details><div class="attribution-links"><a href="/notices/THIRD_PARTY_NOTICES.md" download>Third-party notices</a><a href="/notices/TabPFN-2.6-LICENSE.txt" download>TabPFN licence</a></div></div></section>
   <section class="info-block"><v-icon class="info-icon" icon="mdi-format-quote-close" /><div><h2>Citation</h2><p>{{paper.citation.text}}</p><button class="text-button" @click="copyCitation">{{copied?'Copied':'Copy citation'}}</button></div></section>
  </div>
 </div></div>
</template>
<script setup>
import {ref} from 'vue';import paper from '../content/paper.json';import FigureCard from '../components/FigureCard.vue';
const authors=paper.team.authorsText.split(/,\s+(?=[A-Za-z])/).map(text=>{const match=text.match(/^(.*?)(\d[\d,*]*)$/);return {name:match?match[1]:text,units:match?match[2]:''}});
const copied=ref(false);async function copyCitation(){try{await navigator.clipboard.writeText(paper.citation.text);copied.value=true;setTimeout(()=>copied.value=false,2500)}catch{copied.value=false}}
</script>
<style scoped>
.platform-intro .home-framework-name{font-size:clamp(20px,2vw,24px);font-weight:600;line-height:1.35;color:#252525;overflow-wrap:break-word}
.platform-intro{padding-bottom:20px}
.home-intro-details{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px 24px}
.platform-intro .home-framework-summary{font-size:16px;line-height:1.6;color:#626d7b;text-align:left;margin:0;flex:1 1 380px}
.home-intro-details .home-actions{margin-top:0;flex-shrink:0;white-space:nowrap}
@media(max-width:600px){.home-intro-details{gap:12px}.home-intro-details .home-actions{gap:16px}}
</style>
