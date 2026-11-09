import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 빌드 결과는 파이썬 패키지 안(src/awsglance/static)으로 — 사용자는 Node 없이 wheel 만 받는다.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/awsglance/static",
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    // 개발할 때: 백엔드(awsglance --demo --no-browser)를 8730 에 띄우고 /api 만 넘긴다
    proxy: { "/api": "http://127.0.0.1:8730" },
  },
});
