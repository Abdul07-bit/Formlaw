import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Docker sets VITE_PROXY_TARGET=http://backend:8000; locally the API runs on port 8000 (npm run api).
const env = (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env ?? {}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { '/api': { target: env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:8000', changeOrigin: false } },
  },
})
