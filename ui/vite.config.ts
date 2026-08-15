import { defineConfig } from "vite";

export default defineConfig({
  base: "/next-static/",
  build: {
    outDir: "../harness/server/ui",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "assets/app.js",
        assetFileNames: "assets/app.[ext]",
      },
    },
  },
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
