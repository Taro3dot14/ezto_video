import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

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
  server: {
    port: 5174,
    fs: { allow: [".."] },
  },
});
