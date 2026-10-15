"""가상 데이터·사내 문서에서 화면에 쓸 값을 뽑아 src/shell/generated.ts 를 만든다.

원본: 생성기/masters/app_user.csv, alarm_master.csv, alarm_guide_map.csv,
      가상사내문서/DOC-03(점검 순서 ★ 줄), DOC-05(§3 차단 지점·저장 에너지, §2.4 짧은 작업 줄, §7 고정 서식)
실행: python tools/build_data.py   (이 폴더 기준. 결과 파일은 직접 고치지 않는다)
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # 11_automotive
OUT = Path(__file__).resolve().parents[1] / 'src' / 'shell' / 'generated.ts'


def tags(s):
    return re.sub(r'\s*\[(?:실제|가상|참고)[^\]]*\]', '', s).replace('**', '').strip()


# ---------- 사용자 ----------
users = []
for r in csv.DictReader(open(ROOT / '생성기/masters/app_user.csv', encoding='utf-8-sig')):
    users.append({
        'id': r['user_id'], 'name': r['user_name'], 'role': r['role_code'], 'shift': r['home_shift_type'],
        'procs': [p for p in (r['home_process_code'], r['home_process_code_2']) if p],
    })

# ---------- 알람 + DOC-03 점검 순서 ----------
doc03 = (ROOT / '가상사내문서/DOC-03_고장대응매뉴얼.md').read_text(encoding='utf-8').split('\n')
heads = [(i, l) for i, l in enumerate(doc03) if l.startswith('### ')]


def doc03_steps(code):
    for n, (i, h) in enumerate(heads):
        if re.search(r'(?<![\w.])' + re.escape(code) + r'(?![\w])', h):
            end = heads[n + 1][0] if n + 1 < len(heads) else len(doc03)
            sec = doc03[i:end]
            steps = []
            for l in sec:
                m = re.match(r'\|\s*★(\d+)\s*\|\s*[^|]*\|\s*([^|]+)\|', l)
                if m:
                    steps.append(tags(m.group(2)))
                elif l.startswith('| 점검 |'):
                    cell = l.split('|')[2]
                    steps += [tags(re.sub(r'^★\d+\s*', '', s.strip())) for s in cell.split(' / ') if s.strip().startswith('★')]
            m = re.match(r'### (\d+\.\d+)', h)
            extra = {'symptom': '', 'maint': [], 'actions': []}
            for l in sec:
                mm = re.match(r'\|\s*(?:증상·알람|증상)\s*\|\s*([^|]+)\|', l)
                if mm and not extra['symptom']:
                    extra['symptom'] = tags(mm.group(1)).split('. ')[0].rstrip('.')
                mm = re.match(r'\|\s*(\d+)\s*\|\s*보전\s*\|\s*([^|]+)\|', l)
                if mm:
                    extra['maint'].append(tags(mm.group(2)))
                mm = re.match(r'\*\*조치:?\*\*:?\s*(.+)', l)
                if mm:
                    extra['actions'] = [x.strip() for x in tags(mm.group(1).split('. ')[0]).split(' / ') if x.strip()]
                mm = re.match(r'\|\s*조치\s*\|\s*([^|]+)\|', l)
                if mm and not extra['actions']:
                    extra['actions'] = [tags(mm.group(1)).split('. ')[0]]
            return steps[:5], (('DOC-03 §' + m.group(1)) if m else ''), extra
    return [], '', {'symptom': '', 'maint': [], 'actions': []}


guide_map = {}
for r in csv.DictReader(open(ROOT / '생성기/masters/alarm_guide_map.csv', encoding='utf-8-sig')):
    guide_map.setdefault(r['alarm_code'], []).append(f"{r['doc_no']} {r['section']}")

alarms = {}
for r in csv.DictReader(open(ROOT / '생성기/masters/alarm_master.csv', encoding='utf-8-sig')):
    steps, sec, extra = doc03_steps(r['alarm_code'])
    alarms[r['alarm_code']] = {
        'code': r['alarm_code'], 'process': r['process_code'], 'nameKo': r['name_ko'], 'nameEn': r['name_en'],
        'easy': r['easy_desc'], 'severity': r['severity'], 'responder': r['responder'], 'note': r['responder_note'],
        'lockout': r['lockout_level'], 'chain': r['chain_rule'], 'doc02': 'DOC-02 ' + r['doc02_section'],
        'doc03': guide_map.get(r['alarm_code'], [sec] if sec else []), 'steps': steps,
        'symptom': extra['symptom'], 'maint': extra['maint'], 'actions': extra['actions'],
    }

# ---------- 재고 ----------
stock = {}
for r in csv.DictReader(open(ROOT / '생성기/out/inventory_txn.csv', encoding='utf-8-sig')):
    stock[r['item_no']] = stock.get(r['item_no'], 0) + float(r['qty_change'] or 0)
inventory = []
for r in csv.DictReader(open(ROOT / '생성기/masters/inventory_item.csv', encoding='utf-8-sig')):
    if r['category'] in ('TOOL', 'CONSUMABLE', 'MAINT', 'SUPPLY') or r['item_no'].startswith(('TL-', 'CS-')):
        inventory.append({'no': r['item_no'], 'name': r['item_name'], 'unit': r['unit'], 'owner': r['owner_role'],
                          'safety': float(r['safety_stock'] or 0), 'stock': stock.get(r['item_no'], 0)})

# ---------- 교대 보고서 (지난 교대 브리핑·문서함) ----------
reports = []
for r in csv.DictReader(open(ROOT / '생성기/out/shift_report.csv', encoding='utf-8-sig')):
    reports.append({'id': r['shift_id'], 'status': r['status'], 'target': int(r['target_qty']), 'actual': int(r['actual_qty']), 'defect': int(r['defect_qty']),
                    'notable': r['notable_text'], 'handover': r['handover_text'], 'by': r['confirmed_by']})
last = reports[-1]
ranked = []
for part in re.split(r' / (?=\d(?:-\d)? )', last['handover']):
    m = re.match(r'(\d(?:-\d)?) ([^:]+): (.*)', part.strip())
    if m:
        ranked.append({'rank': m.group(1), 'name': m.group(2), 'items': [] if m.group(3).strip() == '-' else [x.strip() for x in m.group(3).split('; ')]})
orders = [{'no': r['order_no'], 'qty': int(r['order_qty']), 'status': r['status']}
          for r in csv.DictReader(open(ROOT / '생성기/out/production_order.csv', encoding='utf-8-sig')) if r['status'] in ('IN_PROGRESS', 'WAITING')]
briefing = {'last': {k: last[k] for k in ('id', 'target', 'actual', 'defect', 'notable')}, 'ranked': ranked, 'orders': orders,
            'reports': [{k: x[k] for k in ('id', 'status', 'target', 'actual', 'defect')} for x in reports]}

# ---------- DOC-07 5.1 정지 사유 코드 ----------
doc07 = (ROOT / '가상사내문서/DOC-07_설비데이터지표정의서.md').read_text(encoding='utf-8').splitlines()
reasons, grp, on = [], '', False
for l in doc07:
    if l.startswith('### 5.1'):
        on = True
        continue
    if l.startswith('### 5.2'):
        break
    if on:
        m = re.match(r'\|\s*(\*\*[^|]+\*\*)?\s*\|\s*([FMSOP]\d\d)\s*\|\s*([^|]+)\|', l)
        if m:
            if m.group(1):
                grp = re.sub(r'\s*\(.*?\)', '', m.group(1)).strip('* ')
            name = re.sub(r'\*\*', '', m.group(3)).split(' (')[0].strip()
            reasons.append({'group': grp, 'code': m.group(2), 'name': name})

# ---------- DOC-05 ----------
doc05 = (ROOT / '가상사내문서/DOC-05_안전작업기준서.md').read_text(encoding='utf-8').split('\n')
safety = {}
cur = None
for l in doc05:
    m = re.match(r'### 3\.\d+ ([A-Z0-9-]+) ', l)
    if m:
        cur = m.group(1)
        safety[cur] = {'points': [], 'energy': []}
        continue
    if l.startswith('## '):
        cur = None
    if not cur:
        continue
    m = re.match(r'\|\s*([A-Z0-9]+-\d+-[EP]\d)\s*\|\s*([^|]+)\|', l)
    if m:
        safety[cur]['points'].append(f"{m.group(1)} {tags(m.group(2))}")
        continue
    m = re.match(r'\|\s*([^|]+?)\s*\|\s*[^|]+\|\s*[^|]+\|\s*$', l)
    if m and not set(m.group(1)) <= set('- ') and m.group(1) not in ('저장 에너지', '번호'):
        # 저장 에너지 표: 첫 칸이 에너지 이름 (3칸짜리 표)
        if not re.match(r'[A-Z0-9]+-\d+-[EP]\d', m.group(1)):
            safety[cur]['energy'].append(tags(re.sub(r'\s*\(.*?\)\s*', '', m.group(1))))

short = {}
sec24 = False
for l in doc05:
    if l.startswith('### 2.4'):
        sec24 = True
    elif l.startswith('## 3.'):
        sec24 = False
    if sec24 and l.startswith('| **') or (sec24 and l.startswith('| ') and '알람' in l.split('|')[1]):
        c = [x.strip() for x in l.strip().strip('|').split('|')]
        m = re.search(r'알람 ([0-9.]+)', c[0])
        if m and len(c) >= 5:
            short[m.group(1)] = {'work': tags(c[0]), 'judge': tags(c[3]), 'todo': tags(c[4])}

block, grab = [], False
for l in doc05:
    if l.startswith('━━━━━━━━━━ 안전 작업'):
        grab = True
    if grab:
        block.append(l)
    if grab and l.startswith('━━━━━━━━━━━━━━'):
        break

# ---------- 공장 배치 (3D·2D 배치도의 실제 좌표, SCR-04 "실제 크기 배치") ----------
M = lambda n: list(csv.DictReader(open(ROOT / f'생성기/masters/{n}.csv', encoding='utf-8-sig')))
pl = M('plant_layout')[0]
layout = {
    'plant': {k: float(pl[k]) for k in ('width_x_mm', 'depth_y_mm', 'ceiling_z_mm', 'aisle_width_mm', 'work_band_mm', 'equipment_gap_mm')},
    'equipment': {r['equipment_id']: {'process': r['process_code'], 'model': r['model'], 'size': [float(r['size_x_mm']), float(r['size_y_mm']), float(r['size_z_mm'])],
                                      'center': [float(r['center_x_mm']), float(r['center_y_mm'])], 'facing': r['facing'], 'tag': r['size_source_tag'],
                                      'ref': r['ref_model'], 'std_cycle_min': float(r['std_cycle_min'] or 0) or None,
                                      'batch_qty': int(r['batch_qty']) if r['batch_qty'] else None, 'batch_time_min': float(r['batch_time_min']) if r['batch_time_min'] else None}
                  for r in M('equipment')},
    'objects': {r['object_id']: {'kind': r['object_kind'], 'name': r['object_name'], 'x': [float(r['x_min_mm']), float(r['x_max_mm'])],
                                 'y': [float(r['y_min_mm']), float(r['y_max_mm'])], 'h': float(r['height_mm']) if r['height_mm'] else None,
                                 'tag': r['source_tag'], 'buffer': r['buffer_code'] or None} for r in M('layout_object')},
    'wip': {r['buffer_code']: {'from': r['from_process_code'], 'to': r['to_process_code'], 'limit': int(r['limit_qty']),
                               'warn_over': int(r['warn_over_qty']) if r['warn_over_qty'] else None, 'warn': r['warn_enabled'] == 'true'} for r in M('wip_buffer')},
}

# ---------- 기준 정보 (화면 표·이름) ----------
masters = {
    'product': M('product')[0],
    'processes': M('process'),
    'tools': M('tool'), 'tool_types': M('tool_type'),
    'items': M('inventory_item'),
    'inspection_items': M('inspection_item'), 'defect_codes': M('defect_code'),
    'sensors': M('sensor_item'), 'rules': M('notification_rule'), 'docs': M('internal_doc'),
    'downtime': M('downtime_reason'), 'pm_tasks': M('pm_task'), 'isolation': M('isolation_point'),
    'roles': M('role'),
}

data = {'users': users, 'alarms': alarms, 'safety': safety, 'short': short, 'block': block, 'inventory': inventory, 'briefing': briefing, 'reasons': reasons,
        'layout': layout, 'masters': masters}
OUT.write_text(
    '// 자동 생성 파일 — tools/build_data.py 로 다시 만든다. 직접 고치지 않는다.\n'
    'export const GENERATED = ' + json.dumps(data, ensure_ascii=False, indent=1) + ' as const;\n',
    encoding='utf-8')
# 시연 데이터 서버(tools/sim_server.py)도 같은 알람 정리(DOC-02·03)를 쓴다
(Path(__file__).resolve().parent / 'data.json').write_text(json.dumps({'alarms': alarms}, ensure_ascii=False), encoding='utf-8')
print('inventory', [(i['no'], i['stock'], i['safety']) for i in inventory][:12])
print('briefing', briefing['last'], [(x['rank'], len(x['items'])) for x in ranked], orders)
print('reasons', [(r['code'], r['group'], r['name']) for r in reasons])
print('users', len(users), 'alarms', len(alarms), 'safety', list(safety), 'short', list(short), 'block', len(block))
for c in ('992', '2075', '25050', '6302.00', 'WSH-01', 'MP-170', '314'):
    a = alarms[c]
    print(c, a['severity'], a['doc03'], len(a['steps']), a['steps'][:1])
