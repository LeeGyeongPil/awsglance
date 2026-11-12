// pytest 가 부르는 점검 스크립트: 연습 모드 API 응답(JSON 파일)을 두 언어로 화면 문구로 바꿔 보고 결과를 JSON 으로 출력한다.
//   node --experimental-strip-types test/render-check.ts <api.json>
import { readFileSync } from "node:fs";
import { eventReason, findingDetail, makeTranslator, permLabel, ruleText, trustReason, type Lang } from "../src/i18n.ts";

const api = JSON.parse(readFileSync(process.argv[2] ?? "", "utf-8")) as Record<string, any>;
const out: Record<string, unknown> = {};
for (const lang of ["en", "ko"] as Lang[]) {
  const t = makeTranslator(lang);
  const findings = (api["/api/findings?status=all&severity=&rule="]?.items ?? []) as any[];
  out[lang] = {
    findings: findings.map((f) => ({ rule: f.rule_id, hasParams: Boolean(f.params), title: ruleText(t, f.rule_id, "title", f.title), detail: findingDetail(t, f) })),
    rules: ((api["/api/rules"] ?? []) as any[]).map((r) => ({
      id: r.id,
      title: ruleText(t, r.id, "title", r.title),
      description: ruleText(t, r.id, "description", r.description),
      remediation: ruleText(t, r.id, "remediation", r.remediation),
    })),
    trust: trustReason(t, api["/api/status"].trust),
    events: ((api["/api/changes?tab=all&q=&days=14&noise=false"]?.events ?? []) as any[]).map((e) => eventReason(t, e)),
    perms: ((api["/api/setup"]?.permissions ?? []) as any[]).map((p) => permLabel(t, p.collector, p.label)),
  };
}
process.stdout.write(JSON.stringify(out));
