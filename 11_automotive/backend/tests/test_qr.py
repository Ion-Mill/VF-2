"""QR 내용 규칙 (app/domain/qr.py) — DB 없이"""
import unittest

from app.domain import qr


class TestQr(unittest.TestCase):
    def test_parse_prefixed(self):
        self.assertEqual(qr.parse("MOM:LOT:LOT-2609-041-1"), ("LOT", "LOT-2609-041-1"))
        self.assertEqual(qr.parse("MOM:MAT:MAT-2609-12"), ("MAT", "MAT-2609-12"))
        self.assertEqual(qr.parse("MOM:ITEM:TL-EM10"), ("ITEM", "TL-EM10"))
        self.assertEqual(qr.parse("  mom:item:cs-wlub \n"), ("ITEM", "CS-WLUB"))      # 공백·소문자는 고쳐 읽음

    def test_parse_bare_number(self):
        # 이미 붙은 바코드(번호만)·손으로 친 번호도 번호 모양으로 알아본다
        self.assertEqual(qr.parse("LOT-2609-038-1"), ("LOT", "LOT-2609-038-1"))
        self.assertEqual(qr.parse("MAT-2609-05"), ("MAT", "MAT-2609-05"))
        self.assertEqual(qr.parse("FG-BRK-A100"), ("ITEM", "FG-BRK-A100"))

    def test_parse_rejects(self):
        for bad in ("", "   ", "MOM:LOT:MAT-2609-12", "MOM:BOX:LOT-2609-041-1", "ABC:LOT:LOT-2609-041-1",
                    "LOT-26-1", "hello", "MOM:LOT", "X" * 200):
            with self.subTest(bad=bad), self.assertRaises(qr.QrError):
                qr.parse(bad)

    def test_payload_round_trip(self):
        for kind, no in (("LOT", "LOT-2609-041-1"), ("MAT", "MAT-2609-12"), ("ITEM", "TL-TAP6")):
            self.assertEqual(qr.parse(qr.payload(kind, no)), (kind, no))
        with self.assertRaises(qr.QrError):
            qr.payload("ITEM", "LOT-2609-041-1")


if __name__ == "__main__":
    unittest.main()
