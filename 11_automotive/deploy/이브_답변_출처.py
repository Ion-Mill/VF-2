"""이브가 최근 질문에 답할 때 거친 길(조회 도구·시연 서버·사내 문서)을 단계 기록(STEP_LOG)에서 꺼낸다 (2026-10-25, 배포_안내.md 10장).

서버에서 (이브_답변_점검.py 다음에):  docker compose exec -T assistant python - < 이브_답변_출처.py
  - assistant.env의 STEP_LOG=1일 때만 기록이 있다. 기록 폴더는 컨테이너 안 /srv/assistant/C:\\llm\\logs/ (비서를 다시 만들면 비워진다).
  - 읽기만 한다. 질문 글과 단계 이름·조회 도구·문서 조각 번호만 출력한다(키·주소 없음).
  - 환경 변수 N=개수 (기본 25 — 가장 최근 질문부터).
"""
import glob
import json
import os

N = int(os.environ.get("N", "25"))
files = sorted(glob.glob("/srv/**/steps_*.jsonl", recursive=True), key=os.path.getmtime)
if not files:
    raise SystemExit("단계 기록이 없다 — assistant.env의 STEP_LOG=1인지 본다")
rows = []
for f in files[-2:]:                      # 날이 바뀌었으면 어제 파일까지
    rows += [json.loads(line) for line in open(f, encoding="utf-8") if line.strip()]
for r in rows[-N:]:
    out = []
    for s in r.get("단계", []):
        name = s.get("단계")
        if name == "운영 조회":
            out.append("운영 조회(공용 DB) " + json.dumps(s.get("도구"), ensure_ascii=False)[:240])
        elif name == "3 찾기":
            out.append("사내 문서 " + str([c.get("조각") for c in (s.get("상위") or [])][:4]))
        elif name == "알람 카드":
            out.append(f"알람 카드(기준표·문서) {s.get('알람')} 출처 {s.get('출처')}")
        elif name == "1 규칙 판정" and s.get("결과"):
            out.append("길: " + str(s.get("결과"))[:70])
    fin = r.get("최종") or {}
    print(f"- {r.get('질문')}\n    {fin.get('status')} | {str(fin.get('mode'))[:80]}\n    " + "\n    ".join(out or ["(조회·문서 단계 없음)"]) + "\n")
