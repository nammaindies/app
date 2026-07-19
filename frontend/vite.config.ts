import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Namma IndieDex — lean placeholder PWA. A designer will rebuild this later.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "Namma IndieDex",
        short_name: "IndieDex",
        description: "Spot and log indie street dogs around you.",
        start_url: "/",
        display: "standalone",
        background_color: "#FBF3E9",
        theme_color: "#C4562F",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      "/sighting": { target: "http://localhost:8000", changeOrigin: true },
      "/dex": { target: "http://localhost:8000", changeOrigin: true },
      "/auth": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
