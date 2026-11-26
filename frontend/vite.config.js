import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Libraries that rarely change get their own chunks, so an app deploy does not
// invalidate them in users' caches. Charts are lazy-loaded by the pages that use them.
const VENDOR_CHUNKS = {
  'vendor-react': ['react', 'react-dom', 'react-router', 'react-router-dom', 'scheduler'],
  'vendor-auth': ['@supabase/auth-js'],
}

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const match = id.match(/node_modules\/((?:@[^/]+\/)?[^/]+)/)
          if (!match) return undefined
          for (const [chunk, packages] of Object.entries(VENDOR_CHUNKS)) {
            if (packages.includes(match[1])) return chunk
          }
          return undefined
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
