// 화면 문구 표(영어·한국어)와 순수 도우미. React 에 기대지 않아서 node 로 그대로 돌려 볼 수 있다(web/test).
// - 문구는 이 파일 한 곳에만 둔다. 두 언어의 키가 같은지는 테스트가 확인한다.
// - 번역 함수 이름은 항상 `t` — 다른 곳에서 지역 변수 `t` 로 가리지 않는다.
// - 번역하지 않는 것: AWS 리소스 이름·ARN·리전·API/이벤트 이름·심각도 값(critical 등)·JSON 키.

export type Lang = "en" | "ko";
export const LANGS: Lang[] = ["en", "ko"];
export const LANG_STORAGE_KEY = "awsglance-lang";

export type Params = Record<string, string | number | boolean | null | undefined>;

export interface Translator {
  (key: string, params?: Params): string;
  has: (key: string) => boolean;
  lang: Lang;
}

type Table = Record<string, string>;

const en: Table = {
  // ---- 틀·머리글 ----
  "app.nav_label": "Screens",
  "nav.overview": "Overview",
  "nav.resources": "Resources",
  "nav.changes": "Changes",
  "nav.findings": "Findings",
  "nav.setup": "Connection",
  "app.demo_banner": "Example account (practice mode) — mock data for the fictional AWS account {account}. No AWS calls are made.",
  "app.not_found": "Screen not found",
  "app.go_overview": "Back to the overview",
  "app.collecting": "collecting ({job})",
  "app.collected": "collected {ago}",
  "app.last_inventory": "Last inventory collection",
  "app.theme_to_light": "Switch to the light theme",
  "app.theme_to_dark": "Switch to the dark theme",
  "app.theme_title": "Change theme",
  "app.footer": "awsglance {version} · read-only (AWS actions outside the allow-list are blocked in code) · not an official AWS tool",
  "lang.label": "Language",
  "lang.en": "English",
  "lang.ko": "한국어",

  // ---- 공통 ----
  "common.loading": "Loading…",
  "common.load_failed": "Could not load: {message}",
  "common.retry": "Try again",
  "common.close": "Close",
  "common.all": "All",
  "common.none": "None",
  "common.no_data": "no data",
  "common.search": "Search",
  "common.find": "Find",
  "common.count_items": "{count} items",
  "common.count_items.one": "1 item",

  // ---- 심각도·주체·신뢰 신호 ----
  "sev.critical": "Critical",
  "sev.high": "High",
  "sev.medium": "Medium",
  "sev.low": "Low",
  "sev.title": "Severity: {label}",
  "actor.human": "Human",
  "actor.automated": "Automated",
  "actor.unknown": "Undetermined",
  "trust.ok": "OK",
  "trust.warn": "Caution",
  "trust.danger": "Danger",
  "trust.unknown": "Undetermined",
  "trust.reason.never_collected": "Nothing has been collected yet",
  "trust.reason.stale": "Last collection was {hours} hours ago — check credentials and permissions",
  "trust.reason.no_open_findings": "No open findings",
  "trust.reason.top_finding": "{count} {severity} — {title}",

  // ---- 자원 종류·보안 기능 ----
  "type.ec2_instance": "EC2 instance",
  "type.vpc": "VPC",
  "type.subnet": "Subnet",
  "type.security_group": "Security group",
  "type.rds_instance": "RDS DB",
  "type.lambda_function": "Lambda function",
  "type.load_balancer": "Load balancer",
  "type.log_group": "Log group",
  "type.s3_bucket": "S3 bucket",
  "type.iam_user": "IAM user",
  "type.iam_access_key": "Access key",
  "type.iam_role": "IAM role",
  "feature.guardduty": "GuardDuty",
  "feature.securityhub": "Security Hub",
  "feature.config": "AWS Config",
  "feature.accessanalyzer": "Access Analyzer",
  "feature.cloudtrail_multi_region": "Multi-region trail",
  "feature.s3_account_public_access_block": "Account S3 public access block",
  "feature_long.guardduty": "GuardDuty (threat detection)",
  "feature_long.securityhub": "Security Hub (check aggregation)",
  "feature_long.config": "AWS Config (configuration recording)",
  "feature_long.accessanalyzer": "IAM Access Analyzer (external sharing detection)",
  "feature_long.cloudtrail_multi_region": "Multi-region CloudTrail trail (keeps history beyond 90 days)",
  "feature_long.s3_account_public_access_block": "Account-level S3 public access block",
  "posture.state.on": "✓ On",
  "posture.state.off": "✕ Off",
  "posture.state.denied": "? No permission",
  "posture.state.error": "? Error",
  "posture.empty": "Security posture has not been collected yet.",
  "posture.feature": "Feature",
  "posture.account": "Whole account",

  // ---- 차트 ----
  "chart.aria": "CloudTrail write events over the last 14 days",
  "chart.tooltip": "{date} — human {human}, automated {automated}, undetermined {unknown}, snapshot changes {changes}",

  // ---- 개요 ----
  "ov.last_collect": "Last collected {time} ({ago})",
  "ov.check_now": "What to check now",
  "ov.no_findings": "There are no open findings.",
  "ov.all_findings": "See all findings →",
  "ov.last_24h": "Last 24 hours",
  "ov.new": "new findings",
  "ov.reopened": "reopened",
  "ov.resolved": "resolved",
  "ov.human_changes": "changes made by people",
  "ov.kpi_resources": "Resources",
  "ov.kpi_events": "Write events (24h)",
  "ov.kpi_changes": "Resource changes (24h)",
  "ov.kpi_open": "Open findings",
  "ov.bars_title": "Changes in the last 14 days",
  "ov.bars_note": "CloudTrail write events stacked by caller (human, automated, undetermined). Hover a bar to see the number of resource changes found by comparing snapshots.",
  "ov.posture_title": "Security features × region",
  "ov.posture_note": "'No permission' does not mean off — it means we cannot tell (check permissions on the Connection screen).",

  // ---- 연결 ----
  "setup.title": "Connection check",
  "setup.step1": "1. Connected account",
  "setup.account_id": "Account ID",
  "setup.principal": "Principal (ARN)",
  "setup.regions": "Regions",
  "setup.no_identity": "No connection information yet.",
  "setup.creds_note": "awsglance uses your standard AWS credentials (environment variables, `AWS_PROFILE`, SSO, roles) as they are, and can only call read actions.",
  "setup.step2": "2. Permission check",
  "setup.step2_note": "Result of calling one representative read action per collector. Checked at {time}",
  "setup.col_collector": "Collector",
  "setup.col_action": "Action",
  "setup.col_result": "Result",
  "setup.col_meaning": "Meaning",
  "setup.step3": "3. If permissions are missing",
  "setup.denied_count": "{count} collectors were denied. ",
  "setup.denied_count.one": "1 collector was denied. ",
  "setup.policy_intro": "Attach the minimal IAM policy below (a list of read actions, generated from the same source as this program's allow-list) to your user or role, or attach the AWS managed policies",
  "setup.policy_outro": "together.",
  "setup.copy": "Copy minimal IAM policy",
  "setup.copied": "Copied",
  "setup.terminal_hint": "In a terminal: `awsglance policy`",
  "setup.go_overview": "Back to the overview →",
  "perm.allowed": "✓ Allowed",
  "perm.denied": "✕ Denied",
  "perm.unavailable": "– Unavailable",
  "perm.error": "? Error",
  "perm.blocked": "⛔ Blocked in code",
  "perm.help.allowed": "Read permission is in place.",
  "perm.help.denied": "The IAM permission is missing. Attaching the minimal policy below fixes it.",
  "perm.help.unavailable": "Not a permission problem: the feature is off or needs a subscription. You can keep using awsglance.",
  "perm.help.error": "May be temporary. Run it again.",
  "perm.help.blocked": "The action is outside the allow-list, so the program blocked it itself.",
  "perm.label.connection": "Account connection (GetCallerIdentity)",
  "perm.label.ec2": "EC2, VPC, subnets, security groups",
  "perm.label.s3": "S3 bucket list",
  "perm.label.iam": "IAM users, access keys, roles",
  "perm.label.rds": "RDS databases",
  "perm.label.lambda": "Lambda functions",
  "perm.label.elbv2": "Load balancers",
  "perm.label.logs": "CloudWatch log groups",
  "perm.label.cloudtrail": "CloudTrail history (LookupEvents)",
  "perm.label.trails": "CloudTrail trail settings",
  "perm.label.s3_account": "Account-level S3 public access block",

  // ---- 변경 이력 ----
  "ch.title": "Changes",
  "ch.period": "Period",
  "ch.days_1": "1 day",
  "ch.days_7": "7 days",
  "ch.days_14": "14 days",
  "ch.days_30": "30 days",
  "ch.days_90": "90 days",
  "ch.search_ph": "action, principal, resource",
  "ch.events_title": "CloudTrail write events",
  "ch.tab_human": "Done by people",
  "ch.tab_automated": "Automated",
  "ch.tab_unknown": "Undetermined",
  "ch.tab_all": "All",
  "ch.no_events": "No events in this period.",
  "ch.unknown_help": "Undetermined calls cannot be split into human or automated by role name alone. Add role-name patterns to `[classify]` in the `config.toml` settings file to classify them.",
  "ch.root": "■ Root",
  "ch.failed": "Failed: {code}",
  "ch.reason": "Classified because",
  "ch.region": "region",
  "ch.source": "source",
  "ch.redacted": "Request parameters had secret-looking values replaced with *** before saving.",
  "ch.res_title": "Resource changes (snapshot comparison)",
  "ch.res_note": "Result of comparing two inventory collections. Catches changes that CloudTrail missed.",
  "ch.show_noise": "Also show time-only changes (noise)",
  "ch.no_res_changes": "No resource changes.",
  "ch.noise": "(noise)",
  "ch.kind_created": "+ Created",
  "ch.kind_deleted": "− Deleted",
  "ch.kind_modified": "~ Modified",
  "ch.summary_created": "{type} {name} created",
  "ch.summary_deleted": "{type} {name} deleted",
  "ch.summary_modified": "{type} {name} modified",

  // ---- 문제(발견 사항) ----
  "fi.title": "Findings",
  "fi.drawer_default": "Finding",
  "fi.status_open": "Open",
  "fi.status_suppressed": "Suppressed",
  "fi.status_resolved": "Resolved",
  "fi.status_closed": "Closed",
  "fi.severity": "Severity",
  "fi.rule_chip": "Rule",
  "fi.clear_rule": "Clear rule filter",
  "fi.view": "View",
  "fi.view_group": "Grouped by rule",
  "fi.view_list": "Flat list",
  "fi.empty": "No findings match these filters.",
  "fi.reopened_times": "Reopened {count} times",
  "fi.reopened_times.one": "Reopened 1 time",
  "fi.resource": "Resource",
  "fi.first_seen": "First seen",
  "fi.last_seen": "Last checked",
  "fi.suppress_until": "Suppressed until",
  "fi.why": "Why it matters",
  "fi.how": "How to fix",
  "fi.rule_id": "Rule {id}",
  "fi.history": "History",
  "fi.reopen": "Reopen",
  "fi.critical_note": "Critical findings cannot be suppressed. After checking, use 'Close' to record why.",
  "fi.suppress_h": "Suppress",
  "fi.suppress_reason": "Reason (required)",
  "fi.suppress_reason_ph": "e.g. a public web server, so this is intended",
  "fi.suppress_days": "Days (max {max})",
  "fi.suppress_btn": "Suppress",
  "fi.close_h": "Close",
  "fi.close_reason_label": "Reason for closing",
  "fi.close_btn": "Close",
  "fi.close_fixed": "Fixed",
  "fi.close_false_positive": "False positive",
  "fi.close_accepted": "Risk accepted",
  "fi.action_failed": "Could not complete the action: {message}",
  "fi.action.opened": "First found",
  "fi.action.reopened": "Reopened",
  "fi.action.resolved": "Resolved (no longer seen)",
  "fi.action.suppressed": "Suppressed",
  "fi.action.suppress_expired": "Suppression expired",
  "fi.action.closed": "Closed",
  "fi.action.reopened_by_user": "Reopened by you",

  // ---- 자원 ----
  "re.title": "Resources",
  "re.type": "Type",
  "re.region": "Region",
  "re.search_ph": "name, ID, tag",
  "re.empty": "No resources match these filters.",
  "re.col_type": "Type",
  "re.col_name": "Name",
  "re.col_region": "Region",
  "re.col_findings": "Findings",
  "re.col_first_seen": "First seen",
  "re.total": "{count} total",
  "re.drawer_default": "Resource",
  "re.first_seen": "First seen",
  "re.deleted": "Deleted",
  "re.props": "Properties",
  "re.tags": "Tags",
  "re.findings_h": "Findings ({count})",
  "re.none": "None",
  "re.changes_h": "Snapshot change history ({count})",
  "re.no_changes": "Nothing has changed since the baseline.",
  "re.events_h": "Related CloudTrail ({count})",
  "re.events_h_plain": "Related CloudTrail",
  "re.events_unsupported": "This type cannot be matched exactly to CloudTrail events, so it is not linked. Use the search on the Changes screen.",
  "re.events_note": "Only events with exactly the same ID or ARN are shown. For a wider search, use the search on the Changes screen.",
  "re.no_events": "No related events.",

  // ---- 분류 근거(CloudTrail 호출 주체) ----
  "reason.aws_service": "Call made by an AWS service",
  "reason.root": "Root user",
  "reason.iam_user": "IAM user",
  "reason.service_linked_role": "Service-linked role",
  "reason.sso_user": "SSO user",
  "reason.console_session": "Console session",
  "reason.exec_env": "Lambda/ECS execution role",
  "reason.role_name_unclear": "Cannot tell from the role name alone",
  "reason.federated_user": "Federated user",
  "reason.unknown_kind": "Unknown principal type",
  "reason.config_human_role": "Setting: human role ({role})",
  "reason.config_automated_role": "Setting: automated role ({role})",
  "reason.pipeline_name_pattern": "Pipeline name pattern ({role})",

  // ---- 서버 오류 코드 ----
  "error.not_found": "Not found.",
  "error.reason_required": "A reason is required.",
  "error.critical_cannot_be_suppressed": "Critical findings cannot be suppressed.",
  "error.only_open_can_be_suppressed": "Only open findings can be suppressed.",
  "error.days_out_of_range": "Days must be between 1 and {max}.",
  "error.reason_must_be_false_positive_fixed_or_accepted": "Pick one of: fixed, false positive, risk accepted.",
  "error.invalid_body": "The request body was not valid.",
  "error.resource_not_found": "Resource not found.",
  "error.finding_not_found": "Finding not found.",
  "error.collect_unavailable": "Collection is not running in this mode (practice mode).",
  "error.no_such_api": "No such API.",
  "error.export_missing": "This screen is not in the exported copy (run the server to see everything).",
  "error.export_readonly": "The exported copy is read-only.",
  "error.http_status": "Server answered {status}.",

  // ---- 규칙 제목·설명·대응(rule id 별) ----
  "rule.sg-open-world.title": "Security group with sensitive ports open to the whole internet",
  "rule.sg-open-world.description": "If SSH (22), RDP (3389) or database ports are open to 0.0.0.0/0 or ::/0, scanners around the world will try to connect right away.",
  "rule.sg-open-world.remediation": "Narrow the source of the inbound rule to your IP, a corporate range or another security group. Session Manager can replace remote access.",
  "rule.sg-default-has-rules.title": "Default security group has inbound rules",
  "rule.sg-default-has-rules.description": "The default security group is easily attached to new resources by accident. If it has rules, things get opened unintentionally.",
  "rule.sg-default-has-rules.remediation": "Delete the inbound rules of the default security group and create separate security groups per purpose.",
  "rule.rds-public.title": "Publicly accessible RDS database",
  "rule.rds-public.description": "With PubliclyAccessible=true the database endpoint can be reached from the internet (the security group is the last line of defense).",
  "rule.rds-public.remediation": "Modify the DB instance to turn off 'publicly accessible' and connect only from inside the same VPC as your application.",
  "rule.s3-bucket-pab-off.title": "S3 bucket with public access block turned off",
  "rule.s3-bucket-pab-off.description": "A single mistake in a bucket policy or ACL can make objects public.",
  "rule.s3-bucket-pab-off.remediation": "The simplest fix is to turn on the account-level S3 public access block. Serve only buckets that must be public through CloudFront.",
  "rule.lambda-url-no-auth.title": "Lambda function URL without authentication",
  "rule.lambda-url-no-auth.description": "A function URL with AuthType=NONE can be called by anyone who knows the address (cost and data exposure).",
  "rule.lambda-url-no-auth.remediation": "Unless it is an intended public API, change AuthType to AWS_IAM or move it behind API Gateway.",
  "rule.logs-no-retention.title": "Log group without a retention period",
  "rule.logs-no-retention.description": "Without a retention period, logs are kept forever and storage costs keep growing.",
  "rule.logs-no-retention.remediation": "Set a retention period on the log group (for example 30 or 90 days).",
  "rule.iam-key-old.title": "Access key not rotated for over 90 days",
  "rule.iam-key-old.description": "A long-lived key does more damage for longer if it leaks.",
  "rule.iam-key-old.remediation": "Create a new key, swap it in, then deactivate and delete the old one. Where possible, move to SSO or role-based temporary credentials.",
  "rule.root-activity.title": "Root user activity",
  "rule.root-activity.description": "The root user has every permission. Apart from a few tasks such as billing and account settings, it should not be used.",
  "rule.root-activity.remediation": "Check whether it was you. If not, change the root password right away and verify MFA. Do everyday work as an IAM Identity Center user.",
  "rule.trail-tampering.title": "CloudTrail trail stopped, deleted or changed",
  "rule.trail-tampering.description": "Attackers turn off trail logging first to erase their tracks. Attempts that failed for lack of permission are shown too.",
  "rule.trail-tampering.remediation": "Find out who did it. If the change was not intended, turn logging back on and revoke that principal's credentials.",
  "rule.console-login-failed.title": "Failed console login",
  "rule.console-login-failed.description": "Repeated login failures for the same user may be password guessing.",
  "rule.console-login-failed.remediation": "Check whether it was a user mistake; if it repeats, consider a password change and enforcing MFA.",
  "rule.sg-opened-world-event.title": "Change that opened a security group to the whole internet",
  "rule.sg-opened-world-event.description": "A record of AuthorizeSecurityGroupIngress allowing 0.0.0.0/0. Opening something temporarily and forgetting it is common.",
  "rule.sg-opened-world-event.remediation": "Ask the operator whether the change was needed; if not, delete that inbound rule.",
  "rule.posture-off.title": "Security features that are turned off",
  "rule.posture-off.description": "GuardDuty, Security Hub, Config, Access Analyzer, a multi-region trail and the account S3 public access block are the basic tools for noticing incidents early and tracing causes later.",
  "rule.posture-off.remediation": "Turn the feature on in the console of that region. If cost is a concern, start with GuardDuty, Access Analyzer (free tier) and the account S3 public access block (free).",

  // ---- 발견 사항 한 줄 설명(rule id + params) ----
  "finding.sg-open-world": "{name} ({id}): ports {ports} are open to the whole internet (0.0.0.0/0)",
  "finding.sg-open-world.one": "{name} ({id}): port {ports} is open to the whole internet (0.0.0.0/0)",
  "finding.sg-default-has-rules": "Default security group ({id}) has {count} inbound rules",
  "finding.sg-default-has-rules.one": "Default security group ({id}) has 1 inbound rule",
  "finding.rds-public": "{name} ({engine}) is set to publicly accessible",
  "finding.s3-bucket-pab-off": "Public access block is off for bucket {name} (and there is no account-level block)",
  "finding.lambda-url-no-auth": "The function URL of {name} is open without authentication (AuthType=NONE)",
  "finding.logs-no-retention": "Log group {name} has a retention period of 'forever' (not set)",
  "finding.iam-key-old": "{name}: active access key not rotated for {days} days",
  "finding.root-activity": "{count} root user actions in the last 7 days: {names} (last at {time})",
  "finding.root-activity.one": "1 root user action in the last 7 days: {names} (last at {time})",
  "finding.trail-tampering.done": "{actor} ran {name} on trail {trail} ({time})",
  "finding.trail-tampering.denied": "{actor} tried {name} on trail {trail} but was denied ({error_code}) ({time})",
  "finding.console-login-failed": "{actor}: {count} failed console logins (last at {time})",
  "finding.console-login-failed.one": "{actor}: 1 failed console login (last at {time})",
  "finding.sg-opened-world-event": "{actor} ({actor_class}, {via}) opened inbound of {group} to the whole internet ({time})",
  "finding.posture-off": "{feature} is off — {where}",
  "finding.posture_global": "whole account",

  // ---- 시간 ----
  "time.just_now": "just now",
};

const ko: Table = {
  "app.nav_label": "화면",
  "nav.overview": "개요",
  "nav.resources": "자원",
  "nav.changes": "변경 이력",
  "nav.findings": "문제",
  "nav.setup": "연결",
  "app.demo_banner": "예제 계정(연습 모드) — 가상의 AWS 계정 {account} 의 mock 데이터입니다. AWS 를 호출하지 않습니다.",
  "app.not_found": "없는 화면입니다",
  "app.go_overview": "개요로 가기",
  "app.collecting": "수집 중({job})",
  "app.collected": "수집 {ago}",
  "app.last_inventory": "마지막 인벤토리 수집",
  "app.theme_to_light": "밝은 테마로",
  "app.theme_to_dark": "어두운 테마로",
  "app.theme_title": "테마 바꾸기",
  "app.footer": "awsglance {version} · 읽기 전용(허용 목록 밖 AWS 작업은 코드에서 차단) · 이 도구는 AWS 공식 도구가 아닙니다",
  "lang.label": "언어",
  "lang.en": "English",
  "lang.ko": "한국어",

  "common.loading": "불러오는 중…",
  "common.load_failed": "불러오지 못했습니다: {message}",
  "common.retry": "다시 시도",
  "common.close": "닫기",
  "common.all": "전체",
  "common.none": "없음",
  "common.no_data": "데이터 없음",
  "common.search": "검색",
  "common.find": "찾기",
  "common.count_items": "{count}개",

  "sev.critical": "치명",
  "sev.high": "높음",
  "sev.medium": "보통",
  "sev.low": "낮음",
  "sev.title": "심각도: {label}",
  "actor.human": "사람",
  "actor.automated": "자동",
  "actor.unknown": "판단 보류",
  "trust.ok": "정상",
  "trust.warn": "주의",
  "trust.danger": "위험",
  "trust.unknown": "판단 보류",
  "trust.reason.never_collected": "아직 수집한 적이 없음",
  "trust.reason.stale": "마지막 수집이 {hours}시간 전 — 자격증명·권한 확인",
  "trust.reason.no_open_findings": "열린 문제 없음",
  "trust.reason.top_finding": "{severity} {count}건 — {title}",

  "type.ec2_instance": "EC2 인스턴스",
  "type.vpc": "VPC",
  "type.subnet": "서브넷",
  "type.security_group": "보안 그룹",
  "type.rds_instance": "RDS DB",
  "type.lambda_function": "Lambda 함수",
  "type.load_balancer": "로드 밸런서",
  "type.log_group": "로그 그룹",
  "type.s3_bucket": "S3 버킷",
  "type.iam_user": "IAM 사용자",
  "type.iam_access_key": "액세스 키",
  "type.iam_role": "IAM 역할",
  "feature.guardduty": "GuardDuty",
  "feature.securityhub": "Security Hub",
  "feature.config": "AWS Config",
  "feature.accessanalyzer": "Access Analyzer",
  "feature.cloudtrail_multi_region": "다중 리전 트레일",
  "feature.s3_account_public_access_block": "계정 S3 공개 차단",
  "feature_long.guardduty": "GuardDuty(위협 탐지)",
  "feature_long.securityhub": "Security Hub(점검 모음)",
  "feature_long.config": "AWS Config(설정 기록)",
  "feature_long.accessanalyzer": "IAM Access Analyzer(외부 공유 탐지)",
  "feature_long.cloudtrail_multi_region": "다중 리전 CloudTrail 트레일(90일 넘는 기록 보관)",
  "feature_long.s3_account_public_access_block": "계정 수준 S3 퍼블릭 액세스 차단",
  "posture.state.on": "✓ 켜짐",
  "posture.state.off": "✕ 꺼짐",
  "posture.state.denied": "? 권한 없음",
  "posture.state.error": "? 오류",
  "posture.empty": "아직 보안 태세를 수집하지 않았습니다.",
  "posture.feature": "기능",
  "posture.account": "계정 전체",

  "chart.aria": "최근 14일 CloudTrail 쓰기 이벤트 수",
  "chart.tooltip": "{date} — 사람 {human}, 자동 {automated}, 판단 보류 {unknown}, 스냅샷 변경 {changes}",

  "ov.last_collect": "마지막 수집 {time} ({ago})",
  "ov.check_now": "지금 확인할 것",
  "ov.no_findings": "열린 문제가 없습니다.",
  "ov.all_findings": "문제 전체 보기 →",
  "ov.last_24h": "최근 24시간",
  "ov.new": "새 문제",
  "ov.reopened": "재발",
  "ov.resolved": "해결",
  "ov.human_changes": "사람이 한 변경",
  "ov.kpi_resources": "자원",
  "ov.kpi_events": "24시간 쓰기 이벤트",
  "ov.kpi_changes": "24시간 자원 변경",
  "ov.kpi_open": "열린 문제",
  "ov.bars_title": "최근 14일 변경",
  "ov.bars_note": "CloudTrail 의 쓰기 이벤트를 호출 주체(사람·자동·판단 보류)별로 쌓았습니다. 막대에 마우스를 올리면 스냅샷 비교로 찾은 자원 변경 수도 보입니다.",
  "ov.posture_title": "보안 기능 × 리전",
  "ov.posture_note": "'권한 없음'은 꺼짐이 아니라 확인할 수 없다는 뜻입니다(연결 화면에서 권한을 확인하세요).",

  "setup.title": "연결 확인",
  "setup.step1": "1. 연결된 계정",
  "setup.account_id": "계정 ID",
  "setup.principal": "주체(ARN)",
  "setup.regions": "리전",
  "setup.no_identity": "아직 연결 정보가 없습니다.",
  "setup.creds_note": "awsglance 는 표준 AWS 자격증명(환경 변수·`AWS_PROFILE`·SSO·역할)을 그대로 쓰며, 읽기 작업만 부를 수 있습니다.",
  "setup.step2": "2. 권한 점검",
  "setup.step2_note": "수집기마다 대표 읽기 작업을 한 번씩 불러 본 결과입니다. 점검 시각 {time}",
  "setup.col_collector": "수집기",
  "setup.col_action": "작업",
  "setup.col_result": "결과",
  "setup.col_meaning": "의미",
  "setup.step3": "3. 권한이 모자라면",
  "setup.denied_count": "거부된 수집기가 {count}개 있습니다. ",
  "setup.policy_intro": "아래 최소 IAM 정책(읽기 작업 목록, 이 프로그램의 허용 목록과 같은 원천에서 생성)을 사용자·역할에 붙이거나, AWS 관리형 정책",
  "setup.policy_outro": "를 함께 붙입니다.",
  "setup.copy": "최소 IAM 정책 복사",
  "setup.copied": "복사했습니다",
  "setup.terminal_hint": "터미널에서는 `awsglance policy`",
  "setup.go_overview": "개요로 가기 →",
  "perm.allowed": "✓ 허용",
  "perm.denied": "✕ 거부",
  "perm.unavailable": "– 사용 불가",
  "perm.error": "? 오류",
  "perm.blocked": "⛔ 코드에서 차단",
  "perm.help.allowed": "읽기 권한이 있습니다.",
  "perm.help.denied": "IAM 권한이 없습니다. 아래 최소 정책을 붙이면 해결됩니다.",
  "perm.help.unavailable": "권한 문제가 아니라 기능이 꺼져 있거나 구독이 필요합니다. 그대로 써도 됩니다.",
  "perm.help.error": "일시적인 오류일 수 있습니다. 다시 실행해 보세요.",
  "perm.help.blocked": "허용 목록 밖 작업이라 프로그램이 스스로 막았습니다.",
  "perm.label.connection": "계정 연결(GetCallerIdentity)",
  "perm.label.ec2": "EC2·VPC·서브넷·보안 그룹",
  "perm.label.s3": "S3 버킷 목록",
  "perm.label.iam": "IAM 사용자·액세스 키·역할",
  "perm.label.rds": "RDS 데이터베이스",
  "perm.label.lambda": "Lambda 함수",
  "perm.label.elbv2": "로드 밸런서",
  "perm.label.logs": "CloudWatch 로그 그룹",
  "perm.label.cloudtrail": "CloudTrail 변경 이력(LookupEvents)",
  "perm.label.trails": "CloudTrail 트레일 설정",
  "perm.label.s3_account": "계정 수준 S3 공개 차단",

  "ch.title": "변경 이력",
  "ch.period": "기간",
  "ch.days_1": "1일",
  "ch.days_7": "7일",
  "ch.days_14": "14일",
  "ch.days_30": "30일",
  "ch.days_90": "90일",
  "ch.search_ph": "작업·주체·자원",
  "ch.events_title": "CloudTrail 쓰기 이벤트",
  "ch.tab_human": "사람이 한 작업",
  "ch.tab_automated": "자동",
  "ch.tab_unknown": "판단 보류",
  "ch.tab_all": "전체",
  "ch.no_events": "이 기간에 해당하는 이벤트가 없습니다.",
  "ch.unknown_help": "판단 보류는 역할 이름만으로 사람·자동을 가를 수 없는 호출입니다. 설정 파일 `config.toml` 의 `[classify]` 에 역할 이름 패턴을 적으면 분류됩니다.",
  "ch.root": "■ 루트",
  "ch.failed": "실패: {code}",
  "ch.reason": "분류 근거",
  "ch.region": "리전",
  "ch.source": "출처",
  "ch.redacted": "요청 파라미터는 저장 전에 비밀값 모양을 *** 로 가렸습니다.",
  "ch.res_title": "자원 변경(스냅샷 비교)",
  "ch.res_note": "두 번의 인벤토리 수집을 비교한 결과입니다. CloudTrail 이 놓친 변경도 결과로 잡습니다.",
  "ch.show_noise": "시각만 바뀐 변경(노이즈)도 보기",
  "ch.no_res_changes": "자원 변경이 없습니다.",
  "ch.noise": "(노이즈)",
  "ch.kind_created": "+ 생성",
  "ch.kind_deleted": "− 삭제",
  "ch.kind_modified": "~ 수정",
  "ch.summary_created": "{type} {name} 생성",
  "ch.summary_deleted": "{type} {name} 삭제",
  "ch.summary_modified": "{type} {name} 수정",

  "fi.title": "문제",
  "fi.drawer_default": "발견 사항",
  "fi.status_open": "열림",
  "fi.status_suppressed": "숨김",
  "fi.status_resolved": "해결",
  "fi.status_closed": "닫힘",
  "fi.severity": "심각도",
  "fi.rule_chip": "규칙",
  "fi.clear_rule": "규칙 필터 지우기",
  "fi.view": "보기",
  "fi.view_group": "규칙별 묶음",
  "fi.view_list": "낱개",
  "fi.empty": "이 조건의 문제가 없습니다.",
  "fi.reopened_times": "재발 {count}회",
  "fi.resource": "자원",
  "fi.first_seen": "처음 발견",
  "fi.last_seen": "마지막 확인",
  "fi.suppress_until": "숨김 기한",
  "fi.why": "왜 문제인가",
  "fi.how": "어떻게 고치나",
  "fi.rule_id": "규칙 {id}",
  "fi.history": "처리 기록",
  "fi.reopen": "다시 열기",
  "fi.critical_note": "치명 심각도는 숨길 수 없습니다. 확인 후 '닫기'로 처리 사유를 남기세요.",
  "fi.suppress_h": "숨기기",
  "fi.suppress_reason": "사유(필수)",
  "fi.suppress_reason_ph": "예: 공개 웹 서버라 의도한 설정",
  "fi.suppress_days": "기한(일, 최대 {max})",
  "fi.suppress_btn": "숨기기",
  "fi.close_h": "닫기",
  "fi.close_reason_label": "닫는 사유",
  "fi.close_btn": "닫기",
  "fi.close_fixed": "처리함",
  "fi.close_false_positive": "오탐",
  "fi.close_accepted": "위험 감수",
  "fi.action_failed": "처리하지 못했습니다: {message}",
  "fi.action.opened": "처음 발견",
  "fi.action.reopened": "재발",
  "fi.action.resolved": "해결(다시 보이지 않음)",
  "fi.action.suppressed": "숨김",
  "fi.action.suppress_expired": "숨김 기한 지남",
  "fi.action.closed": "닫음",
  "fi.action.reopened_by_user": "다시 열기",

  "re.title": "자원",
  "re.type": "종류",
  "re.region": "리전",
  "re.search_ph": "이름·ID·태그",
  "re.empty": "조건에 맞는 자원이 없습니다.",
  "re.col_type": "종류",
  "re.col_name": "이름",
  "re.col_region": "리전",
  "re.col_findings": "문제",
  "re.col_first_seen": "처음 본 때",
  "re.total": "{count}개",
  "re.drawer_default": "자원",
  "re.first_seen": "처음 본 때",
  "re.deleted": "삭제됨",
  "re.props": "속성",
  "re.tags": "태그",
  "re.findings_h": "발견 사항 ({count})",
  "re.none": "없음",
  "re.changes_h": "스냅샷 변경 이력 ({count})",
  "re.no_changes": "기준선 이후 바뀐 것이 없습니다.",
  "re.events_h": "관련 CloudTrail ({count})",
  "re.events_h_plain": "관련 CloudTrail",
  "re.events_unsupported": "이 종류는 CloudTrail 이벤트와 정확히 맞춰 볼 수 없어 연결하지 않습니다. 변경 이력 화면의 검색을 쓰세요.",
  "re.events_note": "ID·ARN 이 정확히 같은 이벤트만 보여 줍니다. 더 넓게 찾으려면 변경 이력 화면의 검색을 쓰세요.",
  "re.no_events": "관련 이벤트가 없습니다.",

  "reason.aws_service": "AWS 서비스 호출",
  "reason.root": "루트 사용자",
  "reason.iam_user": "IAM 사용자",
  "reason.service_linked_role": "서비스 연결 역할",
  "reason.sso_user": "SSO 사용자",
  "reason.console_session": "콘솔 세션",
  "reason.exec_env": "Lambda/ECS 실행 역할",
  "reason.role_name_unclear": "역할 이름만으로 판단 불가",
  "reason.federated_user": "연동 사용자",
  "reason.unknown_kind": "알 수 없는 주체 유형",
  "reason.config_human_role": "설정: 사람 역할({role})",
  "reason.config_automated_role": "설정: 자동 역할({role})",
  "reason.pipeline_name_pattern": "파이프라인 이름 패턴({role})",

  "error.not_found": "찾을 수 없습니다.",
  "error.reason_required": "사유를 적어야 합니다.",
  "error.critical_cannot_be_suppressed": "치명 심각도는 숨길 수 없습니다.",
  "error.only_open_can_be_suppressed": "열린 문제만 숨길 수 있습니다.",
  "error.days_out_of_range": "기한은 1~{max}일이어야 합니다.",
  "error.reason_must_be_false_positive_fixed_or_accepted": "처리함·오탐·위험 감수 중에서 고르세요.",
  "error.invalid_body": "요청 내용이 올바르지 않습니다.",
  "error.resource_not_found": "자원을 찾을 수 없습니다.",
  "error.finding_not_found": "발견 사항을 찾을 수 없습니다.",
  "error.collect_unavailable": "이 모드(연습 모드)에서는 수집이 돌지 않습니다.",
  "error.no_such_api": "없는 API 입니다.",
  "error.export_missing": "내보낸 사본에 없는 화면입니다(서버를 실행하면 모두 볼 수 있습니다).",
  "error.export_readonly": "내보낸 사본에서는 읽기만 됩니다.",
  "error.http_status": "서버가 {status} 로 응답했습니다.",

  "rule.sg-open-world.title": "민감한 포트가 인터넷 전체에 열린 보안 그룹",
  "rule.sg-open-world.description": "SSH(22)·RDP(3389)·DB 포트가 0.0.0.0/0 또는 ::/0 에 열려 있으면 전 세계 스캐너가 곧바로 접속을 시도한다.",
  "rule.sg-open-world.remediation": "인바운드 규칙의 원본을 내 IP·사내 대역·다른 보안 그룹으로 좁힌다. 원격 접속은 Session Manager 로 대신할 수 있다.",
  "rule.sg-default-has-rules.title": "기본 보안 그룹에 인바운드 규칙이 있음",
  "rule.sg-default-has-rules.description": "기본 보안 그룹은 새 자원에 자동으로 붙기 쉽다. 규칙이 있으면 의도치 않게 열린다.",
  "rule.sg-default-has-rules.remediation": "기본 보안 그룹의 인바운드 규칙을 지우고, 용도별 보안 그룹을 따로 만들어 쓴다.",
  "rule.rds-public.title": "공개 접근 가능한 RDS 데이터베이스",
  "rule.rds-public.description": "PubliclyAccessible=true 이면 인터넷에서 DB 엔드포인트에 닿을 수 있다(보안 그룹이 마지막 방어선).",
  "rule.rds-public.remediation": "DB 인스턴스를 수정해 '퍼블릭 액세스 가능'을 끄고, 애플리케이션과 같은 VPC 안에서만 접속한다.",
  "rule.s3-bucket-pab-off.title": "퍼블릭 액세스 차단이 꺼진 S3 버킷",
  "rule.s3-bucket-pab-off.description": "버킷 정책·ACL 실수 한 번으로 객체가 공개될 수 있다.",
  "rule.s3-bucket-pab-off.remediation": "계정 수준 S3 퍼블릭 액세스 차단을 켜는 것이 가장 간단하다. 공개가 꼭 필요한 버킷만 CloudFront 로 내보낸다.",
  "rule.lambda-url-no-auth.title": "인증 없는 Lambda 함수 URL",
  "rule.lambda-url-no-auth.description": "AuthType=NONE 인 함수 URL 은 주소만 알면 누구나 호출할 수 있다(요금·데이터 노출).",
  "rule.lambda-url-no-auth.remediation": "의도한 공개 API 가 아니면 AuthType 을 AWS_IAM 으로 바꾸거나 API Gateway 뒤로 옮긴다.",
  "rule.logs-no-retention.title": "보존 기간이 없는 로그 그룹",
  "rule.logs-no-retention.description": "보존 기간을 정하지 않으면 로그가 영구 보관되어 저장 비용이 계속 늘어난다.",
  "rule.logs-no-retention.remediation": "로그 그룹에 보존 기간(예: 30·90일)을 설정한다.",
  "rule.iam-key-old.title": "90일 넘게 교체하지 않은 액세스 키",
  "rule.iam-key-old.description": "오래된 장기 키는 유출됐을 때 피해 기간이 길다.",
  "rule.iam-key-old.remediation": "새 키를 만들어 바꿔 끼운 뒤 옛 키를 비활성화·삭제한다. 가능하면 SSO·역할 기반 임시 자격증명으로 옮긴다.",
  "rule.root-activity.title": "루트 사용자 활동",
  "rule.root-activity.description": "루트 사용자는 모든 권한을 가진다. 결제·계정 설정 같은 몇 가지 외에는 쓰지 않는 것이 원칙이다.",
  "rule.root-activity.remediation": "본인 활동인지 확인한다. 아니라면 즉시 루트 비밀번호를 바꾸고 MFA 를 확인한다. 평소 작업은 IAM Identity Center 사용자로 한다.",
  "rule.trail-tampering.title": "CloudTrail 트레일 중지·삭제·변경",
  "rule.trail-tampering.description": "공격자는 흔적을 지우려고 트레일 기록을 먼저 끈다. 권한이 없어 실패한 시도도 함께 보여 준다.",
  "rule.trail-tampering.remediation": "누가 했는지 확인하고, 의도한 변경이 아니면 트레일 기록을 다시 켠 뒤 해당 주체의 자격증명을 회수한다.",
  "rule.console-login-failed.title": "콘솔 로그인 실패",
  "rule.console-login-failed.description": "같은 사용자에게 로그인 실패가 이어지면 비밀번호 추측 시도일 수 있다.",
  "rule.console-login-failed.remediation": "본인 실수인지 확인하고, 반복되면 비밀번호 변경과 MFA 강제를 검토한다.",
  "rule.sg-opened-world-event.title": "보안 그룹을 인터넷 전체에 연 변경",
  "rule.sg-opened-world-event.description": "AuthorizeSecurityGroupIngress 로 0.0.0.0/0 을 허용한 기록. 임시로 열고 잊어버리는 일이 흔하다.",
  "rule.sg-opened-world-event.remediation": "필요한 변경이었는지 작업자에게 확인하고, 아니면 해당 인바운드 규칙을 지운다.",
  "rule.posture-off.title": "꺼져 있는 보안 기능",
  "rule.posture-off.description": "GuardDuty·Security Hub·Config·Access Analyzer·다중 리전 트레일·계정 S3 공개 차단은 사고를 일찍 알아차리고 나중에 원인을 추적하는 기본 장치다.",
  "rule.posture-off.remediation": "해당 리전 콘솔에서 기능을 켠다. 비용이 걱정되면 GuardDuty·Access Analyzer(무료 등급)·계정 S3 공개 차단(무료)부터 켠다.",

  "finding.sg-open-world": "{name}({id}): {ports} 포트가 인터넷 전체(0.0.0.0/0)에 열려 있음",
  "finding.sg-default-has-rules": "기본 보안 그룹({id})에 인바운드 규칙 {count}개",
  "finding.rds-public": "{name}({engine}) 가 공개 접근 가능으로 설정됨",
  "finding.s3-bucket-pab-off": "버킷 {name} 의 퍼블릭 액세스 차단이 꺼져 있음(계정 수준 차단도 없음)",
  "finding.lambda-url-no-auth": "함수 {name} 의 함수 URL 이 인증 없이(AuthType=NONE) 열려 있음",
  "finding.logs-no-retention": "로그 그룹 {name} 의 보존 기간이 '영구'(설정 없음)",
  "finding.iam-key-old": "{name}: 활성 액세스 키가 {days}일째 교체되지 않음",
  "finding.root-activity": "최근 7일 루트 사용자 활동 {count}건: {names} (마지막 {time})",
  "finding.trail-tampering.done": "{actor} 가 트레일 {trail} 에 {name} 실행함 ({time})",
  "finding.trail-tampering.denied": "{actor} 가 트레일 {trail} 에 {name} 시도했으나 거부됨({error_code}) ({time})",
  "finding.console-login-failed": "{actor} 콘솔 로그인 실패 {count}건 (마지막 {time})",
  "finding.sg-opened-world-event": "{actor}({actor_class}, {via}) 가 {group} 인바운드를 인터넷 전체에 열었음 ({time})",
  "finding.posture-off": "{feature} 꺼짐 — {where}",
  "finding.posture_global": "계정 전체",

  "time.just_now": "방금",
};

export const MESSAGES: Record<Lang, Table> = { en, ko };

// ---- 언어 결정 ---------------------------------------------------------------

export function isLang(value: unknown): value is Lang {
  return value === "en" || value === "ko";
}

// 저장값(사용자가 고른 것)이 있으면 그것, 없을 때만 브라우저 언어: ko 로 시작하면 한국어, 아니면 영어
export function detectLang(saved: string | null | undefined, browserLang: string | null | undefined): Lang {
  if (isLang(saved)) return saved;
  return (browserLang ?? "").toLowerCase().startsWith("ko") ? "ko" : "en";
}

// ---- 번역 ------------------------------------------------------------------

function fill(template: string, params: Params | undefined): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) => {
    const value = params[name];
    return value === undefined || value === null ? whole : String(value);
  });
}

export function makeTranslator(lang: Lang): Translator {
  const table = MESSAGES[lang];
  const translate = ((key: string, params?: Params): string => {
    // 영어 단수형: count 가 1 이고 "<키>.one" 이 있으면 그것을 쓴다
    const one = lang === "en" && params?.count === 1 ? table[`${key}.one`] : undefined;
    const template = one ?? table[key] ?? MESSAGES.en[key] ?? key;
    return fill(template, params);
  }) as Translator;
  translate.has = (key: string) => key in table;
  translate.lang = lang;
  return translate;
}

// ---- 서버가 내려 준 값(rule id·code + params)을 화면 문구로 -------------------------

export interface Failure {
  code: string | null;
  params: Params;
  message: string;
}

export function errorText(t: Translator, failure: Failure): string {
  if (failure.code && t.has(`error.${failure.code}`)) return t(`error.${failure.code}`, failure.params);
  if (!failure.code && /^\d{3}$/.test(failure.message)) return t("error.http_status", { status: failure.message });
  return failure.message;
}

export function ruleText(t: Translator, ruleId: string, part: "title" | "description" | "remediation", fallback: string): string {
  const key = `rule.${ruleId}.${part}`;
  return t.has(key) ? t(key) : fallback;
}

export interface FindingLike {
  rule_id: string;
  detail: string;
  params?: Params | null;
}

// 발견 사항 한 줄: params 가 있고 번역 문구가 있으면 언어에 맞게 다시 만들고, 아니면 저장된 문장 그대로(옛 행)
export function findingDetail(t: Translator, f: FindingLike): string {
  const p: Params | null | undefined = f.params;
  if (!p) return f.detail;
  let key = `finding.${f.rule_id}`;
  const params: Params = { ...p };
  if (typeof params.time === "string") params.time = fmtTime(t.lang, params.time);
  if (f.rule_id === "sg-open-world" && params.count === undefined && typeof p.ports === "string") {
    // 옛 행(count 없음): "22(SSH), 3389(RDP)" 문자열의 항목 수로 단수/복수를 고른다
    params.count = p.ports.split(",").filter((x) => x.trim()).length;
  }
  if (f.rule_id === "trail-tampering") key += p.denied ? ".denied" : ".done";
  if (f.rule_id === "sg-opened-world-event" && typeof p.actor_class === "string") {
    params.actor_class = t.has(`actor.${p.actor_class}`) ? t(`actor.${p.actor_class}`) : p.actor_class;
  }
  if (f.rule_id === "posture-off") {
    const feature = String(p.feature ?? "");
    params.feature = t.has(`feature_long.${feature}`) ? t(`feature_long.${feature}`) : feature;
    params.where = p.region === "global" ? t("finding.posture_global") : String(p.region ?? "");
  }
  return t.has(key) ? t(key, params) : f.detail;
}

export interface TrustLike {
  reason: string;
  code?: string | null;
  params?: Params | null;
}

export function trustReason(t: Translator, trust: TrustLike): string {
  const key = trust.code ? `trust.reason.${trust.code}` : "";
  if (!key || !t.has(key)) return trust.reason;
  const params: Params = { ...(trust.params ?? {}) };
  if (trust.code === "top_finding") {
    params.severity = t.has(`sev.${params.severity}`) ? t(`sev.${params.severity}`) : String(params.severity);
    params.title = ruleText(t, String(params.rule_id ?? ""), "title", String(params.title ?? ""));
  }
  return t(key, params);
}

export interface EventReasonLike {
  reason: string;
  reason_code?: string | null;
  reason_params?: Params | null;
}

export function eventReason(t: Translator, e: EventReasonLike): string {
  const key = e.reason_code ? `reason.${e.reason_code}` : "";
  return key && t.has(key) ? t(key, e.reason_params ?? {}) : e.reason;
}

export function permLabel(t: Translator, collector: string, fallback: string): string {
  const key = `perm.label.${collector}`;
  return t.has(key) ? t(key) : fallback;
}

// ---- 날짜·숫자 ---------------------------------------------------------------

const LOCALE: Record<Lang, string> = { en: "en-US", ko: "ko-KR" };

export function fmtTime(lang: Lang, iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(LOCALE[lang], { dateStyle: "medium", timeStyle: "short" }).format(d);
}

// 상대 시간: 방금 / 5분 전 / 5 minutes ago. now 를 넘기면 테스트에서 고정할 수 있다
export function ago(lang: Lang, iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "—";
  const sec = Math.max(0, (now - new Date(iso).getTime()) / 1000);
  if (sec < 60) return makeTranslator(lang)("time.just_now");
  const rtf = new Intl.RelativeTimeFormat(LOCALE[lang], { numeric: "always" });
  if (sec < 3600) return rtf.format(-Math.floor(sec / 60), "minute");
  if (sec < 86400) return rtf.format(-Math.floor(sec / 3600), "hour");
  return rtf.format(-Math.floor(sec / 86400), "day");
}

export function fmtNumber(lang: Lang, n: number): string {
  return new Intl.NumberFormat(LOCALE[lang]).format(n);
}

// 키 이름은 언어 표가 정한다: 두 언어의 키가 같은지 확인하려고 테스트가 쓴다
export function missingKeys(): { en: string[]; ko: string[] } {
  const enKeys = Object.keys(en);
  const koKeys = Object.keys(ko);
  return { en: koKeys.filter((k) => !(k in en)), ko: enKeys.filter((k) => !(k in ko) && !k.endsWith(".one")) };
}
