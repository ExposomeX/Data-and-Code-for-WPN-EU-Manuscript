import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';
export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  // Avoid intermittent native esbuild service stalls on this Windows runtime.
  // The local app targets the installed modern browser; retain readable output.
  esbuild: false,
  build: { target: 'esnext', minify: false, cssMinify: false, chunkSizeWarningLimit: 1700 },
  server: { host: '127.0.0.1' },
});
