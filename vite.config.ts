import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const target = env.VITE_API_BASE_URL || 'http://150.158.38.145';
  
  return {
    plugins: [react()],
    server: {
      proxy: {
        // Local development: proxy /api to the current VPS backend
        '/api': {
          target,
          changeOrigin: true,
        },
        // Proxy challenge assets if needed
        '/challenges': {
          target,
          changeOrigin: true,
        }
      }
    }
  };
})
