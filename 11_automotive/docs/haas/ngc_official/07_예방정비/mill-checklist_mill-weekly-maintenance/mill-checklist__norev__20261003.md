---
source_path: 'C:/code/1/참고문서/매뉴얼/VF 시리즈 서비스 매뉴얼/찐/07_예방정비/mill-checklist_mill-weekly-maintenance/mill-checklist__norev__20261003.pdf'
source_name: 'mill-checklist__norev__20261003.pdf'
file_type: pdf
content_hash: 'sha256:3a2d2f0eb8bd5dd0dc975a0ddf3608a4b1d7ae617acfc5ec6a89a913983984d2'
converter: MarkItDown
converter_version: '0.1.8'
converter_detail: 'MarkItDown convert_stream() 쪽 단위 변환 + PyMuPDF 1.28.2 (다단 쪽 좌->우 단 순서 추출, 머리글·바닥글 분리, heading 판정), pdfminer.six 20260107, pdfplumber 0.11.10'
converted_at: '2026-10-03T18:09:59+09:00'
page_marker_format: '<!-- page: N / 총쪽수 -->'
page_extractors: {"markitdown": 1}
warnings:
  - '다단 판정 쪽 0개는 MarkItDown 대신 PyMuPDF 단어 좌표로 좌->우 단 순서 추출함(쪽별 extractor 주석 참조)'
  - '표 의심(좌우 행 같은 baseline, 항목 번호 아님) 영역이 있는 쪽 0개: 행 단위 원문 추출 보존, 행·열 관계 원문 PDF 대조 필요'
  - 'MarkItDown 출력 토큰 회수율 < 0.95(단어 결합·라벨 뒤섞임) 쪽 0개는 PyMuPDF 행 추출로 대체함'
  - '위첨자 후보 쪽 0개(0건): 앞 글자와 붙어 수치가 바뀔 수 있음(PDF 150쪽 360⁰ -> 3600 육안 확인). 치환하지 않음, 원문 PDF 대조 필요'
  - '제어문자 표시(ctrl:0xNN) 쪽 0개, (cid:N) 0건: 원래 글자 미확인, 치환하지 않음'
  - '같은 줄 연속 반복 후보 쪽 0개(PDF 115쪽 WARNING! 1회 인쇄 -> 5회 추출 육안 확인): 삭제하지 않음'
  - 'MarkItDown이 만든 Markdown 표가 남은 쪽 0개: 행·열 관계 미검증, 원문 PDF 대조 필요'
  - 'heading 계층은 글꼴·제목 막대 기준(ArialMTBlack + 전폭 막대 -> ##, 반폭 막대 -> ###, Arial-Bold 11pt -> ####, 10pt -> #####). PDF 목차(북마크)와 대조하지 않음'
  - '도면 라벨·표·수식·치수·토크 값은 원문 PDF 쪽과 대조 필요'
  - '1쪽은 2013-06-06 Haas 아카이브 표지이며 본문(96-0283 rev C June 2007)과 다른 문서임'
validation_status:
  text_extraction: confirmed_by_token_comparison
  page_boundaries: preserved_with_markers
  reading_order: needs_review
  tables_formulas_diagrams: compare_with_source_pdf
validation_metrics_file: 'mill-checklist__norev__20261003.verification-pages.csv'
validation_summary_file: 'mill-checklist__norev__20261003.verification-summary.json'
---

# mill-checklist__norev__20261003

> 변환·탐색용 Markdown입니다. 사실 확인의 기준은 원본 PDF입니다. 안전 절차·토크·치수·부품 번호는 해당 PDF 쪽과 대조하십시오.

<!-- page: 1 / 1 -->
<!-- header: MILL WEEKLY MAINTENANCE CHECKLIST -->
<!-- extractor: markitdown; layout: single -->

This document provides a list of tasks that are recommended to be completed on a daily and weekly
basis to ensure the proper maintenance and performance of a Haas mill can be achieved.

Morning Tasks:

  Run spindle warm-up program.  We recommend you put a tool holder in the spindle while
running.  For 10,000 RPM spindles and above, you must always use a balanced grade tool
(balanced grade is G2.5 or better ANSI S2.19) in the spindle while the warm-up program is
running.

  Check air lines for water. Depress the trigger on the air gun so any water present in the lines

will be evacuated.  If water issues persist, check the shop air.

  Check coolant level in control.  Verify that it is in the proper operating range.
  Check air pressure in control.  Verify that it is in the proper operating range.
  Check coolant concentration.  Use a refractometer and verify that the concentration meets the

manufacturer’s specifications.

Daily Tasks:

  Check tool holders, pull studs, and tool tapers for damage. Clear off any chips on the tool taper

and remove tools with rust or galling.

End of Day/Shift Tasks:

  Clear off all chips from waycovers.
  Check chip filter on top of coolant tank.  Remove any excessive piles of chips present.
  If leaving machine overnight or for an extended period: Remove the tool from the spindle (if
necessary). Use a rust inhibiter, such as WD 40, to clean and lubricate spindle taper.  Wipe
down taper with a clean, dry rag.

End of Week Tasks:

  SMTC: Clear off chip build up on the side-mounted tool changer arm. Check for sticky plungers

or worn keys.

  UMB: Clear off any chips from the top of the protective cover. Check the extractor forks and

keys for excessive wear or damage.

  Inspect the air regulator pressure gauge in the lube panel on your machine. Verify that it

matches the reading on the control and is within the acceptable operating range.

  Check the coolant float gauge and verify that it is operating properly and the displayed reading

matches the actual level in your tank.

  Check coolant concentration.  Use a refractometer and verify that the concentration meets the

manufacturer’s specifications.

  Check the surface of the coolant tank for tramp oil. Remove any present.
  Remove chips from coolant filter.
  (Add-on) Check TSC filter.  Replace if necessary.
  (Add-on) Check auxiliary filter bag.  Replace if necessary.

