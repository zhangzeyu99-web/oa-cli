import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/oa/dashboard",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": "http://localhost:3456",
    },
  },
});
