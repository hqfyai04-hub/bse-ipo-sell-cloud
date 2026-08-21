import { access, readFile } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..", "app", "static");
const manifest = JSON.parse(await readFile(resolve(root, "manifest.webmanifest"), "utf8"));
const required = ["name", "short_name", "start_url", "display", "icons"];
for (const key of required) {
  if (!manifest[key] || (Array.isArray(manifest[key]) && manifest[key].length === 0)) {
    throw new Error(`manifest 缺少 ${key}`);
  }
}
for (const size of ["192x192", "512x512"]) {
  const icon = manifest.icons.find((item) => String(item.sizes || "").split(/\s+/).includes(size));
  if (!icon) throw new Error(`manifest 缺少 ${size} 图标`);
  await access(resolve(root, icon.src.replace(/^\/static\//, "")));
}
const index = await readFile(resolve(root, "index.html"), "utf8");
for (const marker of ["manifest.webmanifest", "app-config.js", "pwa.js", "installAppBtn"]) {
  if (!index.includes(marker)) throw new Error(`index.html 缺少 ${marker}`);
}
const worker = await readFile(resolve(root, "service-worker.js"), "utf8");
if (!worker.includes("/api/") || !worker.includes("networkOnly")) {
  throw new Error("Service Worker 必须明确绕过实时 API 缓存");
}
console.log("PWA manifest、安装入口、图标和 API 禁缓存规则检查通过。");
