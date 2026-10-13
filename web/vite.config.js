import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // stable file names, so a rebuild replaces files instead of adding new ones
  build: { rollupOptions: { output: { entryFileNames: "assets/app.js", assetFileNames: (a) => (a.names?.[0] || a.name || "").endsWith(".css") ? "assets/app.css" : "assets/[name]-[hash][extname]" } } },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
