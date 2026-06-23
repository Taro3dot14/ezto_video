import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

/** Registry edits need a full reload — HMR can leave a stale CHAPTERS length in memory. */
function registryFullReload(): Plugin {
  return {
    name: "registry-full-reload",
    handleHotUpdate({ file, server }) {
      const norm = file.replace(/\\/g, "/");
      if (
        norm.endsWith("/registry/chapters.ts") ||
        norm.endsWith("/registry/chapter-meta.ts")
      ) {
        server.ws.send({ type: "full-reload" });
        return [];
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), registryFullReload()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5202,
    fs: { allow: [".."] },
  },
});
