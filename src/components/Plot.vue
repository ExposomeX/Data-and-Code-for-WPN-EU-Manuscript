<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import * as echarts from 'echarts';

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: [Number, String], default: 460 },
  mapData: { type: Object, default: null },
  caption: { type: String, default: '' },
  ariaLabel: { type: String, default: 'Interactive scientific chart' },
  figureNumber: { type: Number, default: 1 },
  showNumber: { type: Boolean, default: true },
});
const emit = defineEmits(['point-select']);
const host = ref(null);
const error = ref('');
const downloadError = ref('');
const downloadOptions = computed(() => props.option.toolbox?.feature?.saveAsImage);
let chart;
let observer;
let frame;
let lastMap;
function resize() {
  cancelAnimationFrame(frame);
  frame = requestAnimationFrame(() => chart?.resize());
}
function downloadPng() {
  if (!chart || error.value) return;
  try {
    const link = document.createElement('a');
    const dataUrl = chart.getDataURL({
      type: 'png',
      pixelRatio: downloadOptions.value?.pixelRatio || 2,
      backgroundColor: '#fff',
      excludeComponents: ['toolbox'],
    });
    const bytes = Uint8Array.from(atob(dataUrl.split(',')[1]), character => character.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: 'image/png' }));
    link.href = url;
    link.download = `${downloadOptions.value?.name || 'WPN-figure'}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    downloadError.value = '';
  } catch {
    downloadError.value = 'The PNG could not be downloaded. Please try again.';
  }
}
function render() {
  if (!host.value) return;
  try {
    if (props.mapData && props.mapData !== lastMap) {
      echarts.registerMap('wpn-world', props.mapData);
      lastMap = props.mapData;
    }
    if (!chart) {
      chart = echarts.init(host.value, null, { renderer: 'canvas' });
      chart.on('click', params => {
        if (params.data?.record) emit('point-select', params.data.record);
      });
    }
    const option = { animation: false, ...props.option };
    if (downloadOptions.value) {
      option.toolbox = {
        ...props.option.toolbox,
        feature: {
          ...props.option.toolbox.feature,
          saveAsImage: { ...downloadOptions.value, show: false },
        },
      };
    }
    chart.setOption(option, { notMerge: true });
    error.value = '';
    downloadError.value = '';
    resize();
  } catch (cause) {
    error.value = `The chart could not be displayed. ${cause.message || ''}`;
  }
}
watch([() => props.option, () => props.mapData], () => nextTick(render));
watch(() => props.height, () => nextTick(resize));
onMounted(() => {
  render();
  if (typeof ResizeObserver !== 'undefined') {
    observer = new ResizeObserver(resize);
    observer.observe(host.value);
  }
  window.addEventListener('resize', resize);
});
onBeforeUnmount(() => {
  observer?.disconnect();
  window.removeEventListener('resize', resize);
  cancelAnimationFrame(frame);
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <figure class="wpn-plot">
    <div v-if="downloadOptions || $slots.controls" class="plot-actions">
      <div v-if="$slots.controls" class="plot-controls"><slot name="controls" /></div>
      <button v-if="downloadOptions" type="button" class="plot-download" :disabled="!!error" @click="downloadPng">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3v12m-5-5 5 5 5-5M4 15v5h16v-5" /></svg>
        Download PNG
      </button>
    </div>
    <p v-if="downloadError" class="plot-download-error" role="alert">{{ downloadError }}</p>
    <div v-if="error" class="plot-error" role="alert">{{ error }} <button type="button" @click="render">Retry chart</button></div>
    <div ref="host" class="plot-canvas" :style="{ height: typeof height === 'number' ? `${height}px` : height }" role="img" :aria-label="showNumber ? `Fig ${figureNumber}. ${ariaLabel}` : ariaLabel"></div>
    <figcaption v-if="showNumber||caption"><strong v-if="showNumber" class="figure-number">Fig {{ figureNumber }}.</strong><template v-if="caption">{{ (showNumber ? ' ' : '') + caption }}</template></figcaption>
  </figure>
</template>

<style scoped>
.wpn-plot { margin: 0; min-width: 0; width: 100%; }
.plot-actions { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px 16px; margin-bottom: 8px; }
.plot-controls { min-width: 0; }
.plot-actions > .plot-download { margin-left: auto; flex-shrink: 0; }
.plot-download { display: inline-flex; align-items: center; gap: 8px; padding: 9px 14px; border: 1px solid #a9c1ef; border-radius: 5px; background: #fff; color: #2463df; font: inherit; font-size: 14px; font-weight: 600; cursor: pointer; }
.plot-download svg { width: 18px; height: 18px; }
.plot-download:hover { background: #eef4ff; border-color: #2463df; }
.plot-download:focus-visible { outline: 2px solid #2463df; outline-offset: 3px; }
.plot-download:disabled { opacity: .5; cursor: default; }
.plot-download-error { color: #a23725; font-size: 14px; }
.plot-canvas { width: 100%; min-height: 280px; }
figcaption { color: #5a6473; line-height: 1.6; font-size: 14px; margin: 10px 8px 4px; }
.plot-error { padding: 16px; border: 1px solid #e4bd80; background: #fff8eb; border-radius: 6px; }
.plot-error button { margin-left: 10px; color: #2463df; cursor: pointer; text-decoration: underline; }
</style>
