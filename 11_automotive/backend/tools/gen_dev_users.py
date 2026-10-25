"""개발·시연용 사용자 12명과 비밀번호.

쓰는 법:
    python tools/gen_dev_users.py [비밀번호] > db/dev/20_dev_users.sql     # 개발 목업(--dev)용: 사용자 12명 INSERT
    python tools/gen_dev_users.py --update [비밀번호] | psql -d mom        # 생성기 적재 뒤: 비밀번호가 빈 사용자에게 넣기
개발·시연 전용. 운영에서는 쓰지 않는다 (비밀번호가 저장소·명령 기록에 남음 — NFR-SEC-06).
사용자 = 생성기 masters/app_user.csv 와 같음 (U01~U12, 2026-10-10 두 번째 담당 공정 포함). user_id 형식은 논리 ERD에서
[선택 필요: 기술 회의] — 생성기가 쓰는 U01 모양을 따른다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.domain.passwords import hash_password  # noqa: E402

# (user_id, 이름, 역할, 교대, 공정, 두 번째 공정) — 생성기 masters/app_user.csv (설계서 5.17: OPR 6, MNT 3, SUP 2, MGR 1)
USERS = [
    ("U01", "김하늘", "OPR", "DAY", "OP-10", "OP-20"), ("U02", "이서연", "OPR", "DAY", "OP-30", None),
    ("U03", "박준호", "OPR", "DAY", "OP-50", "OP-40"), ("U04", "최민재", "OPR", "NIGHT", "OP-10", "OP-20"),
    ("U05", "정유진", "OPR", "NIGHT", "OP-30", None), ("U06", "강태윤", "OPR", "NIGHT", "OP-50", "OP-40"),
    ("U07", "이도윤", "MNT", "DAY", None, None), ("U08", "한지훈", "MNT", "DAY", None, None),
    ("U09", "오세린", "MNT", "NIGHT", None, None),
    ("U10", "박서준", "SUP", "DAY", None, None), ("U11", "윤가은", "SUP", "NIGHT", None, None),
    ("U12", "장현우", "MGR", "DAY", None, None),
]


def q(v):
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def main():
    args = sys.argv[1:]
    update = "--update" in args
    args = [a for a in args if a != "--update"]
    pw = args[0] if args else "mom1234!"
    if update:
        print("-- 생성: tools/gen_dev_users.py --update — 비밀번호가 빈 사용자에게 개발·시연 비밀번호 (운영 금지)")
        for u, *_ in USERS:
            print(f"UPDATE app_user SET password_hash = {q(hash_password(pw))} WHERE user_id = {q(u)} AND password_hash IS NULL;")
        return
    print("-- 생성: tools/gen_dev_users.py — 개발·시연 전용 계정 (비밀번호는 README 참고). 운영 금지")
    print("INSERT INTO app_user (user_id, user_name, role_code, home_shift_type, home_process_code, home_process_code_2, "
          "password_hash) VALUES")
    rows = [f"  ({q(u)}, {q(n)}, {q(r)}, {q(s)}, {q(p)}, {q(p2)}, {q(hash_password(pw))})" for u, n, r, s, p, p2 in USERS]
    print(",\n".join(rows) + ";")
    print("UPDATE internal_doc SET approved_by = 'U12', approved_at = '2026-10-07 09:00+09';")


if __name__ == "__main__":
    main()
