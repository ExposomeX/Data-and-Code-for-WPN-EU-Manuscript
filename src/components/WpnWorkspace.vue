<script setup>
import { computed, ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { VAutocomplete } from 'vuetify/components';
import Plot from './Plot.vue';
import { numberText, downloadCsv, escapeHtml } from '../lib/data.js';
import { parsePastedData, rowsToDraft } from '../lib/input-data.js';
import { catalog, catalogLoading, catalogError, loadCatalog, panel, draftRows, evaluatedDraft, validInputs, invalidInputs, workspaceStep, inputMethod, pastedText, draftLabel, locked, dirty, snapshot, runState, health, refreshHealth, subscribeHealth, startRun, resumeRun, addDraftRow, updateDraftRow, removeDraftRow, replaceDraft, loadExample, clearDraft, chemicalName, storageNotice } from '../lib/scenario.js';
const props=defineProps({tab:{type:String,required:true}});
const router=useRouter(),route=useRoute();
const chemicalChoice=ref(null),localError=ref(''),importing=ref(false),scale=ref('log'),fileInput=ref(null),selectedFileName=ref('');
const workspaceElement=ref(null),tableRegion=ref(null),flowActions=ref(null),tableMaxHeight=ref(null),tableFitsViewport=ref(false);
const blocked=computed(()=>locked.value||importing.value);
const options=computed(()=>panel.value.map(row=>({title:chemicalName(row),value:row.id,props:{subtitle:(row.cas||'')+' · '+row.id},search:[row.name,row.id,row.cas,row.id==='DMSMPAJRVJJAGA-UHFFFAOYSA-N'?'BIT':'',...(row.synonyms||[])].join(' ')})));
const chemicalFilter=(value,query,item)=>(item?.raw?.search||value).toLowerCase().includes(query.toLowerCase());
const previewRows=computed(()=>evaluatedDraft.value);
const chartRows=computed(()=>evaluatedDraft.value.filter(row=>row.valid).slice().sort((a,b)=>b.value-a.value));
const modified=row=>row.originalWW!==''&&(Number(row.ww)!==Number(row.originalWW)||!String(row.ww).trim());
const option=computed(()=>{
 const positiveValues=chartRows.value.map(row=>row.value).filter(value=>Number.isFinite(value)&&value>0);
 const minimum=positiveValues.length?Math.min(...positiveValues):1;
 const logarithmicMinimum=Math.max(Number.MIN_VALUE,10**(Math.floor(Math.log10(minimum))-1));
 return ({
 toolbox:{feature:{saveAsImage:{name:'WPN-WW-input-concentrations',pixelRatio:2}}},
 grid:{left:76,right:30,top:45,bottom:180},
 tooltip:{trigger:'axis',formatter:items=>items.map(item=>escapeHtml(chemicalName(item.data.record.chemical))+'<br>WW: '+numberText(item.value,8)+' nM').join('<br>')},
 xAxis:{type:'category',data:chartRows.value.map(row=>chemicalName(row.chemical)),axisLabel:{rotate:45,width:135,overflow:'truncate',fontSize:11,interval:0}},
 yAxis:{type:scale.value,min:scale.value==='log'?logarithmicMinimum:0,startValue:scale.value==='log'?logarithmicMinimum:0,name:'WW (nM)',nameGap:24,axisLabel:{formatter:value=>numberText(value,3)}},
 dataZoom:[{type:'slider',xAxisIndex:0,start:0,end:100,bottom:10,height:28,filterMode:'none'},{type:'inside',xAxisIndex:0,filterMode:'none'}],
 series:[{name:'WW',type:'bar',barMaxWidth:42,itemStyle:{color:'#2463df'},data:chartRows.value.map(row=>({value:row.value,record:row}))}]
});});
let mounted=false,unsubscribeHealth,layoutObserver,fitFrame;
function fitTable(){
 if(!tableRegion.value||typeof window==='undefined'){tableFitsViewport.value=false;return;}
 // Short/narrow windows use ordinary page scrolling; desktop tables reserve space for the next action.
 if(window.innerWidth<=760||window.innerHeight<640){tableMaxHeight.value=null;tableFitsViewport.value=false;return;}
 const tableTop=tableRegion.value.getBoundingClientRect().top+window.scrollY;
 const actionHeight=flowActions.value?.getBoundingClientRect().height||44;
 const availableHeight=Math.floor(window.innerHeight-tableTop-actionHeight-24);
 tableFitsViewport.value=availableHeight>=160;
 tableMaxHeight.value=Math.max(160,availableHeight)+'px';
}
async function scheduleTableFit(){
 await nextTick();
 if(!mounted||typeof window==='undefined')return;
 window.cancelAnimationFrame(fitFrame);
 fitFrame=window.requestAnimationFrame(fitTable);
}
watch([tableRegion,flowActions,workspaceStep,inputMethod,()=>props.tab,()=>draftRows.length],scheduleTableFit);
async function retryCatalog(){try{await loadCatalog(true);}catch{}}
function addChemical(){if(chemicalChoice.value){inputMethod.value='manual';localError.value='';addDraftRow(chemicalChoice.value);chemicalChoice.value=null;}}
function preview(){localError.value='';if(!draftRows.length){localError.value='Add a chemical or import a table first.';return;}workspaceStep.value='preview';}
function back(){workspaceStep.value='input';inputMethod.value='manual';localError.value='';}
function usePaste(){inputMethod.value='paste';localError.value='';try{replaceDraft(parsePastedData(pastedText.value),'Pasted data');preview();}catch(error){localError.value=error.message;}}
async function importFile(event){
 const file=event.target.files?.[0];if(!file)return;selectedFileName.value=file.name;inputMethod.value='upload';localError.value='';importing.value=true;
 try{
  if(file.size>5*1024*1024)throw new Error('Choose a file smaller than 5 MB.');
  let rows;
  if(/\.xlsx$/i.test(file.name)){
   const response=await fetch('/api/import',{method:'POST',headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'},body:file});
   const result=await response.json();if(!response.ok)throw new Error(result.detail||'The spreadsheet could not be read.');
   rows=rowsToDraft(result.rows);
  }else if(/\.(csv|tsv|txt)$/i.test(file.name)){rows=parsePastedData(await file.text());}
  else throw new Error('Choose an .xlsx, .csv or .tsv file. Save older Excel files as .xlsx first.');
  replaceDraft(rows,file.name);preview();
 }catch(error){localError.value=error.message;}finally{importing.value=false;event.target.value='';}
}
function template(){downloadCsv('WPN-input-template.csv',[{header:'Chemical',value:'chemical'},{header:'WW (nM)',value:'ww'}],[{chemical:'BIT',ww:''}]);}
function exportInputs(){downloadCsv('WPN-inputs.csv',[{header:'Chemical',value:'identifier'},{header:'WW (nM)',value:'ww'}],draftRows);}
async function run(reconnect=false){localError.value='';try{const result=await(reconnect?resumeRun():startRun());if(result&&mounted&&route.params.module==='wpn')await router.push('/rank/Figure?source=current');}catch(error){localError.value=error.message;}}
onMounted(async()=>{mounted=true;unsubscribeHealth=subscribeHealth();if(typeof window!=='undefined'){window.addEventListener('resize',scheduleTableFit);if(typeof ResizeObserver!=='undefined'){layoutObserver=new ResizeObserver(scheduleTableFit);if(workspaceElement.value)layoutObserver.observe(workspaceElement.value);}scheduleTableFit();}try{await loadCatalog();if(runState.status==='paused'&&runState.id)await run(true);}catch{}});
onBeforeUnmount(()=>{mounted=false;unsubscribeHealth?.();layoutObserver?.disconnect();if(typeof window!=='undefined'){window.removeEventListener('resize',scheduleTableFit);window.cancelAnimationFrame(fitFrame);}});
</script>

<template>
 <section ref="workspaceElement" class="scenario workspace" :class="{'workspace-data':tab==='Data','workspace-actions-flow':!tableFitsViewport}" aria-label="WPN prediction workspace">
  <div v-if="catalogLoading&&!catalog" class="state" role="status">Loading chemicals…</div>
  <div v-else-if="catalogError" class="state error" role="alert">{{catalogError}} <button class="link" @click="retryCatalog">Retry</button></div>
  <template v-else-if="catalog">
   <div class="workspace-heading"><div><h2>{{tab==='Figure'?'WW input distribution':'Enter wastewater concentrations'}}</h2><p class="note">Choose any of the 52 chemicals and enter WW concentrations in nM.</p></div><span class="service-status" role="status"><i class="health-dot" :class="health.status"></i>{{health.status==='ready'?'Model ready':health.status==='loading'?'Preparing model…':'Model offline'}}<button v-if="health.status==='error'" class="link" @click="refreshHealth">Retry</button></span></div>
   <p v-if="storageNotice" class="notice">{{storageNotice}}</p>
   <p v-if="localError||runState.error" class="error-text" role="alert">{{localError||runState.error}}</p>
   <p v-if="locked" class="notice" role="status">{{runState.status==='paused'?'Connection interrupted. Reconnect to continue.':'Calculating your results…'}} <button v-if="runState.status==='paused'" class="link" @click="run(true)">Reconnect</button></p>
   <template v-if="tab==='Data'">
    <ol class="input-steps" aria-label="Input progress"><li :class="{active:workspaceStep==='input'}">1 <span>Enter data</span></li><li :class="{active:workspaceStep==='preview'}">2 <span>Preview</span></li><li>3 <span>Results</span></li></ol>
    <template v-if="workspaceStep==='input'">
     <p class="input-method-hint">Choose any one input method.</p>
     <div class="input-method-grid" aria-label="Input methods">
      <section class="input-method-card" aria-labelledby="manual-method-title"><h3 id="manual-method-title">Add chemicals</h3><div class="chemical-chooser"><label id="add-chemical-label">Chemical name, CAS or InChIKey</label><VAutocomplete v-model="chemicalChoice" :items="options" :custom-filter="chemicalFilter" item-title="title" item-value="value" aria-labelledby="add-chemical-label" placeholder="Search a chemical, e.g. BIT" variant="outlined" density="compact" hide-details clearable :disabled="blocked" /></div><div class="method-actions"><button class="primary" :disabled="blocked||!chemicalChoice" @click="addChemical">Add chemical</button></div></section>
      <section class="input-method-card" aria-labelledby="upload-method-title"><h3 id="upload-method-title">Upload file</h3><p class="note">Two columns: chemical identifier and WW (nM). Excel uses the first worksheet.</p><div class="file-picker"><button type="button" class="secondary" :disabled="blocked" @click="fileInput?.click()">{{importing?'Reading file…':'Choose file'}}</button><span id="selected-upload-name" class="selected-file-name" role="status">{{selectedFileName||'No file selected'}}</span><input ref="fileInput" class="file-input" type="file" accept=".xlsx,.csv,.tsv,.txt" :disabled="blocked" tabindex="-1" aria-label="Upload concentration file" aria-describedby="selected-upload-name" @change="importFile"></div><div class="method-actions"><button class="link" @click="template">Download template</button></div></section>
      <section class="input-method-card" aria-labelledby="paste-method-title"><h3 id="paste-method-title">Paste from Excel</h3><label for="paste-concentrations">Chemical identifier and WW (nM)</label><textarea id="paste-concentrations" v-model="pastedText" :disabled="blocked" rows="2" placeholder="Chemical&#9;WW (nM)&#10;BIT&#9;0.5"></textarea><div class="method-actions"><button class="primary" :disabled="blocked||!pastedText.trim()" @click="usePaste">Preview pasted data</button><button class="link" @click="template">Download template</button></div></section>
     </div>
     <div class="toolbar"><strong v-if="draftRows.length">{{draftLabel}} · {{draftRows.length}} rows</strong><div class="actions input-table-actions"><button class="secondary" :disabled="blocked" @click="loadExample();localError=''">Example data</button><button class="link" :disabled="blocked||!draftRows.length" @click="clearDraft">Clear inputs</button><button class="primary download-inputs" :disabled="!draftRows.length" @click="exportInputs"><v-icon icon="mdi-download" size="18" aria-hidden="true" />Download CSV</button></div></div>
     <template v-if="draftRows.length">
      <div ref="tableRegion" class="table-scroll workspace-table-scroll" :style="{maxHeight:tableMaxHeight}" tabindex="0" role="region" aria-label="WW inputs, scroll within this table"><table class="ww-input-table"><thead><tr><th>Chemical</th><th>WW input (nM)</th><th>Status</th><th></th></tr></thead><tbody><tr v-for="row in evaluatedDraft" :key="row.key" :class="{'input-modified':modified(row),'input-invalid':!row.valid&&String(row.ww).trim()!==''}">
       <td class="chem"><template v-if="row.chemical">{{chemicalName(row.chemical)}}<small>{{row.chemical.cas}} · {{row.chemical.id}}</small></template><template v-else><input :value="row.identifier" :disabled="blocked" :aria-label="'Chemical identifier, row '+row.position" @input="updateDraftRow(row.key,'identifier',$event.target.value)"><small class="error-text">{{row.reason}}</small></template></td>
       <td class="input-cell"><input :value="row.ww" type="text" inputmode="decimal" :disabled="blocked" :aria-label="(row.chemical?chemicalName(row.chemical):row.identifier)+' WW input in nM'" :aria-invalid="!row.valid&&String(row.ww).trim()!==''" @input="updateDraftRow(row.key,'ww',$event.target.value)"><small v-if="modified(row)" class="original-ww">{{row.origin==='example'?'Example':'Original'}}: {{row.originalWW}} nM <button class="link" :disabled="blocked" @click="updateDraftRow(row.key,'ww',row.originalWW)">Restore</button></small></td>
       <td><span class="input-status" :class="!row.valid?'is-invalid':modified(row)?'is-modified':'is-default'">{{!row.valid?(row.ww===''?'Enter value':'Check input'):modified(row)?'Modified':row.origin==='example'?'Example':'Ready'}}</span><small v-if="!row.valid&&row.chemical&&row.ww!==''" class="row-reason">{{row.reason}}</small></td>
       <td><button class="link" :disabled="blocked" :aria-label="'Remove '+(row.chemical?chemicalName(row.chemical):row.identifier)" @click="removeDraftRow(row.key)">Remove</button></td>
      </tr></tbody></table></div>
     </template>
     <p v-else class="empty-input">Add your first chemical, import a table, or try Example data.</p>
     <div v-if="draftRows.length||snapshot" ref="flowActions" class="flow-actions"><span v-if="draftRows.length" class="note">{{validInputs.length}} valid · {{invalidInputs.length}} to review</span><div class="flow-primary-actions"><button v-if="draftRows.length" class="primary" :disabled="blocked" @click="preview">Preview {{draftRows.length}} rows →</button><router-link v-if="snapshot" class="link saved-result-link" to="/rank/Figure?source=current">View {{dirty?'previous':'my'}} results →</router-link></div></div>
    </template>
    <template v-else>
     <div class="toolbar"><h3 class="preview-title">Review your inputs</h3><span class="note">{{draftLabel}}</span></div>
     <div v-if="previewRows.length" ref="tableRegion" class="table-scroll workspace-table-scroll" :style="{maxHeight:tableMaxHeight}" tabindex="0" role="region" aria-label="Input preview, scroll within this table"><table><thead><tr><th>Row</th><th>Provided identifier</th><th>Matched chemical</th><th>WW (nM)</th><th>Status</th></tr></thead><tbody><tr v-for="row in previewRows" :key="row.key" :class="{'input-invalid':!row.valid}"><td>{{row.position}}</td><td class="provided-identifier">{{row.identifier||'—'}}</td><td class="chem">{{row.chemical?chemicalName(row.chemical):'—'}}</td><td class="number">{{row.ww||'—'}}</td><td><span class="input-status" :class="row.valid?'is-valid':'is-invalid'">{{row.valid?'Valid':'Invalid'}}</span><small v-if="!row.valid" class="row-reason">{{row.reason}}</small></td></tr></tbody></table></div>
     <p v-else class="state">No input records.</p>
     <div ref="flowActions" class="flow-actions"><button class="secondary" :disabled="blocked" @click="back">← Back</button><div class="actions"><span v-if="invalidInputs.length" class="note">{{invalidInputs.length}} invalid rows will be excluded.</span><div class="flow-primary-actions"><button class="primary" :disabled="blocked||!validInputs.length||health.status!=='ready'" @click="run()">{{locked?'Running…':'Run '+validInputs.length+' valid chemical'+(validInputs.length===1?'':'s')+' →'}}</button><router-link v-if="snapshot" class="link saved-result-link" to="/rank/Figure?source=current">View {{dirty?'previous':'my'}} results →</router-link></div></div></div>
    </template>
   </template>
   <template v-else><div class="toolbar"><span>{{chartRows.length}} chemicals with valid WW input</span><router-link v-if="snapshot" class="link saved-result-link" to="/rank/Figure?source=current">View {{dirty?'previous':'my'}} results →</router-link></div><Plot v-if="chartRows.length" :option="option" :height="560" :figure-number="1" :show-number="false" aria-label="WW input concentrations by chemical"><template #controls><div class="actions wpn-plot-controls"><label class="checks"><input v-model="scale" type="checkbox" true-value="log" false-value="value">Logarithmic axis</label><router-link class="secondary" to="/wpn/Data">Edit inputs</router-link></div></template></Plot><div v-else class="state">Add your WW concentrations to view their distribution. <router-link class="link" to="/wpn/Data">Enter data →</router-link></div></template>
  </template>
 </section>
</template>
<style scoped src="./scenario.css"></style>
<style scoped>
.workspace-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}.workspace-heading .note{margin:0}.service-status{display:flex;gap:7px;align-items:center;font-size:12px;white-space:nowrap;color:#64748b;margin-top:7px}.service-status .health-dot{display:inline-block}
.input-steps{list-style:none;display:flex;gap:30px;margin:28px 0;padding:0;font-size:14px;color:#8290a4}.input-steps li{display:flex;align-items:center;gap:10px;font-weight:600}.input-steps li.active{color:#2463df}
.scenario .input-method-hint{margin:0 0 10px;font-size:14px;color:#516071}
.input-method-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:16px}
.input-method-card{display:flex;flex-direction:column;gap:10px;min-width:0;padding:14px;border:1px solid #dce5f1;border-radius:7px;background:#fbfcff}
.scenario .input-method-card h3{font-size:16px;line-height:1.4;margin:0;color:#334155}
.scenario .input-method-card .note{font-size:13px;line-height:1.5;margin:0}
.chemical-chooser{min-width:0}.chemical-chooser label{margin-bottom:8px}
.input-method-card textarea{width:100%;min-height:60px;max-height:160px;resize:vertical;border:1px solid #cbd7e9;border-radius:5px;padding:8px 10px;font:13px/1.5 monospace;background:white}
.method-actions{display:flex;align-items:center;flex-wrap:wrap;gap:8px 12px;margin-top:auto}
.method-actions .primary{padding:8px 12px}
.file-picker{position:relative;display:flex;align-items:center;gap:10px;min-width:0}.file-picker button{flex-shrink:0}.selected-file-name{min-width:0;color:#627084;font-size:13px;overflow-wrap:anywhere}
.scenario .file-picker .file-input{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip-path:inset(50%);white-space:nowrap;border:0}
.empty-input{padding:24px;text-align:center!important;border:1px solid #e2eaf4;border-radius:8px;color:#64748b}.flow-actions{display:flex;justify-content:space-between;align-items:center;gap:16px;margin:24px 0}.scenario .ww-input-table{min-width:760px}.scenario .ww-input-table .input-cell{min-width:190px;width:220px}.row-reason{display:block;font-size:12px;color:#a33624;max-width:240px;margin-top:5px}.input-status.is-valid{background:#e8f5ef;border-color:#b4d9c7;color:#21694c}.provided-identifier{max-width:260px;overflow-wrap:anywhere}.preview-title{margin:0!important}
.input-table-actions{margin-left:auto}.download-inputs{display:inline-flex;align-items:center;gap:7px}.flow-primary-actions{display:flex;flex-direction:column;align-items:flex-end;gap:8px;margin-left:auto}.saved-result-link{font-size:14px}.wpn-plot-controls{font-size:14px}
@media(max-width:960px){.input-method-grid{grid-template-columns:1fr}.input-method-card{gap:10px}.method-actions{margin-top:2px}}
@media(max-width:620px){.workspace-heading{flex-direction:column;gap:8px}.input-steps{gap:20px;font-size:13px}.flow-actions{align-items:flex-start;flex-wrap:wrap}.service-status{margin-bottom:8px}}
.workspace-data .input-steps{margin:18px 0}.workspace-data .toolbar{margin:12px 0}
.workspace-table-scroll{max-height:clamp(160px,calc(100dvh - 560px),560px);scrollbar-gutter:stable;overscroll-behavior:contain}
.workspace-table-scroll th{position:sticky;top:0;z-index:1;box-shadow:0 1px 0 #dce3ec}
.workspace-table-scroll:focus-visible{outline:2px solid #2463df;outline-offset:3px}
.workspace-data .flow-actions{position:sticky;bottom:0;z-index:2;min-height:60px;margin:12px 0 0;padding:10px 0;background:#fff;border-top:1px solid #e5ebf4}
.workspace-data.workspace-actions-flow .flow-actions{position:static}
@media(min-width:761px) and (min-height:640px) and (max-height:820px){.workspace-data .input-steps{margin:12px 0}.workspace-data .toolbar{margin:8px 0}}
@media(max-width:760px),(max-height:639px){.workspace-table-scroll{max-height:48dvh;min-height:180px}.workspace-data .flow-actions{position:static;flex-wrap:wrap}.workspace-data .flow-actions>.actions{flex:1;justify-content:flex-end}}
</style>
