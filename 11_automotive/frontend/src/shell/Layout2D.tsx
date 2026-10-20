'use client';
// SCR-05 2D 배치도 — 3D와 같은 상태·재공·병목·주의 ▲를 위에서 본 모양으로 (실제 크기 배치: equipment.csv · layout_object.csv, mm).
import type { MachineId } from '@/components/types';
import { useApp } from './ctx';
import { CAUSE_KO, ID_OF, LAYOUT, STATE_VIEW, stateOf, WIP_NAME } from './data';
import { EQS } from './live';

const FILL: Record<string, string> = { RUN: '#dcf5e6', WARN: '#dcf5e6', IDLE: '#e9edf1', SETUP: '#e0ecff', ALARM: '#ffe1e1', MAINT: 'url(#hatch)', BLOCKED: '#ffedd5', NODATA: '#ffffff' };
const EDGE: Record<string, string> = { RUN: '#13994f', WARN: '#f0a500', IDLE: '#8a97a4', SETUP: '#3b82f6', ALARM: '#e5484d', MAINT: '#4b5a69', BLOCKED: '#e8954a', NODATA: '#8a97a4' };

export default function Layout2D() {
  const { twin, selected, selectMachine, go } = useApp();
  const W = LAYOUT.plant.width_x_mm, D = LAYOUT.plant.depth_y_mm, Y = (v: number) => D - v; // 북쪽이 위
  const O = LAYOUT.objects;
  const box = (x: number[], y: number[]) => ({ x: x[0], y: Y(y[1]), width: x[1] - x[0], height: y[1] - y[0] });
  const bn = twin?.bottleneck.process_code;
  const e1 = LAYOUT.equipment['VF2-01'], e2 = LAYOUT.equipment['VF2-02'];
  const op30 = [Math.min(e1.center[0] - e1.size[0] / 2, O['WIP-2'].x[0]) - 300, Math.max(e2.center[0] + e2.size[0] / 2, O['WIP-3'].x[1]) + 300, O['WIP-2'].y[0] - 300, Math.max(e1.center[1] + e1.size[1] / 2, e2.center[1] + e2.size[1] / 2) + 300];

  return (
    <div className="absolute inset-x-0 top-0 bottom-[var(--panelH)] bg-[#f4f6f8]">
      <button onClick={() => go('line')} className="absolute left-3 top-3 z-10 h-11 rounded-md border border-slate-300 bg-white px-4 text-[14px] font-semibold hover:bg-slate-50">3D로</button>
      <div className="absolute right-3 top-3 z-10 rounded-md bg-white/90 px-3 py-1 text-[12px] text-slate-600">공장 {W / 1000} × {D / 1000} m · 천장 {LAYOUT.plant.ceiling_z_mm / 1000} m · 실제 크기 (equipment.csv · layout_object.csv)</div>
      <svg viewBox={`-700 -900 ${W + 1400} ${D + 1800}`} className="h-full w-full" role="img" aria-label="2D 배치도">
        <defs>
          <pattern id="hatch" width="220" height="220" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="220" height="220" fill="#d5dbe0" /><line x1="0" y1="0" x2="0" y2="220" stroke="#4b5a69" strokeWidth="90" /></pattern>
        </defs>
        <rect x={0} y={0} width={W} height={D} fill="#fff" stroke="#56616c" strokeWidth="40" />
        {[[0, LAYOUT.plant.aisle_width_mm, '주 통로', '#d7ece6'], [2000, 2800, '재공 띠', '#fbe3cb'], [2800, 3800, '설비 앞 작업 띠', '#dbe8f5']].map(([a, b, label, c]) => (
          <g key={String(label)}><rect x={0} y={Y(Number(b))} width={W} height={Number(b) - Number(a)} fill={String(c)} opacity="0.7" /><text x={200} y={Y(Number(a)) - 110} fontSize="240" fill="#56616c">{label}</text></g>
        ))}
        <line x1={0} x2={W} y1={Y(3800)} y2={Y(3800)} stroke="#56616c" strokeDasharray="200 140" strokeWidth="20" />
        {/* 배치 물체 */}
        <rect {...box(O['RACK-01'].x, O['RACK-01'].y)} fill="#e2e8ee" stroke="#8a97a4" strokeWidth="30" />
        <text x={(O['RACK-01'].x[0] + O['RACK-01'].x[1]) / 2} y={Y(O['RACK-01'].y[1]) - 120} fontSize="280" textAnchor="middle" fill="#26303a">RACK-01 봉재 랙</text>
        <rect {...box(O['INF-01'].x, O['INF-01'].y)} fill="#eef1f4" stroke="#8a97a4" strokeWidth="30" strokeDasharray="120 80" />
        <text x={(O['INF-01'].x[0] + O['INF-01'].x[1]) / 2} y={Y((O['INF-01'].y[0] + O['INF-01'].y[1]) / 2) + 100} fontSize="300" textAnchor="middle" fill="#56616c">INF-01 투입 대</text>
        <rect {...box(O['SOAK-01'].x, O['SOAK-01'].y)} fill="#ece9f8" stroke="#8a84b8" strokeWidth="30" />
        <text x={(O['SOAK-01'].x[0] + O['SOAK-01'].x[1]) / 2} y={Y(O['SOAK-01'].y[0]) + 300} fontSize="230" textAnchor="middle" fill="#3d3770">SOAK-01 선반 {twin ? `${twin.soak_qty}개` : '—'}</text>
        <rect {...box(O['FG-01'].x, O['FG-01'].y)} fill="#e2f6ea" stroke="#4fb07a" strokeWidth="30" strokeDasharray="90 60" />
        <text x={(O['FG-01'].x[0] + O['FG-01'].x[1]) / 2} y={Y((O['FG-01'].y[0] + O['FG-01'].y[1]) / 2) + 90} fontSize="230" textAnchor="middle" fill="#155a33">FG-01 완성품{twin ? ` · 오늘 ${twin.done_today}` : ''}</text>
        <text x={150} y={Y(1000)} fontSize="240" fill="#26303a">◁ EXIT-1 비상구</text>
        <text x={W - 150} y={Y(1300)} fontSize="240" textAnchor="end" fill="#26303a">DOOR-1 반입문 ▷</text>

        {/* OP-30 구역 테두리 — 병목이면 연보라 + "병목" (3D와 같은 색, 2026-10-20) */}
        <rect x={op30[0]} y={Y(op30[3])} width={op30[1] - op30[0]} height={op30[3] - op30[2]} fill="none" stroke={bn === 'OP-30' ? '#a996ef' : '#3c4752'} strokeWidth="50" strokeDasharray="220 130" />
        <text x={(op30[0] + op30[1]) / 2} y={Y(op30[2]) - 80} fontSize="300" fontWeight="700" textAnchor="middle" fill={bn === 'OP-30' ? '#6a43e0' : '#3c4752'}>OP-30 (2대 병렬){bn === 'OP-30' ? ` · 병목 (${CAUSE_KO[twin!.bottleneck.cause_code] ?? ''})` : ''}</text>

        {EQS.map((eq) => {
          const e = LAYOUT.equipment[eq], id: MachineId = ID_OF[eq], x0 = e.center[0] - e.size[0] / 2, x1 = e.center[0] + e.size[0] / 2, y0 = e.center[1] - e.size[1] / 2, y1 = e.center[1] + e.size[1] / 2;
          const s = stateOf(twin?.equipment[eq]), v = STATE_VIEW[s], sel = selected === id, isBn = !!bn && bn !== 'OP-30' && e.process === bn;
          return (
            <g key={eq} onClick={() => selectMachine(id)} className="cursor-pointer" role="button" aria-label={`${eq} ${v.text}`}>
              <rect x={x0} y={Y(y1)} width={x1 - x0} height={y1 - y0} fill={FILL[s]} stroke={sel ? '#7a52f0' : isBn ? '#a996ef' : EDGE[s]} strokeWidth={sel || isBn ? 90 : 50} strokeDasharray={s === 'NODATA' ? '120 80' : undefined} />
              <text x={e.center[0]} y={Y(e.center[1]) - 120} fontSize="360" fontWeight="700" textAnchor="middle" fill="#26303a">{eq}</text>
              <text x={e.center[0]} y={Y(e.center[1]) + 320} fontSize="330" fontWeight="700" textAnchor="middle" fill={v.color}>{v.icon} {v.text}</text>
              <text x={e.center[0]} y={Y(y1) - 120} fontSize="240" textAnchor="middle" fill="#56616c">{e.process} · {(e.size[0] / 1000).toFixed(1)}×{(e.size[1] / 1000).toFixed(1)} m{isBn ? ' · 병목' : ''}</text>
              {twin?.equipment[eq].alarm && !twin.equipment[eq].alarm!.cleared_at && twin.equipment[eq].alarm!.severity === 'WARN' && <text x={x1 - 250} y={Y(y1) + 420} fontSize="420" fill="#f0a500">▲</text>}
            </g>
          );
        })}
        {['WIP-1', 'WIP-2', 'WIP-3', 'WIP-4'].map((k) => {
          const o = O[k], code = o.buffer!, n = twin?.wip[code] ?? 0, L = twin?.wip_limits[code], orange = !!(L?.warn && L.warn_over != null && n > L.warn_over);
          return (
            <g key={k}>
              <rect {...box(o.x, o.y)} rx="60" fill="#fff" stroke={orange ? '#e8954a' : '#8a97a4'} strokeWidth="30" />
              <text x={o.x[0] + 100} y={Y((o.y[0] + o.y[1]) / 2) + 100} fontSize="250" fill="#56616c">{WIP_NAME[code]}</text>
              <text x={o.x[1] - 80} y={Y((o.y[0] + o.y[1]) / 2) + 140} fontSize="400" fontWeight="800" textAnchor="end" fill={orange ? '#b45309' : '#26303a'}>{twin ? n : '—'}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
