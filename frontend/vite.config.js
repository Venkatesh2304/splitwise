import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  },
  preview: {
    // The HTTPS hostname nginx forwards (see NOTIFICATIONS_SETUP.md). Vite rejects
    // unknown Host headers; plain IP addresses are always allowed.
    allowedHosts: ['.duckdns.org'],
  },
})
