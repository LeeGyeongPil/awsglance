# awsglance — 읽기 전용 AWS 계정 상황판
#   docker build -t awsglance .
#   docker run --rm -p 8730:8730 awsglance --demo                       # 연습 모드(자격증명 불필요)
#   docker run --rm -p 8730:8730 -e AWS_PROFILE=myprof \
#     -v ~/.aws:/home/app/.aws:ro awsglance                              # 내 계정(읽기 전용)
# 컨테이너 밖에서 접속하려면 0.0.0.0 에 바인드해야 하므로 접근 토큰이 자동으로 켜진다(터미널에 ?token=… 주소 출력).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 \
    AWSGLANCE_DATA_DIR=/home/app/data
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv

RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --locked --no-dev && chown -R app:app /app

USER app
EXPOSE 8730
ENTRYPOINT ["/app/.venv/bin/awsglance", "--host", "0.0.0.0", "--port", "8730", "--no-browser"]
