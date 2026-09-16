import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Mirror the Netlify proxy so local dev and production behave identically.
      // /api/* is forwarded to the Render backend; cookies are first-party.
      '/api': {
        target: 'https://learning-management-system-5nws.onrender.com',
        changeOrigin: true,
        secure: true,
      },
    },
  },
})
