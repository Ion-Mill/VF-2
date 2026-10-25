"""채팅 음성 입력 — 백엔드(8020)가 비서(8100)의 POST /transcribe 로 소리를 넘기는 쪽 시험 (2026-10-20).
진짜 비서·네트워크는 쓰지 않는다: urllib.request.urlopen 을 가짜로 바꿔 보낸 머리말·본문과 오류 바꾸기(7개 코드)를 확인한다."""
import asyncio
import io
import json
import unittest
import urllib.error
from types import SimpleNamespace
from unittest import mock

from tests.stubs_loader import use_stubs_if_needed

use_stubs_if_needed()

from app.assistant import client  # noqa: E402
from app.errors import ASSISTANT_UNAVAILABLE, CODES, AppError  # noqa: E402
from app.routers import assistant as R  # noqa: E402

SETTINGS = SimpleNamespace(assistant_url="http://127.0.0.1:8100/", assistant_key="k-test", assistant_timeout_seconds=130.0)


class Resp:
    def __init__(self, body):
        self._b = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(status, body):
    raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
    return urllib.error.HTTPError("http://x", status, "err", {}, io.BytesIO(raw))


class TestVoiceClient(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(client, "get_settings", return_value=SETTINGS)
        p.start()
        self.addCleanup(p.stop)
        self.sent = []

    def fake_urlopen(self, reply):
        def go(req, timeout):
            self.sent.append({"url": req.full_url, "method": req.get_method(), "data": req.data, "headers": dict(req.header_items()), "timeout": timeout})
            if isinstance(reply, Exception):
                raise reply
            return Resp(reply)
        return mock.patch.object(client.urllib.request, "urlopen", side_effect=go)

    def test_transcribe_sends_raw_bytes_with_service_key_and_returns_fields(self):
        with self.fake_urlopen({"text": "알람 원인이 뭐야", "reason": None, "seconds": 3.2, "ms": 4500, "extra": "버린다"}):
            out = client.voice_transcribe(b"AUDIO")
        self.assertEqual(out, {"text": "알람 원인이 뭐야", "reason": None, "seconds": 3.2, "ms": 4500})
        s = self.sent[0]
        self.assertEqual((s["url"], s["method"], s["data"]), ("http://127.0.0.1:8100/transcribe", "POST", b"AUDIO"))
        self.assertEqual(s["headers"]["X-service-key"], "k-test")
        self.assertEqual(s["headers"]["Content-type"], "application/octet-stream")
        self.assertEqual(s["timeout"], client.VOICE_TIMEOUT_S)          # 130초가 아니라 짧은 제한

    def test_empty_text_keeps_reason(self):
        with self.fake_urlopen({"text": "", "reason": "no_speech", "seconds": 1.0, "ms": 200}):
            out = client.voice_transcribe(b"A")
        self.assertEqual((out["text"], out["reason"]), ("", "no_speech"))

    def test_status(self):
        with self.fake_urlopen({"enabled": True, "ready": True, "max_seconds": 20.0}):
            self.assertEqual(client.voice_status(), {"enabled": True, "ready": True, "max_seconds": 20.0})
        self.assertEqual((self.sent[0]["method"], self.sent[0]["url"], self.sent[0]["data"]), ("GET", "http://127.0.0.1:8100/voice/status", None))

    def test_assistant_errors_become_the_seven_spec_codes_and_keep_the_reason(self):
        cases = [(404, "VOICE_OFF", 404, "NOT_FOUND"), (400, "BAD_AUDIO", 422, "VALIDATION"), (413, "AUDIO_TOO_LARGE", 422, "VALIDATION"),
                 (413, "AUDIO_TOO_LONG", 422, "VALIDATION"), (429, "VOICE_BUSY", 503, ASSISTANT_UNAVAILABLE),
                 (503, "VOICE_TIMEOUT", 503, ASSISTANT_UNAVAILABLE), (503, "VOICE_FAILED", 503, ASSISTANT_UNAVAILABLE)]
        for http, code, want_status, want_code in cases:
            with self.subTest(code=code), self.fake_urlopen(http_error(http, {"code": code, "message": "비서 안쪽 글", "detail": {}})):
                with self.assertRaises(AppError) as cm:
                    client.voice_transcribe(b"A")
                e = cm.exception
                self.assertEqual((e.status, e.code, e.detail["reason"]), (want_status, want_code, code))
                self.assertIn(e.code, CODES)
                self.assertNotIn("비서 안쪽 글", e.message)             # 비서가 보낸 글을 그대로 화면에 넘기지 않는다

    def test_unknown_errors_are_assistant_unavailable(self):
        for err, reason in [(http_error(401, {"code": "UNAUTHORIZED"}), "SERVICE_KEY"), (http_error(500, b"<html>"), "HTTP_500"),
                            (urllib.error.URLError("refused"), "URLError"), (TimeoutError(), "TimeoutError")]:
            with self.subTest(reason=reason), self.fake_urlopen(err):
                with self.assertRaises(AppError) as cm:
                    client.voice_transcribe(b"A")
                self.assertEqual((cm.exception.status, cm.exception.code, cm.exception.detail["reason"]), (503, ASSISTANT_UNAVAILABLE, reason))

    def test_bad_reply_shapes(self):
        for bad in ({"text": 5}, {"nope": 1}, [1, 2]):
            with self.subTest(bad=bad), self.fake_urlopen(bad):
                with self.assertRaises(AppError) as cm:
                    client.voice_transcribe(b"A")
                self.assertEqual(cm.exception.detail["reason"], "FORMAT")

    def test_chat_503_keeps_only_the_public_failure_sentence(self):
        base = "비서가 지금 답하지 못합니다. 잠시 후 다시 시도해 주세요"
        shown = base + "\nGemini가 바빠 503을 냈습니다."
        with self.fake_urlopen(http_error(503, {"code": "ASSISTANT_UNAVAILABLE", "message": shown, "detail": {"retryable": True}})):
            with self.assertRaises(AppError) as cm:
                client.call("/chat", {"question": "잠금 표지 순서"})
        self.assertEqual(cm.exception.message, shown)
        self.assertEqual(cm.exception.detail["reason"], "ASSISTANT_MESSAGE")
        leak = base + "\nsk-secret /opt/claude"
        with self.fake_urlopen(http_error(503, {"code": "ASSISTANT_UNAVAILABLE", "message": leak})):
            with self.assertRaises(AppError) as cm:
                client.call("/chat", {"question": "잠금 표지 순서"})
        self.assertNotIn("sk-secret", cm.exception.message)
        self.assertEqual(cm.exception.detail["reason"], "HTTP_503")

    def test_not_configured(self):
        with mock.patch.object(client, "get_settings", return_value=SimpleNamespace(assistant_url=None, assistant_key="", assistant_timeout_seconds=30.0)):
            with self.assertRaises(AppError) as cm:
                client.voice_transcribe(b"A")
        self.assertEqual(cm.exception.detail["reason"], "NOT_CONFIGURED")

    def test_status_route_hides_the_button_instead_of_failing(self):
        with mock.patch.object(client, "voice_status", side_effect=AppError(503, ASSISTANT_UNAVAILABLE, "x", {"reason": "URLError"})):
            self.assertEqual(R.voice_status(actor=None), {"enabled": False, "ready": False, "max_seconds": 0})


class FakeRequest:
    def __init__(self, chunks, declared=None):
        self.headers = {} if declared is None else {"content-length": str(declared)}
        self._chunks = chunks

    async def stream(self):
        for c in self._chunks:
            yield c


class TestReadAudio(unittest.TestCase):
    def read(self, req, cap=1000):
        return asyncio.run(R._read_audio(req, cap))

    def test_reads_everything_under_the_cap(self):
        self.assertEqual(self.read(FakeRequest([b"ab", b"cd"], declared=4)), b"abcd")

    def test_declared_length_over_cap_is_refused_before_reading(self):
        with self.assertRaises(AppError) as cm:
            self.read(FakeRequest([b"x"], declared=5000))
        self.assertEqual((cm.exception.status, cm.exception.detail["reason"]), (422, "AUDIO_TOO_LARGE"))

    def test_stream_over_cap_without_header_is_stopped(self):
        with self.assertRaises(AppError) as cm:
            self.read(FakeRequest([b"x" * 600, b"x" * 600]))
        self.assertEqual(cm.exception.detail["reason"], "AUDIO_TOO_LARGE")

    def test_lying_header_does_not_help(self):
        with self.assertRaises(AppError):
            self.read(FakeRequest([b"x" * 600, b"x" * 600], declared=10))


if __name__ == "__main__":
    unittest.main()
