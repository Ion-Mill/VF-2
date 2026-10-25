"""직원 관리 (API-USR-01~05, 2026-10-25) — DB 없이: 기간·숫자 4칸·배치표·배치 바꾸기·직원 추가·정보 고치기 확인, 3D 라인 뷰 토큰 확인.
DB로 도는 흐름(명단·업무 기록·수정 이력·권한)은 tests/test_routers_db.py test_17_staff."""
import os
import unittest
from datetime import datetime, timedelta, timezone

from tests.stubs_loader import use_stubs_if_needed

use_stubs_if_needed()
os.environ.setdefault("MOM_JWT_SECRET", "test-secret-" + "x" * 32)

from app import security  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.domain import staff as rules  # noqa: E402
from app.domain.tokens import create_token  # noqa: E402
from app.errors import AppError  # noqa: E402

KST = timezone(timedelta(hours=9))
U1 = {"user_id": "U01", "user_name": "김하늘", "role_code": "OPR", "home_shift_type": "DAY", "home_process_code": "OP-10",
      "home_process_code_2": "OP-20", "is_active": True}
U7 = {"user_id": "U07", "user_name": "이도윤", "role_code": "MNT", "home_shift_type": "DAY", "home_process_code": None,
      "home_process_code_2": None, "is_active": True}
U12 = {"user_id": "U12", "user_name": "장현우", "role_code": "MGR", "home_shift_type": "DAY", "home_process_code": None,
       "home_process_code_2": None, "is_active": True}


class Fails:
    def __init__(self, case: unittest.TestCase, reason: str, status: int = 422):
        self.case, self.reason, self.status = case, reason, status

    def __enter__(self):
        return self

    def __exit__(self, typ, exc, tb):
        self.case.assertIsInstance(exc, AppError, f"{self.reason}: 오류가 나야 함")
        self.case.assertEqual((exc.status, exc.detail.get("reason")), (self.status, self.reason))
        return True


class TestStaffRules(unittest.TestCase):
    def test_period(self):
        now = datetime(2026, 10, 26, 10, 30, tzinfo=KST)
        self.assertEqual(rules.period_range("7d", now), (now - timedelta(days=7), now))
        self.assertEqual(rules.period_range("today", now)[0], datetime(2026, 10, 26, 0, 0, tzinfo=KST))
        self.assertEqual(rules.period_range("30d", now)[0].day, 26)
        self.assertEqual(rules.period_range("sep", now), (datetime(2026, 9, 1, tzinfo=KST), datetime(2026, 10, 1, tzinfo=KST)))
        start = datetime(2026, 10, 1, 9, 0, tzinfo=KST)
        self.assertEqual(rules.period_range("all", now, start), (start, now))     # 기록 전체 (10월 데이터에서 sep는 빔)

    def test_kpis(self):
        ev = [{"kind": "prod", "pq": "10", "gq": "9"}, {"kind": "prod", "pq": 10, "gq": 10}, {"kind": "tool"},
              {"kind": "wr_confirm", "minutes": "12.5"}, {"kind": "wr_confirm", "minutes": None}]
        self.assertEqual({k["label"]: k["value"] for k in rules.kpis("OPR", ev)},
                         {"생산 수량": 20, "양품률": 95.0, "공구 교체": 1, "정지 사유 입력": 0})
        self.assertEqual({k["label"]: k["value"] for k in rules.kpis("MNT", ev)}["수리 시간 합계"], 12.5)
        self.assertIsNone(rules.kpis("OPR", [])[1]["value"])        # 생산이 없으면 양품률 없음 (0%가 아님)
        self.assertEqual([k["label"] for k in rules.kpis("MGR", [])], ["일일 보고서 확정", "폐기 승인", "설정 변경", "문서 수정"])

    def test_board(self):
        off = {**U1, "user_id": "U13", "home_shift_type": "NIGHT", "is_active": "f"}       # 사용 중지 = 배치표에 없음
        rows, empty = rules.board([U1, U7, off, U12])
        cells = {r["row"]: r["cells"] for r in rows}
        self.assertEqual(cells["OP-10"], {"DAY": ["U01"], "NIGHT": []})
        self.assertEqual(cells["OP-20"]["DAY"], ["U01"])                       # 두 공정을 맡으면 두 줄 모두
        self.assertEqual(cells["보전"], {"DAY": ["U07"], "NIGHT": []})
        self.assertNotIn("반장", [r["row"] for r in rows if any(r["cells"].values())])
        self.assertIn("야간 OP-10", empty)
        self.assertNotIn("주간 OP-10", empty)
        self.assertEqual(len(rows), 7)                                          # 공정 5 + 보전 + 반장 (관리자 줄 없음)

    def test_assignment(self):
        self.assertEqual(rules.check_assignment(U1, {"procs": ["OP-30"]})["home_process_code_2"], None)
        got = rules.check_assignment(U1, {"home_shift_type": "NIGHT", "home_process_code_2": "OP-40"})
        self.assertEqual((got["home_shift_type"], got["home_process_code"], got["home_process_code_2"]), ("NIGHT", "OP-10", "OP-40"))
        self.assertEqual(rules.check_assignment(U1, {"home_process_code_2": ""})["home_process_code_2"], None)   # ""로 비움
        self.assertEqual(rules.check_assignment(U7, {"home_shift_type": "NIGHT"})["home_shift_type"], "NIGHT")
        for change, reason in (({"procs": ["OP-10", "OP-20", "OP-30"]}, "PROCESS"), ({"procs": ["OP-90"]}, "PROCESS"),
                               ({"procs": ["OP-10", "OP-10"]}, "PROCESS"), ({"home_shift_type": "EVE"}, "SHIFT")):
            with Fails(self, reason):
                rules.check_assignment(U1, change)
        with Fails(self, "PROCESS_ROLE"):
            rules.check_assignment(U7, {"procs": ["OP-10"]})                    # 공정 줄은 작업자만
        with Fails(self, "INACTIVE"):
            rules.check_assignment({**U1, "is_active": "f"}, {"home_shift_type": "NIGHT"})

    def test_new_user(self):
        ids = ["U01", "U12", "admin"]
        new = rules.new_user({"user_name": " 새 작업자 ", "role_code": "OPR", "home_shift_type": "NIGHT", "procs": ["OP-30"],
                              "password": "abcd1234"}, ids, 8)
        self.assertEqual((new["user_id"], new["user_name"], new["home_process_code"], new["is_active"]), ("U13", "새 작업자", "OP-30", True))
        self.assertEqual(rules.new_user({"user_id": "kim_01", "user_name": "김", "role_code": "MGR", "password": "x" * 8}, ids, 8)
                         ["home_shift_type"], None)                             # 관리자는 담당 교대를 비워도 됨
        with Fails(self, "DUPLICATE", 409):
            rules.new_user({"user_id": "U01", "user_name": "김", "role_code": "OPR", "home_shift_type": "DAY", "password": "x" * 8}, ids, 8)
        bad = {"user_name": "김", "role_code": "OPR", "home_shift_type": "DAY", "password": "x" * 8}
        for change, reason in (({"user_id": "김!"}, "USER_ID"), ({"user_id": "a"}, "USER_ID"), ({"user_name": "  "}, "NAME"),
                               ({"user_name": "가" * 41}, "NAME"), ({"role_code": "ADM"}, "ROLE"), ({"password": "short"}, "PASSWORD"),
                               ({"home_shift_type": None}, "SHIFT"), ({"role_code": "SUP", "procs": ["OP-10"]}, "PROCESS_ROLE")):
            with Fails(self, reason):
                rules.new_user({**bad, **change}, ids, 8)
        self.assertEqual(rules.next_user_id(["U01", "U09", "kim", "U100"]), "U101")
        self.assertEqual(rules.next_user_id([]), "U01")

    def test_update(self):
        mgrs = ["U12"]
        new = rules.updated_user(U1, {"role_code": "MNT"}, "U12", mgrs, 8)      # 작업자 → 보전: 담당 공정 두 칸을 비움
        self.assertEqual((new["role_code"], new["home_process_code"], new["home_process_code_2"]), ("MNT", None, None))
        self.assertEqual(rules.updated_user(U1, {"user_name": "김하늘2"}, "U12", mgrs, 8)["home_process_code_2"], "OP-20")
        self.assertIsNone(rules.updated_user(U1, {}, "U12", mgrs, 8)["password"])
        self.assertEqual(rules.updated_user(U1, {"password": "newpass99"}, "U12", mgrs, 8)["password"], "newpass99")
        with Fails(self, "SELF"):
            rules.updated_user(U12, {"is_active": False}, "U12", ["U12", "U20"], 8)    # 자기 자신 사용 중지
        with Fails(self, "SELF"):
            rules.updated_user(U12, {"role_code": "SUP"}, "U12", ["U12", "U20"], 8)
        with Fails(self, "LAST_MGR"):
            rules.updated_user(U12, {"is_active": False}, "U20", ["U12"], 8)         # 사용 중인 MGR이 0명
        self.assertFalse(rules.updated_user(U12, {"is_active": False}, "U20", ["U12", "U20"], 8)["is_active"])
        with Fails(self, "PROCESS_ROLE"):
            rules.updated_user(U7, {"procs": ["OP-10"]}, "U12", mgrs, 8)
        with Fails(self, "PASSWORD"):
            rules.updated_user(U1, {"password": "1234"}, "U12", mgrs, 8)

    def test_diff(self):
        new = rules.updated_user(U1, {"role_code": "MNT", "password": "newpass99"}, "U12", ["U12"], 8)
        got = {c["field"]: (c["before"], c["after"]) for c in rules.diff(U1, new)}
        self.assertEqual(got, {"role_code": ("OPR", "MNT"), "home_process_code": ("OP-10", None),
                               "home_process_code_2": ("OP-20", None), "password": (None, "비밀번호 바꿈")})
        self.assertNotIn("newpass99", str(rules.diff(U1, new)))                 # 비밀번호 원문은 이력에 없음
        self.assertEqual(rules.diff({**U1, "is_active": "t"}, {**U1, "is_active": True}), [])
        self.assertEqual(rules.diff(U1, {**U1, "is_active": False}), [{"field": "is_active", "before": "true", "after": "false"}])
        created = {c["field"]: (c["before"], c["after"]) for c in rules.diff({}, {**U7, "password": "x" * 8})}
        self.assertEqual(created["is_active"], (None, "true"))
        self.assertEqual(created["password"], (None, "비밀번호 정함"))
        self.assertNotIn("home_process_code", created)
        self.assertEqual(set(rules.public({**U1, "password_hash": "scrypt$..."})), {"user_id", *rules.FIELDS})


class TestTwinToken(unittest.TestCase):
    """3D 라인 뷰(token_user)는 요청마다 DB를 읽지 않지만 사용 중지·역할 변경은 막는다 (60초 기억, 1025 요청 3장)"""

    def setUp(self):
        self._states = security.user_states_side
        self.token = "Bearer " + create_token("U02", "OPR", get_settings().jwt_secret, 10)

    def tearDown(self):
        security.user_states_side = self._states
        security.reset_user_state_cache()

    def test_states(self):
        for states, ok in (({"U02": ("OPR", True)}, True), ({}, True),                 # 기억에 없음(방금 만든 직원) = 토큰을 믿음
                           ({"U02": ("OPR", False)}, False), ({"U02": ("MNT", True)}, False)):
            security.user_states_side = lambda s=states: s
            with self.subTest(states=states):
                if ok:
                    self.assertEqual(security.token_user(self.token).role_code, "OPR")
                else:
                    with self.assertRaises(AppError) as e:
                        security.token_user(self.token)
                    self.assertEqual(e.exception.status, 401)

    def test_db_failure_keeps_last(self):
        engine = security.side_engine

        def broken():
            raise RuntimeError("DB 끊김")
        security.side_engine = broken
        try:
            with self.assertLogs("mom.security", level="ERROR"):
                security.reset_user_state_cache()
                self.assertEqual(security.user_states_side(), {})                # 처음이면 빈 표 = 막지 않음
                security._user_state_cache = (-1e9, {"U02": ("OPR", False)})    # 기억이 지났어도 못 읽으면 앞 값
                self.assertEqual(security.user_states_side(), {"U02": ("OPR", False)})
        finally:
            security.side_engine = engine


if __name__ == "__main__":
    unittest.main()
