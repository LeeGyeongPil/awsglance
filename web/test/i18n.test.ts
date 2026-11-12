// 화면 문구 표 검사 — node 로 i18n.ts 를 그대로 실행한다(React·브라우저 필요 없음): npm test
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  ago,
  detectLang,
  errorText,
  eventReason,
  findingDetail,
  fmtTime,
  makeTranslator,
  MESSAGES,
  missingKeys,
  permLabel,
  ruleText,
  trustReason,
} from "../src/i18n.ts";

const en = makeTranslator("en");
const ko = makeTranslator("ko");
const HANGUL = /[가-힣]/;

test("en and ko tables have exactly the same keys", () => {
  const missing = missingKeys();
  assert.deepEqual(missing.en, [], "keys only in ko");
  assert.deepEqual(missing.ko, [], "keys only in en");
});

test("every message uses the same {placeholders} in both languages", () => {
  const names = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
  for (const key of Object.keys(MESSAGES.ko)) {
    assert.deepEqual(names(MESSAGES.ko[key] ?? ""), names(MESSAGES.en[key] ?? ""), key);
  }
});

test("English table has no Hangul and Korean table translates everything", () => {
  for (const [key, text] of Object.entries(MESSAGES.en)) {
    if (key === "lang.ko") continue; // 언어 이름은 자기 언어로 보여 준다
    assert.ok(!HANGUL.test(text), `Hangul in en: ${key}`);
  }
  assert.ok(HANGUL.test(MESSAGES.ko["nav.overview"] ?? ""));
});

test("first-run language: saved choice wins, browser language only when nothing is saved", () => {
  assert.equal(detectLang(null, "ko-KR"), "ko");
  assert.equal(detectLang(null, "en-US"), "en");
  assert.equal(detectLang(null, "fr"), "en");
  assert.equal(detectLang("en", "ko-KR"), "en");
  assert.equal(detectLang("ko", "en-US"), "ko");
  assert.equal(detectLang("zz", "ko"), "ko"); // 알 수 없는 저장값은 무시
});

test("translator fills params, falls back to the key, and keeps unknown placeholders", () => {
  assert.equal(en("ov.last_collect", { time: "T", ago: "A" }), "Last collected T (A)");
  assert.equal(ko("ov.last_collect", { time: "T", ago: "A" }), "마지막 수집 T (A)");
  assert.equal(en("no.such.key"), "no.such.key");
  assert.equal(en("fi.reopened_times", { count: 1 }), "Reopened 1 time");
  assert.equal(en("fi.reopened_times", { count: 3 }), "Reopened 3 times");
});

test("findings render from rule id + params in each language; old rows show the stored text", () => {
  const f = { rule_id: "iam-key-old", detail: "stored 한국어 문장", params: { name: "demo-admin", days: 121 } };
  assert.equal(en.has("finding.iam-key-old"), true);
  assert.equal(findingDetail(en, f), "demo-admin: active access key not rotated for 121 days");
  assert.equal(findingDetail(ko, f), "demo-admin: 활성 액세스 키가 121일째 교체되지 않음");
  assert.equal(findingDetail(en, { rule_id: "iam-key-old", detail: "stored 한국어 문장", params: null }), "stored 한국어 문장");
  const trail = { rule_id: "trail-tampering", detail: "x", params: { actor: "mallory", trail: "main", name: "StopLogging", denied: true, error_code: "AccessDenied", time: "2026-11-10T01:02:03+00:00" } };
  assert.match(findingDetail(en, trail), /tried StopLogging on trail main but was denied \(AccessDenied\)/);
  assert.match(findingDetail(ko, trail), /시도했으나 거부됨\(AccessDenied\)/);
  const posture = { rule_id: "posture-off", detail: "x", params: { feature: "guardduty", region: "global" } };
  assert.equal(findingDetail(en, posture), "GuardDuty (threat detection) is off — whole account");
  assert.equal(findingDetail(ko, posture), "GuardDuty(위협 탐지) 꺼짐 — 계정 전체");
});

test("rule texts, trust reasons, event reasons, permission labels and API errors translate", () => {
  assert.equal(ruleText(en, "rds-public", "title", "fallback"), "Publicly accessible RDS database");
  assert.equal(ruleText(ko, "rds-public", "title", "fallback"), "공개 접근 가능한 RDS 데이터베이스");
  assert.equal(ruleText(en, "future-rule", "title", "server text"), "server text");
  const trust = { reason: "high 2건 — x", code: "top_finding", params: { severity: "high", count: 2, rule_id: "rds-public", title: "x" } };
  assert.equal(trustReason(en, trust), "2 High — Publicly accessible RDS database");
  assert.equal(trustReason(ko, trust), "높음 2건 — 공개 접근 가능한 RDS 데이터베이스");
  assert.equal(trustReason(en, { reason: "old text" }), "old text");
  assert.equal(eventReason(en, { reason: "루트 사용자", reason_code: "root", reason_params: {} }), "Root user");
  assert.equal(eventReason(ko, { reason: "설정: 사람 역할(x)", reason_code: "config_human_role", reason_params: { role: "x" } }), "설정: 사람 역할(x)");
  assert.equal(eventReason(en, { reason: "미지의 문장", reason_code: null }), "미지의 문장");
  assert.equal(permLabel(en, "s3", "원문"), "S3 bucket list");
  assert.equal(permLabel(en, "new_collector", "원문"), "원문");
  assert.equal(errorText(en, { code: "days_out_of_range", params: { max: 30 }, message: "days_must_be_1_to_30" }), "Days must be between 1 and 30.");
  assert.equal(errorText(ko, { code: "days_out_of_range", params: { max: 30 }, message: "x" }), "기한은 1~30일이어야 합니다.");
  assert.equal(errorText(en, { code: null, params: {}, message: "502" }), "Server answered 502.");
  assert.equal(errorText(en, { code: "mystery", params: {}, message: "raw message" }), "raw message");
});

test("dates and relative times follow the language", () => {
  const iso = "2026-11-12T08:13:00+00:00";
  assert.notEqual(fmtTime("en", iso), fmtTime("ko", iso));
  assert.match(fmtTime("en", iso), /2026/);
  assert.equal(fmtTime("en", null), "—");
  assert.equal(fmtTime("ko", "not a date"), "not a date");
  const now = Date.parse("2026-11-12T09:13:00+00:00");
  assert.equal(ago("en", iso, now), "1 hour ago");
  assert.equal(ago("ko", iso, now), "1시간 전");
  assert.equal(ago("en", iso, Date.parse(iso) + 5_000), "just now");
  assert.equal(ago("ko", iso, Date.parse(iso) + 5_000), "방금");
});

test("English finding sentences use the singular for a count of 1", () => {
  const t = makeTranslator("en");
  const detail = (rule_id: string, count: number) =>
    findingDetail(t, { rule_id, detail: "stored", params: { count, names: "root", time: "2026-01-01T00:00:00Z", actor: "alice", id: "sg-1" } } as never);
  assert.match(detail("root-activity", 1), /^1 root user action in/);
  assert.match(detail("root-activity", 3), /^3 root user actions in/);
  assert.match(detail("console-login-failed", 1), /1 failed console login /);
  assert.match(detail("sg-default-has-rules", 1), /has 1 inbound rule$/);
});

test("sg-open-world uses singular for one port, with or without a stored count", () => {
  const t = makeTranslator("en");
  const row = (params: Record<string, unknown>) => findingDetail(t, { rule_id: "sg-open-world", detail: "stored", params } as never);
  assert.match(row({ name: "web", id: "sg-1", ports: "22(SSH)", count: 1 }), /: port 22\(SSH\) is open to/);
  assert.match(row({ name: "web", id: "sg-1", ports: "22(SSH)" }), /: port 22\(SSH\) is open to/);
  assert.match(row({ name: "web", id: "sg-1", ports: "22(SSH), 3389(RDP)", count: 2 }), /: ports 22\(SSH\), 3389\(RDP\) are open to/);
  assert.match(row({ name: "web", id: "sg-1", ports: "22(SSH), 3389(RDP)" }), /: ports 22/);
});
