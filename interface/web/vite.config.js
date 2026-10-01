import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// npm run build produit dist/, que sert python -m interface.serveur.
// npm run dev sert l'application sur le port 5173 et relaie /api vers ce serveur Python.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true } }
  },
  build: { outDir: 'dist', chunkSizeWarningLimit: 1500 }
});
