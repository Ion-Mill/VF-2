# MOM 백엔드 (FastAPI). 2026-10-14 이 작업 환경에서 같은 requirements 로 uvicorn 실행·생성기 데이터 적재를 확인했다
# (Docker 이미지 빌드 자체는 Docker가 없어 못 함 — README "확인 범위")
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY db db
COPY tools tools
COPY scripts scripts
# Windows에서 git이 줄 끝을 CRLF로 바꿔 받아도 돌게 (bash: $'\r': command not found 막기). .gitattributes 도 LF로 고정
RUN find scripts db -name '*.sh' -exec sed -i 's/\r$//' {} + && chmod +x scripts/*.sh db/*.sh db/tests/*.sh
ENV PYTHONUNBUFFERED=1 TZ=Asia/Seoul
EXPOSE 8000
ENTRYPOINT ["scripts/docker-entrypoint.sh"]
# 워커 1개: 스케줄러·CMM 감시가 이 프로세스 안에서 돈다 (여러 개로 늘리면 MOM_RUN_WORKERS를 한 곳만 true)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
