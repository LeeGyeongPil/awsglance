// 연습 모드 화면을 캡처한다(README 용). 서버는 따로 띄워 둔다:
//   uv run awsglance --demo --no-browser --port 8730
//   npm i playwright && npx playwright install chromium-headless-shell
//   node scripts/screenshots.mjs http://127.0.0.1:8730 docs/images
// 화면을 바꾸지 않는다 — 문제 숨김 대화상자도 열기만 하고 제출하지 않는다.
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright";

const base = process.argv[2] ?? "http://127.0.0.1:8730";
const out = process.argv[3] ?? "docs/images";
mkdirSync(out, { recursive: true });

const shots = [
  { name: "overview", path: "/" },
  { name: "changes-human", path: "/changes?tab=human", click: ".event-head" },
  { name: "findings", path: "/findings", click: ".finding-row" },
  { name: "resource-drawer", path: "/resources?type=security_group", click: "tr.clickable" },
  { name: "setup", path: "/setup" },
];

const browser = await chromium.launch();
try {
  for (const theme of ["light", "dark"]) {
    const page = await browser.newPage({ viewport: { width: 1360, height: 900 }, deviceScaleFactor: 2 });
    await page.addInitScript((t) => window.localStorage.setItem("awsglance-theme", t), theme);
    for (const s of shots) {
      await page.goto(base + s.path, { waitUntil: "networkidle" });
      if (s.click) {
        await page.locator(s.click).first().click();
        await page.waitForLoadState("networkidle");
      }
      const file = join(out, `${s.name}${theme === "dark" ? "-dark" : ""}.png`);
      await page.screenshot({ path: file, fullPage: true });
      console.log(file);
    }
    await page.close();
  }
  // 900px 이하 반응형
  const narrow = await browser.newPage({ viewport: { width: 420, height: 900 }, deviceScaleFactor: 2 });
  await narrow.goto(base + "/", { waitUntil: "networkidle" });
  await narrow.screenshot({ path: join(out, "overview-mobile.png"), fullPage: true });
  console.log(join(out, "overview-mobile.png"));
} finally {
  await browser.close();
}
