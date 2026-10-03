import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const repoRoot = path.dirname(fileURLToPath(import.meta.url));

function contentTypeFor(filePath: string): string {
  if (filePath.endsWith(".json")) {
    return "application/json; charset=utf-8";
  }
  return "application/octet-stream";
}

/**
 * Serves repo config/ and out/ at /config and /out while Vite root is web/.
 */
function serveRepoDataDirs(): Plugin {
  return {
    name: "serve-repo-data-dirs",
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const rawUrl = request.url || "";
        const pathname = rawUrl.split("?")[0] || "";
        let baseDir: string | null = null;
        let relativePath = "";

        if (pathname.startsWith("/config/")) {
          baseDir = path.join(repoRoot, "config");
          relativePath = pathname.slice("/config/".length);
        } else if (pathname.startsWith("/out/")) {
          baseDir = path.join(repoRoot, "out");
          relativePath = pathname.slice("/out/".length);
        } else {
          next();
          return;
        }

        const filePath = path.resolve(baseDir, relativePath);
        if (!filePath.startsWith(baseDir) || !fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
          response.statusCode = 404;
          response.end("Not found");
          return;
        }

        response.setHeader("Content-Type", contentTypeFor(filePath));
        response.setHeader("Cache-Control", "no-store");
        fs.createReadStream(filePath).pipe(response);
      });
    },
  };
}

export default defineConfig({
  root: "web",
  publicDir: false,
  plugins: [react(), tailwindcss(), serveRepoDataDirs()],
  server: {
    fs: {
      allow: [repoRoot],
    },
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (url) => url.replace(/^\/api/, ""),
      },
    },
  },
  build: {
    outDir: path.join(repoRoot, "dist"),
    emptyOutDir: true,
  },
});
