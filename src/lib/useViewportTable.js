import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';

// Fit the table to the space below its real position, including wrapped controls.
export function useViewportTable(section, table) {
  const tableMaxHeight = ref(null);
  let mounted = false, frame, observer;
  function fit() {
    if (!table.value || !section.value) return;
    if (window.innerWidth <= 620 || window.innerHeight < 640) {
      tableMaxHeight.value = null;
      return;
    }
    const content = section.value.closest('.module-content');
    const footer = document.querySelector('.site-footer');
    const rect = table.value.getBoundingClientRect();
    const top = rect.top + window.scrollY;
    const afterTable = Math.max(0, (content?.getBoundingClientRect().bottom ?? rect.bottom) - rect.bottom);
    const footerHeight = footer?.getBoundingClientRect().height || 0;
    tableMaxHeight.value = Math.max(120, Math.floor(window.innerHeight - top - afterTable - footerHeight - 8)) + 'px';
  }
  async function schedule() {
    await nextTick();
    if (!mounted) return;
    window.cancelAnimationFrame(frame);
    frame = window.requestAnimationFrame(fit);
  }
  function observeLayout() {
    observer?.disconnect();
    if (!observer || !section.value) return;
    const layout = section.value.closest('.module-layout');
    for (const element of [section.value, layout?.querySelector('.sub-navigation'), document.querySelector('.site-footer')]) {
      if (element) observer.observe(element);
    }
  }
  watch([section, table], () => { if (mounted) observeLayout(); schedule(); }, { flush: 'post' });
  onMounted(() => {
    if (typeof window === 'undefined') return;
    mounted = true;
    if (typeof ResizeObserver !== 'undefined') observer = new ResizeObserver(schedule);
    observeLayout();
    window.addEventListener('resize', schedule);
    document.fonts?.ready.then(schedule);
    schedule();
  });
  onBeforeUnmount(() => {
    mounted = false;
    observer?.disconnect();
    if (typeof window !== 'undefined') {
      window.removeEventListener('resize', schedule);
      window.cancelAnimationFrame(frame);
    }
  });
  return { tableMaxHeight };
}
