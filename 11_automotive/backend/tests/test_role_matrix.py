"""역할 × API 권한 기대표 — API명세서_v1.md 2장 "역할" 칸과 기획서 13.1·13.2를 손으로 옮긴 것.

실제 권한(시드 role_permission + 처리기의 require)과 한 칸이라도 다르면 실패한다.
새 API를 만들면 여기에도 한 줄 넣어야 통과한다 (빠뜨린 API가 없게).
표기: 역할 순서 OPR·MNT·SUP·MGR, 글자 = 첫 관문 통과, '.' = 403.
"*" 표시 줄은 관문 뒤에서 범위·대상으로 한 번 더 좁힌다 — tests/test_routers_db.py 가 그 동작을 DB로 확인한다.
"""
import unittest

from tests.role_matrix_util import actual_matrix, seed_table

ALL = "OMSM"

EXPECTED = {
    # 설정·보관 (SET-01~03, 13.2 "설비·사용자·알림 규칙·목표 수량 설정" = G)
    ("GET", "/api/admin/retention"): "...M",
    ("GET", "/api/settings/targets"): "...M", ("PATCH", "/api/settings/targets"): "...M",
    ("GET", "/api/settings/users"): "...M", ("PATCH", "/api/settings/users"): "...M",
    ("GET", "/api/settings/notification-rules"): "...M", ("PATCH", "/api/settings/notification-rules"): "...M",
    ("POST", "/api/sim/snapshot"): "...M",
    # 3D 라인 뷰·생산 (LINE-01~07 전)
    ("GET", "/api/line/layout"): ALL, ("GET", "/api/line/twin"): ALL, ("GET", "/api/replay"): ALL,
    ("GET", "/api/production/target"): ALL, ("GET", "/api/production/orders"): ALL,
    ("GET", "/api/kpi"): ALL, ("GET", "/api/kpi/stops"): ALL,
    ("GET", "/api/alarms"): ALL, ("GET", "/api/alarms/{alarm_event_id}"): ALL,
    ("GET", "/api/downtimes"): ALL,
    ("PATCH", "/api/downtimes/{state_log_id}"): "OMS.",            # * LINE-08 입력 O·M / 확정 S (본문 confirm으로 나눔)
    # 알림·브리핑·비서 (NTF·AST)
    ("GET", "/api/notifications"): ALL, ("GET", "/api/notifications/{notification_id}"): ALL,
    ("POST", "/api/notifications/{notification_id}/read"): ALL,     # * 받는 사람 (MGR은 표시만)
    ("POST", "/api/notifications/{notification_id}/resolve"): ALL,  # * 규칙의 처리 역할 (DB)
    ("POST", "/api/notifications/{notification_id}/ack"): ALL,      # * 받는 사람
    ("GET", "/api/assistant/briefing"): ALL,                        # * AST-01 전형 S·M·G / 요약형 O
    ("GET", "/api/assistant/briefing/checks"): ALL, ("POST", "/api/assistant/briefing/checks"): ALL,   # * 본인 체크만 (2026-10-20)
    ("POST", "/api/assistant/chat"): ALL,                           # * 답은 역할이 볼 수 있는 도구만 (MTTR·센서 = M·G)
    ("GET", "/api/assistant/chat"): ALL, ("GET", "/api/assistant/chat/{chat_id}"): ALL,   # * 본인 채팅 기록만 (30일)
    ("POST", "/api/assistant/transcribe"): ALL, ("GET", "/api/assistant/voice"): ALL,     # 채팅 마이크 (2026-10-20 [제안]) — 채팅과 같은 권한
    # 정비 (MNT·PM)
    ("GET", "/api/maint/guide-card/{alarm_event_id}"): ALL,
    ("GET", "/api/maint/work-orders"): ALL, ("GET", "/api/maint/work-orders/{wo_no}"): ALL,
    ("POST", "/api/maint/work-orders"): ".M..", ("PATCH", "/api/maint/work-orders/{wo_no}"): ".M..",
    ("POST", "/api/maint/work-orders/{wo_no}/assign"): "..S.",
    ("POST", "/api/maint/work-orders/{wo_no}/approve"): "..S.",      # 반장만
    ("POST", "/api/maint/work-orders/{wo_no}/start"): ".M..",        # * 담당 M만
    ("POST", "/api/maint/work-orders/{wo_no}/cancel"): "....",       # 취소 권한 없음
    ("GET", "/api/maint/work-records"): ALL, ("GET", "/api/maint/work-records/{record_no}"): ALL,   # * OPR은 간이만
    ("POST", "/api/maint/work-records"): ".M..",
    ("PATCH", "/api/maint/work-records/{record_no}"): "OM..",        # * 정식은 M만 (MNT-09), 간이는 O·M
    ("POST", "/api/maint/work-records/{record_no}/checks/{check_seq}"): "OM..",
    ("PUT", "/api/maint/work-records/{record_no}/parts"): "OM..",
    ("POST", "/api/maint/work-records/{record_no}/assist"): ".M..",
    ("POST", "/api/maint/work-records/{record_no}/confirm"): "OM..",  # * 정식 M (MNT-11)
    ("POST", "/api/maint/work-records/{record_no}/check"): "..S.",
    ("POST", "/api/maint/quick-records"): "OM..", ("POST", "/api/maint/quick-records/{record_no}/confirm"): "OM..",
    ("GET", "/api/maint/pm-schedule"): ALL,                          # PM-01 전
    ("POST", "/api/maint/pm-records"): ".M..",
    ("GET", "/api/maint/pm-records/{pm_record_id}"): ".MSM",         # 13.1 OPR —
    ("PATCH", "/api/maint/pm-records/{pm_record_id}"): ".M..",
    ("POST", "/api/maint/pm-records/{pm_record_id}/confirm"): ".M..",
    ("POST", "/api/maint/pm-tasks/{pm_task_id}/start"): ".M..",        # [정비 시작]·[정비 끝] (FR-MNT-04-10, 2026-10-20)
    ("POST", "/api/maint/pm-records/{pm_record_id}/end"): ".M..",
    # 로트·품질 (LOT·QLT)
    ("GET", "/api/lots"): ALL, ("GET", "/api/lots/{lot_no}"): ALL, ("GET", "/api/lots/{lot_no}/trace"): ALL,
    ("GET", "/api/lots/suspects"): ALL,   # 의심 로트 제안 (2026-10-20, LOT_TRACE 보기 = 추적과 같음)
    ("GET", "/api/holds"): ALL, ("POST", "/api/lots/{lot_no}/judge"): "..S.",
    ("POST", "/api/lots/{lot_no}/hold"): "..SM", ("POST", "/api/lots/{lot_no}/release"): "..SM",
    ("POST", "/api/lots/{lot_no}/scrap"): "..S.", ("POST", "/api/lots/{lot_no}/scrap/approve"): "...M",
    ("POST", "/api/holds/{hold_id}/resume-normal"): "..SM",          # R-29 (권한 = 보류와 같음, 확인자 SUP는 DB 트리거)
    ("GET", "/api/inspection/results"): ALL,
    ("POST", "/api/inspection/results"): "O.S.",                     # * O는 측정 담당(OP-50)만
    ("POST", "/api/inspection/results/{result_id}/select"): "..S.",
    ("GET", "/api/inspection/cmm-imports"): ALL, ("POST", "/api/inspection/cmm-imports"): "O.S.",
    ("GET", "/api/inspection/instructions"): ALL, ("POST", "/api/inspection/instructions"): "O.S.",
    ("POST", "/api/inspection/instructions/{instruction_id}/start"): "O...",
    ("GET", "/api/quality/summary"): ALL, ("GET", "/api/quality/cpk"): ALL, ("GET", "/api/quality/defects"): ALL,
    ("POST", "/api/quality/items/{product_code}/{item_seq}/resume-sampling"): "...M",   # 전수 → 보통 (DOC-06 §5.2)
    # 재고·출하·공구 (INV·TOOL)
    ("GET", "/api/inventory"): ALL, ("GET", "/api/inventory/{item_no}/txns"): ALL,
    ("POST", "/api/inventory/txns"): ".MS.",                         # * 그 품목 관리 역할 (소모품 M / 공구·원자재·완제품 S)
    ("PATCH", "/api/inventory/items/{item_no}/safety-stock"): "...M",
    ("POST", "/api/raw-lots"): ".MS.",                               # * 원자재 = S 품목 → M은 범위에서 막힘
    ("POST", "/api/raw-lots/{material_lot_no}/inspect"): "..S.",
    ("GET", "/api/shipments"): ALL, ("GET", "/api/shipments/candidates"): ALL, ("GET", "/api/shipments/{shipment_no}"): ALL,
    ("POST", "/api/shipments"): "..S.", ("PATCH", "/api/shipments/{shipment_no}"): "..S.",
    ("PUT", "/api/shipments/{shipment_no}/lines/{lot_no}"): "..S.",
    ("DELETE", "/api/shipments/{shipment_no}/lines/{lot_no}"): "..S.",
    ("POST", "/api/shipments/{shipment_no}/confirm"): "..S.",
    # QR (2026-10-13 가정 [제안] — docs/품질·재고관리/README.md): 조회·라벨·기록은 전원, 입고·실사는 INV-02와 같음, 출하 확인은 S
    ("POST", "/api/qr/scan"): ALL, ("GET", "/api/qr/label/{kind}/{no}"): ALL, ("GET", "/api/qr/scans"): ALL,
    ("POST", "/api/qr/inventory"): ".MS.",                           # * 그 품목 관리 역할 (INV-02와 같음)
    ("POST", "/api/shipments/{shipment_no}/qr-check"): "..S.",
    ("GET", "/api/tools"): ALL, ("GET", "/api/tools/{tool_id}/changes"): ALL, ("POST", "/api/tools/{tool_id}/change"): "OM..",
    # 보고서·문서 (RPT·DOC·DOCS)
    ("GET", "/api/reports/shift/{shift_id}"): ALL,
    ("PATCH", "/api/reports/shift/{shift_id}"): "..S.",              # * 그 교대 S
    ("POST", "/api/reports/shift/{shift_id}/confirm"): "..S.", ("POST", "/api/reports/shift/{shift_id}/revise"): "..S.",
    ("GET", "/api/reports/daily/{work_date}"): ".MSM",               # RPT-05 조회 S·M·G (OPR —)
    ("PATCH", "/api/reports/daily/{work_date}"): "...M", ("POST", "/api/reports/daily/{work_date}/confirm"): "...M",
    ("POST", "/api/reports/daily/{work_date}/revise"): "...M",
    ("GET", "/api/documents"): ALL,                                  # * 역할분
    ("GET", "/api/documents/{doc_type}/{doc_key}/revisions"): ALL,    # * OPR = 자기 것
    ("GET", "/api/documents/revisions/{revision_id}"): ALL,           # * OPR = 자기 것
    ("GET", "/api/internal-docs"): ALL, ("GET", "/api/internal-docs/{doc_no}"): ALL,
    ("GET", "/api/internal-docs/{doc_no}/sections/{section}"): ALL,
    ("POST", "/api/internal-docs/{doc_no}/revisions/{rev}/approve"): "...M",
    # 화면 → 백엔드 전환 C2 (2026-10-23): 화면 한 번에 읽기 — 각 화면의 상세 조회와 같은 권한
    ("GET", "/api/reports/shift"): ALL, ("GET", "/api/reports/daily"): ".MSM",
    ("GET", "/api/documents/revisions"): ALL,                        # * OPR = 자기 것
    ("GET", "/api/maint/history"): ALL, ("GET", "/api/lots/screen"): ALL,
    ("GET", "/api/inventory/screen"): ALL, ("GET", "/api/tools/changes"): ALL,
    # 시뮬레이터가 주인인 기록을 넘기는 문 (MOM_SIM_URL이 있을 때만) — 같은 일을 하는 정식 API와 같은 권한
    ("POST", "/api/sim/work-record-confirmed"): "OM..",              # 작업기록서·간이 기록 확정과 같음
    ("POST", "/api/sim/pm-start"): ".M..", ("POST", "/api/sim/pm-end"): ".M..",
}

# 로그인만 보는 API (처리기 안에서 시연 모드·MGR 등을 따로 본다)
LOGIN_ONLY = {"/api/auth/login", "/api/auth/logout", "/api/demo/role", "/api/me", "/api/codes", "/api/dataset",
              "/api/sim/clock", "/api/sim/inject", "/api/sim/reset", "/api/sim/fire", "/api/stream/events",
              "/api/assist/{kind}"}     # 비서가 다듬은 문장 묻기 (2026-10-24) — 문장만, 운영 데이터를 바꾸지 않음


class TestRoleMatrix(unittest.TestCase):
    def setUp(self):
        self.table = seed_table()
        self.actual = actual_matrix(self.table)

    def test_every_protected_api_is_listed(self):
        protected = {k for k, v in self.actual.items() if v not in ("svc", "login")}
        self.assertEqual(sorted(protected - set(EXPECTED)), [], "기대표에 없는 API — API명세서·기획서 13장을 보고 한 줄 추가")
        self.assertEqual(sorted(set(EXPECTED) - protected), [], "기대표에만 있는 API")

    def test_matrix_matches_spec(self):
        diffs = [f"{m} {p}: 기대 {EXPECTED[(m, p)]} / 실제 {self.actual[(m, p)]}"
                 for (m, p) in sorted(EXPECTED) if self.actual.get((m, p)) != EXPECTED[(m, p)]]
        self.assertEqual(diffs, [], "\n".join(diffs))

    def test_unguarded_apis_are_only_login_or_service(self):
        self.assertEqual({p for (m, p), v in self.actual.items() if v == "login"}, LOGIN_ONLY)
        svc = {p for (m, p), v in self.actual.items() if v == "svc"}
        self.assertTrue(all(p.startswith(("/api/ingest/", "/api/assistant/")) for p in svc), svc)

    def test_scopes(self):
        t = self.table
        self.assertEqual(t.scope("OPR", "BRIEFING", "VIEW"), "SUMMARY")
        self.assertEqual(t.scope("OPR", "REVISION_HISTORY", "VIEW"), "OWN")
        self.assertEqual(t.scope("SUP", "WORK_ORDER", "APPROVE"), "ALL")
        self.assertIsNone(t.scope("MGR", "WORK_ORDER", "APPROVE"))
        self.assertIsNone(t.scope("MGR", "WORK_ORDER", "CANCEL"))
        self.assertIsNone(t.scope("SUP", "WORK_ORDER", "CANCEL"))
        self.assertEqual({t.scope("MNT", "INV_RECEIPT", "INPUT"), t.scope("SUP", "INV_RECEIPT", "INPUT")}, {"OWNED_ITEMS"})
        targets = {tg for (_r, tg, _a) in t._grants}
        self.assertEqual([tg for tg in sorted(targets) if not t.allows("MGR", tg, "VIEW")], [], "MGR은 모든 조회 (D-11)")


if __name__ == "__main__":
    unittest.main()
