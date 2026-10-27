import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";

// Configuracion de Vite para el frontend Vue 3.
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // Proxy opcional para desarrollo: evita configurar CORS en local.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      // Proxy del WebSocket realtime hacia el backend FastAPI.
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
