"""API 서버를 띄우기 전에 DB 연결을 확인한다 (Supabase·Docker·로컬 모두).

쓰는 법:
    python tools/check_connection.py --env-file .env.supabase
    python tools/check_connection.py                      # 이미 MOM_DATABASE_URL 등이 환경 변수에 있으면

확인하는 것:
  1. 앱 계정(MOM_DATABASE_URL)으로 로그인 · 시간대 · 데이터가 들어 있는지 (공정 실적·사내 문서 조각 수)
  2. 비서 읽기 계정(MOM_READONLY_DATABASE_URL)으로 로그인 · 읽기만 되는지 (쓰기가 막히는지)
  3. 실시간 알림 LISTEN/NOTIFY — 화면 실시간 갱신(SSE)이 이것으로 돈다. Supabase Transaction pooler(6543)에서는 안 된다
  4. 왕복 시간 (간단한 쿼리 10번 평균) — Supabase는 인터넷을 오가므로 로컬보다 느리다
비밀번호는 출력하지 않는다. psycopg(requirements.txt)만 쓴다.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import psycopg


def read_env_file(path: str) -> None:
    """KEY=VALUE 줄만 읽어 환경 변수에 넣는다 (이미 있는 값은 그대로)"""
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def dsn(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def masked(url: str) -> str:
    """비밀번호를 가린 주소 (출력용)"""
    try:
        head, rest = url.split("://", 1)
        cred, host = rest.rsplit("@", 1)
        user = cred.split(":", 1)[0]
        return f"{head}://{user}:****@{host}"
    except ValueError:
        return "(주소 형식을 읽지 못함)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env-file", help=".env.supabase 같은 설정 파일")
    a = ap.parse_args()
    if a.env_file:
        read_env_file(a.env_file)
    url = os.environ.get("MOM_DATABASE_URL")
    ro_url = os.environ.get("MOM_READONLY_DATABASE_URL")
    if not url or "<" in url:
        print("MOM_DATABASE_URL 이 없거나 <...> 를 아직 안 바꿈")
        return 2
    ok = True

    print(f"1. 앱 계정  {masked(url)}")
    try:
        with psycopg.connect(dsn(url), options="-c timezone=Asia/Seoul", connect_timeout=15) as c:
            row = c.execute("""SELECT current_user, current_setting('TimeZone'),
                                      (SELECT count(*) FROM operation_report), (SELECT count(*) FROM doc_chunk),
                                      (SELECT count(*) FROM app_user WHERE password_hash IS NOT NULL),
                                      app_now()""").fetchone()
            print(f"   OK  사용자 {row[0]} · 시간대 {row[1]} · 공정 실적 {row[2]} · 문서 조각 {row[3]} · "
                  f"비밀번호 있는 사용자 {row[4]} · 시연 시계 {row[5]:%Y-%m-%d %H:%M}")
            if row[2] == 0:
                print("   주의: 데이터가 비어 있음 (load_data.sh / load_all.sh 먼저)")
            t0 = time.perf_counter()
            for _ in range(10):
                c.execute("SELECT 1").fetchone()
            print(f"4. 왕복 시간  평균 {(time.perf_counter() - t0) * 100:.0f} ms (간단한 쿼리 10번)")
    except Exception as e:  # noqa: BLE001 — 무엇이 틀렸는지 그대로 보여 준다
        print(f"   실패: {type(e).__name__}: {e}")
        return 1

    print(f"2. 비서 읽기 계정  {masked(ro_url) if ro_url else '(없음 — 앱 계정을 읽기 전용 트랜잭션으로 씀)'}")
    if ro_url and "<" not in ro_url:
        try:
            with psycopg.connect(dsn(ro_url), connect_timeout=15) as c:
                n = c.execute("SELECT count(*) FROM alarm_event").fetchone()[0]
                try:
                    c.execute("UPDATE sim_clock SET speed = speed WHERE id = 1")
                    print(f"   실패: 읽기 계정인데 쓰기가 됨 (db/roles.sql 확인)")
                    ok = False
                except psycopg.Error:
                    c.rollback()
                    print(f"   OK  읽기 됨 (알람 {n}건), 쓰기는 막힘")
        except Exception as e:  # noqa: BLE001
            print(f"   실패: {type(e).__name__}: {e}")
            ok = False

    print("3. 실시간 알림 LISTEN/NOTIFY")
    if ":6543/" in url:
        print("   실패: 포트 6543(Transaction pooler)에서는 LISTEN이 안 됨 → 5432(Session pooler)로")
        return 1
    try:
        with psycopg.connect(dsn(url), autocommit=True, connect_timeout=15) as listener, \
                psycopg.connect(dsn(url), autocommit=True, connect_timeout=15) as sender:
            listener.execute("LISTEN mom_events_check")
            sender.execute("SELECT pg_notify('mom_events_check', 'ping')")
            got = None
            for n in listener.notifies(timeout=10, stop_after=1):
                got = n.payload
            if got == "ping":
                print("   OK  다른 연결에서 보낸 알림을 받음 (화면 실시간 갱신 가능)")
            else:
                print("   실패: 10초 안에 알림을 못 받음")
                ok = False
    except Exception as e:  # noqa: BLE001
        print(f"   실패: {type(e).__name__}: {e}")
        ok = False

    print("모두 OK — 이제 서버를 띄운다: uvicorn app.main:app --env-file <설정 파일>" if ok else "실패한 항목이 있음")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
