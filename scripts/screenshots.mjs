// 연습 모드 화면을 캡처한다(문서·README 용). 서랍(drawer)이 열린 장면은 전체 페이지가 아니라 화면 한 장(fullPage: false)만 찍는다. 서버는 따로 띄워 둔다:
//   uv run awsglance --demo --no-browser --port 8730
//   npm i playwright && npx playwright install chromium-headless-shell
//   node scripts/screenshots.mjs http://127.0.0.1:8730 docs/images [en,ko]
// 언어별로 찍는다: 화면 언어는 localStorage 키 awsglance-lang 으로 정한다. 영어는 <이름>.png, 한국어는 <이름>.ko.png.
// 화면을 바꾸지 않는다 — 문제 숨김 대화상자도 열기만 하고 제출하지 않는다.
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright";

const base = process.argv[2] ?? "http://127.0.0.1:8730";
const out = process.argv[3] ?? "docs/images";
const langs = (process.argv[4] ?? "en,ko").split(",");
mkdirSync(out, { recursive: true });

const shots = [
  { name: "overview", path: "/" },
  { name: "changes-human", path: "/changes?tab=human", click: ".event-head" },
  { name: "findings", path: "/findings", click: ".finding-row" },
  { name: "resource-drawer", path: "/resources?type=security_group", click: "tr.clickable", fullPage: false },
  { name: "setup", path: "/setup" },
];

const browser = await chromium.launch();
try {
  for (const lang of langs) {
    const suffix = lang === "en" ? "" : `.${lang}`;
    for (const theme of ["light", "dark"]) {
      const page = await browser.newPage({ viewport: { width: 1360, height: 900 }, deviceScaleFactor: 2 });
      await page.addInitScript(
        ([t, l]) => {
          window.localStorage.setItem("awsglance-theme", t);
          window.localStorage.setItem("awsglance-lang", l);
        },
        [theme, lang],
      );
      for (const s of shots) {
        await page.goto(base + s.path, { waitUntil: "networkidle" });
        if (s.click) {
          await page.locator(s.click).first().click();
          await page.waitForLoadState("networkidle");
        }
        const file = join(out, `${s.name}${theme === "dark" ? "-dark" : ""}${suffix}.png`);
        await page.screenshot({ path: file, fullPage: s.fullPage ?? true });
        console.log(file);
      }
      await page.close();
    }
    // 900px 이하 반응형
    const narrow = await browser.newPage({ viewport: { width: 420, height: 900 }, deviceScaleFactor: 2 });
    await narrow.addInitScript((l) => window.localStorage.setItem("awsglance-lang", l), lang);
    await narrow.goto(base + "/", { waitUntil: "networkidle" });
    const file = join(out, `overview-mobile${suffix}.png`);
    await narrow.screenshot({ path: file, fullPage: true });
    console.log(file);
    await narrow.close();
  }
} finally {
  await browser.close();
}
