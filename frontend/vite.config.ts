import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // No fixed port: the preview harness assigns one via PORT.
  server: { port: Number(process.env.PORT) || 5173, host: true },
});
