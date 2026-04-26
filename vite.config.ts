import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Local development: proxy /api to the current VPS backend
      '/api': {
        target: 'http://150.158.38.145',
        changeOrigin: true,
      },
      // Proxy challenge assets if needed
      '/challenges': {
        target: 'http://150.158.38.145',
        changeOrigin: true,
      }
    }
  }
})
