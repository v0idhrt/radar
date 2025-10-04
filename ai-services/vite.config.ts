import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    return {
      server: {
        port: 3000,
        host: '0.0.0.0',
      },
      plugins: [react()],
      define: {
        'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY),
        'process.env.OPENROUTER_API_KEY': JSON.stringify(env.OPENROUTER_API_KEY),
        'process.env.OLLAMA_HOST': JSON.stringify(env.OLLAMA_HOST || 'http://localhost:11434'),
        'process.env.GEMINI_MODEL': JSON.stringify(env.GEMINI_MODEL || 'gemini-1.5-flash'),
        'process.env.OPENROUTER_MODEL': JSON.stringify(env.OPENROUTER_MODEL || 'google/gemma-2-9b-it'),
        'process.env.OLLAMA_MODEL': JSON.stringify(env.OLLAMA_MODEL || 'gemma2:9b')
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        }
      }
    };
});
