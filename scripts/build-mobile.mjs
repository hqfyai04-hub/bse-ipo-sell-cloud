import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const projectRoot = resolve(import.meta.dirname, "..");
const sourceDir = resolve(projectRoot, "app", "static");
const outputDir = resolve(projectRoot, "www");
const strict = process.argv.includes("--strict");
const rawBaseUrl = (process.env.APP_API_BASE_URL || "").trim();

if (strict && !rawBaseUrl) {
  throw new Error("缺少 APP_API_BASE_URL。APK 必须指向已经部署的 HTTPS 云端地址。");
}
if (rawBaseUrl && !/^https:\/\//i.test(rawBaseUrl)) {
  throw new Error("APP_API_BASE_URL 必须使用 HTTPS，不能把行情口令发往明文 HTTP。");
}

const apiBaseUrl = rawBaseUrl.replace(/\/+$/, "");
await rm(outputDir, { recursive: true, force: true });
await mkdir(resolve(outputDir, "static"), { recursive: true });
await cp(sourceDir, resolve(outputDir, "static"), { recursive: true });
await cp(resolve(sourceDir, "index.html"), resolve(outputDir, "index.html"));

const config = `window.APP_CONFIG = Object.freeze(${JSON.stringify({
  API_BASE_URL: apiBaseUrl,
  NATIVE_BUILD: true,
})});\n`;
await writeFile(resolve(outputDir, "static", "app-config.js"), config, "utf8");

const indexPath = resolve(outputDir, "index.html");
const index = await readFile(indexPath, "utf8");
if (!index.includes("/static/app-config.js")) {
  throw new Error("index.html 缺少 app-config.js，无法注入云端地址。");
}

console.log(
  apiBaseUrl
    ? `Android Web 资源已生成，API: ${apiBaseUrl}`
    : "Android Web 资源已生成（预览模式）；正式同步前请设置 APP_API_BASE_URL。",
);
