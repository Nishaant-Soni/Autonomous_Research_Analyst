import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Vite dev server is browser-facing; the browser calls the API directly at VITE_API_URL.
// No proxy needed (the API has CORS for http://localhost:5173).
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    // HMR over docker volumes can stall on macOS without polling.
    watch: { usePolling: true, interval: 200 },
  },
  test: {
    environment: "jsdom",
  },
});
