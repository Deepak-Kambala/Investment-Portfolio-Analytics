import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api calls are proxied to the FastAPI server, so the browser never needs CORS in dev
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
