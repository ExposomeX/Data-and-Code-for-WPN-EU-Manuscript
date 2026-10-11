<template>
 <section class="intro-data"><h1>Study data and reference results</h1>
  <nav class="resource-modes" aria-label="Reference data view"><button v-for="item in views" :key="item.id" :class="{selected:view===item.id}" :aria-pressed="view===item.id" @click="changeView(item.id)">{{item.label}}</button></nav>
  <div class="reference-browser"><Explorer :key="view" :module="view==='concentrations'?'ww':'imputation'" tab="Combined" /></div>
 </section>
</template>
<script setup>
import {computed,defineAsyncComponent,watch} from 'vue';import {useRoute,useRouter} from 'vue-router';
const Explorer=defineAsyncComponent(()=>import('./Explorer.vue'));
const route=useRoute(),router=useRouter();
const views=[{id:'concentrations',label:'Wastewater Data'},{id:'validation',label:'Reconstruction validation'}];
const view=computed(()=>views.some(v=>v.id===route.query.view)?route.query.view:'concentrations');
function changeView(id){router.replace({query:{...route.query,view:id}})}
watch(()=>route.query.view,value=>{if(!views.some(v=>v.id===value))router.replace({query:{...route.query,view:'concentrations'}})},{immediate:true});
</script>
