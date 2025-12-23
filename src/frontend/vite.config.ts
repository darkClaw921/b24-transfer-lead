import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    allowedHosts: [
      'b17345212eb8.ngrok-free.app',
      'localhost',
    ],
    proxy: {
      '/api/public': {
        target: 'http://localhost:7860',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/public/, '/api/v1/public'),
      },
      '/api': {
        target: 'http://localhost:7860',
        changeOrigin: true,
      },
    },
  },
})

