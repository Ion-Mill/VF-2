# DB 담당 전달용 프롬프트 — 공용 Supabase의 사내 문서 조각 확인 (2026-10-25)

> **보내는 사람(창민) 메모 — 이 칸은 붙여 넣지 않는다.**
> - 이 하위 폴더(`DB_배포담당/`)만 보낸다. **상위 폴더에는 비밀이 든 파일(`ENV.MD`, `assistant/.env`, `backend/.env`)이 있으니 폴더째 보내지 않는다.** 이 폴더 안 파일에는 비밀값이 없다(예시 파일은 자리표시만).
> - 받는 사람은 아래 `========` 줄 **아래 전체**를 자기 Claude Code에 붙여 넣는다.
> - 같이 보는 파일: `예시파일/backend_.env.supabase.example`(읽기 전용 접속 키 이름).
> - 이 프롬프트는 **읽기만** 한다. 공용 DB에 쓰는 일(`load_docs.py` 실행 등)은 사람이 정한다.

========================== 아래부터 붙여 넣기 ==========================

너는 이 저장소(`semi-ai`, `Ion-Mill/VF-2`)에서 **공용 Supabase의 사내 문서 조각이 맞는지 읽기만 해서 확인**하는 일을 돕는다. 아래를 **순서대로** 하고, 모르는 것은 추측하지 말고 "모름"이라고 적는다.

## 지켜야 할 것
- **공용 DB에 쓰지 않는다.** `INSERT`·`UPDATE`·`DELETE`·`TRUNCATE`, 마이그레이션, `tools/load_docs.py` 실행, `fn_demo_reset()` 모두 하지 않는다. 읽기 전용 접속으로 `SELECT`만 한다.
- 접속 주소·비밀번호·키를 화면, 문서, 커밋에 쓰지 않는다. 오류 문장에 접속 주소가 들어갈 수 있으니 예외는 **종류 이름만** 출력한다. 본문(`chunk_text`)도 출력하지 않고 **개수·개정 번호·글자 수만** 본다.
- 코드·설정 파일을 고치지 않는다. 이 일은 확인과 보고만이다.

## 배경 (알아 둘 것)
- 비서(AI 챗봇)가 사내 문서를 공용 DB에서 읽게 만들었다(PR #168, #171, `main`에 합쳐짐). 비서는 DB에 직접 붙지 않고 백엔드의 읽기 전용 `GET /api/assistant/docs`를 부르며, 그 API는 `internal_doc`과 `doc_chunk`를 `SELECT`만 한다(`11_automotive/backend/app/sql/assistant.sql`의 `doc_corpus_docs`, `doc_corpus_chunks`).
- 최종용(final)은 **운영 데이터도 사내 문서도 모두 공용 Supabase**를 쓴다. 그래서 읽기 전용 계정이 두 표를 읽을 수 있어야 하고, `doc_chunk`가 문서 현행 개정과 같아야 한다.
- `doc_chunk`는 `11_automotive/backend/tools/load_docs.py`가 `가상사내문서/*.md`에서 만들어 넣는다(쓰기 작업이라 이 프롬프트에서는 실행하지 않는다).

## 할 일
1. **코드가 최신인지**: `git log --oneline -8` 안에 `#168`, `#171`(문서를 DB에서 읽기) 합치기 커밋이 있는지 본다. 없으면 `git fetch` 후 `origin/main`에 있는지만 확인하고 알린다(받지 않는다).
2. **새 쿼리 읽기**: `11_automotive/backend/app/sql/assistant.sql` 끝의 `doc_corpus_docs`, `doc_corpus_chunks` 두 쿼리가 `SELECT`뿐인지, `app/routers/assistant.py`의 `doc_corpus`가 `get_ro_db`(읽기 전용 연결)를 쓰는지 확인한다.
3. **읽기 전용 계정 권한** (`backend/.env.supabase`의 `MOM_READONLY_DATABASE_URL`을 쓴다. 값은 출력하지 않는다. 이 파일이 없으면 사람에게 받으라고 알리고 멈춘다):
   - `SELECT count(*) FROM internal_doc` 과 `SELECT count(*) FROM doc_chunk`가 **권한 오류 없이** 되는가.
4. **개정 일치 확인** (개수·개정만 출력):
   - `SELECT doc_no, current_rev FROM internal_doc ORDER BY 1`
   - `SELECT doc_no, doc_rev, count(*) FROM doc_chunk GROUP BY 1,2 ORDER BY 1,2`
   - 각 문서의 `doc_chunk.doc_rev`가 `internal_doc.current_rev`와 같은가(현행 개정의 조각이 있는가).
5. **로컬 문서와 비교**: `11_automotive/가상사내문서/*.md` 표지의 개정(`Rev.N`)을 읽어 `internal_doc.current_rev`와 같은지 본다.
   - 2026-10-25에 창민 PC에서 잰 기대값: 문서 8개(DOC-01~07 + 용어집), 조각 232개, 개정 DOC-01 Rev.3 · DOC-02 Rev.1 · DOC-03 Rev.1 · DOC-04 Rev.3 · DOC-05 Rev.3 · DOC-06 Rev.5 · DOC-07 Rev.12 · 용어집 Rev.6. 다르면 어느 문서가 다른지 적는다(문서가 그 뒤에 개정됐을 수 있다).

## 보고 (이 형식으로)
| 확인 | 결과 | 비고 |
|---|---|---|
| 코드가 최신(#168·#171 포함) | 예 / 아니오 / 모름 | |
| 새 쿼리가 SELECT뿐, 읽기 전용 연결 | 예 / 아니오 | |
| 읽기 전용 계정이 `internal_doc`·`doc_chunk`를 읽음 | 예 / 권한 오류(어느 표) | 오류는 종류 이름만 |
| `doc_chunk` 개정 = `internal_doc` 현행 개정 | 전부 같음 / 다른 문서 목록 | |
| 로컬 문서 표지 개정 = `internal_doc` | 전부 같음 / 다른 문서 목록 | |
| 문서 수·조각 수 | N개 / N개 | 기대값 8 / 232 |

마지막에 **사람이 정해야 할 것**을 따로 적는다. 예: "권한이 없으면 읽기 전용 계정에 두 표의 `SELECT`를 줄지", "개정이 다르면 `tools/load_docs.py`를 다시 돌릴지(공용 DB 쓰기라 DB 담당이 직접 판단·실행)". 네가 대신 실행하지 않는다.
