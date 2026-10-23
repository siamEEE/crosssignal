import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    // The FastAPI backend (uvicorn crosssignal.api:app) runs on :8000.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
