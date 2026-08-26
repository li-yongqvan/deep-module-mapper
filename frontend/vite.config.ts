import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Design doc D1/B3: dev server must run on 5175, not Vite's default 5173.
    port: 5175,
  },
  preview: {
    port: 5175,
  },
})
