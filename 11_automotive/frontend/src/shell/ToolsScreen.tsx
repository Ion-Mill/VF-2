'use client';
// SCR-22 공구 수명 — OP-30 VF-2 공구 T01~T05. 사용률 = 누적 ÷ 한도, 90% 이상 ▲. 남은 수명 = 100 − 사용률, 남은 부품 수 = (한도 − 누적) ÷ 부품당 사용량.
// [공구 교체] = API-TOOL-02 → 시뮬레이터 record_tool_change (사용량 0, 준비 3~8분, 재고 차감).
// 화면 구조 (사용자 시안 2026-10-16): 왼쪽 공구 목록(전체/VF2-01/VF2-02) · 오른쪽 고른 공구 상세(원 그래프·누적/한도·교체 이력). 전체 = 두 설비 교체 이력만.
import { useState } from 'react';
import { PAGE, useApp } from './ctx';
import { Band, Tabs } from './ui';
import { toolsBand } from './bands';
import { MASTERS, STATE_VIEW, stateOf } from './data';
import { api, hm, md, useFetch } from './live';
import { userName } from './model';
import { ConfirmBox } from './Safety';

type R = Record<string, any>;
const LIMIT_PCT = 90; // 공구 수명 한도 (교체 준비 기준)
const EQS = ['VF2-01', 'VF2-02'] as const;
// 교체 사유 코드 → 한글
const reasonKo = (r: string) => (r === 'LIFE_90' ? '수명 90% 도달' : r.startsWith('ALARM_') ? `알람 ${r.slice(6)}` : r === 'OTHER' ? '기타' : r || '—');
const box = 'rounded-card border border-line bg-white p-5';

export function ToolsScreen() {
  const { key, twin, role, user, toast, alerts, reloadInv, eve } = useApp(); // eve: 이브 창 열림 — 공구 칸 넓히고 교체 이력 줄임
  const [eq, setEq] = useState<string>(key === 'VF2-01' || key === 'VF2-02' ? key : '전체');
  const [selId, setSelId] = useState<string | null>(null);
  const f = useFetch<{ tools: R[]; changes_today: R[]; past_changes: R[] }>('tools', 8000);
  const [confirm, setConfirm] = useState<string | null>(null);
  const types = MASTERS.tool_types as R[], items = MASTERS.items as R[];
  const toolsOf = (e: string) => (twin?.equipment[e as 'VF2-01'].tools ?? f.data?.tools.filter((t) => t.equipment_id === e) ?? []) as R[];
  const all = EQS.flatMap(toolsOf);
  const list = (eq === '전체' ? all : toolsOf(eq)).slice().sort((a, b) => b.usage_pct - a.usage_pct);
  const sel = eq === '전체' ? null : list.find((t) => t.tool_id === selId) ?? list[0] ?? null;
  const nameOf = (t: R) => items.find((x) => x.item_no === t.item_no)?.item_name ?? '';
  // 최신이 위로. 시연 기준일(10/1)까지만 보여 줌 — 10/2 이후는 시연이 밤새 흘러 생긴 기록 (사용자 요청 2026-10-16)
  const changesAll = [...(f.data?.changes_today ?? []), ...(f.data?.past_changes ?? [])]
    .filter((c) => String(c.changed_at) < '2026-10-02').sort((a, b) => String(b.changed_at).localeCompare(String(a.changed_at)));
  const changes = (sel ? changesAll.filter((c) => c.tool_id === sel.tool_id) : changesAll).slice(0, 30);
  const canChange = role === 'OPR' || role === 'MNT';

  const pickEq = (e: string) => { setEq(e); setSelId(null); };
  const st = sel ? STATE_VIEW[stateOf(twin?.equipment[sel.equipment_id as 'VF2-01'])] : null;
  const al = sel && sel.tool_no === 'T05' ? alerts.find((a) => a.machine === (sel.equipment_id === 'VF2-01' ? 'vf1' : 'vf2') && (a.code === '362' || a.code === '174') && !a.cleared) : undefined;
  const unitOf = (t: R) => (types.find((x) => x.item_no === t.item_no)?.usage_unit === 'HOLES' ? '구멍' : '분');
  const unit = sel ? unitOf(sel) : '분';

  // 교체 이력 높이 = 왼쪽 공구 목록 끝까지. [contain:size]로 표가 칸을 늘리지 않고 안에서 스크롤 (사용자 요청 2026-10-19)
  const history = (
    <section className={`${box} flex min-h-0 flex-1 flex-col`}>
      <h3 className="flex items-center gap-2 text-card font-bold">교체 이력 — {sel ? `${sel.equipment_id}  ${sel.tool_no}` : EQS.join(' · ')}</h3>
      {changes.length === 0 ? <p className="mt-3 text-body text-ink-2">교체 기록 없음</p> : (
        <div className="mt-2 min-h-[160px] flex-1 overflow-y-auto [contain:size]">{/* 이브 열림: 시각·공구·교체 사유만, 줄 간격 줄임 */}
        <table className={`w-full text-left ${eve ? 'text-body' : 'text-card'}`}>
          <thead className="sticky top-0 border-y border-line-soft bg-white text-small text-ink-2"><tr>{(eve ? ['교체 시각', ...(sel ? [] : ['공구']), '교체 사유'] : ['교체 시각', ...(sel ? [] : ['공구']), '교체 시 사용량 / 한도', '교체 사유', '교체자']).map((h) => <th key={h} className={`font-semibold ${eve ? 'py-1.5 pr-4' : 'py-2 pr-6'}`}>{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-100">{changes.map((c, i) => {
            const t = all.find((x) => x.tool_id === c.tool_id), lim = t?.limit, used = Math.round(Number(c.cum_before));
            const u = t ? unitOf(t) : '분';
            return (
              eve ? (
              <tr key={i}>
                <td className="whitespace-nowrap py-1.5 pr-4 font-mono">{md(c.changed_at)} {hm(c.changed_at)}</td>
                {!sel && <td className="whitespace-nowrap py-1.5 pr-4 font-mono font-semibold">{c.tool_id}</td>}
                <td className="whitespace-nowrap py-1.5">{reasonKo(String(c.change_reason ?? ''))}</td>
              </tr>) : (
              <tr key={i}>
                <td className="py-2.5 pr-6 font-mono">{md(c.changed_at)} {hm(c.changed_at)}</td>
                {!sel && <td className="py-2.5 pr-6 font-mono font-semibold">{c.tool_id}</td>}
                <td className="py-2.5 pr-6"><b className="font-mono">{used} / {lim ?? '—'}</b> {u}{lim ? <span className="text-ink-2"> ({Math.round((used / lim) * 100)}%)</span> : null}</td>
                <td className="py-2.5 pr-6">{reasonKo(String(c.change_reason ?? ''))}</td>
                <td className="py-2.5 text-ink-2">{userName(c.changed_by)}</td>
              </tr>));
          })}</tbody>
        </table>
        </div>
      )}
    </section>
  );

  return (
    <div className={PAGE}>
      {/* 디자인 통일 C안: 결론 띠 1개 (bands.ts toolsBand, 보기 전용이라 버튼 없음) */}
      <div className="mx-auto mb-3 max-w-[1440px]"><Band spec={toolsBand(all.map((x) => ({ equipment_id: String(x.equipment_id), tool_no: String(x.tool_no), label: nameOf(x), usage_pct: Number(x.usage_pct), warn: !!x.warn })), LIMIT_PCT)} /></div>
      <div className={`mx-auto grid max-w-[1440px] items-stretch gap-3 ${eve ? 'grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]' : 'grid-cols-[minmax(320px,0.9fr)_1.6fr]'}`}>
        {/* 왼쪽: 공구 목록 */}
        <section className={`${box} self-start`}>
          <h3 className="text-card font-bold">공구 — OP-30 {EQS.join(' · ')}</h3>
          <div className="mt-3"><Tabs label="설비" value={eq} onChange={pickEq} items={['전체', ...EQS].map((e) => ({ key: e, label: e, count: e === '전체' ? all.length : undefined, warn: (e === '전체' ? all : toolsOf(e)).filter((x) => x.warn).length }))} /></div>
          <p className="mt-3 text-right text-small text-ink-2"><span className="mr-1 inline-block h-3 w-[2px] translate-y-0.5 bg-ink" />교체 준비 기준 = 한도의 {LIMIT_PCT}%</p>
          <ul className="mt-2 flex flex-col gap-2">{list.map((t) => {
            const on = sel?.tool_id === t.tool_id;
            return (
              <li key={t.tool_id}>
                <button onClick={() => { if (eq === '전체') setEq(t.equipment_id); setSelId(t.tool_id); }} className={`w-full rounded-tile border px-4 py-3 text-left ${on ? 'border-2 border-brand bg-tile' : 'border-line-soft bg-white'}`}>
                  <div className="flex items-center gap-3 text-card">
                    {t.warn && <span className="text-[#d39a00]">▲</span>}<b>{t.equipment_id}</b><span className="min-w-0 flex-1 truncate">{t.tool_no} {nameOf(t)}</span>
                    {t.limit != null && <span className="shrink-0 whitespace-nowrap font-mono text-small text-ink-2">{Math.round(t.cum)} / {t.limit}{unitOf(t)}</span>}<b className="font-mono">{t.usage_pct}%</b>
                  </div>
                  <div className="relative mt-2 h-2.5 rounded-full bg-track">
                    <div className="h-full rounded-full" style={{ width: `${Math.min(100, t.usage_pct)}%`, background: t.warn ? '#e0b000' : '#4b5a69' }} />
                    <span className="absolute -top-1 flex h-[18px] w-[10px] -translate-x-1/2 cursor-help justify-center" style={{ left: `${LIMIT_PCT}%` }} title={t.limit != null ? `교체 준비 ${Math.round((t.limit * LIMIT_PCT) / 100)}${unitOf(t)} (한도의 ${LIMIT_PCT}%)` : undefined}><span className="h-full w-[2px] bg-ink" /></span>
                  </div>
                </button>
              </li>);
          })}</ul>
          {!canChange && <p className="mt-3 text-small text-ink-2">보기 전용 (공구 교체는 작업자·보전 담당자)</p>}
        </section>

        {/* 오른쪽: 고른 공구 상세 — 전체일 때는 교체 이력만 */}
        <div className="flex flex-col gap-4">
          {sel && (<>
            <section className={`${box} flex flex-wrap items-center gap-4`}>
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-card font-bold">{sel.equipment_id}{st && <span style={{ color: st.color }}>{st.icon} {st.text}</span>}{al && <span className="text-crit">{al.code === '362' ? '⚠' : '▲'} 알람 {al.code}</span>}</div>
                <div className={`font-bold leading-tight ${eve ? 'text-title' : 'text-num'}`}>{sel.tool_no} {nameOf(sel)}</div>
              </div>
              {sel.warn && <span className="rounded-full border border-warn-mark bg-warn-bg px-4 py-1.5 text-card font-bold text-warn">▲ 교체 준비</span>}
              {canChange && <button onClick={() => setConfirm(sel.tool_id)} className="ml-auto h-14 rounded-tile bg-brand px-8 text-band font-bold text-white shadow">공구 교체</button>}
            </section>
            <div className={`grid gap-4 ${eve ? 'grid-cols-1' : 'grid-cols-[1fr_1.3fr]'}`}>
              <section className={`${box} flex items-center justify-center`}><Ring pct={sel.usage_pct} warn={sel.warn} /></section>
              <section className={`${box} flex flex-col justify-center`}>
                <div className="text-card text-ink-2">누적 / 한도</div>
                <div className={`mt-1 font-mono font-semibold ${eve ? 'text-num' : 'text-tablet'}`}>{Math.round(sel.cum)} <span className="mx-2">/</span> {sel.limit} <span className="font-sans text-band">{unit}</span></div>
                <div className="mt-2 text-body text-ink-2">남은 수명 {Math.max(0, Math.round((100 - sel.usage_pct) * 10) / 10)}% · 부품 {sel.left_parts ?? '—'}개</div>
              </section>
            </div>
          </>)}
          {history}
        </div>
      </div>
      {confirm && <ConfirmBox title={`${confirm} 공구 교체를 기록할까요?`} okLabel="공구 교체" body="사용률이 0%가 되고 공구 재고가 차감됩니다 (페이스밀 인서트는 5개). 설비는 3~8분 준비(SETUP)입니다."
        onOk={async () => { const t = confirm; setConfirm(null); try { await api(`tools/${t}/change`, { role, user_id: user.id }); toast(`${t} 공구 교체 — 사용률 0%`); f.reload(); reloadInv(); } catch (e) { toast((e as Error).message); } }} onCancel={() => setConfirm(null)} />}
    </div>
  );
}

// 공구 수명 원 그래프 — 한도(90%) 눈금 표시
function Ring({ pct, warn }: { pct: number; warn: boolean }) {
  const r = 88, c = 2 * Math.PI * r, p = Math.min(100, Math.max(0, pct)) / 100;
  const a = (LIMIT_PCT / 100) * 2 * Math.PI - Math.PI / 2, x1 = 110 + Math.cos(a) * 70, y1 = 110 + Math.sin(a) * 70, x2 = 110 + Math.cos(a) * 106, y2 = 110 + Math.sin(a) * 106;
  return (
    <svg viewBox="0 0 220 220" className="h-[220px] w-[220px]" role="img" aria-label={`공구 수명 ${pct}%`}>
      <circle cx="110" cy="110" r={r} fill="none" stroke="#e5e8ee" strokeWidth="20" />
      <circle cx="110" cy="110" r={r} fill="none" stroke={warn ? '#e0b000' : '#4b5a69'} strokeWidth="20" strokeDasharray={`${p * c} ${c}`} transform="rotate(-90 110 110)" />
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#1c2530" strokeWidth="3" />
      <text x="110" y="118" textAnchor="middle" fontSize="44" fontWeight="800" fill="#1c2530">{pct}%</text>
      <text x="110" y="146" textAnchor="middle" fontSize="15" fill="#5d6b79">공구 수명</text>
    </svg>
  );
}
