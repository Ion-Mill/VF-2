"""나레이션 문구 한 곳 모음 (시연영상_스크립트.md 5장). 자막 = sub (화면 표기), 음성 = tts (읽는 소리).
hl = 자막에서 노란 글자로 강조할 낱말. kw = 강조 박스를 켤 낱말(tts 안의 글자, 순서대로) — 음성의 낱말 시각으로 박스 타이밍을 맞춘다.
실행하면 work/audio/<id>.mp3 와 work/lines.json(길이·낱말 시각 포함)을 만든다.
쓰는 법: .venv 의 python 으로 tools/lines.py [--force]   (목소리: 여성 SunHi, 속도 +25% — 2026-10-25 확정). tts 안의 "|" = 쉼(무음)
"""
import asyncio, json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
VOICE, RATE = "ko-KR-SunHiNeural", "+25%"
PAUSE = 0.55          # tts 안의 "|" = 이 만큼 무음 (초)
def _find(name):      # PATH 에 없으면 winget 기본 설치 위치(Gyan.FFmpeg)도 찾는다
    p = shutil.which(name)
    return p or next((str(x) for x in Path.home().glob(f"AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg*/ffmpeg-*/bin/{name}.exe")), None)


FFPROBE, FFMPEG = _find("ffprobe"), _find("ffmpeg")      # winget install Gyan.FFmpeg 후 새 터미널
if not (FFPROBE and FFMPEG):
    sys.exit("ffmpeg 를 찾지 못했습니다. 설치(winget install Gyan.FFmpeg) 후 새 터미널에서 다시 실행하세요.")

L = [  # (id, sub, tts, hl, kw)
 ("s1a", "로그인하면 공장 전체가\n3D로 나타납니다.", "로그인하면 공장 전체가 쓰리디로 나타납니다.", ["3D"], []),
 ("s1b", "엔진 마운트 브래킷을 만드는,\n다섯 공정이 이어진 하나의 라인입니다.", "엔진 마운트 브래킷을 만드는, 다섯 공정이 이어진 하나의 라인입니다.", ["다섯 공정"], []),
 ("s1c", "설비 위 카드와 설비 색으로\n상태를 바로 알 수 있습니다.", "설비 위 카드와 설비 색으로 상태를 바로 알 수 있습니다.", ["설비 위 카드", "설비 색"], ["설비 위 카드", "설비 색"]),
 ("s1d", "공정 사이 숫자는 쌓여 있는 재공이고,\n공정마다 속도가 달라 알람도 설비마다 다릅니다.", "공정 사이 숫자는 쌓여 있는 재공이고, 공정마다 속도가 달라 알람도 설비마다 다릅니다.", ["재공", "알람"], ["재공", "알람"]),
 ("s1e", "생산은 이번 교대 실적, 예측은 마감 때 수량,\nOEE는 설비 종합 효율입니다.", "생산은 이번 교대 실적, 예측은 마감 때 수량, 오이이는 설비 종합 효율입니다.", ['생산', '예측', 'OEE'], ["생산", "예측", "오이이"]),
 ("s1f", "이 공장의 전반적인 흐름을 AI 비서가\n대신 챙겨 주는 것이 저희 플랫폼입니다.", "이 공장의 전반적인 흐름을 에이아이 비서가 대신 챙겨 주는 것이 저희 플랫폼입니다.", ["AI 비서"], []),
 ("s2a", "교대가 시작되면 비서가 먼저 브리핑합니다.\n이번 교대 목표와 지난 교대 결과,", "교대가 시작되면 비서가 먼저 브리핑합니다. 이번 교대 목표와 지난 교대 결과,", ["브리핑", "이번 교대 목표", "지난 교대 결과"], ["브리핑", "이번 교대 목표", "지난 교대 결과"]),
 ("s2b", "그리고 먼저 챙길 일입니다.\n순서는 AI가 아닌 프로그램이 규칙으로 정한 위험도순입니다.", "그리고 먼저 챙길 일입니다. 순서는 에이아이가 아닌 프로그램이 규칙으로 정한 위험도순입니다.", ['먼저 챙길 일', '규칙'], ["먼저 챙길 일"]),
 ("s2c", "VF2-01의 공구 수명에 대한 내용과,\nVF2-02의 윤활유 점검 기한이 초과되었다는 내용입니다.", "브이에프 투 영일의 공구 수명에 대한 내용과, 브이에프 투 영이의 윤활유 점검 기한이 초과되었다는 내용입니다.", ["공구 수명", "기한이 초과"], ["공구 수명", "기한이 초과"]),
 ("s2d", "시간을 빠르게 돌려 보겠습니다.", "시간을 빠르게 돌려 보겠습니다.", [], ["시간을"]),
 ("s3a", "VF2-01에서 아까 본 공구가 한계에 도달했다는\n주의 알림이 떴습니다.", "브이에프 투 영일에서 아까 본 공구가 한계에 도달했다는 주의 알림이 떴습니다.", ["주의 알림"], ["주의 알림"]),
 ("s3b", "위쪽 알림 띠가 사람이 찾기 전에\n먼저 알려 주는, 선제 알림입니다.", "위쪽 알림 띠가 사람이 찾기 전에 먼저 알려 주는, 선제 알림입니다.", ["선제 알림"], ["선제 알림"]),
 ("s3c", "지침카드를 열면, 설비 매뉴얼에서 이 알람의\n조치만 뽑아 쉬운 말로 정리해 줍니다.", "지침카드를 열면, 설비 매뉴얼에서 이 알람의 조치만 뽑아, 쉬운 말로 정리해 줍니다.", ["지침카드"], ["지침카드를"]),
 ("s3d", "이 알람으로 인한 생산 영향도 계산됩니다.\n정지 시간과 손실 수량, 가공 중이던 로트까지 담겨 있습니다.", "이 알람으로 인한 생산 영향도 계산됩니다. 정지 시간과 손실 수량, 가공 중이던 로트까지 담겨 있습니다.", ["생산 영향", "로트"], ["생산 영향", "정지 시간과 손실 수량", "로트"]),
 ("s3e", "가벼운 알람은 한 장으로 마무리됩니다.\n이제 더 큰 사건입니다.", "가벼운 알람은 한 장으로 마무리됩니다.|이제 더 큰 사건입니다.", [], []),
 ("s4a", "이번에는 실제 고장을 내 보겠습니다.\nVF2-01에서 공구가 공작물과 충돌합니다.", "이번에는 실제 고장을 내 보겠습니다. 브이에프 투 영일에서 공구가 공작물과 충돌합니다.", ["충돌"], ["충돌합니다"]),
 ("s4b", "정지 등급 알람 하나가 모두의 화면 가운데에\n긴급 알림으로 뜨고, 설비는 빨갛게 바뀝니다.", "정지 등급 알람 하나가 모두의 화면 가운데에 긴급 알림으로 뜨고, 설비는 빨갛게 바뀝니다.", ["긴급 알림"], []),
 ("s4c", "VF2-01이 멈추자 병목이 이 공정으로 옮겨 가고,\n앞 공정은 재공이 한도에 막혀 대기합니다.", "브이에프 투 영일이 멈추자 병목이 이 공정으로 옮겨 가고, 앞 공정은 재공이 한도에 막혀 대기합니다.", ["병목", "재공이 한도"], ["병목이", "앞 공정"]),
 ("s4d", "지침카드를 열어 보겠습니다.\n원인은 공구 파손이나 충돌일 수 있고,", "지침카드를 열어 보겠습니다. 원인은 공구 파손이나 충돌일 수 있고,", ["지침카드", "원인"], ["지침카드를", "원인은"]),
 ("s4e", "축 부하가 급하게 올랐다면\n충돌을 먼저 의심하라고 안내합니다.", "축 부하가 급하게 올랐다면 충돌을 먼저 의심하라고 안내합니다.", ["충돌을 먼저 의심"], ["축 부하", "충돌을 먼저 의심"]),
 ("s4f", "가공 중이던 로트와 라인 속도 절반까지\n한 장에 있습니다.", "가공 중이던 로트와 라인 속도 절반까지 한 장에 있습니다.", ["로트", "라인 속도 절반"], ["로트와", "라인 속도 절반"]),
 ("a5", "보전 담당자 계정으로 보겠습니다.", "보전 담당자 계정으로 보겠습니다.", ["보전 담당자"], []),
 ("s5a", "고장이 나면 비서가 작업지시서 초안을 먼저 쓰고,\n검토 알림이 옵니다.", "고장이 나면 비서가 작업지시서 초안을 먼저 쓰고, 검토 알림이 옵니다.", ['작업지시서 초안'], ["작업지시서 초안"]),
 ("s5b", "증상, 점검 순서, 안전 단계가 들어 있고,\n필요한 곳만 고치면 수정 이력으로 남습니다.", "증상, 점검 순서, 안전 단계가 들어 있고, 필요한 곳만 고치면 수정 이력으로 남습니다.", ["안전 단계", "수정 이력"], ["증상", "점검 순서", "안전 단계", "수정 이력"]),
 ("s5c", "모르는 건 비서에게 물어봅니다.\n모터 케이블 저항은 어떻게 재는지 물어보겠습니다.", "모르는 건 비서에게 물어봅니다. 모터 케이블 저항은 어떻게 재는지 물어보겠습니다.", [], []),
 ("s5d", "프로그램이 사내 문서에서 관련 내용만 찾고,\nLLM이 문구를 다듬어 답합니다.", "프로그램이 사내 문서에서 관련 내용만 찾고, 엘엘엠이 문구를 다듬어 답합니다.", ["사내 문서"], []),
 ("s5e", "답마다 근거 문서의 번호와 절이 붙고,\n누르면 그 절이 열립니다.", "답마다 근거 문서의 번호와 절이 붙고, 누르면 그 절이 열립니다.", ["근거 문서"], ["근거 문서", "누르면"]),
 ("s5f", "사내 문서의 내용이고,\n잠금·표지와 고전압 대기 안전 문구도 붙습니다.", "사내 문서의 내용이고, 잠금·표지와 고전압 대기 안전 문구도 붙습니다.", ['사내 문서'], ["잠금", "안전 문구"]),
 ("a6", "이번에는 반장 계정입니다.", "이번에는 반장 계정입니다.", ["반장"], []),
 ("s6a", "승인 요청 알림이 뜨고,\n눌러 들어가 승인합니다.", "승인 요청 알림이 뜨고, 눌러 들어가 승인합니다.", ['승인'], ["승인 요청 알림"]),
 ("s6b", "승인하면 내용이 잠기고,\n보전 담당자에게 배정 알림이 갑니다.", "승인하면 내용이 잠기고, 보전 담당자에게 배정 알림이 갑니다.", ["승인"], ["승인하면"]),
 ("a6c", "다시 보전 담당자 계정입니다.", "다시 보전 담당자 계정입니다.", ["보전 담당자"], []),
 ("s6c", "작업을 시작하면 작업 기록 칸이 열리고,", "작업을 시작하면 작업 기록 칸이 열리고,", [], ["작업 기록 칸"]),
 ("s6c2", "메모를 남기면\n원인과 조치로 나누어 채워 줍니다.", "메모를 남기면 원인과 조치로 나누어 채워 줍니다.", ["원인과 조치"], ["원인과 조치"]),
 ("s6d", "수행 단계와 잠금·표지 단계를\n모두 체크해야 확정할 수 있습니다.", "수행 단계와 잠금·표지 단계를 모두 체크해야 확정할 수 있습니다.", ["확정"], ["수행 단계", "확정할"]),
 ("s6e", "확정하면 설비가 정상으로 돌아오고\n병목이 풀립니다.", "확정하면 설비가 정상으로 돌아오고, 병목이 풀립니다.", ["정상"], ["정상으로"]),
 ("s6g", "쓴 부품은 재고에서 빠지고,\n거래 기록에 사용 내역으로 남습니다.", "쓴 부품은 재고에서 빠지고,|거래 기록에 사용 내역으로 남습니다.", ["쓴 부품", "거래 기록"], ["쓴 부품", "거래 기록"]),
 ("a6f", "마지막으로 반장 계정에서 확인합니다.", "마지막으로 반장 계정에서 확인합니다.", ["반장"], []),
 ("s6f", "초안은 비서가 쓰고,\n승인과 확정은 모두 사람이 합니다.", "초안은 비서가 쓰고, 승인과 확정은 모두 사람이 합니다.", ["승인", "확정"], ["승인과 확정"]),
 ("s7a", "교대 종료, 이어서 야간 교대 시작으로 넘깁니다.", "교대 종료, 이어서 야간 교대 시작으로 넘깁니다.", [], ["교대 종료", "야간 교대 시작"]),
 ("s7a2", "비서가 교대 보고서 초안을 쓰고\n반장에게 알립니다.", "비서가 교대 보고서 초안을 쓰고 반장에게 알립니다.", ["교대 보고서"], ["교대 보고서"]),
 ("s7b", "실적·목표·가동률, 충돌 정지는 필수 정지로 기록되고,\n정비 내용과 인계사항도 들어 있습니다.", "실적·목표·가동률, 충돌 정지는 필수 정지로 기록되고, 정비 내용과 인계사항도 들어 있습니다.", ['필수 정지'], ["실적", "필수 정지", "정비 내용", "인계사항"]),
 ("s7c", "반장이 확정하면,\n공장 관리자 계정에 일일 보고서 확정 알림이 있습니다.", "반장이 확정하면, 공장 관리자 계정에 일일 보고서 확정 알림이 있습니다.", ["확정"], ["확정하면"]),
 ("a7", "이번에는 공장 관리자 계정입니다.", "이번에는 공장 관리자 계정입니다.", ["공장 관리자"], []),
 ("s7d", "오늘 야간 근무는 아직 끝나지 않아,\n전날 10월 23일 일일 보고서를 확정합니다.", "오늘 야간 근무는 아직 끝나지 않아, 전날 시월 이십삼일 일일 보고서를 확정합니다.", ["10월 23일"], []),
 ("s7d2", "일일 보고서에는 오늘의 실적과 불량,\nOEE가 먼저 나옵니다.", "일일 보고서에는 오늘의 실적과 불량, 오이이가 먼저 나옵니다.", ["실적", "OEE"], ["실적"]),
 ("s7d3", "그날의 문제와 생산 피해,\n안전 재고에 못 미친 품목까지 한 장에 정리됩니다.", "그날의 문제와 생산 피해, 안전 재고에 못 미친 품목까지 한 장에 정리됩니다.", ["문제", "안전 재고"], ["문제", "안전 재고"]),
 ("s7e", "알람에서 보고서까지,\n사람은 승인과 확정만 합니다.", "알람에서 보고서까지, 사람은 승인과 확정만 합니다.", ['승인', '확정'], ["승인과 확정"]),
 ("s7z", "이것으로 시연을 마치겠습니다.", "이것으로 시연을 마치겠습니다.", [], []),
]


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip())


def locate(tts, boundaries):
    """WordBoundary(낱말·시작·길이)를 tts 글자 위치에 붙인다 → [{w, a, b, ts, te}] (a,b = 글자 범위, ts,te = 초)"""
    out, cur = [], 0
    for w in boundaries:
        i = tts.find(w["text"], cur)
        if i < 0:
            print(f"  ! 낱말 위치를 못 찾음: {w['text']!r}"); continue
        out.append({"w": w["text"], "a": i, "b": i + len(w["text"]), "ts": round(w["ts"], 3), "te": round(w["te"], 3)}); cur = i + len(w["text"])
    return out


def kw_times(lid, tts, words, kws):
    res = []
    for k in kws:
        i = tts.find(k)
        if i < 0: raise SystemExit(f"{lid}: kw {k!r} 가 읽는 글자에 없음")
        j = i + len(k)
        hit = [w for w in words if w["b"] > i and w["a"] < j]
        if not hit: raise SystemExit(f"{lid}: kw {k!r} 에 맞는 낱말 시각이 없음")
        res.append({"k": k, "s": hit[0]["ts"], "e": hit[-1]["te"]})
    return res


async def synth(tts, f):
    import edge_tts
    com = edge_tts.Communicate(tts, VOICE, rate=RATE, boundary="WordBoundary")
    bs = []
    with open(f, "wb") as fh:
        async for ch in com.stream():
            if ch["type"] == "audio": fh.write(ch["data"])
            elif ch["type"] == "WordBoundary": bs.append({"text": ch["text"], "ts": ch["offset"] / 1e7, "te": (ch["offset"] + ch["duration"]) / 1e7})
    return bs



async def synth_line(tts, f):
    """tts 안의 '|' 는 쉼. 반환: (쉼 표시를 뺀 글, 낱말 시각들). 조각마다 만들어 사이에 PAUSE초 무음을 넣고 이어 붙인다"""
    parts = [p.strip() for p in tts.split("|")]
    clean = " ".join(parts)
    if len(parts) == 1:
        return clean, locate(clean, await synth(parts[0], f))
    words, t_off, c_off, files = [], 0.0, 0, []
    for i, p in enumerate(parts):
        fp = f.with_name(f"{f.stem}.p{i}.mp3")
        bs = await synth(p, fp)
        if i < len(parts) - 1:                                  # 마지막 조각 말고는 뒤에 무음을 붙인다
            fq = f.with_name(f"{f.stem}.q{i}.mp3")
            subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(fp), "-af", f"apad=pad_dur={PAUSE}", str(fq)], check=True)
            fp = fq
        for w in locate(p, bs):
            words.append({**w, "a": w["a"] + c_off, "b": w["b"] + c_off, "ts": round(w["ts"] + t_off, 3), "te": round(w["te"] + t_off, 3)})
        files.append(fp); t_off += dur(fp); c_off += len(p) + 1
    ins = sum([["-i", str(x)] for x in files], [])
    fc = "".join(f"[{k}:a]" for k in range(len(files))) + f"concat=n={len(files)}:v=0:a=1[a]"
    subprocess.run([FFMPEG, "-y", "-v", "error", *ins, "-filter_complex", fc, "-map", "[a]", str(f)], check=True)
    for x in files: x.unlink(missing_ok=True)
    for x in f.parent.glob(f"{f.stem}.p*.mp3"): x.unlink(missing_ok=True)
    return clean, words


async def main():
    (WORK / "audio").mkdir(parents=True, exist_ok=True)
    cache = {}
    cp = WORK / "lines.json"
    if cp.exists() and "--force" not in sys.argv:
        cache = {x["id"]: x for x in json.loads(cp.read_text(encoding="utf-8"))}
    out = []
    for lid, sub, tts, hl, kw in L:
        f = WORK / "audio" / f"{lid}.mp3"
        old = cache.get(lid)
        if old and old.get("tts_src") == tts and old.get("voice") == f"{VOICE}{RATE}" and old.get("words") and f.exists():
            clean, words = old["tts"], old["words"]
        else:
            clean, words = await synth_line(tts, f)
        kt = kw_times(lid, clean, words, kw)
        out.append({"id": lid, "sub": sub, "tts": clean, "tts_src": tts, "voice": f"{VOICE}{RATE}", "hl": hl, "dur": round(dur(f), 3), "words": words, "kw": kt})
    cp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tot = sum(x["dur"] for x in out)
    print(f"{len(out)}줄, 음성 합계 {tot:.1f}초")
    for x in out:
        ks = " ".join(f"{k['k']}@{k['s']:.2f}" for k in x["kw"])
        gaps = [b["s"] - a["s"] for a, b in zip(x["kw"], x["kw"][1:])]
        warn = "  !! 박스 간격 1.0초 미만" if any(g < 1.0 for g in gaps) else ""
        print(f"{x['id']:4s} {x['dur']:5.2f}s  {ks}{warn}")


asyncio.run(main())
