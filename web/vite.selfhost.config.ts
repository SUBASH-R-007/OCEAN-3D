import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/postcss';
import { fileURLToPath, URL } from 'node:url';
const proxy = {
  '/api': process.env.OCEAN_API_UPSTREAM || 'http://127.0.0.1:8000',
};
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('.', import.meta.url)) } },
  css: { postcss: { plugins: [tailwindcss()] } },
  define: { 'import.meta.env.VITE_SCIENTIFIC_API': JSON.stringify('true') },
  build: { outDir: 'selfhost-dist' },
  server: {
    host: '127.0.0.1',
    port: 3000,
    strictPort: true,
    proxy,
  },
  preview: { host: '127.0.0.1', strictPort: true, proxy },
});
