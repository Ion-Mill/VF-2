"""팀원(Gemini) 자료의 주장을 실제 문서에서 찾아 근거를 모은다.
판정(맞음/틀림)은 사람이 하고, 이 코드는 "문서에 실제로 무엇이 적혀 있는지"만 뽑는다.
결과: outputs/claim_evidence.json"""
import csv
import re

from common import DOCS, ROOT, find_all, html_text, pdf_pages, save_json

ev = {}
WEB = DOCS / "haas" / "web_snapshots"

# ---------- Haas 알람 목록 (공식 사이트 JSON 을 표로 바꾼 것) ----------
alarms = list(csv.DictReader(open(DOCS / "haas" / "haas_alarm_list_20250130_en_ko.csv", encoding="utf-8-sig")))


def base_no(r):
    return r["code"].split(".")[0] if r["type"] != "NGC" or r["code"].count(".") == 0 else r["code"]


def lookup(num):
    out = []
    for r in alarms:
        code = r["code"]
        if code == num or code == num + ".0000":
            out.append({"type": r["type"], "code": code, "title": r["title_en"], "description": r["description_en"],
                        "title_ko": r["title_ko"], "description_ko": r["description_ko"]})
    return out


for n in ["135", "179", "992", "645", "2011", "2012", "991", "993", "994"]:
    ev["alarm_" + n] = lookup(n)

old = {r["code"]: r for r in csv.DictReader(open(ROOT.parent / "8_Haas_VF-1_milling" / "docs" / "haas_alarms_2001_extracted.csv", encoding="utf-8-sig"))}
ev["alarm_2001_manual"] = {n: (old[n]["text"] + f" (PDF {old[n]['page_pdf']}쪽)") if n in old else "없음" for n in ["135", "179", "992"]}

# ---------- Haas 문서 전체에서 Gemini 가 쓴 임계값이 나오는지 ----------
haas_pdfs = ["haas/en_electrical_service_manual_2011.pdf", "haas/en_mill_service_manual_2005.pdf",
             "haas/en_mechanical_service_manual_2011.pdf", "haas/en_mill_ngc_operators_manual_2025.pdf"]
web_txt = {p.name: p.read_text(encoding="utf-8", errors="ignore") for p in WEB.glob("*.txt")}


def count_everywhere(pattern):
    res = {}
    for rel in haas_pdfs:
        h = find_all(pdf_pages(rel), pattern, 90)
        if h:
            res[rel] = {"count": len(h), "first": [f"p{p}: {t}" for p, t in h[:3]]}
    for name, t in web_txt.items():
        flat = " ".join(t.split())
        m = list(re.finditer(pattern, flat, re.I))
        if m:
            res["web/" + name] = {"count": len(m), "first": [flat[max(0, x.start() - 90): x.end() + 90] for x in m[:2]]}
    for r in alarms:
        if re.search(pattern, r["description_en"], re.I):
            res.setdefault("alarm_list", {"count": 0, "first": []})
            res["alarm_list"]["count"] += 1
            if len(res["alarm_list"]["first"]) < 3:
                res["alarm_list"]["first"].append(f'{r["type"]} {r["code"]} {r["title_en"]}: {r["description_en"][:160]}')
    return res


ev["threshold_135C"] = count_everywhere(r"135\s?°?\s?C\b")
ev["threshold_150F"] = count_everywhere(r"150\s?°?\s?(degrees\s)?F\b")
ev["threshold_2.5bar"] = count_everywhere(r"2\.5\s?bar")
ev["threshold_60A"] = count_everywhere(r"\b60\s?A\b")
ev["quote_pins_ABC"] = count_everywhere(r"pins labeled A, B,? and C")
ev["wait_5_minutes"] = count_everywhere(r"(at least )?(5|five) minutes")
ev["wait_10_minutes"] = count_everywhere(r"approximately 10 minutes")
ev["lockout"] = count_everywhere(r"lock.?out")

# ---------- 매뉴얼 장 구성 ----------
op = pdf_pages("haas/en_mill_ngc_operators_manual_2025.pdf")
chap = []
for t in op[:25]:
    chap += re.findall(r"Chapter\s+(\d+)\s+([A-Z][A-Za-z &-]+?)\s*\.{3,}", " ".join(t.split()))
ev["operator_manual_2025_chapters"] = sorted({(int(a), b.strip()) for a, b in chap})
ev["operator_manual_2025_pages"] = len(op)
ev["operator_manual_has_alarm_chapter"] = any(re.search(r"alarm", b, re.I) for _, b in ev["operator_manual_2025_chapters"])

# ---------- 톱 기계 (HCS-80) ----------
hcs = {p.name: html_text(p) for p in WEB.glob("haas_hcs_*.html")}
intro = hcs.get("haas_hcs_1_introduction.html", "")
i = intro.find("HCS-80 - Introduction")
ev["hcs80"] = {"mentions_HCS-80": sum(t.count("HCS-80") for t in hcs.values()),
               "intro": intro[i:i + 420],
               "alarm_codes": len(set(re.findall(r"\b\d{4}\.\d{2}\b", hcs.get("haas_hcs_6_troubleshooting.html", "")))),
               "alarm_codes_ko_page": len(set(re.findall(r"\b\d{4}\.\d{2}\b", hcs.get("haas_hcs_6_troubleshooting_ko.html", ""))))}

# ---------- VF-2 사양 ----------
vf2 = " ".join(web_txt.get("vf-2.txt", "").split())
ev["vf2_specs"] = {k: (re.search(p, vf2).group(0) if re.search(p, vf2) else None) for k, p in {
    "travel": r"X Axis\s+\S+ in\s+\S+ mm.{0,120}", "spindle_speed": r"Max Speed\s+\d+ rpm", "air_required": r"Air Required\s+[^A-Z]{5,60}",
    "air_min": r"Air Pressure Min\s+[^A-Z]{5,40}", "tool_changer": r"Capacity\s+\d+[^A-Z]{0,20}"}.items()}

# ---------- KOSHA / 법령 ----------
kosha_dir = DOCS / "kosha"
ev["kosha_guides_saved"] = sorted(p.name for p in kosha_dir.glob("KOSHA_*.pdf"))
ev["kosha_title_contains"] = {kw: [p.name for p in kosha_dir.glob("*.pdf") if kw in p.name] for kw in ["머시닝", "밀링", "정비", "잠금", "LOTO"]}
loto = pdf_pages(next(p for p in kosha_dir.glob("KOSHA_B-M-25-2026*.pdf")).relative_to(DOCS).as_posix())
flat = "\n".join(loto)
ev["loto_guide_pages"] = len(loto)
ev["loto_guide_steps"] = [" ".join(m.split()) for m in re.findall(r"\n\s*([67]\.\d\s[^\n]{3,40})", flat)]
law = (kosha_dir / "law_sanan_gijun_rule_text.txt").read_text(encoding="utf-8", errors="ignore")
for art in ["제92조(", "제95조(", "제32조("]:
    j = law.find(art)
    ev["law_" + art.strip("(")] = " ".join(law[j:j + 700].split())
all_kosha = {}
for p in kosha_dir.glob("*.pdf"):
    try:
        all_kosha[p.name] = "\n".join(pdf_pages(p.relative_to(DOCS).as_posix()))
    except FileNotFoundError:
        pass
for kw in ["면장갑", "NBR", "니트릴", "맨손", "방유", "보안경", "귀마개", "청력보호구", "안전화"]:
    ev["kosha_word_" + kw] = {n: t.count(kw) for n, t in all_kosha.items() if t.count(kw)}
ev["kosha_no_text_pdfs"] = sorted(n for n, t in all_kosha.items() if len(t.strip()) < 1500)

# ---------- 품질 기준 ----------
for name, rel, pat in [("ford_csr_Ppk", "quality/iatf_ford_csr_2026-06.pdf", r"Ppk\s*[>≥]\s*1\.\d\d"),
                       ("ford_ppap_Ppk", "quality/iatf_ford_ppap_specifics_2026-06.pdf", r"Ppk\s*[>≥]\s*1\.\d\d"),
                       ("cummins_Ppk", "quality/cummins_supplier_handbook_csr.pdf", r"1\.(33|67)"),
                       ("danfoss_Cpk", "quality/danfoss_sqm_AH492546005846.pdf", r"Cpk[^.]{0,60}1\.\d\d"),
                       ("general_tolerance", "quality/enersys_general_tolerances_iso2768.pdf", r"120[^0-9]{1,12}400[^\n]{0,60}")]:
    try:
        ev[name] = [f"p{p}: {t}" for p, t in find_all(pdf_pages(rel), pat, 110)[:4]]
    except FileNotFoundError:
        ev[name] = "파일 없음"
mis = html_text(DOCS / "quality" / "misumi_kr_a0194_general_tolerances.html")
k = mis.find("120")
ev["misumi_kr_general_tolerance_excerpt"] = mis[mis.find("보통 허용차"):][:600]

# ---------- KPI 식 (NIST 논문) ----------
try:
    kpi = "\n".join(pdf_pages("quality/05_NIST_ISO22400_KPI_paper_2016.pdf"))
    flatk = " ".join(kpi.split())
    for kw in ["Availability (A)", "Mean time to failure", "MTBF = MOTBF", "Mean time to repair"]:
        j = flatk.find(kw)
        ev["kpi_" + kw] = flatk[j:j + 330]
except FileNotFoundError:
    ev["kpi"] = "파일 없음"

save_json("claim_evidence.json", ev)
for k, v in ev.items():
    s = str(v)
    print(f"\n## {k}\n{s[:1500]}")
