"""촬영 원본(work/raw/raw.webm) + timeline.json + 음성 + 자막 그림 → 시연영상 mp4 (v3: 자르기·디졸브·한 장 자막·제목 카드).
쓰는 법: .venv 의 python 으로 tools/edit.py [출력파일 이름] [--title C]   (기본: 시연영상_v3.mp4, 제목 카드 B안)
먼저 node tools/subs.js 로 자막 그림을 만들어 둔다 (work/subs/).

편집 규칙 (시연영상_스크립트.md 6장)
- cut  : 계정 전환·첫 화면 준비처럼 줄과 줄 사이에서 통째로 자르는 구간
- flow : 시연 시계가 흐르는 구간. 3초 이하는 ×1, 24초 이하는 ×4(최대 6초), 더 길면 앞 12초·뒤 12초만 ×4로 보이고 가운데는 자름
- 꼬리: 줄이 끝난 뒤 다음 줄이 시작될 때까지 3초를 넘는 구간은 앞 1.3초·뒤 1.2초만 남기고 가운데를 자름 (빨리 감지 않음)
- 자른 곳은 0.3초 디졸브, 속도만 바뀌는 곳은 거의 바로 이어 붙임
"""
import json, shutil, subprocess, sys
from pathlib import Path

def _find(name):      # PATH 에 없으면 winget 기본 설치 위치(Gyan.FFmpeg)도 찾는다
    p = shutil.which(name)
    return p or next((str(x) for x in Path.home().glob(f"AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg*/ffmpeg-*/bin/{name}.exe")), None)


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
FFMPEG, FFPROBE = _find("ffmpeg"), _find("ffprobe")      # winget install Gyan.FFmpeg 후 새 터미널
if not (FFMPEG and FFPROBE):
    sys.exit("ffmpeg 를 찾지 못했습니다. 설치(winget install Gyan.FFmpeg) 후 새 터미널에서 다시 실행하세요.")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
TITLE_KIND = sys.argv[sys.argv.index("--title") + 1] if "--title" in sys.argv else "B"
args = [a for a in args if a != TITLE_KIND]
OUT = ROOT / (args[0] if args else "시연영상_v3.mp4")
TITLE_PNG = ROOT / "타이틀시안" / f"title_{TITLE_KIND}.png"
TITLE_SEC, TITLE_DISSOLVE = 2.5, 0.6          # 제목 카드 길이, 로그인 화면으로 녹는 시간
END_HOLD, END_FADE, LIMIT = 1.0, 0.8, 298.0   # 마지막 줄 뒤 머무름, 끝 페이드, 5분 한도
GAP_KEEP, TAIL_MAX, TAIL_HEAD, TAIL_END = 0.3, 1.8, 0.55, 0.55
FLOW_MAX_SEC, FLOW_SPEED, FLOW_PART = 3.0, 4.0, 6.0     # 시계 흐름은 보이는 시간 3초 안 (×4, 길면 앞 6초·뒤 6초 원본만)
D_GAP, D_SPEED = 0.30, 0.08                   # 자른 곳 디졸브 / 속도만 바뀌는 곳
SUB_LEAD, SUB_FADE, SUB_MIN = 0.10, 0.15, 1.8
SUB_BOTTOM, SUB_BOTTOM_UP = 70, 330           # 자막 아래 여백 (홈 하단 패널을 설명하는 줄은 위로)
UP = {"s1e"}                    # 자막을 홈 하단 패널 위로
TOP = {"s6g", "s7d3"}          # 내용이 화면 아래쪽에 있는 장면(재고 거래 기록, 일일 보고서 하단)은 자막을 위쪽으로

tl = json.loads((WORK / "timeline.json").read_text(encoding="utf-8"))
lines = {x["id"]: x for x in json.loads((WORK / "lines.json").read_text(encoding="utf-8"))}
subidx = json.loads((WORK / "subs" / "index.json").read_text(encoding="utf-8"))
raw = WORK / "raw" / "raw.webm"
vdur = float(subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(raw)], capture_output=True, text=True).stdout)
total = min(tl["total"], vdur)

says = sorted([e for e in tl["events"] if e["type"] == "say"], key=lambda e: e["t"])
cuts = sorted([(e["t0"], min(e["t1"], total)) for e in tl["events"] if e["type"] == "cut"])
flows_raw = sorted([e for e in tl["events"] if e["type"] in ("flow", "fast")], key=lambda e: e["t0"])


def minus(a, b, holes):
    """[a,b] 에서 holes 와 겹치는 부분을 뺀 조각들"""
    out, cur = [], a
    for c0, c1 in sorted(holes):
        if c1 <= cur or c0 >= b: continue
        if c0 > cur: out.append((cur, c0))
        cur = max(cur, c1)
    if cur < b: out.append((cur, b))
    return out


# ---- 1) 시계 흐름: 줄이 끝난 뒤로 자르고, 길이에 따라 ×1 / ×4 / 앞뒤만 ×4 ----
flow_segs, flow_cuts = [], []
for f in flows_raw:
    a0 = f["t0"]
    for e in says:                                   # 나레이션이 도는 동안은 ×1 로 둔다
        if e["t"] <= a0 < e["t"] + e["dur"] + GAP_KEEP: a0 = e["t"] + e["dur"] + GAP_KEEP
    for x0, x1 in minus(a0, min(f["t1"], total), cuts):
        r = x1 - x0
        if r <= 3.0: continue
        if r <= FLOW_SPEED * FLOW_MAX_SEC: flow_segs.append((x0, x1, FLOW_SPEED))
        else:
            flow_segs.append((x0, x0 + FLOW_PART, FLOW_SPEED)); flow_segs.append((x1 - FLOW_PART, x1, FLOW_SPEED)); flow_cuts.append((x0 + FLOW_PART, x1 - FLOW_PART))
flow_ranges = [(a, b) for a, b, _ in flow_segs] + flow_cuts

# ---- 2) 꼬리·빈 구간: 줄 사이 3초를 넘으면 가운데를 자름 (끝은 1초만 남김) ----
tail_cuts = []
gap_starts = [(cuts[0][1] if cuts and cuts[0][0] < 1.0 else 0.0)]
bounds = [(gap_starts[0], says[0]["t"])] + [(e["t"] + e["dur"] + GAP_KEEP, says[i + 1]["t"]) for i, e in enumerate(says[:-1])]
for a0, a1 in bounds:
    for x0, x1 in minus(a0, a1, cuts + flow_ranges):
        if x1 - x0 > TAIL_MAX: tail_cuts.append((x0 + TAIL_HEAD, x1 - TAIL_END))
last = says[-1]; e0 = last["t"] + last["dur"] + GAP_KEEP
if total - e0 > END_HOLD: tail_cuts.append((e0 + END_HOLD, total))

# ---- 3) 남길 조각 (a, b, 속도) ----
removed = cuts + flow_cuts + tail_cuts
keep = minus(0.0, total, removed)
pts = sorted({p for a, b in keep for p in (a, b)} | {p for a, b, _ in flow_segs for p in (a, b)})
segs = []
for p, q in zip(pts, pts[1:]):
    if q - p < 0.04 or not any(a - 1e-6 <= p and q <= b + 1e-6 for a, b in keep): continue
    f = FLOW_SPEED if any(fa - 1e-6 <= p and q <= fb + 1e-6 for fa, fb, _ in flow_segs) else 1.0
    segs.append((p, q, f))
# 같은 속도로 이어지는 조각은 하나로
merged = []
for a, b, f in segs:
    if merged and abs(merged[-1][1] - a) < 1e-3 and merged[-1][2] == f: merged[-1] = (merged[-1][0], b, f)
    else: merged.append((a, b, f))
segs = merged
junc = [TITLE_DISSOLVE] + [(D_GAP if segs[i][0] - segs[i - 1][1] > 0.01 else D_SPEED) for i in range(1, len(segs))]   # junc[i] = i 번째 조각 앞 이음새
lens = [(b - a) / f for a, b, f in segs]
starts, acc = [], TITLE_SEC                         # 각 조각이 결과 영상에서 나타나기 시작하는 시각
for i, ln in enumerate(lens):
    st = acc - junc[i]; starts.append(st); acc = st + ln
dur_all = acc


def out_t(rt):                                       # 원본 시각 → 결과 시각
    for (a, b, f), s0 in zip(segs, starts):
        if a - 1e-6 <= rt <= b + 1e-6: return s0 + (rt - a) / f
    for (a, b, f), s0 in zip(segs, starts):
        if a > rt: return s0
    return dur_all


# ---- ffmpeg 필터 ----
inputs = ["-i", str(raw), "-loop", "1", "-framerate", "25", "-t", f"{TITLE_SEC:.3f}", "-i", str(TITLE_PNG)]
fc = []
fmt = "fps=25,scale=1920:1080,format=yuv420p,setsar=1"
for i, (a, b, f) in enumerate(segs):
    fc.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)/{f:g},{fmt}[v{i}]")
fc.append(f"[1:v]{fmt},trim=duration={TITLE_SEC:.3f},setpts=PTS-STARTPTS[vt]")
prev = "vt"
for i in range(len(segs)):
    fc.append(f"[{prev}][v{i}]xfade=transition=fade:duration={junc[i]:.3f}:offset={starts[i]:.3f}[x{i}]"); prev = f"x{i}"
fc.append(f"[{prev}]fade=t=out:st={dur_all - END_FADE:.3f}:d={END_FADE},format=yuv420p[vb]")

n_in = 2
cur = "vb"
for k, e in enumerate(says):                         # 자막 한 장 그림을 줄마다 얹음
    L = lines[e["id"]]; w, h = subidx[e["id"]]["w"], subidx[e["id"]]["h"]
    s = out_t(e["t"]) + SUB_LEAD; d = max(SUB_MIN, e["dur"] + 0.35)
    x = (1920 - w) // 2; y = 96 if e["id"] in TOP else 1080 - (SUB_BOTTOM_UP if e["id"] in UP else SUB_BOTTOM) - h
    inputs += ["-loop", "1", "-framerate", "25", "-t", f"{d:.3f}", "-i", str(WORK / "subs" / f"{e['id']}.png")]
    fc.append(f"[{n_in}:v]format=rgba,fade=t=in:st=0:d={SUB_FADE}:alpha=1,fade=t=out:st={d - SUB_FADE:.3f}:d={SUB_FADE}:alpha=1,setpts=PTS+{s:.3f}/TB[sub{k}]")
    fc.append(f"[{cur}][sub{k}]overlay=x={x}:y={y}:enable='between(t,{s:.3f},{s + d:.3f})':eof_action=pass[o{k}]"); cur = f"o{k}"; n_in += 1
fc.append(f"[{cur}]format=yuv420p[vout]")

a_idx = []
for e in says:
    inputs += ["-i", str(WORK / "audio" / f"{e['id']}.mp3")]
    ms = int((out_t(e["t"]) + SUB_LEAD) * 1000)
    fc.append(f"[{n_in}:a]adelay={ms}|{ms}[a{n_in}]"); a_idx.append(n_in); n_in += 1
fc.append("".join(f"[a{i}]" for i in a_idx) + f"amix=inputs={len(a_idx)}:normalize=0:dropout_transition=0,loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st={dur_all - END_FADE:.2f}:d={END_FADE},apad=whole_dur={dur_all:.2f}[aout]")
(WORK / "filter.txt").write_text(";\n".join(fc), encoding="utf-8")

cmd = [FFMPEG, "-y", "-v", "error", "-stats", *inputs, "-/filter_complex", "filter.txt", "-map", "[vout]", "-map", "[aout]",
       "-t", f"{dur_all:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", str(OUT)]
kept = sum(b - a for a, b, _ in segs)
print(f"원본 {total:.1f}s → 결과 {dur_all:.1f}s | 조각 {len(segs)}개 · 남긴 원본 {kept:.1f}s · 자른 곳 {len(removed)}곳 · 시계 흐름 조각 {len(flow_segs)}개 · 나레이션 {len(says)}줄 · 제목 {TITLE_KIND}안")
if dur_all > LIMIT: print(f"!! 5분 한도({LIMIT:.0f}s)를 {dur_all - LIMIT:.1f}초 넘음")
if "--times" in sys.argv:                      # 줄마다 결과 영상에서 시작 시각 (확인용)
    for e in says: print(f"{e['id']} {out_t(e['t']) + SUB_LEAD:.2f}")
    sys.exit(0)
if "--gaps" in sys.argv:                       # 결과 영상에서 나레이션 줄 사이 말없는 시간이 큰 곳
    tot = 0.0
    for e, n in zip(says, says[1:]):
        g = out_t(n["t"]) - (out_t(e["t"]) + e["dur"]); tot += max(g, 0)
        if g > 1.2: print(f"  {e['id']:5s} → {n['id']:5s} 말없는 시간 {g:4.1f}초")
    print(f"  줄 사이 말없는 시간 합계 {tot:.1f}초 (나레이션 {sum(e['dur'] for e in says):.1f}초)")
    sys.exit(0)
if "--plan" in sys.argv:
    for i, (a, b, f) in enumerate(segs): print(f"  {i:2d} 원본 {a:7.1f}~{b:7.1f} ×{f:g} → 결과 {starts[i]:6.1f} (+{lens[i]:.1f}s) 앞 이음새 {junc[i]:.2f}")
    sys.exit(0)
r = subprocess.run(cmd, cwd=str(WORK))
print("끝" if r.returncode == 0 else f"ffmpeg 실패 {r.returncode}", OUT)
