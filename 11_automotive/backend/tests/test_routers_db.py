"""라우터 처리기를 직접 불러 실제 DB에서 업무 흐름을 돌려 본다.

FastAPI가 없으면 tests/stubs 의 가짜 모듈로 import만 한다 (tests/stubs/README.md).
→ 확인: 처리기 ↔ 서비스 ↔ SQL 연결, 처리기에 걸린 권한(require)이 역할별로 맞는지, 업무 규칙 오류
→ 확인 안 됨: HTTP 라우팅·요청 검증·응답 직렬화·미들웨어 (진짜 FastAPI에서 따로 확인 필요)
필요: MOM_TEST_PSQL (tests/test_services_db.py 와 같음)
"""
import inspect
import io
import os
import tempfile
import unittest
from types import SimpleNamespace

from tests.stubs_loader import use_stubs_if_needed

USING_STUBS = use_stubs_if_needed()
os.environ.setdefault("MOM_JWT_SECRET", "test-secret-" + "x" * 32)
os.environ.setdefault("MOM_CMM_PROCESSED_DIR", tempfile.mkdtemp(prefix="mom-cmm-"))

from app import security  # noqa: E402
from app.errors import AppError  # noqa: E402
from app.routers import (alarms, assistant, auth, documents, ingest, inventory, line, maintenance,  # noqa: E402
                         master, notifications, production, qr, quality)
from tests.psqldb import PsqlDb, PsqlError, clone_db, drop_db  # noqa: E402

PSQL = os.environ.get("MOM_TEST_PSQL")
REQ = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))


def permission_dep(fn):
    """처리기에 걸린 require(...)/require_any(...) 의존성 (인자 이름, 의존성 함수)"""
    for name, p in inspect.signature(fn).parameters.items():
        dep = getattr(p.default, "dependency", None)
        if dep is not None and hasattr(dep, "permission"):
            return name, dep
    return None, None


@unittest.skipUnless(PSQL, "MOM_TEST_PSQL 없음 — DB 시험 건너뜀")
class RouterFlows(unittest.TestCase):
    DB = "mom_router_test"

    @classmethod
    def setUpClass(cls):
        cls.db = PsqlDb(clone_db(PSQL, "mom_test", cls.DB))
        cls.db._run("SELECT fn_sim_set('SIM', '2026-09-15 13:00+09', 1, true)", quiet=True)
        security.reset_permission_cache()
        cls.logged = []
        fake_log = lambda *a, **k: cls.logged.append(a)   # noqa: E731 (접근 기록은 따로 저장 — 시험에서는 모아 봄)
        auth.log_access = assistant.log_access = fake_log

    @classmethod
    def tearDownClass(cls):
        drop_db(PSQL, cls.DB)

    def user(self, user_id):
        r = self.db.one("common.user_public", user_id=user_id)
        return security.User(r["user_id"], r["user_name"], r["role_code"], r["home_process_code"] or None)

    def call(self, fn, user_id=None, **kw):
        """처리기에 걸린 권한 의존성을 그 사용자로 실제로 통과시킨 뒤 처리기를 부른다"""
        name, dep = permission_dep(fn)
        if name:
            kw[name] = dep(self.user(user_id), self.db)
        if "db" in inspect.signature(fn).parameters:
            kw["db"] = self.db
        for pname, p in inspect.signature(fn).parameters.items():   # Query(...) 기본값 채우기
            if pname not in kw and hasattr(p.default, "default") and not hasattr(p.default, "dependency"):
                kw[pname] = p.default.default
        return fn(**kw)

    def denied(self, fn, user_id, **kw):
        with self.assertRaises(AppError) as e:
            self.call(fn, user_id, **kw)
        self.assertEqual(e.exception.status, 403)

    # ---------------------------------------------------------------
    def test_01_login(self):
        out = auth.login(auth.LoginIn(user_id="U10", password="mom1234!"), REQ, self.db)
        self.assertEqual((out.role_code, out.home), ("SUP", "SCR-04"))
        with self.assertRaises(AppError) as e:
            auth.login(auth.LoginIn(user_id="U10", password="틀림"), REQ, self.db)
        self.assertEqual(e.exception.status, 401)
        with self.assertRaises(AppError):
            auth.login(auth.LoginIn(user_id="nobody", password="mom1234!"), REQ, self.db)
        self.assertEqual([a[1] for a in self.logged[-3:]], ["LOGIN", "LOGIN_FAIL", "LOGIN_FAIL"])
        opr = auth.login(auth.LoginIn(user_id="U02", password="mom1234!"), REQ, self.db)   # 담당 공정 (API-AUTH-01, 2026-10-20)
        self.assertTrue(opr.process_codes and all(p.startswith("OP-") for p in opr.process_codes))

    def test_02_line_and_alarms(self):
        now = self.call(line.twin, "U02", shift_id=None)
        self.assertEqual(len(now["equipment"]), 6)
        self.assertIsNotNone(now["shift"])
        self.assertEqual(now["shift"]["total_target_qty"], "90")       # 주간 총 목표 = 90 + 이월 0 (R-88)
        self.assertIn("loss_qty", now["shift"])                      # 3D 손실 = 고장 + 속도 합 하나
        self.assertIsNotNone(now["line_oee"])                        # 지표 카드 처음 값 = 라인 OEE
        tgt = self.call(production.target, "U02", shift_id=None)
        self.assertEqual(tgt["shift_id"], "2026-09-15-D")
        self.assertTrue({"forecast_qty", "shortfall_qty", "is_target_risk", "carry_over_qty", "hourly"} <= set(tgt))
        night = self.call(production.target, "U10", shift_id="2026-09-15-N")
        self.assertEqual(night["carry_over_is_provisional"], True)    # 주간 보고서 확정 전 → 이월 잠정
        card = self.call(alarms.guide_card, "U02", alarm_event_id=3)
        self.assertEqual(card["alarm_code"], "992")
        self.assertIn("same_cases", card)
        # 연쇄 알람·작업지시서·영어 이름 (API-MNT-01, 2026-10-20): 992의 앞 알람 = 994(2번), 작업지시서 MW-0901
        self.assertEqual(str(card["prev_alarm_event_id"]), "2")
        self.assertIn("name_en", card)
        self.assertIn("\"wo_no\": \"MW-0901\"", str(card["work_order"]).replace("'", "\""))     # 시험 DB는 jsonb를 글로 줌
        # 의심 로트 제안 (FR-PRD-05-05 수용 기준: S1에서 LOT-2609-041-1, 2026-10-20) — 제안만, 상태는 그대로
        self.assertIn("LOT-2609-041-1", [x["lot_no"] for x in card["suspect_lots"]])
        self.denied(alarms.downtime_patch, "U02", state_log_id=1, body=alarms.DowntimeIn(confirm=True))   # 확정은 SUP
        got = self.call(alarms.downtime_patch, "U02", state_log_id=4, body=alarms.DowntimeIn(reason_code="F01"))
        self.assertEqual(got["reason_status"], "ENTERED")
        rows = self.call(alarms.downtimes, "U10", shift_id="2026-09-15-D", pending_only=True)
        self.assertTrue(all(r["reason_status"] != "CONFIRMED" for r in rows))
        k = self.call(production.kpi, "U10", shift_id="2026-09-15-D")
        self.assertEqual((k["scope"], len(k["rows"])), ("line", 1))                 # 라인 OEE 1줄 (OP-30 2대 합)
        self.assertIn("mttr_min", k["reliability"][0])
        ke = self.call(production.kpi, "U10", scope="equipment", shift_id="2026-09-15-D", equipment_id="VF2-01")
        # 진행 중 교대의 계획 시간 = 지금까지 지난 근무 분 (2026-10-23 결정, 1023 메모 11장): 13:00 = 300분 − 휴식 60분 = 240분,
        # VF2-01 RUN 176분 → 가동률 73.3% (480분 기준이던 때는 36.7%로 주의였음)
        self.assertAlmostEqual(float(ke["rows"][0]["availability_pct"]), 73.3, delta=0.2)
        self.assertEqual(ke["rows"][0]["is_availability_warn"], False)
        orders = self.call(production.orders, "U10", shift_id="2026-09-15-D")
        self.assertTrue(all("is_late" in o and "defect_qty" in o for o in orders))

    def test_03_maintenance_flow(self):
        # 사람·비서가 초안 API로 만드는 흐름 — 정지 알람 자동 초안(2026-10-20)은 끄고 알람만 넣는다 (자동 초안은 db/tests/96d)
        aid = int(self.db._run("SET app.auto_work_order = 'off'; SELECT fn_ingest_alarm('VF2-02', '254')", quiet=True).splitlines()[1])
        body = maintenance.WoDraftIn(equipment_id="VF2-02", title="알람 254 점검", symptom="과열", alarm_event_id=int(aid),
                                     steps=[maintenance.StepIn(step_text="팬 확인", source_section="DOC-03 §2.9")])
        self.denied(maintenance.wo_create, "U02", body=body)
        wo = self.call(maintenance.wo_create, "U07", body=body)["wo_no"]
        # 보전 담당자가 직접 만든 것은 수정 중(v0 = HUMAN)에서 시작 — AI비서 초안(AI_DRAFT)과 구분
        got = self.call(maintenance.wo_get, "U07", wo_no=wo)
        self.assertEqual(got["status"], "EDITING")
        self.assertEqual(self.db.all("documents.revisions", doc_type="WORK_ORDER", doc_key=wo, own_user=None)[0]["author_kind"],
                         "HUMAN")
        with self.assertRaises(AppError) as e:      # 버전이 다르면 CONFLICT_VERSION
            self.call(maintenance.wo_edit, "U07", wo_no=wo, body=maintenance.EditIn(version=3, changes={"title": "x"}))
        self.assertEqual(e.exception.code, "CONFLICT_VERSION")
        self.call(maintenance.wo_edit, "U07", wo_no=wo,
                  body=maintenance.EditIn(version=0, changes={"title": "알람 254 냉각 점검"}))
        # AI비서 초안은 사람이 열어 고치기 전에는 승인 안 됨
        aid2 = int(self.db._run("SET app.auto_work_order = 'off'; SELECT fn_ingest_alarm('VF2-01', '994')", quiet=True).splitlines()[1])
        ai = assistant.draft_work_order(maintenance.WoDraftIn(equipment_id="VF2-01", title="알람 994 점검", symptom="x",
                                                              alarm_event_id=int(aid2)), self.db)["wo_no"]
        self.assertEqual(self.call(maintenance.wo_get, "U10", wo_no=ai)["status"], "AI_DRAFT")
        self.call(maintenance.wo_assign, "U10", wo_no=ai, body=maintenance.AssignIn(mnt_user_id="U09"))
        with self.assertRaises(AppError) as e:      # AI비서 초안 그대로는 승인 안 됨 → INVALID_STATE
            self.call(maintenance.wo_approve, "U10", wo_no=ai, body=maintenance.VersionIn(version=0))
        self.assertEqual(e.exception.code, "INVALID_STATE")
        self.denied(maintenance.wo_approve, "U07", wo_no=wo, body=maintenance.VersionIn(version=1))
        with self.assertRaises(PsqlError) as e:    # 담당자 없이 승인 불가
            self.call(maintenance.wo_approve, "U10", wo_no=wo, body=maintenance.VersionIn(version=1))
        self.assertIn("ck_wo_approved", str(e.exception))
        self.call(maintenance.wo_assign, "U10", wo_no=wo, body=maintenance.AssignIn(mnt_user_id="U07"))
        self.call(maintenance.wo_approve, "U10", wo_no=wo, body=maintenance.VersionIn(version=1))
        mine = self.call(maintenance.wo_list, "U07", mine=True)
        self.assertIn(wo, [w["wo_no"] for w in mine])
        self.denied(maintenance.wo_start, "U09", wo_no=wo)        # 담당이 아닌 보전 담당자는 시작 못 함 (MNT-07)
        self.call(maintenance.wo_start, "U07", wo_no=wo)          # [작업 시작] (6.13, SCR-11)
        rec = self.call(maintenance.wr_create_full, "U07", body=maintenance.WrFullIn(wo_no=wo, cause="팬 먼지", action="청소"))
        no = rec["record_no"]
        # 잠금·표지 9단계를 다 체크하기 전에는 확정 불가 (R-32)
        detail = self.call(maintenance.wr_get, "U07", record_no=no)
        ver = maintenance.VersionIn(version=int(detail["current_version"]))
        with self.assertRaises(PsqlError) as e:
            self.call(maintenance.wr_confirm, "U07", record_no=no, body=ver)
        self.assertIn("R-32", str(e.exception))
        # 체크 9칸·작업 순서·사용 부품을 PATCH 한 번에 (MNT-09)
        after = self.call(maintenance.wr_edit, "U07", record_no=no, body=maintenance.WrEditIn(
            version=ver.version, checks=[maintenance.CheckSet(check_seq=int(c["check_seq"])) for c in detail["checks"]],
            parts=[maintenance.WrPartIn(item_no="CS-SLUB", qty=0.5)]))
        self.assertTrue(all(c["is_checked"] is True for c in after["checks"]))
        self.denied(maintenance.wr_confirm, "U02", record_no=no, body=ver)          # 정식 기록 확정은 MNT
        self.call(maintenance.wr_confirm, "U07", record_no=no, body=ver)
        self.assertEqual(self.call(maintenance.wo_get, "U10", wo_no=wo)["status"], "DONE")
        self.call(maintenance.wr_sup_check, "U10", record_no=no)
        # 확정된 기록 고치기: 사유 없으면 막힘, 사유 있으면 새 버전 + 반장 확인이 풀림
        cur = int(self.call(maintenance.wr_get, "U07", record_no=no)["current_version"])
        with self.assertRaises(AppError) as e:
            self.call(maintenance.wr_edit, "U07", record_no=no,
                      body=maintenance.WrEditIn(version=cur, changes={"action": "청소·교체"}))
        self.assertEqual(e.exception.code, "VALIDATION")    # 확정 뒤 수정은 사유 필수
        after = self.call(maintenance.wr_edit, "U07", record_no=no,
                          body=maintenance.WrEditIn(version=cur, changes={"action": "청소·교체"}, reason="교체 누락"))
        self.assertEqual(int(after["current_version"]), cur + 1)
        self.assertEqual(after["status"], "CONFIRMED")
        with self.assertRaises(AppError) as e:          # 비서 서비스가 없으면 503 (화면은 기본 문구)
            self.call(maintenance.wr_assist, "U07", record_no=no, body=maintenance.AssistIn(memo="팬 먼지"))
        self.assertEqual((e.exception.status, e.exception.code), (503, "ASSISTANT_UNAVAILABLE"))
        # OPR은 정식 기록 목록을 못 봄 → 간이만
        rows = self.call(maintenance.wr_list, "U02", record_type=None, status=None, limit=100)
        self.assertTrue(all(r["record_type"] == "SIMPLE" for r in rows))
        # 제때 실시율 (FR-MNT-04-07, 2026-10-20): 분모 = 기한이 온 항목 (안 한 채 기한 지난 것 포함), 맨 끝 줄 = 라인 합
        on_time = self.call(maintenance.pm_schedule, "U07", equipment_id=None, frm=None, to=None)["on_time"]
        self.assertIn(on_time[-1]["equipment_id"], (None, ""))      # 시험 DB(psql csv)는 NULL을 빈 글로 돌려줌
        self.assertEqual(int(on_time[-1]["due_count"]), sum(int(r["due_count"]) for r in on_time[:-1]))
        self.assertTrue(all(int(r["due_count"]) == int(r["done_count"]) + int(r["missed_count"]) for r in on_time))

    def test_035_lot_hold(self):
        t = self.call(production.trace, "U02", lot_no="LOT-2609-041-1")
        self.assertEqual(t["lot_no"], "LOT-2609-041-1")
        self.assertTrue(t["suspect"] and all(x["kind"] == "ALARM" for x in t["suspect"]))     # 로트 추적의 의심 이유
        self.assertIn("LOT-2609-041-1", [x["lot_no"] for x in self.call(production.suspect_lots, "U10", since=None)])
        body = production.HoldIn(trigger_type="AI_SUSPECT", reason="충돌 의심", alarm_event_id=3)
        self.denied(production.hold, "U02", lot_no="LOT-2609-041-1", body=body)    # 보류는 사람(SUP·MGR)만
        out = self.call(production.hold, "U10", lot_no="LOT-2609-041-1", body=body)
        hid = out["hold_id"]
        self.assertEqual(out["lot"]["status"], "ON_HOLD")
        holds = self.call(production.holds, "U10", open_only=True)
        self.assertIn(hid, [h["hold_id"] for h in holds])
        # 041-1은 아직 OP-50 실적이 없어(완료 0) 해제할 수 없다 — 검사 뒤 해제하거나 폐기
        with self.assertRaises(PsqlError) as e:
            self.call(production.release, "U10", lot_no="LOT-2609-041-1", body=production.ReleaseIn())
        self.assertIn("1개 이상", str(e.exception))

    def test_04_shipment_flow(self):
        self.db._run("SELECT fn_lot_pass('LOT-2609-038-1', '2026-09-15 09:00+09')", quiet=True)
        cands = self.call(inventory.candidates, "U10")
        self.assertEqual(cands[0]["lot_no"], "LOT-2609-038-1")
        self.denied(inventory.shipment_create, "U02", body=inventory.ShipmentIn(customer_code="CUST-01", due_date="2026-09-16"))
        shp = self.call(inventory.shipment_create, "U10",
                        body=inventory.ShipmentIn(customer_code="CUST-01", due_date="2026-09-16"))["shipment_no"]
        self.call(inventory.line_set, "U10", shipment_no=shp, lot_no="LOT-2609-038-1", body=inventory.LineIn(qty=30))
        with self.assertRaises(AppError):      # 합격 안 된 로트는 줄을 만들 수 없음 (0행)
            self.call(inventory.line_set, "U10", shipment_no=shp, lot_no="LOT-2609-041-1", body=inventory.LineIn(qty=1))
        self.assertEqual(int(self.call(inventory.shipment_confirm, "U10", shipment_no=shp,
                                       body=inventory.ConfirmShipmentIn())["lines"]), 1)
        s = self.call(inventory.shipment, "U02", shipment_no=shp)
        self.assertEqual((s["status"], len(s["lines"])), ("CONFIRMED", 1))
        with self.assertRaises(AppError) as e:          # 보류 로트로 출하 등록 → INVALID_STATE (INV-04)
            self.call(inventory.shipment_create, "U10", body=inventory.ShipmentIn(
                customer_code="CUST-01", due_date="2026-09-16", lines=[inventory.ShipLineIn(lot_no="LOT-2609-041-1", qty=1)]))
        self.assertEqual(e.exception.code, "INVALID_STATE")
        inv = {i["item_no"]: i for i in self.call(inventory.items, "U10")}
        fg = [i for i in inv.values() if i["category"] == "FINISHED"][0]
        self.assertIsNotNone(fg["held_qty"])                                         # 완제품 줄에 보류 수량
        t = self.call(inventory.txn, "U07", body=inventory.TxnIn(item_no="CS-WLUB", kind="RECEIPT", qty=2))
        self.assertTrue(int(t["txn_id"]) > 0)
        with self.assertRaises(AppError) as e:
            self.call(inventory.txn, "U07", body=inventory.TxnIn(item_no="CS-WLUB", kind="ADJUST", qty=-1))
        self.assertEqual(e.exception.code, "VALIDATION")                             # 실사 조정은 사유 필수

    def test_05_quality_upload_and_tools(self):
        f = SimpleNamespace(filename="CMM-01_LOT-2609-038-1_S01_FIRST.csv",
                            file=io.BytesIO(open("tests/data/CMM-01_LOT-2609-038-1_S01_FIRST.csv", "rb").read()))
        r = self.call(quality.upload, "U03", file=f)
        self.assertEqual(r["status"], "SUCCESS")
        ref = self.db.one("quality.imports", problem_only=False, limit=1)["original_file_ref"]
        self.assertTrue(os.path.exists(ref), ref)          # 올린 원본도 보관 (R-80)
        bad = SimpleNamespace(filename="x.csv", file=io.BytesIO(b"\xff\xfe\x00garbage"))
        self.assertEqual(self.call(quality.upload, "U03", file=bad)["status"], "FAILED")
        self.denied(quality.select, "U03", result_id=1, body=quality.SelectIn())
        manual = quality.ResultIn(lot_no="LOT-2609-038-1", part_seq=1, item_seq=1, insp_kind="FIRST", measured_value=45.0)
        self.denied(quality.result_create, "U02", body=manual)    # OP-30 작업자는 측정 담당이 아님 (QLT-02)
        self.denied(quality.result_create, "U07", body=manual)
        self.assertIsInstance(self.call(quality.results, "U07", lot_no="LOT-2609-038-1"), list)   # 조회는 전원
        m = self.call(quality.result_create, "U03", body=quality.ResultIn(
            lot_no="LOT-2609-038-1", part_seq=1, item_seq=1, insp_kind="FIRST", measured_value=45.012))
        self.assertEqual((m["input_method"], m["check_status"]), ("MANUAL", "NEEDS_CHECK"))
        self.assertEqual(self.call(quality.select, "U10", result_id=int(m["result_id"]), body=quality.SelectIn())["check_status"],
                         "CHECKED")
        res = self.call(quality.results, "U03", lot_no="LOT-2609-038-1")
        self.assertIn("MANUAL", {r["input_method"] for r in res})
        summ = self.call(quality.summary, "U10")
        self.assertTrue({"defects", "items"} <= set(summ))
        self.assertTrue(all({"cpk", "chart"} <= set(i) for i in summ["items"]))
        self.assertGreater(len(self.call(quality.imports, "U03")), 0)
        tool = self.call(inventory.tool_change, "U02", tool_id="VF2-01-T05", body=inventory.ToolChangeIn(reason="LIFE_90"))
        self.assertTrue(int(tool["tool_change_id"]) > 0)

    def test_06_reports_and_revisions(self):
        self.call(documents.shift_report_edit, "U10", shift_id="2026-09-15-D",
                  body=documents.EditIn(version=0, changes={"notable_text": "VF2-01 992 정지"}))
        # 다른 교대 반장은 저장·확정 못 함 (RPT-02·03 "그 교대 S" — 처리기가 막고, 확정은 DB 트리거 R-36도 막음)
        self.denied(documents.shift_report_confirm, "U11", shift_id="2026-09-15-D", body=documents.VersionIn(version=1))
        self.denied(documents.shift_report_edit, "U11", shift_id="2026-09-15-D",
                    body=documents.EditIn(version=1, changes={"notable_text": "x"}))
        with self.assertRaises(PsqlError):         # 처리기를 거치지 않아도 DB가 막는다 (R-36)
            self.db.exec("documents.shift_report_confirm", shift_id="2026-09-15-D", actor="U11")
        self.call(documents.shift_report_confirm, "U10", shift_id="2026-09-15-D", body=documents.VersionIn(version=1))
        with self.assertRaises(AppError) as e:     # 확정된 보고서는 PATCH가 아니라 revise
            self.call(documents.shift_report_edit, "U10", shift_id="2026-09-15-D",
                      body=documents.EditIn(version=1, changes={"notable_text": "x"}))
        self.assertEqual(e.exception.code, "INVALID_STATE")
        revs = self.call(documents.revisions, "U02", doc_type="SHIFT_REPORT", doc_key="2026-09-15-D")
        self.assertEqual(revs, [])                 # OPR은 자기가 고친 버전만 (OWN)
        revs = self.call(documents.revisions, "U11", doc_type="SHIFT_REPORT", doc_key="2026-09-15-D")
        self.assertEqual([r["version_no"] for r in revs], ["0", "1"])
        self.denied(documents.daily_report, "U02", work_date="2026-09-15")
        rep = self.call(documents.shift_report, "U02", shift_id="2026-09-15-D")   # OPR도 교대 보고서 보기
        self.assertEqual(rep["carry_over_qty"], "0")
        # 확정 뒤 사유와 함께 고치면 관리자에게 문서 수정 알림 → 관리자가 열면 처리 (FR-AST-03-07, 6.36)
        self.call(documents.shift_report_revise, "U10", shift_id="2026-09-15-D",
                  body=documents.ReviseIn(changes={"notable_text": "VF2-01 992 정지 (48분)"}, reason="정지 시간 보완"))
        nid = self.db._run("SELECT notification_id FROM notification WHERE rule_code = 'DOC_REVISED'", quiet=True).splitlines()[1]
        self.assertEqual(self.call(notifications.read, "U12", notification_id=int(nid))["processed"], "1")
        with self.assertRaises(AppError):          # OPR은 정식 작업기록 이력을 못 봄
            self.call(documents.revisions, "U02", doc_type="WORK_RECORD", doc_key="MR-0901")
        # 일일 보고서: 9/15 야간 보고서가 확정 전이면 MGR 확정 불가 (R-72 잠정)
        self.db.scalar("reports.daily_draft", work_date="2026-09-15")
        d = self.call(documents.daily_report, "U07", work_date="2026-09-15")      # MNT도 조회 (기획서 3.3)
        self.assertIn("2026-09-15-N", d["provisional_shift_ids"])
        with self.assertRaises(AppError) as e:
            self.call(documents.daily_report_confirm, "U12", work_date="2026-09-15",
                      body=documents.VersionIn(version=int(d["current_version"])))
        self.assertEqual(e.exception.code, "INVALID_STATE")
        box = self.call(documents.inbox, "U10", mine=True)
        self.assertTrue(box and all(r["is_todo"] is True for r in box))                # 반장의 할 일
        self.assertFalse([r for r in self.call(documents.inbox, "U02") if r["doc_type"] == "DAILY_REPORT"])
        # 관리자 메모 (2026-10-20 정비 탭 확인 요청 1): 저장(PATCH)·확정 때 받아 조회 응답 memo로
        self.call(documents.daily_report_edit, "U12", work_date="2026-09-15",
                  body=documents.EditIn(version=int(d["current_version"]), changes={"memo": "공구 재고 주문 확인"}))
        d = self.call(documents.daily_report, "U12", work_date="2026-09-15")
        self.assertEqual(d["memo"], "공구 재고 주문 확인")
        night = self.call(documents.shift_report, "U11", shift_id="2026-09-15-N")
        self.call(documents.shift_report_confirm, "U11", shift_id="2026-09-15-N",
                  body=documents.VersionIn(version=int(night["current_version"])))
        d = self.call(documents.daily_report, "U12", work_date="2026-09-15")
        self.call(documents.daily_report_confirm, "U12", work_date="2026-09-15",
                  body=documents.DailyConfirmIn(version=int(d["current_version"]), memo="내일 오전 정비 일정 확인"))
        d = self.call(documents.daily_report, "U12", work_date="2026-09-15")
        self.assertEqual((d["status"], d["memo"]), ("CONFIRMED", "내일 오전 정비 일정 확인"))
        # 필수 정지 ↔ 작업지시서 (확인 요청 2): VF2-01 992 정지(10:58~) → MW-0901, 보고서 시점 상태. 2분 정지(994)는 빠짐
        stops = self.call(documents.shift_report, "U10", shift_id="2026-09-15-D")["stops"]
        self.assertEqual([(s["equipment_id"], s["alarm_code"], s["wo_no"]) for s in stops], [("VF2-01", "992", "MW-0901")])
        self.assertIn(stops[0]["wo_status_at_report"], ("IN_PROGRESS", "DONE"))
        self.assertTrue(float(stops[0]["loss_qty"]) > 0)
        self.assertEqual([s["wo_no"] for s in d["stops"]], ["MW-0901"])                  # 일일 보고서도 같은 목록
        # 보고서 원기록 칸 (2026-10-20 상 4번): 교대 = 로트·병목·정비·순간 정지, 일일 = + 손실 전체·교대 비교·알람·MTTR·재고
        shift = self.call(documents.shift_report, "U10", shift_id="2026-09-15-D")
        self.assertTrue({"lots", "bottleneck", "maintenance", "micro_stops"} <= set(shift))
        self.assertIn("MW-0901", [m["wo_no"] for m in shift["maintenance"]])
        self.assertIn("LOT-2609-041-1", [x["lot_no"] for x in shift["lots"] if x["made_here"] is True])
        self.assertEqual([x["shift_id"] for x in d["shifts"]], ["2026-09-15-D", "2026-09-15-N"])
        self.assertEqual(int(d["alarms"]["total"]), int(d["alarms"]["stop_count"]) + int(d["alarms"]["warn_count"])
                         + int(d["alarms"]["guide_count"]))
        self.assertEqual([x["kind"] for x in d["losses"]][:1], ["FAILURE"])
        fg = d["inventory"]["finished"]
        self.assertEqual(float(fg["end_qty"]), float(fg["start_qty"]) + float(fg["in_qty"]) - float(fg["ship_qty"]) + float(fg["adjust_qty"]))

    def test_07_notifications(self):
        mine = self.call(notifications.mine, "U07", sort="rank")
        self.assertTrue(all("rule_code" in n for n in mine["items"]))
        self.assertEqual(mine["counts"]["total"], sum(1 for n in mine["items"] if n["is_processed"] is False))
        urgent = [n for n in mine["items"] if n["importance"] == "URGENT"]
        self.assertTrue(urgent)
        self.assertEqual(self.call(notifications.ack, "U07", notification_id=int(urgent[0]["notification_id"])), {"ok": True})
        self.assertIn("badge", mine)                                                   # 이브 아이콘 숫자 (2026-10-13)
        self.assertTrue(all(n["delivery_kind"] in ("POPUP", "BUBBLE", "LIST") for n in mine["items"]))
        self.assertTrue(all(n["delivery_kind"] == "POPUP" for n in urgent))             # 긴급 = 팝업
        docs = self.call(notifications.mine, "U07", kind="doc")["items"]
        self.assertTrue(all(n["alert_kind"] == "DOC" for n in docs))                     # 문서 알림 칸 = 문서 알림 규칙 (2026-10-20 — 말풍선 없는 것 포함)
        self.assertEqual(mine["badge"]["total"], sum(1 for n in mine["items"] if n["is_processed"] is False
                                                     and n["alert_kind"] in ("FAULT", "DOC")))  # 아이콘 숫자 = ② + ③
        self.assertIn("active", mine["flood"])                                           # 폭주 상태 (FR-AST-02-12)
        # 반장도 정지 알람 긴급 알림(팝업)을 받는다 (2026-10-11)
        stop_sup = [n for n in self.call(notifications.mine, "U10", status="all")["items"] if n["rule_code"] == "ALARM_STOP"]
        stop_mnt = [n for n in mine["items"] if n["rule_code"] == "ALARM_STOP"]
        if stop_mnt:
            self.assertTrue(stop_sup)
            self.assertEqual(self.call(notifications.ack, "U10", notification_id=int(stop_sup[0]["notification_id"])), {"ok": True})
        # 받지 않은 알림은 1건 보기·읽음도 막힘 (MGR은 전부 보기)
        other = int(self.db._run("SELECT n.notification_id FROM notification n WHERE NOT EXISTS (SELECT 1 FROM "
                                 "notification_recipient r WHERE r.notification_id = n.notification_id AND r.user_id = 'U01') "
                                 "ORDER BY 1 LIMIT 1", quiet=True).splitlines()[1])
        self.denied(notifications.get, "U01", notification_id=other)
        self.denied(notifications.read, "U01", notification_id=other)
        self.denied(notifications.ack, "U01", notification_id=other)                   # 받은 사람만
        self.assertEqual(int(self.call(notifications.get, "U12", notification_id=other)["notification_id"]), other)
        self.assertEqual(int(self.call(notifications.get, "U07", notification_id=int(urgent[0]["notification_id"]))
                             ["notification_id"]), int(urgent[0]["notification_id"]))
        b = self.call(notifications.briefing, "U10")
        self.assertEqual(set(b), {"view", "counts", "lines", "prev_shift", "this_shift"})
        self.assertEqual(b["counts"]["total"], len(b["lines"]))                    # 전체 N = 줄 수
        self.assertEqual(b["lines"][0]["report_rank"], "R0")                       # 잠금·표지 맨 위
        self.assertEqual(b["this_shift"]["total_target_qty"], "90")
        o = self.call(notifications.briefing, "U02")
        self.assertEqual(o["view"], "operator")
        self.assertEqual(set(o["prev_shift"]), {"shift_id", "good_qty", "is_provisional"})
        self.denied(notifications.rule_update, "U10", body=notifications.RuleIn(rule_code="TOOL_LIFE_90", is_enabled=False))
        self.call(notifications.rule_update, "U12", body=notifications.RuleIn(rule_code="TOOL_LIFE_90", is_enabled=False))
        self.assertEqual(self.call(notifications.briefing, "U10", view="operator")["view"], "operator")

    def test_074_briefing_checks(self):
        """브리핑 "먼저 챙길 일" 체크 저장 (2026-10-20): 본인 것만, 거듭 보내도 같은 결과, 교대·사용자별로 따로, 풀기"""
        BC, check, checks = notifications.BriefingCheckIn, notifications.briefing_check, notifications.briefing_checks
        key = "r1/pm:PM-VF2-01-W-05"
        self.assertEqual(self.call(checks, "U10", shift_id="r1/S1")["items"], [])                                # 처음엔 없음
        self.assertEqual(self.call(check, "U10", body=BC(shift_id="r1/S1", item_key=key)),
                         {"shift_id": "r1/S1", "item_key": key, "checked": True})
        self.call(check, "U10", body=BC(shift_id="r1/S1", item_key=key))                                          # 거듭 보내도 1건
        self.call(check, "U10", body=BC(shift_id="r1/S1", item_key="r1/lock", checked=True))
        self.assertEqual([i["item_key"] for i in self.call(checks, "U10", shift_id="r1/S1")["items"]], ["r1/lock", key])   # 같은 시각이면 항목 글자 순
        self.assertEqual(self.call(checks, "U10", shift_id="r1/S2")["items"], [])                                 # 다른 교대와 따로
        self.assertEqual(self.call(checks, "U08", shift_id="r1/S1")["items"], [])                                 # 다른 사람은 못 봄
        for uid in ("U02", "U08", "U10", "U12"):                                                                  # 역할 4개 모두 쓸 수 있음
            self.call(check, uid, body=BC(shift_id="r1/S9", item_key="r1/x"))
            self.assertEqual(len(self.call(checks, uid, shift_id="r1/S9")["items"]), 1)
        self.call(check, "U10", body=BC(shift_id="r1/S1", item_key="r1/lock", checked=False))                     # 풀기
        self.call(check, "U10", body=BC(shift_id="r1/S1", item_key="r1/없는-항목", checked=False))                 # 없는 걸 풀어도 오류 아님
        self.assertEqual([i["item_key"] for i in self.call(checks, "U10", shift_id="r1/S1")["items"]], [key])
        with self.assertRaises(AppError) as e:                                                                     # 공백뿐인 글자는 거절
            self.call(check, "U10", body=BC(shift_id="r1/S1", item_key="   "))
        self.assertEqual(e.exception.status, 422)

    def test_075_role_matrix(self):
        """역할 4개가 같은 화면·API에서 다르게 막히는지 (기획서 13장) — 대표 동작 몇 개를 실제 DB 권한표로"""
        self.assertIsInstance(self.call(maintenance.pm_schedule, "U02"), (list, dict))        # 일정은 전원 (PM-01)
        pm = self.db._run("SELECT pm_record_id FROM pm_record ORDER BY 1 LIMIT 1", quiet=True).splitlines()
        if len(pm) > 1 and pm[1].strip().isdigit():
            self.denied(maintenance.pm_record_get, "U02", pm_record_id=int(pm[1]))           # 실시 기록은 OPR 없음 (13.1)
            self.call(maintenance.pm_record_get, "U10", pm_record_id=int(pm[1]))
        for user in ("U02", "U07", "U10"):                                               # 설정은 MGR만
            self.denied(master.users, user)
        self.call(master.users, "U12")
        for user in ("U02", "U07"):                                                        # 보류는 SUP·MGR
            self.denied(production.hold, user, lot_no="LOT-2609-038-1",
                        body=production.HoldIn(trigger_type="AI_SUSPECT", reason="x", alarm_event_id=3))
        me = {u: auth.me(self.user(u), self.db) for u in ("U02", "U07", "U10", "U12")}
        self.assertEqual({u: m["home"] for u, m in me.items()},                                # 역할별 첫 화면 (NFR-USE-08)
                         {"U02": "SCR-26", "U07": "SCR-04", "U10": "SCR-04", "U12": "SCR-04"})   # 2026-10-13 MNT·MGR도 3D
        self.assertNotIn("DAILY_REPORT", me["U02"]["permissions"])
        self.assertIn("CONFIRM", me["U12"]["permissions"]["DAILY_REPORT"])

    # ---------------- 역할별 범위 (scope) — tests/test_role_matrix.py 의 "*" 줄 ----------------
    def test_091_owned_items(self):
        txn = lambda u, item, kind="RECEIPT", qty=1, reason=None: self.call(  # noqa: E731
            inventory.txn, u, body=inventory.TxnIn(item_no=item, kind=kind, qty=qty, reason=reason))
        self.assertTrue(int(txn("U07", "CS-WLUB")["txn_id"]) > 0)                   # MNT = 정비 소모품
        self.assertTrue(int(txn("U10", "TL-TAP6")["txn_id"]) > 0)                   # SUP = 공구
        for user, item in (("U07", "TL-TAP6"), ("U10", "CS-WLUB"), ("U07", "FG-BRK-A100")):
            with self.subTest(user=user, item=item):
                with self.assertRaises(AppError) as e:
                    txn(user, item)
                self.assertEqual((e.exception.status, e.exception.detail.get("reason")), (403, "NOT_ITEM_OWNER"))
        with self.assertRaises(AppError) as e:                                         # 실사 조정도 같은 규칙
            txn("U07", "RM-6061", kind="ADJUST", qty=-1, reason="실사")
        self.assertEqual(e.exception.status, 403)
        self.denied(inventory.txn, "U02", body=inventory.TxnIn(item_no="TL-TAP6", kind="RECEIPT", qty=1))
        body = inventory.MaterialIn(item_no="RM-6061", qty=10, supplier_cert_no="CERT-9")
        self.denied(inventory.material_receipt, "U07", body=body)                   # 원자재 = SUP 품목
        self.assertTrue(self.call(inventory.material_receipt, "U10", body=body)["material_lot_no"].startswith("MAT-"))
        with self.assertRaises(AppError) as e:                                         # 원자재 아닌 품목을 원자재 로트로
            self.call(inventory.material_receipt, "U10", body=inventory.MaterialIn(item_no="TL-TAP6", qty=1,
                                                                                    supplier_cert_no="X"))
        self.assertEqual(e.exception.status, 422)

    def test_092_own_revisions_and_gates(self):
        no = self.call(maintenance.quick_create, "U02",
                       body=maintenance.QuickIn(equipment_id="VF2-01", action="칩 제거", alarm_event_id=1))["record_no"]
        mine = self.call(documents.revisions, "U02", doc_type="WORK_RECORD", doc_key=no)
        self.assertTrue(mine and all(r["author_user_id"] == "U02" for r in mine))
        # 2026-10-20: 보충용 2점 잠금 알람(2075) 간이 기록은 화면이 False를 보내도 잠금·표지 9칸이 생긴다 (R-32·33)
        a2075 = int(self.db._run("SELECT fn_ingest_alarm('VF2-02', '2075', '2026-09-15 12:10+09', 'LOT-2609-041-1')",
                                 quiet=True).splitlines()[1])
        loto_no = self.call(maintenance.quick_create, "U02",
                            body=maintenance.QuickIn(equipment_id="VF2-02", action="축 윤활유 보충", alarm_event_id=a2075,
                                                     safety_block_required=False))["record_no"]
        self.assertEqual(self.db._run(f"SELECT safety_block_required::text || '/' || (SELECT count(*) FROM work_record_check c "
                                      f"WHERE c.record_no = w.record_no AND c.check_kind = 'LOTO') FROM work_record w "
                                      f"WHERE w.record_no = '{loto_no}'", quiet=True).splitlines()[1], "true/9")
        # 2026-10-20: MNT 문서함 "내 할 일"에 초안(DRAFT) 예방 정비 기록이 나온다 (전에는 없는 상태 EDITING을 찾아 늘 비었음)
        self.db._run("INSERT INTO pm_record (pm_task_id, due_date, done_at, done_by, recorded_by, result, status) "
                     "VALUES ('PM-VF2-02-2.3-01', '2026-10-15', '2026-09-15 12:20+09', 'U07', 'U07', 'NORMAL', 'DRAFT')", quiet=True)
        self.assertIn("PM_RECORD", [r["doc_type"] for r in self.call(documents.inbox, "U07", mine=True)])
        self.assertEqual(self.call(documents.revision, "U02", revision_id=int(mine[0]["revision_id"]))["doc_key"], no)
        other = self.call(documents.revisions, "U10", doc_type="SHIFT_REPORT", doc_key="2026-09-14-N")
        self.assertTrue(other)
        self.assertEqual(self.call(documents.revisions, "U02", doc_type="SHIFT_REPORT", doc_key="2026-09-14-N"), [])
        self.denied(documents.revision, "U02", revision_id=int(other[0]["revision_id"]))   # 번호로 직접 열어도 막힘
        self.call(documents.revision, "U10", revision_id=int(other[0]["revision_id"]))
        # 작업기록 쓰기는 첫 관문에서 SUP·MGR 막힘 (확인은 /check 따로)
        for user in ("U10", "U12"):
            self.denied(maintenance.wr_confirm, user, record_no=no, body=maintenance.VersionIn(version=0))

    def test_093_supervisor_approval_only(self):
        """승인은 반장만. 관리자 승인·취소는 거절. 조회 칸 approved_as_proxy 는 남고, 반장 승인은 대리가 아니다."""
        aid = self.db.scalar("alarms.ingest", equipment_id="VF2-02", alarm_code="254", occurred_at=None, lot_no=None,
                             prev_alarm_event_id=None, is_injected=False, scenario_code=None)
        wo = self.call(maintenance.wo_create, "U07", body=maintenance.WoDraftIn(
            equipment_id="VF2-02", title="반장 승인", symptom="x", alarm_event_id=int(aid)))["wo_no"]
        self.call(maintenance.wo_edit, "U07", wo_no=wo, body=maintenance.EditIn(version=0, changes={"title": "반장 승인 시험"}))
        self.call(maintenance.wo_assign, "U10", wo_no=wo, body=maintenance.AssignIn(mnt_user_id="U07"))
        self.denied(maintenance.wo_approve, "U12", wo_no=wo, body=maintenance.VersionIn(version=1))
        self.denied(maintenance.wo_cancel, "U12", wo_no=wo, body=maintenance.CancelIn(reason="시험"))
        self.denied(maintenance.wo_cancel, "U10", wo_no=wo, body=maintenance.CancelIn(reason="시험"))
        out = self.call(maintenance.wo_approve, "U10", wo_no=wo, body=maintenance.VersionIn(version=1))
        self.assertEqual((out["status"], out["proxy"]), ("APPROVED", False))
        self.assertIs(self.call(maintenance.wo_get, "U10", wo_no=wo)["approved_as_proxy"], False)

    def test_094_qr(self):
        """QR (2026-10-13 가정 [제안]): 조회·입고·실사·출하 전 로트 확인·측정 시작 로트 확인, 찍은 기록"""
        def err(fn, user, **kw):
            with self.assertRaises(AppError) as e:
                self.call(fn, user, **kw)
            return e.exception.status, e.exception.detail.get("reason")

        # 조회: 종류별 상태 + 이 역할이 할 수 있는 일
        item = self.call(qr.scan, "U07", body=qr.ScanIn(code="MOM:ITEM:CS-WLUB"))
        self.assertEqual((item["kind"], item["found"], item["can"]), ("ITEM", True, ["RECEIPT", "STOCKTAKE"]))
        self.assertEqual(self.call(qr.scan, "U10", body=qr.ScanIn(code="CS-WLUB"))["can"], [])   # SUP 품목 아님
        self.assertEqual(self.call(qr.scan, "U02", body=qr.ScanIn(code="MOM:MAT:MAT-2609-05"))["info"]["status"],
                         "AVAILABLE")
        self.assertFalse(self.call(qr.scan, "U02", body=qr.ScanIn(code="MOM:LOT:LOT-2609-999-1"))["found"])
        self.assertEqual(err(qr.scan, "U02", body=qr.ScanIn(code="hello")), (422, "BAD_QR"))
        lab = self.call(qr.label, "U10", kind="item", no="tl-em10")
        self.assertEqual(lab["payload"], "MOM:ITEM:TL-EM10")
        # 입고·실사: 그 품목 관리 역할만 (INV-02와 같음)
        before = float(self.call(qr.scan, "U07", body=qr.ScanIn(code="CS-AFLT"))["info"]["on_hand_qty"])
        r = self.call(qr.qr_inventory, "U07", body=qr.QrInventoryIn(code="MOM:ITEM:CS-AFLT", kind="RECEIPT", qty=2))
        self.assertTrue(int(r["txn_id"]) > 0)
        self.assertEqual(err(qr.qr_inventory, "U07", body=qr.QrInventoryIn(code="TL-TAP6", kind="RECEIPT", qty=1)),
                         (403, "NOT_ITEM_OWNER"))
        self.denied(qr.qr_inventory, "U02", body=qr.QrInventoryIn(code="CS-AFLT", kind="RECEIPT", qty=1))
        self.assertEqual(err(qr.qr_inventory, "U10", body=qr.QrInventoryIn(code="RM-6061", kind="RECEIPT", qty=1))[0],
                         422)                                                    # 원자재는 로트로 입고
        self.assertEqual(err(qr.qr_inventory, "U10", body=qr.QrInventoryIn(code="MAT-2609-05", kind="RECEIPT",
                                                                             qty=1)), (422, "WRONG_QR_KIND"))
        same = self.call(qr.qr_inventory, "U07", body=qr.QrInventoryIn(code="CS-AFLT", kind="STOCKTAKE",
                                                                          counted_qty=before + 2))
        self.assertIsNone(same["txn_id"])                                        # 차이 없음 → 거래 없음
        self.assertEqual(err(qr.qr_inventory, "U07", body=qr.QrInventoryIn(code="CS-AFLT", kind="STOCKTAKE",
                                                                             counted_qty=before)), (422, None))   # 사유 필수
        adj = self.call(qr.qr_inventory, "U07", body=qr.QrInventoryIn(code="CS-AFLT", kind="STOCKTAKE",
                                                                         counted_qty=before, reason="실사 2개 부족"))
        self.assertEqual(float(adj["diff"]), -2.0)
        self.assertEqual(float(self.call(qr.scan, "U07", body=qr.ScanIn(code="CS-AFLT"))["info"]["on_hand_qty"]), before)
        # 출하 전 로트 확인 (작성 중 출하만): 맞는 로트 OK, 출하 줄에 없는 로트 MISMATCH (기록은 남음)
        self.db._run("SELECT fn_lot_pass('LOT-2609-040-1', '2026-09-15 10:00+09')", quiet=True)
        cand = {c["lot_no"]: c for c in self.call(inventory.candidates, "U10")}
        lot = next(iter(cand))
        shp = self.call(inventory.shipment_create, "U10", body=inventory.ShipmentIn(
            customer_code="CUST-02", due_date="2026-09-16", lines=[inventory.ShipLineIn(lot_no=lot, qty=1)]))["shipment_no"]
        other = "LOT-2609-041-1"
        bad = self.call(qr.ship_check, "U10", shipment_no=shp, body=qr.ShipCheckIn(code="MOM:LOT:" + other))
        self.assertEqual((bad["ok"], bad["result"], bad["unchecked"]), (False, "MISMATCH", [lot]))
        self.denied(qr.ship_check, "U02", shipment_no=shp, body=qr.ShipCheckIn(code=lot))
        # QR 확인 필수 설정이면 안 찍은 로트가 있을 때 확정이 막힘
        settings = inventory.get_settings()
        settings.qr_ship_check_required = True
        try:
            self.assertEqual(err(inventory.shipment_confirm, "U10", shipment_no=shp, body=inventory.ConfirmShipmentIn()),
                             (409, "QR_NOT_CHECKED"))
            ok = self.call(qr.ship_check, "U10", shipment_no=shp, body=qr.ShipCheckIn(code=lot))
            self.assertEqual((ok["ok"], ok["unchecked"], ok["total"]), (True, [], 1))
            self.assertTrue(self.call(inventory.shipment, "U10", shipment_no=shp)["lines"][0]["qr_checked_at"])
            self.call(inventory.shipment_confirm, "U10", shipment_no=shp,
                      body=inventory.ConfirmShipmentIn(fifo_skip_reason="QR 시험"))
        finally:
            settings.qr_ship_check_required = False
        self.assertEqual(err(qr.ship_check, "U10", shipment_no=shp, body=qr.ShipCheckIn(code=lot)), (409, "NOT_DRAFT"))
        log = self.call(qr.scans, "U12", shipment_no=shp)
        self.assertEqual(sorted(x["result"] for x in log), ["MISMATCH", "OK"])
        # 측정 시작: 부품 꼬리표 로트 QR이 지시와 같아야 함, 못 찍으면 사유(수동)
        ins = [i for i in self.call(quality.instructions, "U03") if i["status"] == "ISSUED"][0]
        iid = int(ins["instruction_id"])
        self.assertEqual(err(quality.start, "U03", instruction_id=iid, body=quality.StartIn(scanned_code=other)),
                         (409, "LOT_MISMATCH"))
        self.assertEqual(err(quality.start, "U03", instruction_id=iid, body=quality.StartIn())[0], 422)
        self.assertEqual(self.call(quality.start, "U03", instruction_id=iid,
                                   body=quality.StartIn(scanned_code="MOM:LOT:" + ins["lot_no"]))["lot_no"], ins["lot_no"])
        started = self.call(qr.scans, "U10", purpose="MEASURE_START")
        self.assertEqual((started[0]["result"], int(started[0]["instruction_id"])), ("OK", iid))

    def test_08_assistant_and_ingest(self):
        opr_tools = {t["name"] for t in assistant.tool_list("U02", self.db)}
        self.assertNotIn("work_records", opr_tools)     # OPR은 정식 작업기록 조회 불가
        self.assertIn("work_records", {t["name"] for t in assistant.tool_list("U07", self.db)})
        out = assistant.tool_call("kpi", assistant.ToolCallIn(on_behalf_of="U10",
                                                             args={"from_date": "2026-09-15", "to_date": "2026-09-15"}),
                                  REQ, self.db)
        self.assertGreater(len(out["rows"]), 0)
        with self.assertRaises(AppError):
            assistant.tool_call("work_records", assistant.ToolCallIn(on_behalf_of="U02"), REQ, self.db)
        # AI 비서 서비스가 없으면 응답 없음(NO_RESPONSE, 화면은 기본 문구) — 질문은 채팅 기록에 남는다 (chat_log, 2026-10-13)
        out = self.call(assistant.chat, "U02", body=assistant.ChatIn(question="VF2-01 주축 부하 괜찮아?",
                                                                      context={"screen": "SCR-26"}), request=REQ)
        self.assertEqual((out["status"], out["answer"]), ("NO_RESPONSE", None))
        hist = self.call(assistant.chat_history, "U02", since=None, limit=10)
        self.assertEqual([h["question"] for h in hist][:1], ["VF2-01 주축 부하 괜찮아?"])
        self.assertEqual(self.call(assistant.chat_history, "U07", since=None, limit=10), [])     # 본인 것만
        with self.assertRaises(AppError) as e:
            self.call(assistant.chat_one, "U07", chat_id=int(out["chat_id"]))
        self.assertEqual(e.exception.status, 404)
        follow = self.call(assistant.chat, "U02", body=assistant.ChatIn(question="그럼 언제 점검해?",
                                                                         prev_chat_id=int(out["chat_id"])), request=REQ)
        self.assertEqual(int(self.call(assistant.chat_one, "U02", chat_id=int(follow["chat_id"]))["prev_chat_id"]),
                         int(out["chat_id"]))
        # 채팅 권한 (2026-10-13): MTTR·센서 도구는 MNT·MGR만
        self.assertNotIn("reliability", {t["name"] for t in assistant.tool_list("U10", self.db)})
        self.assertNotIn("sensor_trend", {t["name"] for t in assistant.tool_list("U02", self.db)})
        self.assertIn("reliability", {t["name"] for t in assistant.tool_list("U07", self.db)})
        self.assertIn("sensor_trend", {t["name"] for t in assistant.tool_list("U12", self.db)})
        with self.assertRaises(AppError) as e:          # 시연 모드가 아니면 시연 데이터 되돌리기 불가 (SIM-03)
            master.sim_reset(self.user("U12"), self.db)
        self.assertEqual(e.exception.status, 403)
        sid = ingest.state(ingest.StateIn(equipment_id="VF2-02", state_code="IDLE", at="2026-09-15T13:05:00+09:00",
                                          execution="READY", reason_suggested_code="M01"), self.db)["state_log_id"]
        self.assertTrue(int(sid) > 0)
        ingest.production(ingest.ProductionIn(lot_no="LOT-2609-041-1", equipment_id="VF2-02", worker_user_id="U02", gq=1),
                          self.db)
        ingest.wip(ingest.WipIn(buffer_code="WIP-30-40", wip_qty=12), self.db)
        po = ingest.order(ingest.OrderIn(product_code="BRK-A100", order_qty=36, due_at="2026-09-17T17:00:00+09:00"),
                          self.db)["order_no"]
        lot = ingest.lot_start(ingest.LotStartIn(order_no=po, material_lot_no="MAT-2609-05", input_qty=36), self.db)["lot_no"]
        self.assertEqual(lot, "LOT-" + po[3:] + "-1")
        ingest.lot_arrived(lot, self.db)
        sensor = self.db._run("SELECT sensor_code FROM sensor_item ORDER BY 1 LIMIT 1", quiet=True).splitlines()[1]
        n = ingest.sensors(ingest.SensorsIn(equipment_id="VF2-01", rows=[
            ingest.SensorRow(sensor_code=sensor, sampled_at="2026-09-15T13:00:00+09:00", value=1.5)]), self.db)
        self.assertEqual(n["inserted"], 1)
        # 시뮬레이터 시계 입구 (2026-10-20): 시연 모드도 MOM_SIM_SYNC도 아니면(공용 DB 서버) 409 — 시연 서버 DB 중계가 스스로 꺼진다
        # (2026-10-23 MOM_SIM_SYNC가 생기며 이유 코드가 SIM_SYNC_OFF로 바뀜 — 2026-10-24 시험을 맞춤)
        with self.assertRaises(AppError) as e:
            ingest.clock(ingest.ClockIn(sim_at="2026-09-15T13:00:00+09:00", speed=60), self.db)
        self.assertEqual((e.exception.status, e.exception.detail.get("reason")), (409, "SIM_SYNC_OFF"))

    def test_099_pm_start_end(self):
        # [정비 시작]·[정비 끝 · 실시 기록] (FR-MNT-04-10, 2026-10-20): MAINT 구간 = 두 버튼 사이. 시계를 앞으로 돌리므로 맨 끝에 둔다
        self.db._run("SELECT fn_sim_set('SIM', '2026-09-15 16:00+09', 1, true)", quiet=True)
        self.denied(maintenance.pm_start, "U02", pm_task_id="PM-VF2-02-2.3-01", body=None)
        st = self.call(maintenance.pm_start, "U07", pm_task_id="PM-VF2-02-2.3-01", body=None)
        self.assertEqual(st["maint"]["equipment_id"], "VF2-02")
        self.db._run("SELECT fn_sim_set('SIM', '2026-09-15 17:30+09', 1, true)", quiet=True)
        done = self.call(maintenance.pm_end, "U07", pm_record_id=st["pm_record_id"],
                         body=maintenance.PmEndIn(result="REFILLED", measured_value=1.5, measured_unit="L"))
        self.assertEqual((done["result"], done["status"]), ("REFILLED", "DRAFT"))
        self.assertIsNone(self.db.one("maintenance.pm_open_maint", pm_record_id=st["pm_record_id"]))


if __name__ == "__main__":
    unittest.main()
