# 보안 정책 / Security policy

보안 취약점을 발견하셨다면 **공개 이슈 대신** 이 레포의 **Security → Report a vulnerability**(비공개 취약점 신고)로 알려 주세요. 확인 후 답변드리고, 고친 버전을 릴리스하면서 함께 안내합니다.

If you find a security issue, please **do not open a public issue**. Use **Security → Report a vulnerability** in this repository to report it privately. We will reply after checking and announce the fix with a release.

awsglance 는 허용 목록에 있는 AWS 읽기 작업만 부를 수 있도록 코드에서 막혀 있고, 기본 설정은 내 컴퓨터(127.0.0.1)에서만 접속됩니다. 읽기 전용 가드를 우회하는 방법이나 비밀값이 가려지지 않고 저장되는 경우를 찾으면 특히 알려 주세요. / awsglance can only call allow-listed AWS read operations (enforced in code), and by default it only listens on your own machine (127.0.0.1). Reports of read-only guard bypasses or secrets stored unmasked are especially welcome.
