// Vercel 환경변수에서 공개 API 주소만 정적 설정 파일로 만듭니다.
import { writeFileSync, mkdirSync, cpSync } from "node:fs";
import { fileURLToPath } from "node:url";
const base = (process.env.API_BASE_URL || "").replace(/\/+$/, "");
if (base) {
  const url = new URL(base);
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== "/") {
    throw new Error("API_BASE_URL must be an HTTP(S) server origin without credentials, path or query.");
  }
  if (process.env.VERCEL && url.protocol !== "https:") throw new Error("Use HTTPS for the deployed API.");
}
if (process.env.VERCEL && !base) throw new Error("Set API_BASE_URL to the Render server origin.");
const output = fileURLToPath(new URL("dist/", import.meta.url));
mkdirSync(output, { recursive: true });
cpSync(fileURLToPath(new URL("index.html", import.meta.url)), fileURLToPath(new URL("dist/index.html", import.meta.url)));
cpSync(fileURLToPath(new URL("assets/", import.meta.url)), fileURLToPath(new URL("dist/assets/", import.meta.url)), { recursive: true });
writeFileSync(fileURLToPath(new URL("dist/config.js", import.meta.url)),
  `window.APP_CONFIG = ${JSON.stringify({ apiBaseUrl: base })};\n`, "utf8");
console.log("Frontend built in dist; only the public API address was included.");
