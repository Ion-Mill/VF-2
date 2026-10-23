'use client';
// SCR-25 설정 (관리자만) — 설비·알림 규칙·목표 수량·안전 재고. 바꾸면 서버(API-SET-01·02, API-INV-05)에 남고 누가·언제 기록. 보고 순위는 보기만.
import { useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { LAYOUT, MASTERS } from './data';
import { api, hm, md, useFetch } from './live';
import { userName } from './model';
import { ConfirmBox } from './Safety';
import { Band as CBand } from './ui';
import { settingsBand } from './bands';

type R = Record<string, any>;
const TABS = ['설비', '알림 규칙', '목표 수량', '안전 재고'] as const; // 사용자 탭은 직원 관리(SCR-27)로 옮김 (2026-10-23)

export function SettingsScreen() {
  const { key, role, user, back, go, toast, inv, reloadInv } = useApp();
  const [tab, setTab] = useState<(typeof TABS)[number]>((TABS as readonly string[]).includes(key ?? '') ? (key as (typeof TABS)[number]) : '알림 규칙');
  const s = useFetch<{ targets: R; safety: R; rules: R; log: R[] }>('settings', 0, []);
  const [draft, setDraft] = useState<R>({});
  const [confirm, setConfirm] = useState(false);
  if (role !== 'MGR') return <div className={PAGE}><div className={CARD}>설정은 관리자만 열 수 있습니다 (서버도 거부, NFR-SEC-04). <button onClick={back} className={BTN}>닫기</button></div></div>;
  const rules = { ...(s.data?.rules ?? {}), ...(draft.rules ?? {}) };
  const save = async () => { try { await api('settings', { role, user_id: user.id, ...draft }); toast('설정 저장 — DOC-07과 다른 값이면 DOC-07 개정이 필요합니다'); setDraft({}); s.reload(); reloadInv(); } catch (e) { toast((e as Error).message); } };
  const inp = 'h-11 w-24 rounded border border-line px-1';
  const R2 = [['repeat_days', '반복 알람 — 며칠 안', '7일 안 3번 이상', 'DOC-07 10.2 [가상]'], ['repeat_count', '반복 알람 — 몇 번', '', ''], ['target_risk_pct', '목표 미달 위험 (총 목표의 %)', '90% 미만', 'DOC-07 8장 [가상]'], ['repeat2_days', '반복 알람 2단계 재발 확인 기간 (일)', '조치 계획 뒤 7일 안 재발 1번', 'DOC-07 §10.4 [가상]']];

  return (
    <div className={PAGE}>
      {/* 디자인 통일 C안: 결론 띠 (bands.ts settingsBand) — 저장 안 한 칸 수, 없으면 지금 알림 기준 */}
      <div className="mx-auto mb-3 max-w-[1440px]"><CBand spec={settingsBand({ repeat_days: Number(rules.repeat_days ?? 7), repeat_count: Number(rules.repeat_count ?? 3), target_risk_pct: Number(rules.target_risk_pct ?? 90) }, Object.values(draft).reduce((n: number, v) => n + (v && typeof v === 'object' ? Object.keys(v).length : 1), 0))} onAction={() => setConfirm(true)} /></div>
      <div className={`${CARD} mx-auto max-w-[1440px]`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-card font-bold">설정</h2>
          <div className="flex flex-wrap gap-1">{TABS.map((t) => <button key={t} onClick={() => setTab(t)} className={`${BTN} ${tab === t ? '!border-brand !bg-tile' : ''}`}>{t}</button>)}<button onClick={back} className={BTN}>닫기</button></div>
        </div>
        <button onClick={() => go('staff')} className="mt-2 text-small font-semibold text-info hover:underline">사용자(직원 명단·담당 교대·공정)는 직원 관리에서 봅니다 ›</button>{/* 사용자 탭을 SCR-27로 옮김 (2026-10-23) */}
        {tab === '설비' && <table className="mt-3 w-full text-left text-body"><thead className="text-ink-2"><tr><th>설비</th><th>공정</th><th>모델</th><th>크기 (mm)</th><th>가운데 (mm)</th><th>정면</th><th>기준 사이클</th><th>구분</th></tr></thead>
          <tbody>{Object.entries(LAYOUT.equipment).map(([k, e]) => <tr key={k} className="border-t border-line-soft"><td>{k}</td><td>{e.process}</td><td>{e.model}{e.ref ? ` (${e.ref})` : ''}</td><td>{e.size.join(' × ')}</td><td>{e.center.join(', ')}</td><td>{e.facing === 'POS_X' ? '동쪽' : '통로(남)'}</td><td>{e.std_cycle_min ? `${e.std_cycle_min}분` : `${e.batch_time_min}분/${e.batch_qty}개`}</td><td>{e.tag}</td></tr>)}</tbody></table>}
        {tab === '알림 규칙' && (<div className="mt-3 text-body">
          <table className="w-full text-left"><thead className="text-ink-2"><tr><th>규칙</th><th>값</th><th>근거</th></tr></thead><tbody>
            {R2.map(([k, n, , src]) => <tr key={k} className="border-t border-line-soft"><td>{n}</td><td><input type="number" value={rules[k] ?? ''} onChange={(e) => setDraft({ ...draft, rules: { ...(draft.rules ?? {}), [k]: Number(e.target.value) } })} className={inp} /></td><td>{src}</td></tr>)}
            <tr className="border-t border-line-soft"><td>짧은 반복 묶기</td><td>{rules.burst}</td><td>DOC-07 10.2 [참고] (보기만)</td></tr>
            <tr className="border-t border-line-soft"><td>알림 폭주</td><td>{rules.flood}</td><td>DOC-07 10.3 [참고] (보기만)</td></tr>
            <tr className="border-t border-line-soft"><td>보고 순위 (전부 보고)</td><td>0 안전 ~ 4 참고</td><td>DOC-07 §10.5 [제안] (프로그램 규칙, 보기만)</td></tr>
          </tbody></table>
          <h3 className="mt-3 font-bold text-ink-2">알림 규칙 25종 (notification_rule.csv)</h3>
          <ul className="text-small">{(MASTERS.rules as R[]).map((r) => <li key={r.rule_code}>{r.rule_code} · {r.rule_name} · {r.importance} · {r.delivery_kind} — {r.condition_text}</li>)}</ul>
        </div>)}
        {tab === '목표 수량' && <div className="mt-3 text-body">교대 목표 <input type="number" value={draft.shift_target ?? s.data?.targets.shift ?? 90} onChange={(e) => setDraft({ ...draft, shift_target: Number(e.target.value) })} className={inp} />개 · 하루 180개 (DOC-07 4.1) {draft.shift_target && draft.shift_target !== 90 ? <span className="font-semibold text-ink-2">ⓘ DOC-07과 다른 값입니다 — DOC-07 개정이 필요합니다</span> : null}</div>}
        {tab === '안전 재고' && <table className="mt-3 w-full text-left text-body"><thead className="text-ink-2"><tr><th>품목</th><th>지금 재고</th><th>안전 재고</th></tr></thead>
          <tbody>{(inv?.items ?? []).filter((i) => i.category !== 'FG').map((i) => <tr key={i.item_no} className="border-t border-line-soft"><td>{i.item_name}</td><td>{i.stock_qty}{i.unit}</td><td><input type="number" value={draft.safety?.[i.item_no] ?? i.safety_stock} onChange={(e) => setDraft({ ...draft, safety: { ...(draft.safety ?? {}), [i.item_no]: Number(e.target.value) } })} className={inp} /></td></tr>)}</tbody></table>}
        {tab !== '설비' && <div className="mt-3 flex items-center gap-2 border-t border-line pt-3"><button disabled={!Object.keys(draft).length} onClick={() => setConfirm(true)} className={DARK}>바꾸기</button><span className="text-small text-ink-2">식: 안전 재고 = 설비에 달린 수 + 하루 사용량 × 3일분 [참고]</span></div>}
        <section className="mt-3 border-t border-line-soft pt-3 text-small"><b className="text-ink-2">바꾼 사람·시각</b>
          <ul>{(s.data?.log ?? []).map((l, i) => <li key={i}>{md(l.at)} {hm(l.at)} · {userName(l.by)} · {JSON.stringify(l.what)}</li>)}{!(s.data?.log ?? []).length && <li>—</li>}</ul></section>
      </div>
      {confirm && <ConfirmBox title="설정을 바꿀까요?" okLabel="바꾸기" body="바꾼 사람·시각이 기록됩니다. DOC-07과 다른 값이면 DOC-07 개정이 필요합니다." onOk={() => { setConfirm(false); void save(); }} onCancel={() => setConfirm(false)} />}
    </div>
  );
}
