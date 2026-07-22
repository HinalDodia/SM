import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  // Load env vars so we can use them inside the config
  const env = loadEnv(mode, process.cwd(), '');
  const backendUrl = env.VITE_API_URL || 'http://localhost:5000';

  return {
    plugins: [react()],
    server: {
      port: 5173,
      // Dev proxy: any request starting with /api is forwarded to the Flask backend.
      // Frontend code uses VITE_API_URL directly (no /api prefix) — this is only for
      // edge cases like PDF opens where window.location is the same origin.
      proxy: {
        '/stock-bse-filings': {
          target: backendUrl,
          changeOrigin: true,
        },
        '/bse-company': {
          target: backendUrl,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
      chunkSizeWarningLimit: 1500,
    },
  };
});
