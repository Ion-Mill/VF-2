# 시험용 가짜 모듈 (FastAPI·SQLAlchemy·psycopg가 설치되지 않은 곳 전용)

이 작업 환경에서는 패키지 저장소(PyPI)에 접근할 수 없어 FastAPI·SQLAlchemy·psycopg를 설치하지 못했다.
그래서 **import만 되게 하는 가짜 모듈**을 두고, 라우터의 처리기 함수를 직접 불러 DB(psql)에서 돌려 본다.

- 확인되는 것: 처리기 → 서비스 → SQL 매개변수 연결, Pydantic 모델, 권한 표시, 업무 규칙 오류
- 확인 **안 되는** 것: 실제 라우팅, 요청 검증·직렬화, 의존성 주입, 미들웨어, SSE, 예외 처리기
- 진짜 패키지가 설치돼 있으면(`pip install -r requirements.txt`) 이 폴더는 쓰이지 않는다 (tests/conftest_stubs.py가 확인)
