"""모은 문서(알람 목록, 고장 대응 안내, 정비 일정, 안전 지침)의 크기와 구조를 센다.
결과: outputs/documents_summary.json, fig_alarm_documents.png, fig_haas_alarm_text.png"""
import csv
import json
import re
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from common import DOCS, OUT, TEXT, html_text, pdf_pages, save_json

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
res = {}
WEB = DOCS / "haas" / "web_snapshots"

# ---------- 1. Haas 공식 알람 목록 ----------
alarms = list(csv.DictReader(open(DOCS / "haas" / "haas_alarm_list_20250130_en_ko.csv", encoding="utf-8-sig")))
ACTION = re.compile(r"\b(check|replace|verify|inspect|clean|adjust|reduce|add|allow|make sure|ensure|contact|correct|remove|reset|change|increase|decrease|tighten|refill|cycle power)\b", re.I)
by_type = {}
for typ in ["NGC", "CHC-Mill", "CHC-Lathe"]:
    rows = [r for r in alarms if r["type"] == typ]
    lens = sorted(len(r["description_en"]) for r in rows)
    by_type[typ] = {
        "entries": len(rows),
        "distinct_base_numbers": len({r["code"].split(".")[1] if (typ == "NGC" and re.fullmatch(r"\d+\.\d{1,3}", r["code"]) and r["extension"] and r["extension"] != "0000") else r["code"].split(".")[0] for r in rows}),
        "with_axis_prefix": sum(1 for r in rows if r["extension"] not in ("", "0000")),
        "desc_len_median": lens[len(lens) // 2], "desc_len_q1": lens[len(lens) // 4], "desc_len_q3": lens[3 * len(lens) // 4],
        "desc_under_60_chars": sum(1 for x in lens if x < 60),
        "with_action_word": sum(1 for r in rows if ACTION.search(r["description_en"])),
        "korean_title": sum(1 for r in rows if re.search(r"[가-힣]", r["title_ko"])),
        "korean_description": sum(1 for r in rows if re.search(r"[가-힣]", r["description_ko"])),
    }
res["haas_alarm_list"] = {"total": len(alarms), "by_type": by_type}

ngc = [r for r in alarms if r["type"] == "NGC"]
bucket = Counter()
for r in ngc:
    n = r["extension"] if r["extension"] not in ("", "0000") and "." in r["code"] and len(r["base"]) <= 2 else r["base"]
    try:
        v = int(n)
    except ValueError:
        continue
    bucket[f"{v // 1000 * 1000:04d}~{v // 1000 * 1000 + 999}"] += 1
res["haas_ngc_number_ranges"] = dict(sorted(bucket.items()))

# ---------- 2. Haas 고장 대응 안내(troubleshooting guide) 구조 ----------
tsg = {}
for p in sorted(WEB.glob("tsg_*.txt")):
    t = " ".join(p.read_text(encoding="utf-8", errors="ignore").split())
    tsg[p.stem] = {"chars": len(t), "corrective_action": len(re.findall(r"Corrective Action", t)),
                   "possible_cause": len(re.findall(r"(Possible|Probable) Cause", t)),
                   "alarm_numbers_mentioned": len(set(re.findall(r"\bAlarm\s+(\d{3,5}(?:\.\d+)?)", t))),
                   "has_electrical_safety": "Electrical Safety" in t}
res["haas_troubleshooting_guides"] = tsg

# ---------- 3. 정비 일정 ----------
ms = (WEB / "howto_vmc_maintenance_schedule.txt").read_text(encoding="utf-8", errors="ignore")
lines = [x.strip() for x in ms.split("\n") if x.strip()]
INTERVALS = ["Daily", "Weekly", "Monthly", "Quarterly", "Six Months", "Annually", "Two Years", "Four Years", "As Required", "Check the Gauge"]
iv = Counter()
for a, b in zip(lines, lines[1:]):
    for k in INTERVALS:
        if b == k or b.startswith(k + " ") or b.lower().startswith(k.lower()):
            iv[k] += 1
            break
res["haas_vmc_maintenance_schedule"] = {"items": sum(iv.values()), "by_interval": dict(iv)}

# ---------- 4. 다른 설비의 알람 매뉴얼 ----------
def count_pdf(rel, pattern, flags=re.M):
    pages = pdf_pages(rel)
    return {"pages": len(pages), "entries": sum(len(re.findall(pattern, t, flags)) for t in pages)}


others = {}
others["Siemens SINUMERIK 840D sl 알람 (한국어)"] = count_pdf("line/siemens_840Dsl_alarms_diagnostics_man_0818_ko-KR.pdf", r"^해결책:")
others["Siemens SINUMERIK 840D sl 알람 (영어)"] = count_pdf("line/siemens_840Dsl_alarms_diagnostics_man_0818_en-US.pdf", r"^Remedy:")
others["Siemens SINUMERIK 808D (영어)"] = count_pdf("line/siemens_808D_ADVANCED_Diagnostics_Manual_022016_eng.pdf", r"^Remedy:")
others["Mitsubishi M800/M80 알람 (영어)"] = count_pdf("line/mitsubishi_m800_m80_alarm_param_ib1501279engr.pdf", r"^Remedy\s*$")
y = pdf_pages("line/yaskawa_YRC1000_alarm_codes_178644-1CD.pdf")
others["Yaskawa YRC1000 로봇 알람 (영어)"] = {"pages": len(y), "entries": len({m for t in y for m in re.findall(r"^(\d{4}):\s?[A-Z]", t, re.M)})}
g = pdf_pages("line/ls_INV_G100_Troubleshooting_Rev1.0_KR.pdf")
others["LS G100 인버터 원인·조치 표 (한국어)"] = {"pages": len(g), "entries": sum(len(re.findall(r"원인\s+조치\s?사항", " ".join(t.split()))) for t in g)}
i7 = pdf_pages("line/ls_iS7_Troubleshooting_KOR_Rev1.0_150812.pdf")
others["LS iS7 인버터 원인·조치 표 (한국어)"] = {"pages": len(i7), "entries": sum(len(re.findall(r"원인\s+조치\s?사항", " ".join(t.split()))) for t in i7)}
hcs = html_text(WEB / "haas_hcs_6_troubleshooting.html")
others["Haas Cold Saw HCS-80 알람 (영어·한국어 페이지)"] = {"pages": None, "entries": len(set(re.findall(r"\b\d{4}\.\d{2}\b", hcs)))}
hx = html_text(DOCS / "line" / "hexagon_pcdmis_sheffield_MP_error_codes.html") + html_text(DOCS / "line" / "hexagon_pcdmis_sheffield_MLB_error_codes.html")
others["Hexagon PC-DMIS 측정기 오류 코드 MP·MLB (영어)"] = {"pages": None, "entries": len(set(re.findall(r"\b(?:MP|MLB)-\d{3}\b", hx)))}
res["other_equipment_alarm_manuals"] = others

# ---------- 5. 안전 문서 ----------
kosha = []
for p in sorted((DOCS / "kosha").glob("*.pdf")):
    try:
        pages = pdf_pages(p.relative_to(DOCS).as_posix())
    except FileNotFoundError:
        continue
    chars = sum(len(t) for t in pages)
    kosha.append({"file": p.name, "pages": len(pages), "chars": chars, "text_ok": chars / max(1, len(pages)) > 300})
res["kosha_documents"] = {"count": len(kosha), "total_pages": sum(k["pages"] for k in kosha),
                          "text_not_extractable": [k["file"] for k in kosha if not k["text_ok"]], "list": kosha}

# ---------- 6. 한국어 Haas 매뉴얼 ----------
ko = {}
for rel in ["haas/ko_96-KO8210_Mill.pdf", "haas/ko_mill_operators_manual_2015.pdf"]:
    pages = pdf_pages(rel)
    txt = "\n".join(pages)
    ko[rel] = {"pages": len(pages), "hangul_chars": len(re.findall(r"[가-힣]", txt)), "mentions_알람": txt.count("알람"), "mentions_유지보수": txt.count("유지보수")}
res["haas_korean_manuals"] = ko

save_json("documents_summary.json", res)
print(json.dumps({k: v for k, v in res.items() if k != "kosha_documents"}, ensure_ascii=False, indent=1)[:6000])
print("KOSHA:", res["kosha_documents"]["count"], "개,", res["kosha_documents"]["total_pages"], "쪽, 글자 추출 안 됨:", res["kosha_documents"]["text_not_extractable"])

# ---------- 그림 1: 알람 문서별 항목 수 ----------
items = [(f'Haas NGC 알람 목록 (영어, 한국어 번역 {by_type["NGC"]["korean_title"]}개)', by_type["NGC"]["entries"]),
         ("Haas 구형 제어기 밀 알람 (영어)", by_type["CHC-Mill"]["entries"])] + [(k, v["entries"]) for k, v in others.items()]
items.sort(key=lambda x: x[1])
fig, ax = plt.subplots(figsize=(9, 4.6))
ax.barh([k for k, _ in items], [v for _, v in items], color="#2a78d6", height=0.55)
for i, (_, v) in enumerate(items):
    ax.text(v + 40, i, f"{v:,}", va="center", fontsize=9)
ax.set_xlabel("알람·오류 항목 수")
ax.set_title("설비별 알람 문서의 항목 수 (직접 센 값)", loc="left", fontsize=12)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
ax.grid(axis="x", color="#e1e0d9", linewidth=0.8)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(OUT / "fig_alarm_documents.png", dpi=130)

# ---------- 그림 2: Haas NGC 알람 설명 길이 ----------
lens = [len(r["description_en"]) for r in ngc]
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.hist(lens, bins=range(0, 900, 30), color="#2a78d6", edgecolor="#fcfcfb")
ax.set_xlabel("알람 설명 글자 수 (영어)")
ax.set_ylabel("알람 수")
ax.set_title(f"Haas NGC 알람 {len(ngc)}개의 설명 길이 (중앙값 {sorted(lens)[len(lens) // 2]}자)", loc="left", fontsize=12)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
ax.grid(axis="y", color="#e1e0d9", linewidth=0.8)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(OUT / "fig_haas_alarm_text.png", dpi=130)
