<script setup>
import { computed, onMounted, ref } from 'vue';

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
</script>

<template>
  <section class="code-download" aria-labelledby="code-heading">
    <div class="code-intro">
      <div class="code-intro-heading">
        <p class="code-eyebrow">WPN LOCAL CODE</p>
        <h1 id="code-heading">Run WPN on your computer</h1>
      </div>
      <div class="code-download-action">
        <a v-if="bundle && !error" href="/downloads/WPN-local-code.zip" download="WPN-local-code.zip" class="code-download-button"><v-icon icon="mdi-download" aria-hidden="true" /> Download WPN Code</a>
        <span v-else-if="loading" role="status">Preparing download…</span>
        <div v-else role="alert"><p>{{ error }}</p><button @click="loadBundle">Retry</button></div>
        <span v-if="bundle && !error" class="code-download-meta">ZIP · {{ sizeLabel }}</span>
      </div>
      <p class="code-lead">Enter WW concentrations to generate chemical rankings, a results table and a BEQ plot.</p>
    </div>

    <ol class="code-steps" aria-label="Local WPN instructions">
      <li><span class="code-step-number" aria-hidden="true">1</span><div><h2>Download and unzip</h2><p>Extract the complete package to a folder on your computer.</p></div></li>
      <li><span class="code-step-number" aria-hidden="true">2</span><div><h2>Set up once</h2><p>Install <a href="https://www.python.org/downloads/release/python-31210/" target="_blank" rel="noopener">Python 3.12 (64-bit)</a>, then double-click <code>Setup_WPN.bat</code>. This first setup downloads the required libraries.</p></div></li>
      <li><span class="code-step-number" aria-hidden="true">3</span><div><h2>Fill in your concentrations</h2><p>Open <code>inputs/concentrations.xlsx</code> and enter WW concentrations in nM. Leave unused chemicals blank. CSV input and example data are also included.</p></div></li>
      <li><span class="code-step-number" aria-hidden="true">4</span><div><h2>Run and view your results</h2><p>Double-click <code>Run_WPN.bat</code> or run <code>run.py</code> to calculate locally on <span class="cpu-badge">CPU</span>. Find your ranking table and BEQ plot in <code>results</code>.</p></div></li>
    </ol>

    <div class="code-outputs">
      <div><v-icon icon="mdi-table" aria-hidden="true" /><div><h2>Results table</h2><p>Rank · Chemical · WW input · BEQ · Contribution (%)</p></div></div>
      <div><v-icon icon="mdi-chart-bar" aria-hidden="true" /><div><h2>BEQ plot</h2><p>All evaluated chemicals, a logarithmic BEQ axis and cumulative contribution.</p></div></div>
    </div>
    <p class="code-footnote">Built with PriorLabs-TabPFN · <a href="/notices/TabPFN-2.6-LICENSE.txt" target="_blank" rel="noopener">Model license</a></p>
  </section>
</template>

<style scoped>
.code-download{color:#2f3948;max-width:1200px;margin:0 auto;font-size:15px;line-height:1.6}
.code-intro{display:grid;grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"heading action" "lead lead";align-items:center;gap:12px 32px;padding:6px 0 28px;border-bottom:1px solid #e3e9f2}
.code-intro-heading{grid-area:heading;min-width:0}.code-lead{grid-area:lead}
.code-eyebrow{font-size:12px;letter-spacing:1.6px;font-weight:700;color:#4667d7;margin:0 0 8px}
h1{font-size:26px;line-height:1.3;margin:0;color:#273342}.code-intro p:not(.code-eyebrow){margin:0;color:#67758a}
.cpu-badge{display:inline-block;border:1px solid #a9c2f3;border-radius:4px;background:#eef4ff;color:#315ba7;font-weight:600;line-height:1.4;padding:0 6px}
.code-download-action{grid-area:action;display:flex;flex-direction:column;align-items:center;gap:10px;flex-shrink:0}.code-download-button{display:inline-flex;align-items:center;justify-content:center;gap:9px;background:#2463df;color:#fff;font-weight:600;padding:13px 22px;border-radius:6px;text-decoration:none}.code-download-button:hover{background:#194fc0}.code-download-meta{font-size:12px;color:#78859a}.code-download-action button{color:#2463df;text-decoration:underline}
.code-steps{list-style:none;padding:0;margin:26px 0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px 36px}.code-steps li{display:flex;gap:14px;align-items:flex-start}.code-step-number{display:grid;place-items:center;background:#edf3ff;color:#2463df;font-weight:700;flex:0 0 34px;height:34px;border-radius:50%}h2{font-size:16px;margin:2px 0 6px;line-height:1.5}.code-steps p,.code-outputs p{margin:0;color:#67758a;line-height:1.7}.code-steps code{background:#f3f5f9;border-radius:3px;padding:1px 4px;font-size:13px;overflow-wrap:anywhere}
.code-outputs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;padding:20px;border:1px solid #dfe8f6;border-radius:8px;background:#fafcff}.code-outputs>div{display:flex;gap:14px}.code-outputs .v-icon{color:#4265df;margin-top:4px}.code-outputs p{font-size:13px}.code-footnote{font-size:12px;color:#7d8796;margin:18px 0 0}
@media(max-width:900px){.code-intro{grid-template-columns:minmax(0,1fr);grid-template-areas:"heading" "lead" "action";align-items:start;gap:18px}.code-download-action{align-items:flex-start}.code-steps{gap:20px}}
@media(max-width:620px){h1{font-size:23px}.code-steps,.code-outputs{grid-template-columns:1fr}.code-download-action,.code-download-button{width:100%}.code-download-action{align-items:center}.code-outputs{padding:16px}.code-steps{gap:22px}}
</style>
