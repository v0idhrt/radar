import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    return {
      server: {
        port: 3000,
        host: '0.0.0.0',
        allowedHosts: [
          '.ngrok-free.app',    // Allow all ngrok hosts
          '.ngrok.io',          // Alternative ngrok domain
          'localhost',
          '127.0.0.1',
        ],
        cors: true,
      },
      plugins: [react()],
      // Note: API keys and LLM configs removed - now handled by backend
      define: {
        // Keep only if needed for other purposes
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        }
      }
    };
});
