<template>
 <figure v-if="figure" class="paper-figure">
  <button class="figure-open" @click="open=true" :aria-label="`Enlarge ${labelledTitle}`"><img :src="figure.url" :alt="labelledTitle" decoding="async" /></button>
  <figcaption v-if="showNumber||showCaption"><div v-if="showNumber||(showCaption&&showTitle)" class="figure-caption-title"><strong v-if="showNumber" class="figure-number">Fig {{figureNumber}}.</strong><strong v-if="showCaption&&showTitle">{{(showNumber?' ':'')+title}}</strong></div><p v-if="showCaption&&caption">{{caption}}</p></figcaption>
  <div v-if="showActions" class="figure-actions"><button class="text-button" @click="open=true">Enlarge figure</button><a :href="figure.url" download>Download original image</a></div>
  <Teleport to="body"><div v-if="open" class="figure-modal" role="dialog" aria-modal="true" :aria-label="labelledTitle" @click.self="open=false" @keydown.esc="open=false"><button ref="closeButton" class="modal-close" @click="open=false" aria-label="Close figure">×</button><img :src="figure.url" :alt="labelledTitle" /></div></Teleport>
 </figure>
</template>
<script setup>
import {computed,ref,watch,nextTick,onUnmounted} from 'vue';
import {unnumberedFigureText} from '../lib/figureText.js';
const props=defineProps({figure:Object,figureNumber:{type:Number,default:1},showNumber:{type:Boolean,default:true},showCaption:{type:Boolean,default:true},showTitle:{type:Boolean,default:true},showActions:{type:Boolean,default:true}});
const title=computed(()=>unnumberedFigureText(props.figure?.title));
const labelledTitle=computed(()=>props.showNumber?`Fig ${props.figureNumber}. ${title.value}`:title.value);
const caption=computed(()=>{
 const text=unnumberedFigureText(props.figure?.caption);
 return props.showTitle&&text.startsWith(`${title.value}\n`)?text.slice(title.value.length).trim():text;
});
const open=ref(false),closeButton=ref(null);let returnFocus;
watch(open,async value=>{if(value){returnFocus=document.activeElement;await nextTick();closeButton.value?.focus()}else returnFocus?.focus()});onUnmounted(()=>{open.value=false});
</script>
