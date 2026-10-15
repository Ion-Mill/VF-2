'use client';
// SCR-22 공구 수명 — OP-30 VF-2 공구 T01~T05. 사용률 = 누적 ÷ 한도, 90% 이상 ▲. 남은 수명 = 100 − 사용률, 남은 부품 수 = (한도 − 누적) ÷ 부품당 사용량.
// [공구 교체 기록] = API-TOOL-02 → 시뮬레이터 record_tool_change (사용량 0, 준비 3~8분, 재고 차감).
import { useState } from 'react';
import { BTN, CARD, PAGE, useApp } from './ctx';
import { MASTERS } from './data';
import { api, hm, md, useFetch } from './live';
import { userName } from './model';
import { ConfirmBox } from './Safety';

type R = Record<string, any>;

export function ToolsScreen() {
  const { key, twin, role, user, back, toast, alerts, reloadInv } = useApp();
  const [eq, setEq] = useState<string>(key === 'VF2-02' ? 'VF2-02' : 'VF2-01');
  const f = useFetch<{ tools: R[]; changes_today: R[]; past_changes: R[] }>('tools', 8000);
  const [confirm, setConfirm] = useState<string | null>(null);
  const types = MASTERS.tool_types as R[], items = MASTERS.items as R[];
  const tools = (twin?.equipment[eq as 'VF2-01'].tools ?? f.data?.tools.filter((t) => t.equipment_id === eq) ?? []) as R[];
  const al = alerts.filter((a) => a.machine === (eq === 'VF2-01' ? 'vf1' : 'vf2') && (a.code === '362' || a.code === '174') && !a.cleared);
  const changes = [...(f.data?.changes_today ?? []), ...[...(f.data?.past_changes ?? [])].reverse()].filter((c) => c.tool_id.startsWith(eq)).slice(0, 15);
  const canChange = role === 'OPR' || role === 'MNT';

  return (
    <div className={PAGE}>
      <div className={CARD}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[19px] font-bold">공구 수명</h2>
          <div className="flex gap-1">{['VF2-01', 'VF2-02'].map((e) => <button key={e} onClick={() => setEq(e)} className={`${BTN} ${eq === e ? '!border-[#0f9fbd] !bg-[#e8f6fa]' : ''}`}>{e}</button>)}<button onClick={back} className={BTN}>닫기</button></div>
        </div>
        <table className="mt-3 w-full text-left text-[14px]">
          <thead className="text-slate-500"><tr>{['공구', '단위', '누적 / 한도', '사용률', '알람', '남은 수명', ''].map((h) => <th key={h} className="pr-2 font-semibold">{h}</th>)}</tr></thead>
          <tbody>{tools.map((t) => {
            const ty = types.find((x) => x.item_no === t.item_no), it = items.find((x) => x.item_no === t.item_no);
            const unit = ty?.usage_unit === 'HOLES' ? '구멍 수' : '이송 시간 분', tag = ty?.limit_basis?.startsWith('[참고]') ? '[참고]' : '[가상]';
            const a = al.find((x) => (x.code === '362' || x.code === '174'));
            return (
              <tr key={t.tool_id} className="border-t border-slate-100">
                <td className="pr-2 font-semibold">{t.tool_no} {it?.item_name}</td><td className="pr-2">{unit}</td><td className="pr-2">{Math.round(t.cum)} / {t.limit} {tag}</td>
                <td className="pr-2"><div className="flex items-center gap-2"><div className="h-3 w-[120px] overflow-hidden rounded bg-slate-200"><div className="h-full" style={{ width: `${Math.min(100, t.usage_pct)}%`, background: t.warn ? '#f0a500' : '#8a97a4' }} /></div><span className={t.warn ? 'font-bold text-[#9a6200]' : ''}>{t.usage_pct}%{t.warn ? ' ▲ 교체 준비' : ''}</span></div></td>
                <td className="pr-2">{a && t.tool_no === 'T05' ? `${a.code === '362' ? '⚠' : '▲'} ${a.code}` : '—'}</td>
                <td className="pr-2">{Math.max(0, Math.round((100 - t.usage_pct) * 10) / 10)}% (부품 {t.left_parts ?? '—'}개)</td>
                <td>{canChange && <button onClick={() => setConfirm(t.tool_id)} className="h-10 rounded border border-slate-300 px-2 text-[13px] font-semibold">공구 교체 기록</button>}</td>
              </tr>);
          })}</tbody>
        </table>
        <p className="mt-1 text-[12px] text-slate-500">"공구 수명 N%" = 사용률. 남은 수명은 계산식 값 (예측 모델 아님, 2026-10-14). OPR은 현장 태블릿으로 교체 기록.</p>
        <section className="mt-3 border-t border-slate-200 pt-3 text-[13px]">
          <h3 className="mb-1 text-[14px] font-bold text-slate-500">교체 이력 (오늘 + 9월)</h3>
          <ul>{changes.map((c, i) => <li key={i}>{md(c.changed_at)} {hm(c.changed_at)} · {c.tool_id} · 교체 전 {Math.round(Number(c.cum_before))} · {c.change_reason} · {userName(c.changed_by)}</li>)}</ul>
        </section>
        {!canChange && <p className="mt-2 text-[14px] text-slate-500">보기 전용 (교체 기록은 작업자·보전 담당자)</p>}
      </div>
      {confirm && <ConfirmBox title={`${confirm} 공구 교체를 기록할까요?`} okLabel="교체 기록" body="사용률이 0%가 되고 공구 재고가 차감됩니다 (페이스밀 인서트는 5개). 설비는 3~8분 준비(SETUP)입니다."
        onOk={async () => { const t = confirm; setConfirm(null); try { await api(`tools/${t}/change`, { role, user_id: user.id }); toast(`${t} 교체 기록 — 사용률 0%`); f.reload(); reloadInv(); } catch (e) { toast((e as Error).message); } }} onCancel={() => setConfirm(null)} />}
    </div>
  );
}
