import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// GitHub Pages project site is served from https://<user>.github.io/sat-prep/
// so the base path must match the repository name.
export default defineConfig({
  base: '/sat-prep/',
  plugins: [react()],
});
