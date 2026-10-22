// @ts-nocheck
'use client';
/**
 * 3D Factory Process Visualization — LINE A Digital Twin (v19 기준)
 * 3D 장면(three.js) + 관제 UI를 하나의 React 클래스 컴포넌트로 옮긴 파일입니다.
 * - 데이터/상태: 클래스 상단의 MACH(설비), STAT(상태), TOUR(투어 단계), initSim() 참고
 * - 3D 장면: init() 안에서 생성, loop()에서 매 프레임 갱신
 * - 화면 UI: 맨 아래 render() — Tailwind 클래스 + 실시간 값만 inline style
 * 대형 이식 파일이라 타입 검사는 꺼 두었습니다(@ts-nocheck). 데이터 타입은 src/types.ts 참고.
 */
import React from 'react';
import * as THREE_NS from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import type { DashboardProps } from './types';
import { createRobot } from './robot3d';

export const DEFAULT_PROPS: DashboardProps = {
  "quality": "자동",
  "introOnLoad": true,
  "scenario": "복합 (주의+고장)",
  "showCards": true,
  "showFlow": true,
  "flowSpeed": 1,
  "autoRotate": false
};

export default class FactoryDashboard extends React.Component<any, any> {
  static defaultProps = DEFAULT_PROPS;
  STAT = {
    RUN: { label: 'RUNNING', fg: '#13994f', dot: '#1fbf63', bg: '#dcf5e6' },
    IDLE: { label: 'IDLE', fg: '#4b5a69', dot: '#8a97a4', bg: '#e9edf1' },
    WARN: { label: 'WARNING', fg: '#9a6200', dot: '#f0a500', bg: '#fff1cc' },
    ALARM: { label: 'ALARM', fg: '#c62a2f', dot: '#e5484d', bg: '#ffe1e1' },
    SETUP: { label: 'SETUP', fg: '#1f5fc4', dot: '#3b82f6', bg: '#e0ecff' },
    MAINT: { label: 'MAINT', fg: '#4b5a69', dot: '#8a97a4', bg: '#e9edf1' },
    BLOCKED: { label: 'BLOCKED', fg: '#b45309', dot: '#e8954a', bg: '#ffedd5' },
    NODATA: { label: 'NO DATA', fg: '#4b5a69', dot: '#b8c0c8', bg: '#eef1f4' },
  };
  // UI설계서 2.3: 색 + 아이콘 + 글자 (3D 위 설비 이름표에 붙임). 데이터 없음 = 테두리만 + "기록 없음" (SCR-04 상태 표)
  STV = { RUN: ['●', '가공', '#13994f'], IDLE: ['○', '대기', '#4b5a69'], SETUP: ['🔧', '준비', '#1f5fc4'], WARN: ['▲', '가공 · 주의', '#9a6200'], ALARM: ['⚠', '고장', '#c62a2f'], MAINT: ['▨', '정비', '#4b5a69'], BLOCKED: ['⛔', '막힘', '#b45309'], NODATA: ['□', '기록 없음', '#4b5a69'] };
  // 데이터적용본: 알람 번호는 가상 알람 코드집(DOC-02) 그대로. 실제 화면 글자는 props.alarmText(시뮬레이터 알람)로 덮는다
  ISSUE = {
    inf: { w: ['—', '투입 대 (알람 없음)', '', ''], a: ['—', '투입 대 (알람 없음)', '', ''] },
    saw: { w: ['5303.00', '가이드 레일 윤활유 레벨 낮음', '', ''], a: ['6302.00', '톱날 모터 전류가 경보 한계를 초과함', '', ''] },
    mil: { w: ['10720', '소프트웨어 리미트 스위치', '', ''], a: ['25050', '축 추종오차 과대', '', ''] },
    vf1: { w: ['2075', '축 윤활유 저장소 비워짐', '', ''], a: ['992', '전류가 높은 증폭기', '', ''] },
    vf2: { w: ['2075', '축 윤활유 저장소 비워짐', '', ''], a: ['992', '전류가 높은 증폭기', '', ''] },
    wsh: { w: ['WSH-02', '세정력 저하', '', ''], a: ['WSH-01', '과열 정지', '', ''] },
    cmm: { w: ['TempComp-202', '온도 기울기 한계 초과', '', ''], a: ['MP-170', '접촉 프로브가 다시 준비되지 않음', '', ''] },
  };
  IMPACT = { inf: 'SAW-01 소재 공급 중단', saw: 'OP-10→20 재공 공급 중단 → 뒤 공정 대기', mil: 'OP-20→30 재공 공급 중단', vf1: 'OP-30 처리 능력 절반 → OP-20→30 재공 증가', vf2: 'OP-30 처리 능력 절반 → OP-20→30 재공 증가', wsh: 'OP-30→40 재공 증가 · OP-50 대기', cmm: 'OP-40→50 재공 증가' };
  nowStr() { return [new Date().getHours(), new Date().getMinutes(), new Date().getSeconds()].map(n => String(n).padStart(2, '0')).join(':'); }
  demo(kind) {
    const id = this.state.demoT;
    if (kind === 'warn') this.setState(s => ({ warn: { ...s.warn, [id]: true }, st: { ...s.st, [id]: s.st[id] === 'ALARM' ? 'ALARM' : 'RUN' }, at: { ...s.at, ['w' + id]: this.nowStr() } }));
    else if (kind === 'alarm') this.setState(s => { const w = { ...s.warn }; delete w[id]; return { warn: w, st: { ...s.st, [id]: 'ALARM' }, at: { ...s.at, ['a' + id]: this.nowStr() }, vf2Tool: id === 'vf2' ? 8 : s.vf2Tool }; });
    else if (kind === 'fix') { const s0 = this.state.st[id]; if (s0 === 'ALARM') this.restart(id); else if (s0 === 'MAINT' || s0 === 'BLOCKED') this.setState(s => ({ st: { ...s.st, [id]: 'RUN' } })); this.clearWarn(id); }
    else if (kind === 'maint') this.setState(s => ({ st: { ...s.st, [id]: 'MAINT' } }));
    else if (kind === 'block') this.setState(s => ({ st: { ...s.st, [id]: 'BLOCKED' } }));
    else if (kind === 'reset') { clearTimeout(this.rsT); this.mt = this.mt || {}; this.setState({ st: { inf: 'RUN', saw: 'RUN', mil: 'RUN', vf1: 'RUN', vf2: 'RUN', wsh: 'RUN', cmm: 'RUN' }, warn: {}, vf2Tool: 76, wip: { w1: 6, w2: 6, w3: 4, w4: 4, fg: 9 } }); return; }
    if (kind !== 'fix' && this.state.demoFocus) this.select(id);
  }
  scen() { return (this.props && this.props.scenario) || '복합 (주의+고장)'; }
  initSim() {
    const alarm = this.scen() !== '정상 가동' && this.scen() !== 'MIL-01 주의';
    const warnOn = this.scen() === '복합 (주의+고장)' || this.scen() === 'MIL-01 주의';
    const st = { inf: 'RUN', saw: 'RUN', mil: 'RUN', vf1: 'RUN', vf2: alarm ? 'ALARM' : 'RUN', wsh: 'RUN', cmm: 'RUN' };
    const wip = alarm ? { w1: 6, w2: 15, w3: 1.2, w4: 4, fg: 9 } : { w1: 6, w2: 6, w3: 4, w4: 4, fg: 9 };
    const d = new Date(Date.now() - 4 * 60000 - 12000);
    const d2 = new Date(Date.now() - 90000);
    const tA = [d.getHours(), d.getMinutes(), d.getSeconds()].map(n => String(n).padStart(2, '0')).join(':'), tW = [d2.getHours(), d2.getMinutes(), d2.getSeconds()].map(n => String(n).padStart(2, '0')).join(':');
    return { st, wip, at: { avf2: tA, wmil: tW }, warn: warnOn ? { mil: true } : {}, warnAt: [d2.getHours(), d2.getMinutes(), d2.getSeconds()].map(n => String(n).padStart(2, '0')).join(':'), vf2Tool: alarm ? 8 : 76, alarmAt: [d.getHours(), d.getMinutes(), d.getSeconds()].map(n => String(n).padStart(2, '0')).join(':') };
  }
  state = { view: 'front', clock: '', uph: 52, sel: null, ph: 0, legend: false, pop: null,
    introOn: !(this.props && this.props.introOnLoad === false), detail: 'summary', navOpen: false, explode: false, qNote: '', layers: { bloom: true, agv: false, holo: false, heat: false, flow: false }, narrow: false, hist: { uph: [52, 51, 53, 52, 50, 52], wip: [30, 31, 31, 32, 32, 33] }, introRun: false, night: false, tourOn: false, tourIdx: 0, tourU: 0, tourPaused: false, demoT: 'vf1', demoFocus: true, ...this.initSim(),
    m: { saw: [85, 92], vf1: [88, 92], vf2: [82, 76], wsh: [64, 81] } };
  mt = {};
  tour = { on: false, t: 0 };
  // 데이터적용본: 투어 문장 = BRK-A100 엔진 마운트 브래킷 (DOC-01 §2·§4, DOC-06 §9.1)
  TOUR = [
    { k: 'INF-01 · 투입 대', t: '평각봉 투입', d: 'RACK-01의 6061-T6 압출 평각봉(19.05 × 57.15 mm, 3,658 mm)을 투입 베드가 절단 위치까지 보냅니다.', dur: 3.5, mv: 'line', form: 0, cam: [0.7, 1.1, 2.6] },
    { k: 'SAW-01 · OP-10', t: '콜드쏘 절단', d: 'Haas HCS-80이 바이스로 고정한 뒤 152.0 ± 0.3 mm 토막으로 자릅니다 (1.0분/개). 이때 로트 번호를 붙입니다.', dur: 4, mv: 'line', form: 0, form2: 1, at: 0.55, fx: 'spark', cam: [0.6, 0.9, 2.1] },
    { k: '이송 · WIP-1', t: 'OP-10→20 재공 → MIL-01', d: '절단 소재가 OP-10→20 재공 자리(한도 30개)를 거쳐 MIL-01로 갑니다. 같은 로트끼리 꺼냅니다.', dur: 3, mv: 'arc', form: 1, cam: [0.9, 1.5, 3.2] },
    { k: 'MIL-01 · OP-20', t: '외곽 황삭', d: '정삭 여유를 옆면마다 0.5 ± 0.1 mm 남기고 외곽을 깎습니다 (황삭 뒤 길이 151.0 ± 0.2 mm, 3.5분/개).', dur: 4, mv: 'hold', form: 1, form2: 2, at: 0.6, fx: 'chips', cam: [0.6, 0.8, 1.9] },
    { k: '이송 · WIP-2', t: 'OP-20→30 재공 → VF2-01·02', d: '병목 앞 재공(한도 30개)입니다. OP-30 두 대 중 비어 있는 설비로 갑니다.', dur: 3.5, mv: 'arc', form: 2, cam: [0.9, 1.5, 3.4] },
    { k: 'VF2-01 · OP-30', t: '정삭 · 보링 · M6 나사', d: 'Haas VF-2가 외곽 정삭(엔드밀 Ø10) → Ø45 H7 부싱 압입 구멍 보링 → 드릴 Ø5.0 → M6 탭을 합니다 (7.0분/개, 라인 병목).', dur: 4.5, mv: 'hold', form: 2, form2: 3, at: 0.65, fx: 'chips', cam: [0.6, 0.8, 1.9] },
    { k: '이송 · WIP-3', t: 'OP-30→40 재공 → WSH-01', d: 'OP-30→40 재공(한도 60개)에 모입니다. 한 로트가 30개 모이면 한 묶음으로 세척으로 갑니다.', dur: 3, mv: 'arc', form: 3, cam: [0.9, 1.5, 3.4] },
    { k: 'WSH-01 · OP-40', t: '버 제거 · 초음파 세척', d: '한 묶음 = 한 로트, 최대 30개. 진동 바렐로 버 제거 → 50 ℃ 중성 세척액 초음파 세척 → 헹굼·건조 (묶음당 25분).', dur: 4, mv: 'line', form: 3, form2: 4, at: 0.8, fx: 'water', cam: [0.5, 1.1, 2.5] },
    { k: '이송 · WIP-4', t: 'OP-40→50 재공 · 온도 맞춤', d: '측정할 부품은 온도 맞춤 선반(SOAK-01)에 90분 이상 두어 16~26 ℃로 맞춘 뒤 측정기로 갑니다.', dur: 3, mv: 'arc', form: 4, cam: [0.9, 1.5, 3.2] },
    { k: 'CMM-01 · OP-50', t: '3차원 측정 · 로트 판정', d: '첫 부품 + 5개마다 1개를 잽니다: Ø45 H7(+0.025/0), 길이 150 ± 0.5, 폭 55 ± 0.3, 두께 12 ± 0.2, 평면도 0.05. 나머지는 육안 + M6 게이지.', dur: 4.5, mv: 'hold', form: 4, form2: 5, at: 0.7, cam: [0.6, 0.8, 1.9] },
    { k: 'FG-01 · 완성', t: '합격 로트 → 완제품 재고', d: '합격 로트만 완제품 재고로 들어가고 먼저 합격한 로트부터 출하합니다 (DOC-01 §5.5).', dur: 3.5, mv: 'arc', form: 5, cam: [1.0, 1.4, 3.0] },
  ];
  presetPos(v) {
    const T = this.T, pr = this.PRESETS[v];
    const tgt = new T.Vector3(...pr.t), pos = new T.Vector3(...pr.p);
    pos.sub(tgt).multiplyScalar(Math.max(1.12, 2.15 / this.camera.aspect)).add(tgt);
    return { pos, tgt };
  }
  startIntro() {
    const T = this.T; if (!T || !this.camera) return;
    if (this.tour.on) this.stopTour(true);
    const { pos, tgt } = this.presetPos('front');
    this.introCam = { curve: new T.CatmullRomCurve3([new T.Vector3(-16, 24, 30), new T.Vector3(-3, 13, 17), new T.Vector3(7, 9, 13), pos.clone()]), t0: new T.Vector3(12.5, 0, -4), t1: tgt };
    this.intro = { t: 0 }; this.goal = null; if (this.controls) this.controls.enabled = false;
    this.setState({ introOn: true, introRun: true, sel: null, view: 'front', pop: null });
  }
  startTour() {
    if (!this.T) return;
    if (this.buildTourPaths) try { this.buildTourPaths(); } catch (e) { console.error('[factory] tour paths', e); }
    if (this.intro) this.intro.t = 99;
    this.tour = { on: true, t: 0, paused: false, lastUi: -1 }; this.goal = null;
    if (this.controls) { this.controls.enabled = false; this.controls.autoRotate = false; }
    this.setState({ tourOn: true, tourIdx: 0, tourU: 0, tourPaused: false, sel: null, pop: null });
  }
  stopTour(silent) {
    this.tour = { on: false, t: 0 }; if (this.controls) this.controls.enabled = true;
    this.setState({ tourOn: false }); if (!silent) this.setView('front');
  }
  tourJump(d) {
    if (!this.tour.on) return;
    const i = Math.max(0, Math.min(this.TOUR.length - 1, (this.state.tourIdx || 0) + d));
    let acc = 0; for (let k = 0; k < i; k++) acc += this.TOUR[k].dur; this.tour.t = acc + 0.001;
  }
  tourPause() { this.tour.paused = !this.tour.paused; this.setState({ tourPaused: this.tour.paused }); }
  componentDidUpdate(pp, ps) { if (ps !== this.state && this.props.onSnapshot) { const t = this.state; this.props.onSnapshot({ st: t.st, warn: t.warn, wip: t.wip, m: t.m, uph: t.uph, hist: t.hist, clock: t.clock, sel: t.sel, view: t.view, vf2Tool: t.vf2Tool, alarmAt: t.alarmAt }); } if (pp.scenario !== this.props.scenario) { clearTimeout(this.rsT); const s0 = this.initSim(); this.setState(s0); if (this.buf && s0.wip) Object.keys(this.buf).forEach(k => { this.buf[k] = Math.round(s0.wip[k] || 0); }); } }
  clearWarn(id) { this.setState(s => { const w = { ...s.warn }; delete w[id]; return { warn: w }; }); }
  restart(id) {
    this.setState(s => ({ st: { ...s.st, [id]: 'SETUP' }, vf2Tool: id === 'vf2' ? 100 : s.vf2Tool }));
    clearTimeout(this.rsT);
    this.rsT = setTimeout(() => { if (!this.dead) this.setState(s => ({ st: { ...s.st, [id]: 'RUN' } })); }, 6000);
  }
  wrapRef = React.createRef(); stageRef = React.createRef(); ovRef = React.createRef();
  simT = 0;
  ORDER = ['inf', 'saw', 'mil', 'vf1', 'vf2', 'wsh', 'cmm'];
  MACH = {
    // 데이터적용본: 글자는 DOC-01 §2.2·§4, DOC-06 §9.1 (b = 원본 3D 모양 좌표 — 화면에 그릴 때 데이터 좌표로 옮긴다, LAYOUT_WARP)
    inf: { name: 'INF-01', kr: 'SAW-01 투입 베드 (투입 대)', op: '투입 대', T: 60, off: 0,
      desc: 'RACK-01의 6061-T6 압출 평각봉을 SAW-01 절단 위치까지 보내는 투입 베드입니다. 상태를 따로 갖지 않는 배치 물체입니다.',
      steps: [[0, '평각봉 이송', '절단 길이만큼 전진'], [0.2, '정지', '절단 위치 도달'], [0.9, '다음 토막 대기', 'SAW-01 절단 끝 대기']],
      params: [['소재', '6061-T6 평각봉'], ['단면', '19.05 × 57.15 mm'], ['봉 길이', '3,658 mm (12 ft)'], ['봉 1개', '약 23개분']], io: ['RACK-01', 'SAW-01'], b: [800, 4200, 3900, 4900, 0, 1.0] },
    saw: { name: 'SAW-01', kr: 'Haas HCS-80 콜드쏘', op: 'OP-10', T: 60, off: 0,
      desc: '6061-T6 평각봉을 152.0 ± 0.3 mm로 절단합니다. 이 공정에 투입할 때 로트 번호를 붙입니다 (DOC-01 §4.1).',
      steps: [[0, '봉재 이송', '투입 베드에서 절단 길이만큼 전진'], [0.2, '바이스 고정', '공작물을 바이스에 완전히 고정'], [0.3, '자동 절단', '[CYCLE START] — 톱날 회전 + 하강'], [0.75, '복귀 · 풀기', '톱날 상승, 바이스 개방'], [0.9, '배출', 'OP-10→20 재공 대차에 놓음 (한도 30개)']],
      params: [['기준 사이클', '1.0분/개'], ['절단 길이', '152.0 ± 0.3 mm'], ['소재', '6061-T6'], ['알람', '6302.00 · 5303.00']], io: ['INF-01', 'OP-10→20 재공'], b: [4500, 6300, 3800, 5200, 0, 1.9] },
    mil: { name: 'MIL-01', kr: '3축 머시닝센터 (Siemens 840D sl)', op: 'OP-20', T: 210, off: 0.3,
      desc: '절단 소재의 외곽을 황삭합니다. 정삭 여유를 옆면마다 0.5 ± 0.1 mm 남깁니다 (DOC-01 §4.2).',
      steps: [[0, '소재 꺼내기 · 고정', 'OP-10→20 대차에서 같은 로트, 바이스 고정'], [0.12, '프로그램 확인', 'BRK-A100 황삭 프로그램'], [0.22, '외곽 황삭', '자동 운전 — 옆면 여유 0.5 mm'], [0.8, '공구 후퇴', '절삭 끝'], [0.9, '칩 털기 · 배출', 'OP-20→30 대차 (한도 30개)']],
      params: [['기준 사이클', '3.5분/개'], ['황삭 뒤 길이', '151.0 ± 0.2 mm'], ['정삭 여유', '0.5 ± 0.1 mm'], ['알람', '25050 · 10720']], io: ['OP-10→20 재공', 'OP-20→30 재공'], b: [7200, 8800, 3800, 5400, 0, 2.6] },
    vf1: { name: 'VF2-01', kr: 'Haas VF-2 수직 머시닝센터 #1', op: 'OP-30', T: 420, off: 0,
      desc: '외곽 정삭(엔드밀 Ø10), 포켓, 부싱 압입 구멍(Ø45 H7) 보링, M6 나사를 가공합니다. 라인의 병목 공정입니다 (DOC-01 §4.3).',
      steps: [[0, '부품 고정', 'OP-20→30 대차에서 같은 로트, 도어 닫고 [CYCLE START]'], [0.1, '공구 교환', 'T01 페이스밀 → T02 엔드밀 Ø10'], [0.2, '외곽 정삭 · 포켓', '엔드밀 Ø10'], [0.55, '보링 · 드릴 · 탭', 'T03 Ø45 H7 보링 → T04 드릴 Ø5.0 → T05 M6 탭'], [0.85, '칩 털기 · 배출', 'OP-30→40 대차 (한도 60개)']],
      params: [['기준 사이클', '7.0분/개'], ['부싱 구멍', 'Ø45 H7 (+0.025/0)'], ['나사', 'M6 6H'], ['공구', 'T01~T05 (사용률 → 공구 수명)']], io: ['OP-20→30 재공', 'OP-30→40 재공'], b: [10060, 12600, 3650, 5600, 0, 3.05] },
    vf2: { name: 'VF2-02', kr: 'Haas VF-2 수직 머시닝센터 #2', op: 'OP-30', T: 420, off: 0.5,
      desc: 'VF2-01과 같은 BRK-A100 OP-30 프로그램으로 가공합니다. OP-30은 2대 병렬이라 1대가 멈추면 라인 속도가 절반이 됩니다.',
      steps: [[0, '부품 고정', 'OP-20→30 대차에서 같은 로트, 도어 닫고 [CYCLE START]'], [0.1, '공구 교환', 'T01 페이스밀 → T02 엔드밀 Ø10'], [0.2, '외곽 정삭 · 포켓', '엔드밀 Ø10'], [0.55, '보링 · 드릴 · 탭', 'T03 Ø45 H7 보링 → T04 드릴 Ø5.0 → T05 M6 탭'], [0.85, '칩 털기 · 배출', 'OP-30→40 대차 (한도 60개)']],
      params: [['기준 사이클', '7.0분/개'], ['부싱 구멍', 'Ø45 H7 (+0.025/0)'], ['나사', 'M6 6H'], ['공구', 'T01~T05 (사용률 → 공구 수명)']], io: ['OP-20→30 재공', 'OP-30→40 재공'], b: [13460, 16000, 3650, 5600, 0, 3.05] },
    wsh: { name: 'WSH-01', kr: '진동 바렐 + 초음파 세척기', op: 'OP-40', T: 50, off: 0,
      desc: '한 묶음 = 한 로트만, 최대 30개, 묶음당 25분. 버 제거(텀블러) → 초음파 세척 → 헹굼·건조 (DOC-01 §4.4).',
      steps: [[0, '묶음 모으기', 'OP-30→40 대차에서 한 로트 30개까지'], [0.15, '버 제거', '진동 바렐(텀블러)'], [0.45, '초음파 세척', '중성 세척액 5%, 50 ℃'], [0.65, '헹굼 · 건조', '깨끗한 물로 헹구고 말림'], [0.88, '배출', 'OP-40→50 대차에 로트별로']],
      params: [['묶음', '1 로트 · 최대 30개'], ['묶음 시간', '25분'], ['세척 온도', '50 ℃ 설정'], ['알람', 'WSH-01 · WSH-02 [가상 번호]']], io: ['OP-30→40 재공', 'OP-40→50 재공'], b: [17150, 20450, 3700, 5200, 0, 2.05] },
    cmm: { name: 'CMM-01', kr: '3차원 측정기 ([참고] Hexagon TIGO SF)', op: 'OP-50', T: 54, off: 0,
      desc: '발췌(첫 부품 + 5개마다 1개)로 재고, 나머지는 육안 + M6 게이지. 측정 결과는 결과 파일로 자동 기록합니다 (DOC-01 §4.5).',
      steps: [[0, '로트 바코드 확인', '측정 지시와 같은지'], [0.15, '온도 확인', 'SOAK-01 90분 이상, 부품 16~26 ℃'], [0.4, 'Ø45 H7 · 길이 · 폭', '측정 프로그램 실행'], [0.65, '두께 · 평면도 · 구멍 간 거리', '결과 파일 자동 기록'], [0.88, '판정', '1개라도 불합격이면 보류 검토 → 반장']],
      params: [['측정', '2.5분/개 (게이지 0.5분)'], ['평소 평균', '약 0.9분/개'], ['강화(전수)', '5.0분/개'], ['측정 기준 온도', '20 ℃']], io: ['OP-40→50 재공', '완제품 (합격 로트)'], b: [21400, 24000, 3700, 5400, 0, 2.7] },
  };
  // 데이터적용본: 공장 28 × 8 m + 동쪽 자동창고 (x 30~39 m)
  PRESETS = {
    front: { p: [13.8, 7.4, 16.7], t: [13.8, 1.7, -4.5] }, // 사용자 요청 2026-10-22: 첫 화면 = INF-01~CMM-01 한 줄이 다 보이게 조금 멀리·낮게 (전엔 [14, 9, 12.5] → [14, 1.6, -3.8])
    iso: { p: [-3.5, 17.5, 13.5], t: [15, 2.2, -3.8] },
    top: { p: [16, 37, -1.6], t: [16, 0, -2.1] },
    wh: { p: [25.5, 6.6, 4.5], t: [32.4, 1.8, -6.8] },
    op30: { p: [14.8, 6.2, 7.2], t: [14.8, 1.4, -3.8] },
  };

  componentDidMount() {
    if (this.props.onReady) this.props.onReady(this);
    const HANG_Z = 0.3; // 가장 높은 설비 윗면 위로 이름표 줄이 뜨는 높이(m)
    this.anch = {
      'ax-x': [12500, -1500, 0], 'ax-y': [-1400, 8900, 0],
      'z-boundary': [12500, 750, 0], 'z-exit': [1700, 750, 0], 'z-door': [24300, 750, 0],
      'z-wip': [1300, 2400, 0], 'z-work': [1300, 3400, 0], 'z-front': [23500, 3550, 0],
      'z-op30': [13300, 1650, 0],
      'wip-1': [6750, 2400, 0.62], 'wip-2': [11900, 2400, 0.62], 'wip-3': [14300, 2400, 0.62],
      'wip-4': [20800, 2400, 0.62], 'fg-01': [24000, 2400, 0.62], 'soak-01': [24850, 600, 0],
      'tag-inf': [3300, 4400, 1.15], 'tag-rack': [1300, 6350, 1.6], 'tag-mil': [8200, 4500, 2.3],
      'card-saw': [4900, 4400, 2.6], 'card-vf1': [11300, 4600, 3.05], 'card-vf2': [14900, 4600, 3.05],
      'card-wsh': [18800, 4400, 2.0], 'card-cmm': [22700, 4500, 3.6],
    };
    this.ORDER.forEach(id => { const b = this.MACH[id].b; this.anch['fx-' + id] = [(b[0] + b[1]) / 2 - 250, b[2], b[5] * 0.55]; });
    for (let X = 0; X <= 25000; X += 5000) this.anch['xt' + X] = [X, -650, 0];
    for (let Y = 0; Y <= 8000; Y += 2000) this.anch['yt' + Y] = [-950, Y, 0];
    const LY = this.setupLayout();
    if (LY) {
      // 데이터적용본: 3D 위 글자도 실제 좌표에 (layout_object.csv · equipment.csv)
      const top = (id, dx = 0) => { const d = this.MACH[id].bd; return [(d[0] + d[1]) / 2 + dx, (d[2] + d[3]) / 2, d[5] + 0.15]; };
      const TAGS = ['inf', 'saw', 'mil', 'vf1', 'vf2', 'wsh', 'cmm'], tagY = Math.max(...TAGS.map(k => this.MACH[k].bd[3])), tagZ = Math.max(...TAGS.map(k => this.MACH[k].bd[5])) + HANG_Z; // 모든 이름표를 같은 깊이·같은 높이에 한 줄로
      const hang = (id, dx = 0) => { const d = this.MACH[id].bd; return [(d[0] + d[1]) / 2 + dx, tagY, tagZ]; }; // 이름표는 설비 뒤쪽 위 천장에 매달림 — 위에서 봐도 설비를 안 가림
      Object.assign(this.anch, {
        'z-boundary': [(LY.op30[0] + LY.op30[1]) / 2, LY.op30[2] - 300, 0], 'z-exit': [600, 1000, 0], 'z-door': [27300, 1300, 0],
        'z-wip': [600, 2400, 0], 'z-work': [600, 3300, 0], 'z-front': [26500, 3650, 0], 'z-op30': [(LY.op30[0] + LY.op30[1]) / 2, tagY, tagZ + 1.25], // 병목 칩 = 이름표 줄 위
        'wip-1': [LY.wip.w1 * 1000, 2400, 0.62], 'wip-2': [LY.wip.w2 * 1000, 2400, 0.62], 'wip-3': [LY.wip.w3 * 1000, 2400, 0.62],
        'wip-4': [LY.wip.w4 * 1000, 2400, 0.62], 'fg-01': [LY.fg * 1000, 2400, 0.62], 'soak-01': [(LY.soak.x[0] + LY.soak.x[1]) / 2, (LY.soak.y[0] + LY.soak.y[1]) / 2, 1.45],
        'tag-inf': hang('inf', -600), 'tag-saw': hang('saw'), 'tag-vf1': hang('vf1'), 'tag-vf2': hang('vf2'), 'tag-wsh': hang('wsh'), 'tag-cmm': hang('cmm'), 'tag-rack': [(LY.rack.x[0] + LY.rack.x[1]) / 2, (LY.rack.y[0] + LY.rack.y[1]) / 2, 2.1], 'tag-mil': hang('mil'),
        'card-saw': top('saw'), 'card-vf1': top('vf1'), 'card-vf2': top('vf2'), 'card-wsh': top('wsh'), 'card-cmm': top('cmm'),
      });
      this.ORDER.forEach(id => { const d = this.MACH[id].bd; this.anch['fx-' + id] = [(d[0] + d[1]) / 2, d[2], d[5] * 0.55]; });
      this.anch['xt28000'] = [28000, -650, 0];
    }
    this.init().catch(e => { console.error('[factory]', e); if (this.props.onFail) this.props.onFail('3D를 그리지 못했습니다'); });
    this.updateData();
    this.tick = setInterval(() => this.updateData(), 1500);
  }
  componentWillUnmount() {
    this.dead = true; clearInterval(this.tick); clearInterval(this.wd); clearInterval(this.safeTopT); cancelAnimationFrame(this.raf);
    this.ro && this.ro.disconnect(); this.renderer && this.renderer.dispose();
  }
  // ---------- 데이터적용본: 실제 크기 배치 (SCR-04 "실제 크기 배치", masters/equipment.csv · layout_object.csv) ----------
  // 설비 모델은 원본 그대로 두고, 설비마다 묶음(그룹)을 데이터 좌표·크기로 옮기고 늘린다 (place). 재공 자리·상자·컨베이어는 데이터 위치에 짓는다.
  setupLayout() {
    const L = this.props.layout; if (!L) return null;
    const E = L.equipment, O = L.objects;
    const ebox = (eq) => { const e = E[eq], [cx, cy] = e.center, [sx, sy, sz] = e.size; return [cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, 0, sz / 1000]; };
    const inf = O['INF-01'];
    const D = { inf: [inf.x[0], inf.x[1], inf.y[0], inf.y[1], 0, (inf.h || 925) / 1000], saw: ebox('SAW-01'), mil: ebox('MIL-01'), vf1: ebox('VF2-01'), vf2: ebox('VF2-02'), wsh: ebox('WSH-01'), cmm: ebox('CMM-01') };
    const P = {};
    Object.keys(D).forEach(id => {
      const b = this.MACH[id].b, d = D[id];
      const sx = (d[1] - d[0]) / (b[1] - b[0]), sz = (d[3] - d[2]) / (b[3] - b[2]), sy = d[5] / b[5];
      // world.x = ox + sx·x,  world.z = oz + sz·z  (z = −Y/1000, 정면 b[2] → d[2]),  world.y = sy·y
      P[id] = { sx, sy, sz, ox: (d[0] - sx * b[0]) / 1000, oz: (-d[2] + sz * b[2]) / 1000 };
      this.MACH[id].bd = d;
    });
    const c = (o) => (o.x[0] + o.x[1]) / 2000;
    const w = { w1: c(O['WIP-1']), w2: c(O['WIP-2']), w3: c(O['WIP-3']), w4: c(O['WIP-4']) };
    const op30 = [D.vf1[0] - 300, Math.max(D.vf2[1], O['WIP-3'].x[1]) + 300, O['WIP-2'].y[0] - 300, Math.max(D.vf1[3], D.vf2[3]) + 300];
    // 장식 곡선(투어·흐름선)용: 원본 X(mm) → 데이터 X(mm), 설비 가운데·재공 자리를 지나는 꺾은선
    const pts = [[0, 0], [2500, (D.inf[0] + D.inf[1]) / 2], [5400, (D.saw[0] + D.saw[1]) / 2], [6750, w.w1 * 1000], [8000, (D.mil[0] + D.mil[1]) / 2], [11330, (D.vf1[0] + D.vf1[1]) / 2],
      [14300, w.w3 * 1000], [14730, (D.vf2[0] + D.vf2[1]) / 2], [18800, (D.wsh[0] + D.wsh[1]) / 2], [20800, w.w4 * 1000], [22700, (D.cmm[0] + D.cmm[1]) / 2], [24000, c(O['FG-01']) * 1000]];
    const mapX = (X) => { if (X <= 0) return X; for (let i = 1; i < pts.length; i++) if (X <= pts[i][0]) { const [a, A] = pts[i - 1], [b, B] = pts[i]; return A + (B - A) * (X - a) / (b - a); } return X + pts[pts.length - 1][1] - pts[pts.length - 1][0]; };
    this.LY = { P, wip: w, fg: c(O['FG-01']), soak: O['SOAK-01'], rack: O['RACK-01'], op30, mapX, plant: L.plant };
    return this.LY;
  }
  // 원본 좌표의 점(미터)을 그 설비의 데이터 자리로
  placePt(id, v) { const p = this.LY && this.LY.P[id]; if (p) { v.x = p.ox + p.sx * v.x; v.y = p.sy * v.y; v.z = p.oz + p.sz * v.z; } return v; }
  placeX(id, x) { const p = this.LY && this.LY.P[id]; return p ? p.ox + p.sx * x : x; }
  placeZ(id, z) { const p = this.LY && this.LY.P[id]; return p ? p.oz + p.sz * z : z; }
  mapXm(x) { return this.LY ? this.LY.mapX(x * 1000) / 1000 : x; }
  // ---------- 데이터적용본: 시연 데이터 서버(/api/line/twin) → 3D ----------
  EQ_OF = { saw: 'SAW-01', mil: 'MIL-01', vf1: 'VF2-01', vf2: 'VF2-02', wsh: 'WSH-01', cmm: 'CMM-01' };
  applyLive(L) {
    this.liveT = L;
    if (!L) { const st = {}; this.ORDER.forEach(k => { st[k] = 'NODATA'; }); this.frozen = true; this.setState({ st, warn: {}, bn: null }); return; }
    const MAP = { RUN: 'RUN', IDLE: 'IDLE', SETUP: 'SETUP', DOWN: 'ALARM', MAINT: 'MAINT', BLOCKED: 'BLOCKED' };
    const st = {}, warn = {}, m = {}, sp = Math.max(1, L.clock.speed);
    Object.entries(this.EQ_OF).forEach(([k, eq]) => {
      const E = L.equipment[eq]; if (!E) { st[k] = 'NODATA'; return; }
      st[k] = MAP[E.state_code] || 'IDLE';
      if (E.warn_marker || (E.alarm && E.alarm.severity === 'WARN' && !E.alarm.cleared_at)) warn[k] = true;
      const top = (E.tools || []).slice().sort((a, b) => b.usage_pct - a.usage_pct)[0];
      m[k] = [E.sensor ? Math.round(E.sensor.SpindleLoadPct) : null, top ? top.usage_pct : null, top ? top.tool_no : null];
      // 3D 사이클 = 데이터 기준 사이클 ÷ 배속 (실제 초)
      this.MACH[k].T = Math.max(0.4, (E.std_cycle_min || 1) * 60 / sp);
    });
    st.inf = st.saw === 'NODATA' ? 'NODATA' : st.saw === 'RUN' ? 'RUN' : 'IDLE'; // 투입 대는 상태가 없다 — 절단기가 돌 때만 롤러가 돈다
    this.MACH.inf.T = this.MACH.saw.T;
    const W = L.wip || {};
    const wip = { w1: W['WIP-10-20'] || 0, w2: W['WIP-20-30'] || 0, w3: W['WIP-30-40'] || 0, w4: W['WIP-40-50'] || 0, fg: L.done_today || 0, soak: L.soak_qty || 0 };
    this.frozen = !!L.clock.paused;
    this.speed = sp;
    // 기준 병목(OP-30이 원래 가장 느림, cause BASE)은 3D에 안 보임 — 사건 원인(①~④ · 고장)으로 생기거나 옮겨 갔을 때만 (사용자 결정 2026-10-22)
    this.setState({ st, warn, m, wip, uph: Math.round((L.production && L.production.rate_per_hour) || 0), clock: (L.clock.sim_at || '').slice(11, 19), bn: L.bottleneck && L.bottleneck.cause_code !== 'BASE' ? L.bottleneck.process_code : null, wipLimits: L.wip_limits });
  }
  updateData() {
    if (this.props.dataMode) return; // 데이터적용본: 가짜 값 대신 applyLive
    const j = (v, lo, hi) => Math.max(lo, Math.min(hi, v + Math.round((Math.random() - 0.5) * 4)));
    const cl = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
    const now = new Date();
    this.setState(s => {
      const st = { ...s.st }, w = { ...s.wip };
      const nVF = ['vf1', 'vf2'].filter(k => st[k] === 'RUN').length;
      const wshRun = st.wsh === 'RUN';
      if (this.buf) Object.assign(w, this.buf); else {
      w.w1 = cl(w.w1 + (Math.random() - 0.5) * 0.8, 4, 8);
      const feed = st.saw === 'RUN' && st.mil === 'RUN' && st.inf === 'RUN' ? 0.5 : 0;
      w.w2 = cl(w.w2 + feed - 0.3 * nVF + (Math.random() - 0.5) * 0.2, 2, 24);
      w.w3 = cl(w.w3 + 0.3 * nVF - (wshRun ? 0.55 : 0), 0, 24); }
      if (st.wsh === 'RUN' && w.w3 < 0.5) st.wsh = 'IDLE'; else if (st.wsh === 'IDLE' && w.w3 >= 2) st.wsh = 'RUN';
      const cmmRun = st.cmm === 'RUN';
      if (!this.buf) { w.w4 = cl(w.w4 + (wshRun ? 0.55 : 0) - (w.w4 > 0.5 && cmmRun ? 0.5 : 0), 0, 24);
      w.fg = w.fg + (w.w4 > 0.5 && cmmRun ? 0.5 : 0); if (w.fg > 23) w.fg = 4; }
      return {
        clock: [now.getHours(), now.getMinutes(), now.getSeconds()].map(n => String(n).padStart(2, '0')).join(':'),
        st, wip: w,
        uph: j(s.uph, nVF === 2 ? 48 : 28, nVF === 2 ? 56 : 34),
        hist: { uph: [...s.hist.uph, s.uph].slice(-24), wip: [...s.hist.wip, Math.round(w.w1 + w.w2 + w.w3 + w.w4)].slice(-24) },
        m: { saw: [j(s.m.saw[0], 78, 92), s.m.saw[1]], vf1: [j(s.m.vf1[0], 80, 94), s.m.vf1[1]],
          vf2: [j(s.m.vf2[0], 74, 90), s.m.vf2[1]], wsh: [j(s.m.wsh[0], 56, 72), s.m.wsh[1]] },
      };
    });
  }
  canWork(id) {
    if (this.tour && this.tour.on) return true; if (this.intro) return true;
    if (this.props.dataMode) return this.state.st[id] === 'RUN'; // 데이터가 가공 중이라고 하면 가공 동작
    const S = this.msRef && this.msRef[id]; if (!S) return true;
    return S.loaded && S.inPlace !== false && !S.hold;
  }
  starved(id) { if (this.props.dataMode) return false; const S = this.msRef && this.msRef[id]; return !!S && !this.tour.on && !this.intro && (!S.loaded || S.inPlace === false); }
  blocked(id) { if (this.props.dataMode) return false; const S = this.msRef && this.msRef[id]; return !!S && !this.tour.on && !!S.hold; }
  phOf(id) { const m = this.MACH[id]; return (((this.mt[id] || 0) / m.T) + m.off) % 1; }

  setView(v, instant) {
    this.setState({ view: v, sel: null });
    const T = this.T; if (!T) return;
    const pr = this.PRESETS[v];
    const tgt = new T.Vector3(...pr.t), pos = new T.Vector3(...pr.p);
    const f = Math.max(1.12, 2.15 / this.camera.aspect);
    pos.sub(tgt).multiplyScalar(f).add(tgt);
    if (instant) { this.camera.position.copy(pos); this.controls.target.copy(tgt); this.goal = null; }
    else this.goal = { pos, target: tgt };
  }
  // 로그인 뒤 첫 화면 (사용자 요청 2026-10-22): 투입 쪽 위에서 정한 각도(front)로 미끄러져 들어옴. 움직임 줄이기 설정이면 바로 정한 각도
  entry() {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const T = this.T, c = this.camera, tg = this.controls.target, end = { pos: c.position.clone(), target: tg.clone() };
    const off = end.pos.clone().sub(end.target).multiplyScalar(0.8).applyAxisAngle(new T.Vector3(0, 1, 0), -0.7); off.y += 3; // 왼쪽으로 40° 돌고 조금 높게·가깝게 (maxDist 안)
    tg.set(end.target.x - 7, end.target.y - 0.4, end.target.z); c.position.copy(tg).add(off);
    this.goal = { ...end, dur: 2.6 };
  }
  select(id) {
    this.setState({ sel: id, ph: this.phOf(id) });
    if (this.props.onSelect) this.props.onSelect(id);
    const T = this.T; if (!T) return;
    const b = this.MACH[id].bd || this.MACH[id].b, w = (b[1] - b[0]) / 1000;
    const tgt = new T.Vector3((b[0] + b[1]) / 2000, b[5] * 0.4, -(b[2] + b[3]) / 2000 + 0.2);
    const d = (3.6 + w * 2.0) * Math.max(1, 1.5 / this.camera.aspect);
    const pos = tgt.clone().add(new T.Vector3(0.28, 0.48, 1).normalize().multiplyScalar(d));
    const W = this.stageRef.current.clientWidth;
    if (W > 760 && !this.props.embedded) {
      const half = d * Math.tan((this.camera.fov / 2) * Math.PI / 180) * this.camera.aspect;
      const sh = (182 / (W / 2)) * half;
      tgt.x += sh; pos.x += sh;
    }
    this.goal = { pos, target: tgt };
  }

  // 여러 설비를 한 화면에 — 현장 화면 공정 묶음 버튼 (사용자 요청 2026-10-19)
  frameGroup(ids) {
    const T = this.T; if (!T) return;
    this.setState({ sel: null });
    const bs = ids.map(id => this.MACH[id].bd || this.MACH[id].b);
    const x0 = Math.min(...bs.map(b => b[0])), x1 = Math.max(...bs.map(b => b[1])), y0 = Math.min(...bs.map(b => b[2])), y1 = Math.max(...bs.map(b => b[3])), h = Math.max(...bs.map(b => b[5]));
    const tgt = new T.Vector3((x0 + x1) / 2000, h * 0.35, -(y0 + y1) / 2000 + 0.3);
    const d = (2.4 + ((x1 - x0) / 1000) * 1.15) * Math.max(1, 1.6 / this.camera.aspect);
    this.goal = { pos: tgt.clone().add(new T.Vector3(0, 0.32, 1).normalize().multiplyScalar(d)), target: tgt }; // 설비 정면에서 (사용자 요청 2026-10-19)
  }

  nav(kind, amt) {
    const T = this.T, cam = this.camera, c = this.controls; if (!T) return;
    this.goal = null;
    const off = cam.position.clone().sub(c.target);
    if (kind === 'orbit' || kind === 'tilt') {
      const s = new T.Spherical().setFromVector3(off);
      if (kind === 'orbit') s.theta += amt; else s.phi = Math.max(0.05, Math.min(c.maxPolarAngle, s.phi + amt));
      off.setFromSpherical(s); cam.position.copy(c.target).add(off);
    } else if (kind === 'zoom') {
      const len = Math.max(c.minDistance, Math.min(c.maxDistance, off.length() * amt));
      off.setLength(len); cam.position.copy(c.target).add(off);
    } else if (kind === 'pan') {
      const fwd = new T.Vector3(off.x, 0, off.z).normalize().negate();
      const right = new T.Vector3().crossVectors(fwd, new T.Vector3(0, 1, 0));
      const k = off.length() * 0.06;
      const mv = right.multiplyScalar(amt[0] * k).add(fwd.multiplyScalar(amt[1] * k));
      cam.position.add(mv); c.target.add(mv);
    } else if (kind === 'reset') { this.setView(this.state.view || 'front'); return; }
    c.update();
    this.renderNow && this.renderNow();
  }
  holdNav(kind, amt) {
    return {
      onPointerDown: (e) => {
        e.preventDefault(); this.nav(kind, amt);
        clearInterval(this.holdT); this.holdT = setInterval(() => this.nav(kind, amt), 60);
        const up = () => { clearInterval(this.holdT); window.removeEventListener('pointerup', up); };
        window.addEventListener('pointerup', up);
      },
    };
  }

  async init() {
    const THREE: any = THREE_NS, OC: any = { OrbitControls }, RE: any = { RoomEnvironment };
    const RBG: any = RoundedBoxGeometry;
    const PP: any = [{ EffectComposer }, { RenderPass }, { UnrealBloomPass }, { OutputPass }];
    // 표지판·재공 글자는 캔버스에 그려서, Pretendard(한글은 조각 파일)을 먼저 읽고 그린다 (디자인 통일 C안, 2026-10-20). 늦어도 3초면 그냥 그림
    try { await Promise.race([Promise.all(['400', '600', '700', '800'].map((w) => document.fonts.load(`${w} 40px "Pretendard Variable"`, '가공대기준비정비고장막힘주의병목투입봉재랙세척측정 0123456789/·-ABCDEFGHIJKLMNOPQRSTUVWXYZ'))), new Promise((r) => setTimeout(r, 3000))]); } catch { /* 글꼴 못 읽으면 기본 글꼴로 */ }
    if (this.dead) return;
    this.T = THREE;
    const host = this.stageRef.current;
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer = renderer;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);

    const EMB = !!this.props.embedded; // UI설계서 적용: 설계서에 없는 연출·조작을 끈다
    const NOWORK = new Set(['ALARM', 'SETUP', 'MAINT', 'BLOCKED']);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xeef1f4);
    scene.fog = new THREE.Fog(0xeef1f4, 34, 75);
    const pm = new THREE.PMREMGenerator(renderer);
    scene.environment = pm.fromScene(new RE.RoomEnvironment(), 0.04).texture;

    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 200); this.camera = camera;
    let composer = null, bloom = null;
    if (PP) try {
      composer = new PP[0].EffectComposer(renderer); composer.addPass(new PP[1].RenderPass(scene, camera));
      bloom = new PP[2].UnrealBloomPass(new THREE.Vector2(512, 512), 0.15, 0.5, 0.92); composer.addPass(bloom); composer.addPass(new PP[3].OutputPass());
    } catch (e) { composer = null; console.error('[factory] composer', e); }
    const qual = () => this.props.quality || '자동';
    const doRender = () => { const L0 = this.state.layers || {}; if (composer && !this.lowQ && qual() !== '저사양' && L0.bloom !== false) composer.render(); else renderer.render(scene, camera); };
    const controls = new OC.OrbitControls(camera, renderer.domElement); this.controls = controls;
    controls.enableDamping = true; controls.dampingFactor = 0.12;
    controls.maxPolarAngle = Math.PI * 0.45; controls.minPolarAngle = 0.12; controls.minDistance = 0.8; controls.maxDistance = 48;
    controls.rotateSpeed = 0.55; controls.zoomSpeed = 0.85;
    controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.PAN, RIGHT: THREE.MOUSE.PAN }; // 휠 누르고 끌기 = 화면 잡고 옮기기 (확대·축소는 휠 굴리기)
    if (EMB) { controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.PAN, RIGHT: THREE.MOUSE.PAN }; controls.enablePan = true; } // 사용자 요청 2026-10-15: 화면 모드에서도 휠 누르고 끌어 옮기기
    renderer.domElement.addEventListener('contextmenu', e => e.preventDefault());
    { const cv = renderer.domElement, grab = (on) => { cv.style.cursor = on ? 'grabbing' : ''; }; cv.addEventListener('pointerdown', e => { if (e.button === 1 || e.button === 2) grab(true); }); window.addEventListener('pointerup', () => grab(false)); cv.addEventListener('mousedown', e => { if (e.button === 1) e.preventDefault(); }); } // 가운데 버튼 자동 스크롤 막고 손바닥 커서
    {
      const rc = new THREE.Raycaster(), nd = new THREE.Vector2(), fp = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), hit = new THREE.Vector3();
      renderer.domElement.addEventListener('dblclick', (e) => {
        if (EMB || this.intro || this.tour.on) return;
        const rb = renderer.domElement.getBoundingClientRect(); nd.set(((e.clientX - rb.left) / rb.width) * 2 - 1, -((e.clientY - rb.top) / rb.height) * 2 + 1);
        rc.setFromCamera(nd, camera); if (!rc.ray.intersectPlane(fp, hit)) return;
        hit.x = Math.max(-1, Math.min(39, hit.x)); hit.z = Math.max(-12, Math.min(1, hit.z));
        const dir = camera.position.clone().sub(controls.target); const d0 = Math.max(6, dir.length() * 0.6);
        this.goal = { pos: hit.clone().add(dir.normalize().multiplyScalar(d0)), target: hit.clone() };
      });
    }
    controls.autoRotateSpeed = 0.6;
    controls.addEventListener('start', () => { this.goal = null; });
    controls.screenSpacePanning = false; controls.panSpeed = 1.0; controls.keyPanSpeed = 20;
    controls.zoomToCursor = false; controls.enableZoom = false;
    {
      const rcZ = new THREE.Raycaster(), ndZ = new THREE.Vector2(), fpZ = new THREE.Plane(new THREE.Vector3(0, 1, 0), -0.6), hz = new THREE.Vector3(), dv = new THREE.Vector3();
      this.zoomV = 0;
      renderer.domElement.addEventListener('wheel', (e) => {
        if (this.intro || this.tour.on) return;
        e.preventDefault(); this.goal = null;
        const dy0 = e.deltaMode === 1 ? e.deltaY * 33 : e.deltaY;
        if (dy0 > 0) { // 축소 = [전체] 화면 쪽으로 한 칸씩 돌아감(카메라 · 가운데 같이), 끝까지 굴리면 [전체]와 같은 화면. 커서 쪽 기준이면 확대한 채 옆으로 미끄러졌다 (사용자 요청 2026-10-22)
          const H = this.presetPos('front'), s = Math.min(0.4, dy0 * 0.002);
          camera.position.lerp(H.pos, s); controls.target.lerp(H.tgt, s);
          if (camera.position.distanceTo(H.pos) < 0.05) { camera.position.copy(H.pos); controls.target.copy(H.tgt); }
          return;
        }
        const rb = renderer.domElement.getBoundingClientRect(); ndZ.set(((e.clientX - rb.left) / rb.width) * 2 - 1, -((e.clientY - rb.top) / rb.height) * 2 + 1);
        rcZ.setFromCamera(ndZ, camera);
        const hits = rcZ.intersectObjects(scene.children, true).filter(x0 => x0.object.visible && x0.object.isMesh && !x0.object.isInstancedMesh || x0.object.isInstancedMesh);
        let ok = false;
        if (hits.length && hits[0].distance < 80) { hz.copy(hits[0].point); ok = true; }
        else if (rcZ.ray.intersectPlane(fpZ, hz)) ok = true;
        if (!ok) return;
        const dist = camera.position.distanceTo(hz);
        const dy = e.deltaMode === 1 ? e.deltaY * 33 : e.deltaY;
        let k = Math.max(-0.35, Math.min(0.35, -dy * 0.0015));
        if (k > 0 && dist * (1 - k) < 1.6) k = Math.max(0, 1 - 1.6 / dist);
        if (!k) return;
        dv.copy(hz).sub(camera.position).multiplyScalar(k);
        camera.position.add(dv); controls.target.add(dv);
        if (k > 0) { const tv = controls.target.clone().sub(camera.position), tl = tv.length(); if (tl > dist * 0.98) controls.target.copy(camera.position).add(tv.multiplyScalar((dist * (1 - k)) / tl)); }
      }, { passive: false });
    }
    // 데이터적용본: 터치 두 손가락 벌리기·모으기 = 확대·축소 (D-01, SCR-04 [3]). 한 손가락 끌기 = 각도(OrbitControls), 탭 = 설비 고르기
    {
      let pd = 0; const el2 = renderer.domElement;
      const gap = (e) => Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      el2.addEventListener('touchstart', (e) => { if (e.touches.length === 2) pd = gap(e); }, { passive: true });
      el2.addEventListener('touchmove', (e) => { if (e.touches.length !== 2 || !pd || this.intro || this.tour.on) return; const d = gap(e); if (d > 0) { this.nav('zoom', pd / d); pd = d; } }, { passive: true });
      el2.addEventListener('touchend', () => { pd = 0; });
    }
    controls.keys = { LEFT: 'ArrowLeft', UP: 'ArrowUp', RIGHT: 'ArrowRight', BOTTOM: 'ArrowDown' };
    if (!EMB) controls.listenToKeyEvents(window);
    this.keys = new Set();
    const kd = e => { if (EMB) return; if (e.target && /INPUT|TEXTAREA/.test(e.target.tagName)) return; const k = e.key.toLowerCase(); if ('wasdqe+-='.includes(k)) { this.keys.add(k); this.goal = null; } };
    const ku = e => this.keys.delete(e.key.toLowerCase());
    window.addEventListener('keydown', kd); window.addEventListener('keyup', ku);
    window.addEventListener('blur', () => this.keys.clear());
    let lastW = 0, lastH = 0, viewSet = false;
    const fit = () => {
      const r = host.getBoundingClientRect();
      const w = Math.round(r.width) || window.innerWidth, h = Math.round(r.height) || window.innerHeight;
      if (!w || !h || (w === lastW && h === lastH)) return;
      lastW = w; lastH = h;
      if ((w < 1180) !== this.state.narrow) this.setState({ narrow: w < 1180 });
      renderer.setSize(w, h); if (composer) { composer.setPixelRatio(renderer.getPixelRatio()); composer.setSize(w, h); } camera.aspect = w / h; camera.updateProjectionMatrix();
      if (!viewSet) { viewSet = true; this.setView(this.state.view, true); if (EMB) { this.maxDist = camera.position.distanceTo(controls.target) * 1.03; controls.maxDistance = this.maxDist; this.entry(); } }
    };
    this.ro = new ResizeObserver(fit); this.ro.observe(host);
    fit();

    const towers = {}, flows = [], pickables = [], outlines = {}, pads = {}, bots = {}, rigs = {}, pallets = {}, rings = {}, fx = {}, groups = {};
    const env = { panels: [], grids: [], inLights: [], glow: [] };
    let smoke = null, sparkFx = null;
    let curId = null;
    const flowG = new THREE.Group(); scene.add(flowG);
    let cur = scene;
    const P = (X, Y, h) => new THREE.Vector3(X / 1000, h, -Y / 1000);
    const M = (c, o = {}) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.55, metalness: 0.1, ...o });
    const mat = {
      green: M(0xe8ecef, { roughness: 0.5 }), greenD: M(0x8f99a2, { roughness: 0.5 }), white: M(0xeef1f3, { roughness: 0.4 }), grey: M(0xc4cbd1),
      dark: M(0x3e4650, { roughness: 0.5 }), steel: M(0xb8c0c8, { metalness: 0.7, roughness: 0.3 }),
      granite: M(0x353a41, { roughness: 0.75 }), wood: M(0xc8925a, { roughness: 0.8 }),
      blue: M(0x4a6fa5), yellow: M(0xe8b53a), lav: M(0xc6c1e4), orange: M(0xe9a23b), inner: M(0x67707a, { roughness: 0.7 }),
      part: M(0xd3d9de, { metalness: 0.85, roughness: 0.22 }), blade: M(0xe6ebef, { metalness: 0.9, roughness: 0.18 }),
      glass: new THREE.MeshPhysicalMaterial({ color: 0x22323e, roughness: 0.08, metalness: 0.2, transparent: true, opacity: 0.78 }),
      clear: new THREE.MeshPhysicalMaterial({ color: 0xd6ebf5, roughness: 0.05, metalness: 0, transparent: true, opacity: 0.14, depthWrite: false }),
      screen: new THREE.MeshStandardMaterial({ color: 0x0d2a3a, emissive: 0x3fa9d8, emissiveIntensity: 0.6 }),
    };
    const shade = (m) => { m.castShadow = true; m.receiveShadow = true; return m; };
    const box = (x0, x1, y0, y1, h0, h1, m, parent = cur) => {
      const bw = (x1 - x0) / 1000, bh = h1 - h0, bd = (y1 - y0) / 1000, mn = Math.min(bw, bh, bd);
      const geo = RBG && mn > 0.06 ? new RBG(bw, bh, bd, 2, Math.min(0.03, mn * 0.18)) : new THREE.BoxGeometry(bw, bh, bd);
      const mesh = shade(new THREE.Mesh(geo, m));
      mesh.position.set((x0 + x1) / 2000, (h0 + h1) / 2, -(y0 + y1) / 2000); parent.add(mesh); return mesh;
    };
    const cyl = (X, Y, h0, h1, r, m, parent = cur) => {
      const mesh = shade(new THREE.Mesh(new THREE.CylinderGeometry(r, r, h1 - h0, 24), m));
      mesh.position.set(X / 1000, (h0 + h1) / 2, -Y / 1000); parent.add(mesh); return mesh;
    };
    const cylX = (x0, x1, Y, h, r, m, parent = cur) => { const c = cyl((x0 + x1) / 2, Y, h - (x1 - x0) / 2000, h + (x1 - x0) / 2000, r, m, parent); c.rotation.z = Math.PI / 2; return c; };
    const cylY = (X, y0, y1, h, r, m, parent = cur) => { const c = cyl(X, (y0 + y1) / 2, h - (y1 - y0) / 2000, h + (y1 - y0) / 2000, r, m, parent); c.rotation.x = Math.PI / 2; return c; };
    const grp = (parent = cur) => { const g = new THREE.Group(); parent.add(g); return g; };
    const pivot = (X, Y, h, parent = cur) => { const g = new THREE.Group(); g.position.copy(P(X, Y, h)); parent.add(g); return g; };
    const mesh = (geo, m, parent, x = 0, y = 0, z = 0) => { const o = shade(new THREE.Mesh(geo, m)); o.position.set(x, y, z); parent.add(o); return o; };
    const tower = (X, Y, h) => {
      cyl(X, Y, h, h + 0.22, 0.014, mat.dark);
      [[0xff4a3d, 0.1], [0xffb02e, 0.1], [0x22d36b, 1]].forEach(([c, e], i) => {
        const m = new THREE.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: e, transparent: true, opacity: 0.92 });
        const s = cyl(X, Y, h + 0.22 + i * 0.075, h + 0.29 + i * 0.075, 0.034, m);
        (towers[curId || 'x'] = towers[curId || 'x'] || []).push(m);
        s.castShadow = false;
      });
    };
    const shell = (x0, x1, y0, y1, h0, h1, w, body, sideH0) => {
      const t = 40, sh = sideH0 ?? h0;
      box(x0, x1, y1 - t, y1, h0, h1, body);
      box(x0, x0 + t, y0, y1 - t, sh, h1, body); box(x1 - t, x1, y0, y1 - t, sh, h1, body);
      box(x0, x1, y0, y1, h1 - 0.05, h1, body);
      box(x0 + t, x1 - t, y0 + t, y1 - t, h0, h0 + 0.03, mat.inner);
      box(x0 + t, x1 - t, y1 - t - 20, y1 - t, h0, h1 - 0.05, mat.inner);
      box(x0, x1, y0, y0 + t, h0, w[2], body); box(x0, x1, y0, y0 + t, w[3], h1 - 0.05, body);
      box(x0, w[0], y0, y0 + t, w[2], w[3], body); box(w[1], x1, y0, y0 + t, w[2], w[3], body);
      const g = box(w[0], w[1], y0 + 15, y0 + 25, w[2], w[3], mat.clear); g.castShadow = false;
      box(w[0] - 20, w[1] + 20, y0 - 12, y0, w[3], w[3] + 0.03, mat.dark); box(w[0] - 20, w[1] + 20, y0 - 12, y0, w[2] - 0.03, w[2], mat.dark);
      const L = new THREE.PointLight(0xfff4e6, 5, 4, 2); L.position.copy(P((w[0] + w[1]) / 2, y0 + 450, w[3] - 0.12)); cur.add(L); env.inLights.push(L);
    };
    const emitter = (color, n, size, opacity = 0.9, mid = null) => {
      const pos = new Float32Array(n * 3).fill(-50), vel = new Float32Array(n * 3), life = new Float32Array(n);
      const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      const pts = new THREE.Points(g, new THREE.PointsMaterial({ color, size, transparent: true, opacity, depthWrite: false }));
      pts.frustumCulled = false; scene.add(pts);
      let k = 0;
      const self = this, ov = new THREE.Vector3();
      return {
        spawn(o0, rate, dt, spread, vy, lf) {
          const o = mid ? self.placePt(mid, ov.copy(o0)) : o0; // 데이터적용본: 설비 안 효과는 그 설비의 데이터 자리에서
          const c = Math.floor(rate * dt + Math.random());
          for (let s = 0; s < c; s++) {
            const i = (k++) % n;
            pos[i * 3] = o.x + (Math.random() - 0.5) * 0.02; pos[i * 3 + 1] = o.y; pos[i * 3 + 2] = o.z + (Math.random() - 0.5) * 0.02;
            vel[i * 3] = (Math.random() - 0.5) * spread; vel[i * 3 + 1] = vy * (0.4 + Math.random() * 0.6); vel[i * 3 + 2] = (Math.random() - 0.5) * spread;
            life[i] = lf * (0.6 + Math.random() * 0.4);
          }
        },
        step(dt, grav, floorH = -1) {
          for (let i = 0; i < n; i++) {
            if (life[i] <= 0) { pos[i * 3 + 1] = -50; continue; }
            life[i] -= dt; vel[i * 3 + 1] -= grav * dt;
            pos[i * 3] += vel[i * 3] * dt; pos[i * 3 + 1] += vel[i * 3 + 1] * dt; pos[i * 3 + 2] += vel[i * 3 + 2] * dt;
            if (pos[i * 3 + 1] < floorH) life[i] = 0;
          }
          g.attributes.position.needsUpdate = true;
        },
      };
    };
    const cvTex = (w, hh, draw) => { const c = document.createElement('canvas'); c.width = w; c.height = hh; draw(c.getContext('2d'), w, hh); const tx = new THREE.CanvasTexture(c); tx.colorSpace = THREE.SRGBColorSpace; tx.anisotropy = 4; return tx; };
    const hazTex = cvTex(128, 16, (g, w, hh) => { g.fillStyle = '#f2c230'; g.fillRect(0, 0, w, hh); g.fillStyle = '#1d232a'; for (let x = -16; x < w + 16; x += 16) { g.beginPath(); g.moveTo(x, hh); g.lineTo(x + 8, hh); g.lineTo(x + 16, 0); g.lineTo(x + 8, 0); g.fill(); } });
    hazTex.wrapS = THREE.RepeatWrapping;
    const aoTex = cvTex(128, 128, (g) => { const gr = g.createRadialGradient(64, 64, 10, 64, 64, 64); gr.addColorStop(0, 'rgba(20,28,36,0.55)'); gr.addColorStop(0.6, 'rgba(20,28,36,0.22)'); gr.addColorStop(1, 'rgba(20,28,36,0)'); g.fillStyle = gr; g.fillRect(0, 0, 128, 128); });
    const hatchTex = cvTex(64, 64, (g, w, hh) => { g.fillStyle = 'rgba(176,184,192,0.92)'; g.fillRect(0, 0, w, hh); g.strokeStyle = '#4b5a69'; g.lineWidth = 7; for (let k = -hh; k < w + hh; k += 22) { g.beginPath(); g.moveTo(k, hh); g.lineTo(k + hh, 0); g.stroke(); } });
    hatchTex.wrapS = hatchTex.wrapT = THREE.RepeatWrapping;
    const TOPH = { inf: 0.9, saw: 0.8, mil: 2.35, vf1: 2.15, vf2: 2.15, wsh: 1.55, cmm: 0.9 };
    const leds = {};
    const decorate = (id, g) => {
      const b = this.MACH[id].b, cx = (b[0] + b[1]) / 2000, cz = -(b[2] + b[3]) / 2000, w = (b[1] - b[0]) / 1000, d = (b[3] - b[2]) / 1000;
      const ao = new THREE.Mesh(new THREE.PlaneGeometry(w * 1.35, d * 1.45), new THREE.MeshBasicMaterial({ map: aoTex, transparent: true, depthWrite: false }));
      ao.rotation.x = -Math.PI / 2; ao.position.set(cx, 0.005, cz); (g.parent || scene).add(ao);
      const x0 = id === 'vf1' || id === 'vf2' ? b[0] + 140 : b[0], x1 = id === 'vf1' || id === 'vf2' ? b[1] : b[1];
      if (id !== 'inf') { const hz = hazTex.clone(); hz.needsUpdate = true; hz.repeat.set(((x1 - x0) / 1000) / 0.25, 1); box(x0 + 40, x1 - 40, 3790, 3800, 0.015, 0.11, new THREE.MeshStandardMaterial({ map: hz, roughness: 0.6 }), g); }
      const top = TOPH[id];
      const lm = new THREE.MeshBasicMaterial({ color: 0x22d36b }); leds[id] = lm;
      box(x0 + 60, x1 - 60, 3786, 3800, top - 0.07, top - 0.035, lm, g).castShadow = false;
      const M0 = this.MACH[id];
      const plate = cvTex(256, 72, (g2, ww, hh) => { g2.fillStyle = '#20272f'; g2.fillRect(0, 0, ww, hh); g2.fillStyle = '#0fb5d4'; g2.fillRect(0, 0, 6, hh); g2.fillStyle = '#ffffff'; g2.font = '700 30px "Pretendard Variable", sans-serif'; g2.fillText(M0.name, 18, 34); g2.fillStyle = '#9fb1c2'; g2.font = '500 18px "Pretendard Variable", sans-serif'; g2.fillText(M0.op + ' · BRK-A100', 18, 60); });
      const pm = new THREE.Mesh(new THREE.PlaneGeometry(0.46, 0.13), new THREE.MeshStandardMaterial({ map: plate, roughness: 0.4, metalness: 0.2 }));
      const ph = Math.max(0.35, Math.min(top - 0.22, 1.85));
      pm.position.set(x0 / 1000 + 0.32, ph, -3.8 + 0.006); g.add(pm);
      const AX = this.AXM || (this.AXM = { es: M(0xd8262b, { roughness: 0.35 }), ey: M(0xf2c230, { roughness: 0.5 }), vent: M(0x5d6771, { roughness: 0.7 }), tank: M(0x4d6b84, { roughness: 0.45, metalness: 0.2 }), cab: M(0x2a3138, { roughness: 0.8 }) });
      if (id !== 'inf' && top > 0.6) {
        const ex = x1 / 1000 - 0.16, ey = Math.min(top - 0.3, 1.25);
        const base0 = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.02, 20), AX.ey); base0.rotation.x = Math.PI / 2; base0.position.set(ex, ey, -3.8 + 0.012); g.add(base0);
        const btn = new THREE.Mesh(new THREE.CylinderGeometry(0.032, 0.036, 0.035, 20), AX.es); btn.rotation.x = Math.PI / 2; btn.position.set(ex, ey, -3.8 + 0.035); g.add(btn);
        const vx0 = x1 / 1000 - 0.62, vy = 0.16;
        for (let k = 0; k < 5; k++) { const sl = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.012, 0.01), AX.vent); sl.position.set(vx0 + 0.2, vy + 0.06 + k * 0.032, -3.8 + 0.008); g.add(sl); }
      }
      if (id === 'vf1' || id === 'vf2' || id === 'mil') {
        const bz = -b[3] / 1000, tx = (x0 + x1) / 2000;
        const tk = shade(new THREE.Mesh(RBG ? new RBG(Math.min(1.1, w * 0.6), 0.5, 0.42, 2, 0.04) : new THREE.BoxGeometry(Math.min(1.1, w * 0.6), 0.5, 0.42), AX.tank)); tk.position.set(tx, 0.25, bz - 0.24); g.add(tk);
        const mag = shade(new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.36, 0.12, 40), AX.cab)); mag.rotation.x = Math.PI / 2; mag.position.set(x0 / 1000 + 0.5, top - 0.55, bz - 0.07); g.add(mag);
        for (let k = 0; k < 16; k++) { const a0 = k / 16 * Math.PI * 2; const pk = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.1, 10), mat.steel); pk.rotation.x = Math.PI / 2; pk.position.set(x0 / 1000 + 0.5 + Math.cos(a0) * 0.29, top - 0.55 + Math.sin(a0) * 0.29, bz - 0.15); g.add(pk); }
        const duct = shade(new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.12, Math.max(0.2, d - 0.3)), AX.cab)); duct.position.set(x1 / 1000 - 0.25, top + 0.06, cz); g.add(duct);
      }
    };
    const machine = (id, build) => {
      // 데이터적용본: 설비 모델(g)은 원본 좌표로 짓고, 바깥 묶음(place)이 데이터 좌표·크기로 옮긴다
      const place = new THREE.Group(); scene.add(place);
      const g = new THREE.Group(); place.add(g); cur = g; curId = id;
      try { build(g); } catch (e) { console.error('[factory] build ' + id, e); }
      cur = scene; curId = null;
      const PL = this.LY && this.LY.P[id];
      if (PL) { place.position.set(PL.ox, 0, PL.oz); place.scale.set(PL.sx, PL.sy, PL.sz); }
      g.traverse(o => { if (o.isMesh) { o.userData.mid = id; pickables.push(o); } });
      const b = this.MACH[id].bd || this.MACH[id].b;
      const w = (b[1] - b[0]) / 1000 + 0.2, d = (b[3] - b[2]) / 1000 + 0.2, h = b[5] + 0.1;
      const ol = new THREE.Group(); ol.position.set((b[0] + b[1]) / 2000, 0, -(b[2] + b[3]) / 2000);
      const line = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w, h, d)), new THREE.LineBasicMaterial({ color: 0x14a9cc }));
      line.position.y = h / 2; ol.add(line);
      const pad = new THREE.Mesh(new THREE.PlaneGeometry(w + 0.3, d + 0.3), new THREE.MeshBasicMaterial({ color: 0x3cc8e6, transparent: true, opacity: 0.22, depthWrite: false }));
      pad.rotation.x = -Math.PI / 2; pad.position.y = 0.012; ol.add(pad);
      ol.visible = false; ol.userData = { lm: line.material, pm: pad.material, ln: line }; scene.add(ol); outlines[id] = ol;
      groups[id] = g;
      {
        const px = (b[0] + b[1]) / 2000, pz = -(b[2] + b[3]) / 2000, mk = (wd, ht, o) => { const tx = hatchTex.clone(); tx.needsUpdate = true; tx.wrapS = tx.wrapT = THREE.RepeatWrapping; tx.repeat.set(wd / 0.28, ht / 0.28); return new THREE.Mesh(new THREE.PlaneGeometry(wd, ht), new THREE.MeshBasicMaterial({ map: tx, transparent: true, opacity: o, depthWrite: false })); };
        const hatch = mk(w + 0.3, d + 0.3, 0.9); hatch.rotation.x = -Math.PI / 2; hatch.position.set(px, 0.022, pz);
        const block = new THREE.Mesh(new THREE.PlaneGeometry(w + 0.3, d + 0.3), new THREE.MeshBasicMaterial({ color: 0xe8954a, transparent: true, opacity: 0.5, depthWrite: false })); block.rotation.x = -Math.PI / 2; block.position.set(px, 0.023, pz);
        [hatch, block].forEach(o0 => { o0.visible = false; scene.add(o0); }); // 설비 앞면 빗금판은 보류(H-10)
        pads[id] = { hatch, block };
      }
      try { decorate(id, g); } catch (e) { console.error('[factory] deco', e); }
      const cx = (b[0] + b[1]) / 2000, cz = -(b[2] + b[3]) / 2000;
      const F = { g: new THREE.Group(), ringG: new THREE.Group(), beam: new THREE.Group(), mats: [], rings: [] };
      F.g.position.set(cx, b[5] + 0.42, cz); scene.add(F.g); F.g.add(F.beam);
      const dome = new THREE.Mesh(new THREE.SphereGeometry(0.085, 20, 14), new THREE.MeshBasicMaterial({ color: 0xff3b3b })); F.g.add(dome); F.mats.push(dome.material);
      [0, Math.PI].forEach(a => {
        const cm = new THREE.MeshBasicMaterial({ color: 0xff3b3b, transparent: true, opacity: 0.16, depthWrite: false, side: THREE.DoubleSide });
        const c = new THREE.Mesh(new THREE.ConeGeometry(0.42, 1.7, 24, 1, true), cm); c.rotation.z = Math.PI / 2; c.position.x = 0.85;
        const hd = new THREE.Group(); hd.rotation.y = a; hd.add(c); F.beam.add(hd); F.mats.push(cm);
      });
      F.light = new THREE.PointLight(0xff3b3b, 0, 6, 1.6); F.g.add(F.light);
      F.ringG.position.set(cx, 0.016, cz); const rs0 = Math.max(w, d) * 0.55; F.ringG.scale.set(rs0, rs0, rs0); scene.add(F.ringG);
      for (let i = 0; i < 3; i++) {
        const rm = new THREE.MeshBasicMaterial({ color: 0xff3b3b, transparent: true, opacity: 0, depthWrite: false });
        const rg = new THREE.Mesh(new THREE.RingGeometry(0.93, 1.0, 64), rm); rg.rotation.x = -Math.PI / 2; F.ringG.add(rg); F.rings.push(rg); F.mats.push(rm);
      }
      F.top = new THREE.Vector3(cx, b[5] + 0.05, cz); F.front = new THREE.Vector3(cx, b[5] * 0.55, -b[2] / 1000 + 0.06);
      F.g.visible = false; F.ringG.visible = false; fx[id] = F;
    };

    const hemi = new THREE.HemisphereLight(0xffffff, 0xc9d0d6, 0.55); scene.add(hemi);
    const sun = new THREE.DirectionalLight(0xffffff, 1.5);
    sun.position.set(8, 22, 12); sun.target.position.set(16, 0, -4);
    sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048);
    Object.assign(sun.shadow.camera, { left: -24, right: 24, top: 16, bottom: -16, near: 1, far: 60 }); // 데이터적용본: 28 m 공장 + 자동창고
    sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.02; sun.shadow.radius = 4;
    scene.add(sun, sun.target);

    try {
      // floor, walls, background
      const floor = new THREE.Mesh(new THREE.PlaneGeometry(140, 90), M(0xe3e7ea, { roughness: 0.85 }));
      floor.rotation.x = -Math.PI / 2; floor.position.set(12.5, 0, -8); floor.receiveShadow = true; scene.add(floor); env.floor = floor.material;
      const flat = (x0, x1, y0, y1, color, op, h = 0.002) => {
        const p = new THREE.Mesh(new THREE.PlaneGeometry((x1 - x0) / 1000, (y1 - y0) / 1000),
          new THREE.MeshStandardMaterial({ color, transparent: op < 1, opacity: op, roughness: 0.8, depthWrite: op >= 1 }));
        p.rotation.x = -Math.PI / 2; p.position.set((x0 + x1) / 2000, h, -(y0 + y1) / 2000); p.receiveShadow = true; scene.add(p); return p;
      };
      env.inner = flat(0, 28000, 0, 8000, 0xf5f7f9, 1, 0.001).material;
      // 벽 윤곽선(28 x 8 m, 천장 4 m 선)은 사용자 요청 2026-10-15로 지움
      // 데이터적용본: 주 통로 0~2,000 · 재공 띠 2,000~2,800 · 설비 앞 작업 띠 2,800~3,800 (plant_layout.csv, 원본 색 그대로)
      flat(0, 28000, 0, 2000, 0xbfe9dc, 0.45, 0.003);
      flat(0, 28000, 2000, 2800, 0xf7b979, 0.4, 0.003);
      flat(0, 28000, 2800, 3800, 0xb6d3ee, 0.35, 0.003);
      const wall = new THREE.Mesh(new THREE.PlaneGeometry(90, 10), M(0xeceff2, { roughness: 0.9 }));
      wall.position.set(12.5, 5, -16); wall.receiveShadow = true; scene.add(wall); env.wall = wall.material;
      const decoG = new THREE.Group(); scene.add(decoG); const cur0 = cur; cur = decoG; // 배경 건물·크레인: 설계서에 없지만 3D 디자인이라 보류(H-05)로 둠
      box(-30000, 55000, 15800, 16000, 0, 0.9, M(0xd6dbe0));
      for (let X = -6000; X < 34000; X += 5200) env.panels.push(box(X, X + 3400, 15880, 16000, 6.4, 7.0, new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0.4 })).material);
      box(17000, 27000, 13200, 15800, 0, 2.6, M(0xe2e6e9));
      box(17000, 27000, 13200, 15800, 2.6, 5.4, mat.white);
      box(17600, 26400, 13170, 13200, 3.0, 5.0, new THREE.MeshPhysicalMaterial({ color: 0x8fb4cf, roughness: 0.05, transparent: true, opacity: 0.55, metalness: 0.1 }));
      [18500, 20800, 23100].forEach(X => box(X, X + 900, 13600, 13900, 3.0, 3.6, mat.dark));
      const bgm = (X, Y, w, d, h, m) => { box(X, X + w, Y, Y + d, 0, h, m); box(X + 200, X + w * 0.6, Y - 20, Y, h * 0.4, h * 0.82, mat.glass); };
      bgm(-4000, 10200, 2200, 1800, 2.4, mat.white); bgm(-500, 10600, 2000, 1800, 2.2, mat.green);
      bgm(3200, 10000, 2400, 1900, 2.5, mat.white); bgm(7000, 10400, 2200, 1800, 2.4, mat.white);
      bgm(10600, 10200, 2000, 1800, 2.6, mat.green); bgm(-8000, 9000, 2000, 1800, 2.3, mat.green);
      cur = cur0;
      decoG.visible = false; // 사용자 요청 2026-10-15: 뒷배경 하얀 사각형(건물·조명판·배경 설비) 숨김. 다시 보이려면 true

      const gl = (pts, color, op, nColor) => {
        const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
        const lm = new THREE.LineBasicMaterial({ color, transparent: true, opacity: op });
        scene.add(new THREE.LineSegments(g, lm));
        env.grids.push({ g, m: lm, op, n: pts.length / 3, cd: new THREE.Color(color), cn: new THREE.Color(nColor) });
      };
      const mn = [], mj = [];
      for (let X = 0; X <= 28000; X += 1000) (X % 5000 ? mn : mj).push(X / 1000, 0.005, 0.25, X / 1000, 0.005, -8);
      for (let Y = 0; Y <= 8000; Y += 1000) (Y % 4000 ? mn : mj).push(-0.25, 0.005, -Y / 1000, 28, 0.005, -Y / 1000);
      gl(mn, 0x8796a5, 0.5, 0x1f5266); gl(mj, 0x4f6173, 0.75, 0x3fb5d6);
      const dashLine = (pts, color, ds, gs, h = 0.012) => {
        const g = new THREE.BufferGeometry().setFromPoints(pts.map(([X, Y]) => P(X, Y, h)));
        const l = new THREE.Line(g, new THREE.LineDashedMaterial({ color, dashSize: ds, gapSize: gs })); l.computeLineDistances(); scene.add(l); return l;
      };
      dashLine([[0, 3800], [28000, 3800]], 0x56616c, 0.2, 0.14);
      // OP-30 구역 테두리 = VF2-01·02와 그 앞 WIP-3 (WIP-2는 MIL-01·VF2-01 사이, 2026-10-20) (데이터 좌표). 시뮬레이터 병목이 OP-30이면 주황 (loop)
      { const R0 = this.LY ? this.LY.op30 : [9700, 16900, 1550, 5900];
        env.op30 = dashLine([[R0[0], R0[2]], [R0[1], R0[2]], [R0[1], R0[3]], [R0[0], R0[3]], [R0[0], R0[2]]], 0x3c4752, 0.3, 0.16, 0.02).material; }

      // glow boundary
      const gradTex = (axis) => {
        const c = document.createElement('canvas'); c.width = axis === 'u' ? 256 : 4; c.height = axis === 'u' ? 4 : 256;
        const g = c.getContext('2d');
        const gr = axis === 'u' ? g.createLinearGradient(0, 0, 256, 0) : g.createLinearGradient(0, 256, 0, 0);
        if (axis === 'w') { gr.addColorStop(0, 'rgba(70,205,235,0.75)'); gr.addColorStop(0.3, 'rgba(110,220,240,0.28)'); gr.addColorStop(1, 'rgba(140,230,245,0)'); }
        else { gr.addColorStop(0, 'rgba(70,205,235,0)'); gr.addColorStop(0.5, 'rgba(70,205,235,0.8)'); gr.addColorStop(1, 'rgba(70,205,235,0)'); }
        g.fillStyle = gr; g.fillRect(0, 0, c.width, c.height);
        const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
      };
      const gm = (axis) => new THREE.MeshBasicMaterial({ map: gradTex(axis), transparent: true, depthWrite: false, side: THREE.DoubleSide, fog: false });
      const gU = gm('u'), gV = gm('v'), gW = gm('w'); env.glow = [gU, gV, gW];
      const glowG = new THREE.Group(); scene.add(glowG); // 청록 구역 띠: 보류(H-04)로 둠
      const bx0 = 0.3, bx1 = 27.7, bz0 = -0.4, bz1 = -7.6, bw = 0.9, bh = 0.45; // 데이터적용본: 공장 28 × 8 m 안쪽
      const strip = (w, d, x, z, m) => { const p = new THREE.Mesh(new THREE.PlaneGeometry(w, d), m); p.rotation.x = -Math.PI / 2; p.position.set(x, 0.008, z); glowG.add(p); };
      strip(bx1 - bx0, bw, (bx0 + bx1) / 2, bz0, gV); strip(bx1 - bx0, bw, (bx0 + bx1) / 2, bz1, gV);
      strip(bw, bz0 - bz1, bx0, (bz0 + bz1) / 2, gU); strip(bw, bz0 - bz1, bx1, (bz0 + bz1) / 2, gU);
      const wallG = (len, x, z, ry) => { const p = new THREE.Mesh(new THREE.PlaneGeometry(len, bh), gW); p.position.set(x, bh / 2, z); p.rotation.y = ry; glowG.add(p); };
      wallG(bx1 - bx0, (bx0 + bx1) / 2, bz0, 0); wallG(bx1 - bx0, (bx0 + bx1) / 2, bz1, 0);
      wallG(bz0 - bz1, bx0, (bz0 + bz1) / 2, Math.PI / 2); wallG(bz0 - bz1, bx1, (bz0 + bz1) / 2, Math.PI / 2);
      const core = new THREE.MeshBasicMaterial({ color: 0x5fdcf2, fog: false, transparent: true }); env.core = core;
      const cb = (w, d, x, z) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, 0.02, d), core); m.position.set(x, 0.012, z); glowG.add(m); };
      cb(bx1 - bx0, 0.035, (bx0 + bx1) / 2, bz0); cb(bx1 - bx0, 0.035, (bx0 + bx1) / 2, bz1);
      cb(0.035, bz0 - bz1, bx0, (bz0 + bz1) / 2); cb(0.035, bz0 - bz1, bx1, (bz0 + bz1) / 2);

      // RACK-01
      // RACK-01 봉재 랙 (데이터 1,000~4,814 × 6,300~7,020, 높이 2,000) + 6061-T6 평각봉 3,658 mm (원본은 Ø40 둥근 봉)
      { const R0 = this.LY ? this.LY.rack : { x: [770, 3830], y: [5970, 6730], h: 2000 }, rx0 = R0.x[0], rx1 = R0.x[1], ry0 = R0.y[0], ry1 = R0.y[1], rh = (R0.h || 2000) / 1000;
        [0, 1, 2, 3].forEach(i => { const X = rx0 + 30 + (rx1 - rx0 - 60) * i / 3; [ry0 + 30, ry1 - 30].forEach(Y => box(X - 30, X + 30, Y - 30, Y + 30, 0, rh, mat.blue)); });
        [0.15, 0.75, 1.35, rh - 0.05].forEach(h => box(rx0, rx1, ry0, ry1, h, h + 0.04, mat.dark));
        [0.75, 1.35].forEach(h => { for (let i = 0; i < 6; i++) { const Y = ry0 + 120 + i * ((ry1 - ry0 - 240) / 5); box(rx0 + 80, rx0 + 80 + 3658, Y - 28, Y + 28, h + 0.04, h + 0.059, mat.steel); } }); }
      cur = decoG;
      const truss = M(0x9aa5b0, { metalness: 0.55, roughness: 0.4 });
      for (let X = -6000; X <= 32000; X += 6000) {
        box(X - 60, X + 60, 12600, 15800, 9.6, 9.85, truss); box(X - 40, X + 40, 12600, 15800, 8.9, 9.0, truss);
        for (let Y = 12600; Y < 15800; Y += 1100) box(X - 20, X + 20, Y, Y + 30, 9.0, 9.6, truss);
      }
      const crane = M(0xe2b23c, { roughness: 0.45, metalness: 0.2 });
      box(-8000, 34000, 15350, 15600, 6.0, 6.25, crane);
      cylX(-8000, 34000, 15300, 5.6, 0.26, M(0xd2d8dd, { metalness: 0.65, roughness: 0.3 }));
      cylX(-8000, 34000, 15100, 5.05, 0.14, M(0xc5ccd2, { metalness: 0.6, roughness: 0.35 }));
      env.lamps = [];
      for (let X = -3000; X < 30000; X += 6000) [13800].forEach(Y => {
        cyl(X + 3000, Y, 6.95, 8.95, 0.008, mat.dark);
        const lm0 = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff4e2, emissiveIntensity: 0.7 });
        box(X + 2350, X + 3650, Y - 130, Y + 130, 6.85, 6.95, lm0); env.lamps.push(lm0);
      });
      cur = cur0;
      env.floor.roughness = 0.62; env.floor.metalness = 0.08; env.inner.roughness = 0.38; env.inner.metalness = 0.06;
    } catch (e) { console.error('[factory] env', e); }

    // INF-01
    machine('inf', () => {
      [900, 2500, 4100].forEach(X => [3950, 4850].forEach(Y => box(X - 30, X + 30, Y - 30, Y + 30, 0, 0.75, mat.steel)));
      box(800, 4200, 3900, 3960, 0.72, 0.9, M(0x6f8aa6)); box(800, 4200, 4840, 4900, 0.72, 0.9, M(0x6f8aa6));
      rigs.rollers = [];
      for (let X = 950; X < 4200; X += 230) {
        const r = cylY(X, 3970, 4830, 0.8, 0.04, mat.steel);
        mesh(new THREE.BoxGeometry(0.012, 0.86, 0.082), mat.dark, r);
        rigs.rollers.push(r);
      }
      // 6061-T6 압출 평각봉 19.05 × 57.15 mm (원본은 Ø40 둥근 봉재)
      for (let i = 0; i < 6; i++) if (i !== 2) box(1000, 4200, 4150 + i * 100 - 28, 4150 + i * 100 + 28, 0.843, 0.862, mat.part);
      box(1000, 5600, 4322, 4378, 0.843, 0.862, mat.part);
      box(4150, 4200, 4000, 4800, 0.9, 1.0, mat.orange);
    });

    // SAW-01: band saw
    machine('saw', () => {
      box(4560, 6240, 3860, 5140, 0, 0.12, mat.dark);
      box(4500, 6300, 3800, 5200, 0.12, 0.8, mat.green);
      box(4600, 6200, 3950, 5050, 0.8, 0.84, mat.steel);
      box(5300, 5560, 4400, 4480, 0.84, 0.98, mat.dark);
      const jaw = grp(); box(5300, 5560, 4180, 4260, 0.84, 0.98, mat.orange, jaw);
      cyl(5430, 4060, 0.84, 0.9, 0.03, mat.steel);
      box(5640, 6250, 4250, 4450, 0.84, 0.86, mat.steel);
      cyl(5450, 5050, 0.84, 1.55, 0.045, mat.steel);
      const head = grp();
      box(5420, 5780, 3850, 4950, 1.38, 1.46, mat.green, head);
      box(5420, 5520, 3850, 4950, 0.98, 1.38, mat.green, head);
      box(5592, 5608, 3950, 4850, 0.888, 0.912, mat.blade, head);
      box(5592, 5608, 3950, 4850, 1.31, 1.334, mat.blade, head);
      box(5560, 5640, 4220, 4300, 0.9, 1.38, mat.dark, head);
      box(5560, 5640, 4520, 4600, 0.9, 1.38, mat.dark, head);
      box(5400, 5500, 4980, 5120, 1.2, 1.5, mat.greenD, head);
      const wheels = [3950, 4850].map(Y => {
        const pv = pivot(5600, Y, 1.11, head);
        const w = mesh(new THREE.CylinderGeometry(0.21, 0.21, 0.05, 32), mat.steel, pv); w.rotation.z = Math.PI / 2;
        mesh(new THREE.BoxGeometry(0.06, 0.38, 0.05), mat.dark, pv);
        mesh(new THREE.BoxGeometry(0.06, 0.05, 0.38), mat.dark, pv);
        return pv;
      });
      const piece = box(5615, 5767, 4322, 4378, 0.843, 0.862, mat.part); piece.userData.x0 = piece.position.x; // 152 mm 토막
      box(5900, 6250, 3700, 3800, 0.9, 1.5, mat.dark); box(5940, 6210, 3690, 3700, 1.15, 1.42, mat.screen);
      box(6200, 6400, 4100, 4600, 0.5, 0.84, mat.steel).rotation.z = -0.35;
      tower(6200, 5100, 0.8);
      rigs.saw = { jaw, head, wheels, piece, sparks: emitter(0xffb347, 90, 0.022, 0.9, 'saw') };
    });

    // MIL-01: vertical mill
    machine('mil', () => {
      box(7260, 8740, 3760, 5340, 0, 0.12, mat.dark);
      shell(7200, 8800, 3800, 5400, 0.12, 2.35, [7330, 8250, 0.8, 1.95], mat.green);
      box(7300, 8700, 4100, 5300, 2.35, 2.55, mat.greenD);
      box(7300, 8780, 3780, 3800, 0.2, 0.55, mat.greenD);
      box(8320, 8760, 3660, 3800, 1.0, 1.9, mat.dark); box(8360, 8720, 3650, 3660, 1.45, 1.8, mat.screen);
      box(7480, 8120, 4100, 4800, 0.15, 0.85, mat.grey);
      const table = grp();
      box(7420, 8180, 4100, 4650, 0.85, 0.95, mat.steel, table);
      [4180, 4320, 4460, 4600].forEach(Y => box(7420, 8180, Y - 8, Y + 8, 0.948, 0.952, mat.dark, table));
      box(7650, 7950, 4250, 4450, 0.95, 1.0, mat.dark, table);
      // 외곽 황삭: 152 × 57 × 19 소재 → 151 × 56 (옆면 여유 0.5 mm). 깎이는 층(raw)이 줄어든다
      const milPart = box(7724, 7876, 4322, 4378, 1.0, 1.012, mat.part, table);
      const milShine = box(7725, 7875, 4323, 4377, 1.012, 1.0135, M(0xf4f8fb, { metalness: 0.9, roughness: 0.12 }), table);
      const milRaw = box(7724, 7876, 4322, 4378, 1.012, 1.019, M(0x737b83, { metalness: 0.45, roughness: 0.7 }), table);
      box(7600, 8000, 4950, 5320, 0.15, 2.3, mat.grey);
      const head = grp();
      box(7680, 7920, 4350, 4980, 1.5, 1.85, mat.greenD, head);
      cyl(7800, 4400, 1.27, 1.5, 0.06, mat.dark, head);
      const tool = pivot(7800, 4400, 1.21, head);
      mesh(new THREE.CylinderGeometry(0.085, 0.085, 0.07, 28), mat.steel, tool);
      mesh(new THREE.BoxGeometry(0.19, 0.03, 0.025), mat.orange, tool, 0, -0.02, 0);
      const noz = cyl(7980, 4300, 1.25, 1.45, 0.012, mat.blue, head); noz.rotation.z = 0.5;
      tower(8650, 5250, 2.55);
      rigs.mil = { table, head, tool, parts: [milPart, milShine], raw: milRaw, rawW: 0.152, rawX1: 7.876, chips: emitter(0xd8dee4, 70, 0.02, 0.9, 'mil'), cool: emitter(0x5fb8ff, 90, 0.018, 0.75, 'mil') };
    });

    // VF2 machining centers
    const vf = (id, x0, x1) => machine(id, () => {
      const y0 = 3800, y1 = 5600, wc = (x0 + 160 + x1 - 600) / 2;
      box(x0 + 60, x1 - 60, y0 + 60, y1 - 60, 0, 0.14, mat.dark);
      shell(x0, x1, y0, y1, 0.14, 2.15, [x0 + 160, x1 - 600, 0.62, 1.9], mat.white);
      box(x0 + 80, x1 - 560, y0 - 25, y0, 0.2, 0.5, M(0x9aa3ac));
      box(x0, x1, y0 - 14, y0, 1.98, 2.08, mat.dark);
      box(x1 - 520, x1 - 70, y0 - 150, y0, 1.0, 1.95, mat.dark); box(x1 - 470, x1 - 120, y0 - 160, y0 - 150, 1.5, 1.86, mat.screen);
      [1.2, 1.32].forEach(h => box(x1 - 440, x1 - 150, y0 - 162, y0 - 150, h, h + 0.06, mat.grey));
      const cx = (x0 + x1) / 2 - 150;
      box(cx - 420, cx + 420, y1 - 1050, y1 - 250, 2.15, 2.72, mat.grey);
      box(cx - 280, cx + 280, y1 - 1250, y1 - 650, 2.72, 2.92, mat.dark);
      cyl(cx, y1 - 900, 2.92, 3.02, 0.17, mat.dark);
      box(wc - 560, wc + 560, 3950, 4800, 0.17, 0.7, mat.grey);
      box(wc - 520, wc + 520, 4000, 4750, 0.7, 0.8, mat.steel);
      [4100, 4300, 4500, 4700].forEach(Y => box(wc - 520, wc + 520, Y - 8, Y + 8, 0.798, 0.802, mat.dark));
      box(wc - 210, wc + 210, 4180, 4520, 0.8, 0.85, mat.dark);
      // BRK-A100: 151 × 56 황삭품 → 외곽 정삭(strips) · Ø45 H7 보링(pocket) · M6 4개(holes)
      const vfPart = box(wc - 75, wc + 75, 4322, 4378, 0.85, 0.862, mat.part);
      const vfShine = this.VFSH || (this.VFSH = M(0xf4f8fb, { metalness: 0.9, roughness: 0.12 }));
      const pocket = cyl(wc, 4350, 0, 1, 1, mat.dark); pocket.visible = false;
      const strips = [
        box(wc - 75, wc + 75, 4322, 4326, 0.862, 0.8635, vfShine), box(wc + 71, wc + 75, 4322, 4378, 0.862, 0.8635, vfShine),
        box(wc - 75, wc + 75, 4374, 4378, 0.862, 0.8635, vfShine), box(wc - 75, wc - 71, 4322, 4378, 0.862, 0.8635, vfShine)];
      const holes = [[-0.055, -0.018], [0.055, -0.018], [0.055, 0.018], [-0.055, 0.018]].map(([hx, hz]) => cyl(wc + hx * 1000, 4350 - hz * 1000, 0.862, 0.8635, 0.003, mat.dark));
      [...strips, ...holes].forEach(m0 => { m0.visible = false; m0.castShadow = false; });
      [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([a, c]) => box(wc - 200 + (a > 0 ? 330 : 0), wc - 130 + (a > 0 ? 330 : 0), 4180 + (c > 0 ? 270 : 0), 4250 + (c > 0 ? 270 : 0), 0.85, 0.95, mat.blue));
      box(wc - 260, wc + 260, 5050, 5520, 0.17, 2.1, mat.grey);
      const head = grp();
      box(wc - 140, wc + 140, 4250, 5080, 1.45, 1.78, M(0xdfe3e7), head);
      cyl(wc, 4350, 1.16, 1.45, 0.07, mat.dark, head);
      const tool = pivot(wc, 4350, 1.12, head);
      mesh(new THREE.CylinderGeometry(0.045, 0.03, 0.06, 20), mat.steel, tool);
      mesh(new THREE.CylinderGeometry(0.014, 0.014, 0.08, 12), M(0xe8c070, { metalness: 0.8, roughness: 0.25 }), tool, 0, -0.07, 0);
      mesh(new THREE.BoxGeometry(0.1, 0.012, 0.012), mat.orange, tool, 0, 0.015, 0);
      const car = pivot(x0 - 90, 4700, 1.5);
      const disc = mesh(new THREE.CylinderGeometry(0.36, 0.36, 0.08, 36), mat.grey, car); disc.rotation.z = Math.PI / 2;
      for (let k = 0; k < 12; k++) {
        const a = (k / 12) * Math.PI * 2;
        mesh(new THREE.BoxGeometry(0.1, 0.06, 0.06), k % 3 === 0 ? mat.orange : mat.dark, car, -0.06, Math.cos(a) * 0.3, Math.sin(a) * 0.3);
      }
      box(x0 - 60, x0, 4300, 5100, 1.05, 1.95, mat.grey);
      tower(x1 - 140, y1 - 140, 2.15);
      rigs[id] = { wc, head, tool, car, parts: [vfPart], pocket, strips, holes, o: new THREE.Vector3(0.3, 0.4, 0), x0,
        chips: emitter(0xe2c27a, 80, 0.018, 0.9, id), cool: emitter(0x5fb8ff, 90, 0.017, 0.75, id), air: emitter(0xffffff, 60, 0.03, 0.5, id) };
    });
    vf('vf1', 10200, 12600); vf('vf2', 13600, 16000);

    // WSH-01: tunnel washer
    machine('wsh', () => {
      box(17460, 20140, 3860, 5140, 0, 0.12, mat.dark);
      shell(17400, 20200, 3800, 5200, 0.12, 1.55, [17600, 20000, 0.3, 1.35], mat.green, 0.85); // 앞 창 아래 끝 0.62 → 0.3: 안을 지나는 바스켓이 보이게 (개선안 5, 2026-10-20)
      box(17600, 20000, 4000, 5100, 1.55, 1.82, mat.greenD);
      box(17700, 18300, 3740, 3800, 1.4, 1.52, mat.dark); box(17740, 18260, 3735, 3740, 1.42, 1.5, mat.screen);
      box(17150, 20450, 4150, 4850, 0.5, 0.55, mat.dark);
      [17200, 20400].forEach(X => [4200, 4800].forEach(Y => box(X - 30, X + 30, Y - 30, Y + 30, 0, 0.5, mat.steel)));
      [18690, 19300].forEach(X => box(X - 10, X + 10, 4100, 4900, 0.95, 1.5, mat.inner));
      [17950, 18400, 19000].forEach(X => { cylY(X, 4100, 4900, 1.28, 0.022, mat.steel); [4250, 4500, 4750].forEach(Y => cyl(X, Y, 1.22, 1.27, 0.015, mat.dark)); });
      box(19580, 19620, 4100, 4900, 1.0, 1.25, mat.dark);
      cyl(17800, 5000, 1.55, 2.05, 0.12, mat.steel);
      box(19400, 20000, 4950, 5150, 1.55, 1.75, mat.blue);
      const baskets = [0, 1, 2].map(() => {
        const g = pivot(17200, 4500, 0.55);
        mesh(new THREE.BoxGeometry(0.36, 0.04, 0.5), mat.yellow, g, 0, 0.02, 0);
        [[-0.17, 0], [0.17, 0]].forEach(([x]) => mesh(new THREE.BoxGeometry(0.02, 0.18, 0.5), mat.yellow, g, x, 0.1, 0));
        [-0.24, 0.24].forEach(z => mesh(new THREE.BoxGeometry(0.36, 0.18, 0.02), mat.yellow, g, 0, 0.1, z));
        [[0, -0.15], [0, -0.05], [0, 0.05], [0, 0.15]].forEach(([x, z]) => mesh(new THREE.BoxGeometry(0.15, 0.012, 0.055), mat.part, g, x, 0.05, z)); // BRK-A100
        return g;
      });
      tower(20050, 5050, 1.82);
      rigs.wsh = { baskets, water: emitter(0x6fbef5, 260, 0.018, 0.75, 'wsh'), mist: emitter(0xffffff, 80, 0.03, 0.45, 'wsh') };
    });

    // CMM-01
    machine('cmm', () => {
      const cx0 = 21400, cx1 = 23600, cy0 = 3800, cy1 = 5400, ym = 4700;
      box(cx0 + 150, cx1 - 150, cy0 + 150, cy1 - 150, 0, 0.55, mat.dark);
      box(cx0, cx1, cy0, cy1, 0.55, 0.9, mat.granite);
      box(cx0 + 20, cx0 + 120, cy0, cy1, 0.9, 0.96, mat.steel);
      const bridge = grp();
      box(cx0 + 30, cx0 + 190, ym - 140, ym + 140, 0.96, 2.3, mat.white, bridge);
      box(cx1 - 190, cx1 - 30, ym - 140, ym + 140, 0.9, 2.3, mat.white, bridge);
      box(cx0 + 30, cx1 - 30, ym - 170, ym + 170, 2.3, 2.5, mat.white, bridge);
      const carr = grp(bridge);
      box(22370, 22630, ym - 240, ym + 240, 2.2, 2.62, mat.grey, carr);
      const ram = grp(carr);
      box(22450, 22550, ym - 50, ym + 50, 1.2, 2.62, mat.steel, ram);
      box(22465, 22535, ym - 35, ym + 35, 1.14, 1.2, mat.dark, ram);
      cyl(22500, ym, 1.09, 1.14, 0.006, mat.steel, ram);
      const probeM = new THREE.MeshStandardMaterial({ color: 0xff3b30, emissive: 0xff3b30, emissiveIntensity: 0.8 });
      const probe = shade(new THREE.Mesh(new THREE.SphereGeometry(0.014, 16, 12), probeM));
      probe.position.copy(P(22500, ym, 1.085)); ram.add(probe);
      const cmmP1 = box(22425, 22575, 4372, 4428, 0.92, 0.932, mat.part); // BRK-A100 150 × 55 × 12
      const cmmP2 = cyl(22500, 4400, 0.932, 0.9335, 0.0225, mat.inner); // Ø45 H7 부싱 압입 구멍
      box(22300, 22700, 4200, 4600, 0.9, 0.92, mat.dark);
      box(cx1 + 60, cx1 + 380, 3700, 4100, 0, 1.1, mat.dark); box(cx1 + 90, cx1 + 350, 3690, 3700, 0.75, 1.02, mat.screen);
      tower(cx1 - 120, cy1 - 120, 0.9);
      rigs.cmm = { parts: [cmmP1, cmmP2], bridge, carr, ram, probeM, ym, tip: new THREE.Vector3(22.5, 1.6, -5.0) };
    });

    try {
      const pallet = (key, X, Y, partM, mark) => {
        if (this.LY) flat2(X - 600, X + 600, 2000, 2800, mark); else flat2(X - 760, X + 760, 1440, 2920, mark); // 데이터: 재공 자리 1,200 × 800
        const rg = new THREE.Mesh(new THREE.RingGeometry(0.74, 0.84, 56), new THREE.MeshBasicMaterial({ color: 0x3cc8e6, transparent: true, opacity: 0.3, depthWrite: false }));
        rg.rotation.x = -Math.PI / 2; rg.position.copy(P(X, Y, 0.01)); scene.add(rg); rings[key] = rg;
        rg.visible = false;
        const arr = [];
        for (let L = 0; L < 2; L++) for (let rr = 0; rr < 3; rr++) for (let c = 0; c < 4; c++) arr.push(cyl(X - 330 + c * 220, Y - 250 + rr * 250, 0.12 + L * 0.17, 0.27 + L * 0.17, 0.085, partM));
        pallets[key] = arr;
      };
      const flat2 = (x0, x1, y0, y1, color) => {
        const p = new THREE.Mesh(new THREE.PlaneGeometry((x1 - x0) / 1000, (y1 - y0) / 1000), new THREE.MeshStandardMaterial({ color, transparent: true, opacity: 0.55, depthWrite: false }));
        p.rotation.x = -Math.PI / 2; p.position.set((x0 + x1) / 2000, 0.006, -(y0 + y1) / 2000); scene.add(p);
      };
      const WPX = this.LY ? { w1: this.LY.wip.w1 * 1000, w2: this.LY.wip.w2 * 1000, w3: this.LY.wip.w3 * 1000, w4: this.LY.wip.w4 * 1000, fg: this.LY.fg * 1000 } : { w1: 6750, w2: 11900, w3: 14300, w4: 20800, fg: 24000 };
      pallet('w1', WPX.w1, 2400, mat.part, 0xf2a052); pallet('w2', WPX.w2, 2400, mat.part, 0xf2a052);
      pallet('w3', WPX.w3, 2400, mat.part, 0xf2a052); pallet('w4', WPX.w4, 2400, mat.part, 0xf2a052);
      pallet('fg', WPX.fg, 2400, M(0xd5e3ee, { metalness: 0.75, roughness: 0.2 }), 0x8fd3a8);
      // 병목 공정의 설비 (사용자 선택 2026-10-19): 위에서 비추던 주황 조명은 빼고, 천장 표지판에 연보라 달팽이 배지로 조용히 표시 — 주의(주황 판)가 늘 먼저 보이게
      this.bnIds = { 'OP-10': ['saw'], 'OP-20': ['mil'], 'OP-30': ['vf1', 'vf2'], 'OP-40': ['wsh'], 'OP-50': ['cmm'] };
      // 재공 수를 바닥에 칠한 글자로 (사용자 선택 2026-10-19) — 떠 있는 재공 판이 설비를 가려서. 각도에 따라 읽기 어려운 건 감수
      if (this.props.dataMode) this.floorWip = [['wip-1', 'w1', 'WIP-1', 'WIP-10-20'], ['wip-2', 'w2', 'WIP-2', 'WIP-20-30'], ['wip-3', 'w3', 'WIP-3', 'WIP-30-40'], ['wip-4', 'w4', 'WIP-4', 'WIP-40-50'], ['fg-01', 'fg', 'FG-01', null]].map(([id, key, name, code]) => {
        const cv = document.createElement('canvas'); cv.width = 512; cv.height = 128;
        const tex = new THREE.CanvasTexture(cv); tex.anisotropy = 8;
        const m = new THREE.Mesh(new THREE.PlaneGeometry(3.6, 0.9), new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, fog: false, toneMapped: false }));
        const a = this.anch[id]; m.rotation.x = -Math.PI / 2; m.position.set(a[0] / 1000 + 0.5, 0.09, -1.35); m.renderOrder = 5; // 상자 컨베이어(Y 1,765~) 앞 통로 바닥 scene.add(m);
        return { key, name, code, cv, tex, last: '', m };
      });
      // SOAK-01 보라색 온도 맞춤 선반은 그리지 않음 (사용자 요청 2026-10-19)
      // 천장 표지판 (사용자 선택 2026-10-19, 시안 A를 3D로): 앱 화면에서는 설비 이름표를 장면 안 실제 판으로 천장 레일에 매단다.
      // 화면 위 글자처럼 매 프레임 자리를 다시 잡지 않으니 카메라를 움직여도 흔들리거나 비켜 내려오지 않는다. 글자·색은 아래 루프에서 상태가 바뀔 때만 다시 그림
      if (this.props.embedded) {
        const ids = ['inf', 'saw', 'mil', 'vf1', 'vf2', 'wsh', 'cmm'].filter(id => this.anch['tag-' + id] && this.MACH[id]);
        const xs = ids.map(id => this.anch['tag-' + id][0] / 1000).sort((p, q) => p - q);
        const gap = xs.length > 1 ? Math.min(...xs.slice(1).map((x, i) => x - xs[i])) : 2.2;
        const SW = Math.min(3.0, Math.max(1.2, gap - 0.25)), SH = SW * 0.42; // 판끼리 닿지 않는 만큼 크게 (가장 좁은 설비 간격 기준)
        const g = new THREE.Group(); scene.add(g);
        const frameM = new THREE.MeshStandardMaterial({ color: 0x1c232b, roughness: 0.6 }), wireM = new THREE.LineBasicMaterial({ color: 0x4b5764 });
        let rx0 = Infinity, rx1 = -Infinity, ry = 0, rz = 0;
        const sign = (id, a, SW, SH) => {
          const x = a[0] / 1000, y = a[2] + SH / 2, z = -a[1] / 1000;
          const cv = document.createElement('canvas'); cv.width = 680; cv.height = 286;
          const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
          const face = new THREE.Mesh(new THREE.PlaneGeometry(SW, SH), new THREE.MeshBasicMaterial({ map: tex, transparent: true, toneMapped: false, fog: false })); // 안개에 묻히지 않게 (글자·상태색 그대로)
          face.position.set(x, y, z + 0.03);
          const back = new THREE.Mesh(new THREE.BoxGeometry(SW * 0.98, SH * 0.96, 0.05), frameM); back.position.set(x, y, z);
          if (id !== 'inf' && id !== 'rack') { face.userData.mid = id; back.userData.mid = id; pickables.push(face, back); } // 판을 눌러도 그 설비 선택 (투입 대·봉재 랙은 선택 없음)
          const top = y + SH / 2, ceil = top + 0.5;
          const V3 = (vx, vy) => new THREE.Vector3(vx, vy, z);
          g.add(face, back, new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints([V3(x - SW * 0.36, top), V3(x - SW * 0.36, ceil), V3(x + SW * 0.36, top), V3(x + SW * 0.36, ceil)]), wireM));
          // 병목 배지: 판 아래 오른쪽 모서리에 반쯤 걸친 동그란 달팽이 판 (사용자 요청 2026-10-19). 한 번 그려 두고 병목일 때만 보임
          const bd = SH * 0.66, bcv = document.createElement('canvas'); bcv.width = bcv.height = 192;
          { const c = bcv.getContext('2d'); c.beginPath(); c.arc(96, 96, 88, 0, Math.PI * 2); c.fillStyle = '#1c232b'; c.fill(); c.lineWidth = 10; c.strokeStyle = '#b9a8ff'; c.stroke();
            c.translate(36, 34); c.scale(5, 5); c.strokeStyle = '#b9a8ff'; c.lineCap = 'round'; c.lineJoin = 'round'; c.lineWidth = 2.2;
            ['M3 18h15.5a2.5 2.5 0 0 0 2.5-2.5V13', 'M16.5 12a5.5 5.5 0 1 1-11 0a5.5 5.5 0 1 1 11 0', 'M11 12a2.2 2.2 0 1 1 2.2-2.2', 'M19.5 13 18.5 8.5', 'M21 13l1.4-4.2'].forEach(d => c.stroke(new Path2D(d))); }
          const btex = new THREE.CanvasTexture(bcv); btex.colorSpace = THREE.SRGBColorSpace; btex.anisotropy = 8;
          const badge = new THREE.Mesh(new THREE.PlaneGeometry(bd, bd), new THREE.MeshBasicMaterial({ map: btex, transparent: true, toneMapped: false, fog: false }));
          badge.position.set(x + SW / 2 - bd * 0.2, y - SH / 2 + bd * 0.12, z + 0.06); badge.renderOrder = 6; badge.visible = false; g.add(badge);
          if (id !== 'rack') { rx0 = Math.min(rx0, x - SW * 0.7); rx1 = Math.max(rx1, x + SW * 0.7); ry = ceil; rz = z; } // 봉재 랙은 설비 줄과 깊이가 달라 레일 밖에 따로 매달림
          return { id, cv, tex, badge, last: '' };
        };
        this.ceilSigns = ids.map(id => sign(id, this.anch['tag-' + id], SW, SH));
        if (this.anch['tag-rack']) this.ceilSigns.push(sign('rack', this.anch['tag-rack'], 1.9, 1.9 * 0.42));
        if (ids.length) { const rail = new THREE.Mesh(new THREE.BoxGeometry(rx1 - rx0, 0.08, 0.1), frameM); rail.position.set((rx0 + rx1) / 2, ry + 0.04, rz); g.add(rail); }
        this.ceilG = g;
      }

      const red = new THREE.MeshStandardMaterial({ color: 0x29c6e6, emissive: 0x16b4d6, emissiveIntensity: 0.45, roughness: 0.35 });
      const halo = new THREE.MeshBasicMaterial({ color: 0x5fdcf2, transparent: true, opacity: 0.16, depthWrite: false }); env.halo = halo;
      const dotM = new THREE.MeshBasicMaterial({ color: 0xeafcff });
      const greyM = new THREE.MeshStandardMaterial({ color: 0xa3abb3, roughness: 0.5 });
      const up = new THREE.Vector3(0, 1, 0);
      const mk = (a, b, dashed, src, dst) => {
        const mX = (X) => (this.LY ? this.LY.mapX(X) : X); // 데이터적용본: 흐름선도 데이터 배치를 따라
        const A = P(mX(a[0]), a[1], a[2]), B = P(mX(b[0]), b[1], b[2]), d = A.distanceTo(B);
        const mid = A.clone().add(B).multiplyScalar(0.5); mid.y = Math.max(A.y, B.y) + 0.35 + d * 0.06;
        const curve = new THREE.QuadraticBezierCurve3(A, mid, B);
        let tube = null, haloM = null, lineRef = null;
        if (dashed) {
          const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(40)), new THREE.LineDashedMaterial({ color: 0x29c6e6, dashSize: 0.12, gapSize: 0.08 }));
          l.computeLineDistances(); flowG.add(l); lineRef = l;
        } else {
          tube = shade(new THREE.Mesh(new THREE.TubeGeometry(curve, 48, 0.018, 8), red.clone())); flowG.add(tube);
          haloM = new THREE.Mesh(new THREE.TubeGeometry(curve, 48, 0.05, 8), halo); flowG.add(haloM);
        }
        const tan = curve.getTangentAt(1);
        const cone = shade(new THREE.Mesh(new THREE.ConeGeometry(dashed ? 0.05 : 0.065, 0.18, 16), red));
        cone.quaternion.setFromUnitVectors(up, tan); cone.position.copy(B).addScaledVector(tan, -0.11); flowG.add(cone);
        const parts = [];
        if (!dashed) for (let i = 0; i < 2; i++) { const s = new THREE.Mesh(new THREE.SphereGeometry(0.055, 12, 10), dotM); flowG.add(s); parts.push(s); }
        flows.push({ curve, len: curve.getLength(), parts, src, dst, tube, halo: haloM, line: lineRef, tubeN: tube ? tube.geometry.index.count : 0, reveal: 1, cone, coneOn: red, coneOff: greyM, act: true });
      };
      const W = (X) => [X, 2400, 0.42];
      mk([3900, 4200, 0.95], [4800, 4000, 0.95], false, 'inf', 'saw');
      mk([6000, 3800, 0.85], W(6750), false, 'saw');
      mk(W(6750), [7600, 3800, 0.9], false, null, 'mil');
      mk([8500, 3800, 0.9], W(11900), false, 'mil');
      mk(W(11900), [11100, 3800, 0.9], false, null, 'vf1');
      mk(W(11900), [14200, 3800, 0.9], false, null, 'vf2');
      mk([12300, 3800, 0.9], W(14300), false, 'vf1');
      mk([15300, 3800, 0.9], W(14300), false, 'vf2');
      mk(W(14300), [17700, 3800, 0.9], false, null, 'wsh');
      mk([19900, 3800, 0.65], W(20800), false, 'wsh');
      mk(W(20800), [22100, 3800, 0.95], false, null, 'cmm');
      mk([23300, 3800, 0.95], W(24000), false, 'cmm');
      
    } catch (e) { console.error('[factory] flows', e); }
    const convG = new THREE.Group(); scene.add(convG);
    const convRoutes = [];
    try {
      const CM = { frame: M(0x56626e, { metalness: 0.5, roughness: 0.4 }), rail: M(0xdfe4e8, { metalness: 0.7, roughness: 0.3 }), roller: M(0xc3cad0, { metalness: 0.85, roughness: 0.22 }), leg: M(0x39424b, { roughness: 0.6 }), tray: M(0x2d5e8c, { roughness: 0.5 }), motor: M(0x1f6fb2, { roughness: 0.4, metalness: 0.2 }), bore: M(0x262c33, { roughness: 0.6 }) };
      const TOP = 0.5, rl = [];
      const seg = (x0, x1, y0, y1, ax) => {
        box(x0, x1, y0, y1, TOP - 0.11, TOP - 0.035, CM.frame, convG);
        if (ax) { box(x0, x1, y0 - 22, y0, TOP - 0.035, TOP + 0.012, CM.rail, convG); box(x0, x1, y1, y1 + 22, TOP - 0.035, TOP + 0.012, CM.rail, convG); }
        else { box(x0 - 22, x0, y0, y1, TOP - 0.035, TOP + 0.012, CM.rail, convG); box(x1, x1 + 22, y0, y1, TOP - 0.035, TOP + 0.012, CM.rail, convG); }
        const L = ax ? x1 - x0 : y1 - y0, Wd = ax ? y1 - y0 : x1 - x0;
        for (let s = 55; s < L - 25; s += 105) rl.push([ax ? x0 + s : (x0 + x1) / 2, ax ? (y0 + y1) / 2 : y0 + s, ax, Wd]);
        for (let s = 150; s < L; s += 1500) {
          if (ax) { box(x0 + s - 25, x0 + s + 25, y0 + 15, y0 + 65, 0, TOP - 0.11, CM.leg, convG); box(x0 + s - 25, x0 + s + 25, y1 - 65, y1 - 15, 0, TOP - 0.11, CM.leg, convG); }
          else { box(x0 + 15, x0 + 65, y0 + s - 25, y0 + s + 25, 0, TOP - 0.11, CM.leg, convG); box(x1 - 65, x1 - 15, y0 + s - 25, y0 + s + 25, 0, TOP - 0.11, CM.leg, convG); }
        }
      };
      // 데이터적용본: 재공 자리·상자 자리·컨베이어를 데이터 배치(layout_object.csv)에 짓는다. 설비 투입·배출 위치는 설비를 옮긴 자리(place)를 따른다
      const D3 = this.LY ? (() => {
        const w = this.LY.wip, fg = this.LY.fg, wi = this.placeX('wsh', 17.9), wo = this.placeX('wsh', 19.7), sex = w.w3 - 0.5, fex = fg - 0.5;
        return { w, fg, wi, wo, sex, fex, l1: [this.placeX('saw', 6.0) - 0.25, Math.max(this.placeX('vf2', 15.3), sex) + 0.3], l2: [wo + 0.75, fex + 0.3],
          wz: this.placeZ('wsh', -4.45), dyw: Math.round(-this.placeZ('wsh', -3.7) * 1000 - 3700), aso: fg + 2.2 - 26.2 };
      })() : null;
      // ㄷ자 한 줄 (사용자 선택 2026-10-20): 일자 롤러는 세척기 왼쪽 꺾임(WIP-3 바스켓 자리) 앞에서 끝나고, 오른쪽 꺾임(꺼내는 자리) 뒤에서 다시 시작
      const WB3 = this.MACH.wsh.bd || this.MACH.wsh.b, XA3 = WB3[0] / 1000 - 0.55, XB3 = WB3[1] / 1000 + 0.8;
      // 게이트 컨베이어 (사용자 요청 2026-10-20): 설비 앞 0.9 m 한 토막은 따로 지어, 정비 로봇(이브)이 지날 때 오른쪽 끝 경첩으로 들려 올라감
      const gates = {}; this.gates = gates;
      const rg0 = new THREE.CylinderGeometry(0.026, 0.026, 1, 12);
      const segG = (x0, x1, y0, y1) => {
        const gs = ['saw', 'mil', 'vf1', 'vf2', 'cmm'].map(id => { const bd = this.MACH[id].bd || this.MACH[id].b; return [id, Math.round((bd[0] + bd[1]) / 2)]; }).filter(q0 => q0[1] > x0 && q0[1] < x1).sort((p0, q0) => p0[1] - q0[1]);
        let c0 = x0;
        gs.forEach(([id, gx]) => {
          const ga = Math.max(c0, Math.min(gx - 450, x1 - 900)), gb = Math.min(x1, ga + 900), zc = -(y0 + y1) / 2000; if (gb - ga < 400) return;
          if (ga - c0 > 50) seg(c0, ga, y0, y1, true);
          const piv = new THREE.Group(), inner = new THREE.Group(); piv.position.set(gb / 1000, TOP - 0.07, zc); inner.position.set(-gb / 1000, -(TOP - 0.07), -zc); piv.add(inner); convG.add(piv);
          box(ga + 8, gb - 8, y0, y1, TOP - 0.11, TOP - 0.035, CM.frame, inner); box(ga + 8, gb - 8, y0 - 22, y0, TOP - 0.035, TOP + 0.012, CM.rail, inner); box(ga + 8, gb - 8, y1, y1 + 22, TOP - 0.035, TOP + 0.012, CM.rail, inner);
          for (let s = 55; s < gb - ga - 25; s += 105) { const r0 = new THREE.Mesh(rg0, CM.roller); r0.rotation.x = Math.PI / 2; r0.scale.y = (y1 - y0) / 1000 - 0.03; r0.position.set((ga + s) / 1000, TOP - 0.01, zc); r0.castShadow = true; inner.add(r0); }
          box(ga + 15, ga + 65, y0 + 15, y1 - 15, 0, TOP - 0.11, CM.leg, convG); // 들리는 쪽 끝 받침 기둥 (바닥에 남음)
          gates[id] = { piv, a: 0, x: (ga + gb) / 2000 }; c0 = gb;
        });
        if (x1 - c0 > 50) seg(c0, x1, y0, y1, true);
      };
      if (D3) { D3.l1[1] = XA3 - 0.72; D3.l2[0] = XB3 + 0.72; segG(Math.round(D3.l1[0] * 1000), Math.round(D3.l1[1] * 1000), 2950, 3350); segG(Math.round(D3.l2[0] * 1000), Math.round(D3.l2[1] * 1000), 2950, 3350); }
      else { segG(5750, Math.round((XA3 - 0.72) * 1000), 2950, 3350); segG(Math.round((XB3 + 0.72) * 1000), 24350, 2950, 3350); }
      { const hz = new THREE.MeshBasicMaterial({ map: hazTex, transparent: true }); const hzT = hazTex.clone(); hzT.needsUpdate = true; hzT.repeat.set(16, 1); hz.map = hzT;
        const ends = D3 ? [[D3.l1[1] * 1000 + 100, D3.l1[1] * 1000 + 160], [D3.l2[0] * 1000 - 160, D3.l2[0] * 1000 - 100]] : [[15700, 15760], [20290, 20350]];
        ends.forEach(([a0, a1]) => { const m0 = new THREE.Mesh(new THREE.PlaneGeometry(0.06, 2.4), new THREE.MeshBasicMaterial({ color: 0xf2c230 })); m0.rotation.x = -Math.PI / 2; m0.position.set((a0 + a1) / 2000, 0.012, -2.5); convG.add(m0); });
        const cw = new THREE.Mesh(new THREE.PlaneGeometry(D3 ? D3.wo - D3.wi + 2.7 : 4.5, 0.12), new THREE.MeshBasicMaterial({ map: hzT })); cw.rotation.x = -Math.PI / 2; cw.position.set(D3 ? (D3.wi + D3.wo) / 2 : 18.0, 0.012, D3 ? -3.68 - D3.dyw / 1000 : -3.68); convG.add(cw); }
      const FR = { saw: 3800, mil: 3800, vf1: 3650, vf2: 3650, wsh: 3700, cmm: 3700 };
      const rg = new THREE.CylinderGeometry(0.026, 0.026, 1, 12);
      const im = new THREE.InstancedMesh(rg, CM.roller, rl.length); im.castShadow = true; im.receiveShadow = true;
      const q = new THREE.Quaternion(), e = new THREE.Euler(), sc = new THREE.Vector3(), ps = new THREE.Vector3(), m4 = new THREE.Matrix4();
      rl.forEach(([X, Y, ax, Wd], i) => { e.set(ax ? Math.PI / 2 : 0, 0, ax ? 0 : Math.PI / 2); q.setFromEuler(e); sc.set(1, Wd / 1000 - 0.03, 1); ps.set(X / 1000, TOP - 0.01, -Y / 1000); m4.compose(ps, q, sc); im.setMatrixAt(i, m4); });
      convG.add(im);
      const V = (x, y, z) => new THREE.Vector3(x, y, z);
      const BY = TOP + 0.012 + 0.075, LZ = -3.15;
      // 데이터적용본: 재공 부품 = BRK-A100 토막·브래킷 (152 × 57 × 19 mm 소재 → 150 × 55 × 12 mm). 바닥 높이는 원본 원기둥과 같게
      const itemGeo = new THREE.BoxGeometry(0.152, 0.019, 0.057); itemGeo.translate(0, -0.075 + 0.0095, 0);
      const pool = [], jobs = [];
      const GM = { y: M(0xe2b23c, { roughness: 0.45, metalness: 0.25 }), s: M(0xcfd5da, { metalness: 0.85, roughness: 0.25 }), d: M(0x2a3138, { roughness: 0.6 }) };
      const GTOP = 1.42;
      const mkGrip = () => {
        const g0 = new THREE.Group(); g0.visible = false; convG.add(g0);
        const bridge = mesh(new THREE.BoxGeometry(1.5, 0.07, 0.09), GM.y, g0); bridge.name = 'bridge';
        const car = mesh(new THREE.BoxGeometry(0.16, 0.1, 0.16), GM.d, g0);
        const rod = mesh(new THREE.CylinderGeometry(0.014, 0.014, 1, 12), GM.s, g0);
        const head = mesh(new THREE.BoxGeometry(0.24, 0.04, 0.1), GM.d, g0);
        const f1 = mesh(new THREE.BoxGeometry(0.022, 0.09, 0.07), GM.s, g0), f2 = mesh(new THREE.BoxGeometry(0.022, 0.09, 0.07), GM.s, g0);
        g0.userData = { bridge, car, rod, head, f1, f2 }; return g0;
      };
      const getItem = (m) => { let o = pool.pop(); if (!o) { o = new THREE.Mesh(itemGeo, m); o.castShadow = true; convG.add(o); o.userData.grip = mkGrip(); } o.material = m; o.visible = true; return o; };
      const release = (o) => { o.visible = false; o.userData.grip.visible = false; pool.push(o); };
      const gripAt = (o, air) => {
        const G = o.userData.grip; G.visible = air; if (!air) return;
        const p = o.position, U = G.userData, wipSide = p.z > -3.0;
        const top = wipSide ? GTOP : Math.min(p.y + 0.9, 2.0), py = p.y + 0.075;
        U.bridge.visible = wipSide;
        if (wipSide) { const wx = Object.values(WX).reduce((a0, b0) => Math.abs(b0 - p.x) < Math.abs(a0 - p.x) ? b0 : a0); U.bridge.position.set(wx, top, p.z); }
        U.car.position.set(p.x, top - 0.06, p.z);
        const len = Math.max(0.02, top - 0.1 - (py + 0.04)); U.rod.scale.y = len; U.rod.position.set(p.x, py + 0.04 + len / 2, p.z);
        U.head.position.set(p.x, py + 0.02, p.z);
        U.f1.position.set(p.x - 0.098, py - 0.035, p.z); U.f2.position.set(p.x + 0.098, py - 0.035, p.z);
      };
      const WX = D3 ? { w1: D3.w.w1, w2: D3.w.w2, w3: D3.w.w3, w4: D3.w.w4, fg: D3.fg } : { w1: 6.75, w2: 11.9, w3: 14.3, w4: 20.8, fg: 24.0 };
      const MC = {
        saw: { xo: 6.0, fr: 3.8, load: V(5.5, 0.92, -4.35), src: null, dst: 'w1' },
        mil: { xi: 7.6, xo: 8.5, fr: 3.8, load: V(7.8, 1.09, -4.35), src: 'w1', dst: 'w2' },
        vf1: { xi: 11.1, xo: 12.3, fr: 3.65, load: V(11.18, 1.13, -4.35), src: 'w2', dst: 'w3' },
        vf2: { xi: 14.2, xo: 15.3, fr: 3.65, load: V(14.58, 1.13, -4.35), src: 'w2', dst: 'w3' },
        wsh: { xi: 17.7, xo: 19.9, fr: 3.7, load: V(17.75, 0.85, -4.45), unload: V(19.85, 0.85, -4.45), src: 'w3', dst: 'w4' },
        cmm: { xi: 22.1, xo: 23.3, fr: 3.7, load: V(22.5, 1.12, -4.4), src: 'w4', dst: 'fg' },
      };
      // 데이터적용본: 설비 투입·배출 자리 = 설비를 옮긴 자리 (부품이 실제 설비로 들어가게)
      if (D3) Object.keys(MC).forEach(id => { const c = MC[id]; if (c.xi != null) c.xi = this.placeX(id, c.xi); c.xo = this.placeX(id, c.xo); c.fr = -this.placeZ(id, -c.fr); this.placePt(id, c.load); if (c.unload) this.placePt(id, c.unload); });
      const TR0 = D3 ? { w1: D3.w.w1, w2: D3.w.w2 } : { w1: 6.75, w2: 11.9 }, TZ = -2.2, TRAD = 0.45, NP = 12, PIT = Math.PI * 2 / NP;
      const aI = -Math.PI * 2 / 3, aO = -Math.PI / 3, BZE = -2.86;
      const pw = (k, a) => V(TR0[k] + TRAD * Math.cos(a), BY, TZ + TRAD * Math.sin(a));
      const xI = (k) => TR0[k] + TRAD * Math.cos(aI), xO = (k) => TR0[k] + TRAD * Math.cos(aO);
      const CAP = {}; Object.keys(TR0).forEach(k => { CAP[k] = NP - 1; });
      const TM = { plate: M(0x8f9aa5, { metalness: 0.6, roughness: 0.3 }), rim: M(0xf2c230, { roughness: 0.5 }), nest: M(0x2a3138, { roughness: 0.6 }), hub: M(0x1f6fb2, { roughness: 0.4, metalness: 0.2 }), base: M(0x39424b, { roughness: 0.6 }) };
      const TT = {};
      Object.keys(TR0).forEach(k => {
        const cx = TR0[k], ty = BY - 0.075;
        mesh(new THREE.CylinderGeometry(0.32, 0.38, ty - 0.05, 40), TM.base, convG, cx, (ty - 0.05) / 2, TZ);
        const g = new THREE.Group(); g.position.set(cx, 0, TZ); convG.add(g);
        mesh(new THREE.CylinderGeometry(0.62, 0.62, 0.045, 72), TM.plate, g, 0, ty - 0.0225, 0);
        mesh(new THREE.CylinderGeometry(0.628, 0.628, 0.016, 72), TM.rim, g, 0, ty - 0.03, 0);
        for (let p = 0; p < NP; p++) { const a = p * PIT; mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.006, 28), TM.nest, g, TRAD * Math.cos(a), ty + 0.003, TRAD * Math.sin(a)); }
        mesh(new THREE.CylinderGeometry(0.13, 0.13, 0.1, 32), TM.hub, g, 0, ty + 0.05, 0);
        mesh(new THREE.BoxGeometry(0.2, 0.015, 0.03), TM.rim, g, 0, ty + 0.105, 0);
        const sxI = Math.round(xI(k) * 1000); seg(sxI - 150, sxI + 150, 2830, 2950, false);
        if (k !== 'fg') { const sxO = Math.round(xO(k) * 1000); seg(sxO - 150, sxO + 150, 2830, 2950, false); }
        TT[k] = { g, phi: 0, cur: null, ops: [], pockets: Array(NP).fill(null), outPending: false };
      });
      const md = (x) => ((x % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
      // ---- batch logistics: pallet boxes + forklift + batch washer ----
      const WGL = (op) => new THREE.MeshStandardMaterial({ color: 0xdfe8ee, metalness: 0.1, roughness: 0.05, transparent: true, opacity: op, depthWrite: false });
      const PMW = { hood: WGL(0.22), hole: WGL(0.05), shut: WGL(0.18) }; // 세척기 앞 = 유리 (2026-10-19)
      const EZA = -1.83, EZB = -2.58;
      const SB = {
        S: { x: 14.3, z: -2.35, ez: EZA, box: null, res: false, name: 'S' }, E1: { x: 16.0, z: -2.35, ez: EZA, box: null, res: false, name: 'E1' },
        WI: { x: 17.9, z: -3.1, ez: EZB, box: null, res: false, name: 'WI' }, WO: { x: 19.7, z: -3.1, ez: EZB, box: null, res: false, name: 'WO' },
        E2: { x: 20.9, z: -2.35, ez: EZA, box: null, res: false, name: 'E2' }, WH: { x: 26.2, z: -2.35, ez: EZA, box: null, res: false, name: 'WH' }, ER: { x: 33.0, z: -2.35, ez: EZA, box: null, res: false, name: 'ER' },
        FG: { x: 24.0, z: -2.35, ez: EZA, box: null, res: false, name: 'FG' },
      };
      // 데이터적용본: WIP-3 상자 = OP-30→40 재공 자리, 세척 투입·배출 = 세척기 앞, FG = 완성품 자리, 자동창고는 FG 동쪽으로
      if (D3) { SB.S.x = D3.w.w3; SB.E1.x = D3.w.w3 + 1.7; SB.WI.x = D3.wi; SB.WO.x = D3.wo; SB.E2.x = Math.max(D3.wo + 1.3, D3.w.w4); SB.FG.x = D3.fg; SB.WH.x = D3.fg + 2.2; SB.ER.x = D3.fg + 9.0; }
      const XIN = SB.WI.x, XOUT = SB.WO.x; // 세척기 안 들어가는·나오는 자리 (원래 앞자리 x)
      { const wb = this.MACH.wsh.bd || this.MACH.wsh.b; SB.WI.x = wb[0] / 1000 - 0.55; SB.WO.x = wb[1] / 1000 + 0.8; SB.WI.z = SB.WO.z = SB.S.z; SB.E2.x = Math.max(SB.E2.x, SB.WO.x + 1.55); }
      // ㄷ자 한 줄: WIP-3 바스켓(S)이 곧 세척 투입 자리(WI) — 일자 줄 끝 꺾임. 꺼내는 자리(WO) = 오른쪽 꺾임. 둘 사이 앞쪽 줄 = 빈 바스켓 복귀(E1에서 대기). 앞쪽 트레이 벨트는 없앰
      SB.S.x = SB.WI.x; SB.S.z = SB.WO.z = LZ; SB.WI = SB.S;
      // 바스켓 4개 (사용자 선택 2026-10-20 개선안 1): 복귀 줄에 빈 바스켓 대기 두 곳 — 세 등분 자리 (세척기 3,000이면 간격 1.45 > 바스켓 1.34)
      SB.E1.x = SB.S.x + (SB.WO.x - SB.S.x) / 3; SB.E2.x = SB.S.x + (SB.WO.x - SB.S.x) * 2 / 3; SB.E1.z = SB.E2.z = LZ;
      const BM = { wall: M(0xaeb6bf, { metalness: 0.7, roughness: 0.35 }), rib: M(0x7d8792, { metalness: 0.7, roughness: 0.4 }), stand: M(0x56626e, { metalness: 0.5, roughness: 0.4 }), ship: new THREE.MeshBasicMaterial({ color: 0x8fd3a8 }) };
      const BOXY = BY - 0.075, BCAP = 30, SEX = D3 ? D3.sex : 13.8, FEX = D3 ? D3.fex : 23.5, FRZ = -2.75, GAPZ = -2.92;
      // 칸 간격 = 부품(0.152 × 0.057)에 맞춤: 가로 0.18 · 세로 0.1 (전에는 0.2 × 0.2라 바스켓이 너무 컸음, 사용자 요청 2026-10-20)
      const slotL = (n) => { const rr = 4 - Math.floor(n / 6), cc = 5 - (n % 6); return V(-0.45 + cc * 0.18, 0.075, -0.2 + rr * 0.1); };
      const takeOrder = []; [2, 1, 3, 0, 4].forEach(rr => { for (let cc = 5; cc >= 0; cc--) takeOrder.push((4 - rr) * 6 + (5 - cc)); });
      const boxes = [];
      const mkBox = () => {
        const g = new THREE.Group(); convG.add(g);
        // 바스켓 1.16 × 0.58 (6 × 5칸, 2026-10-20 줄임 — 전 1.34 × 1.14)
        mesh(new THREE.BoxGeometry(1.16, 0.02, 0.58), mat.wood, g, 0, -0.03, 0);
        [-0.47, 0, 0.47].forEach(x => mesh(new THREE.BoxGeometry(0.1, 0.1, 0.58), mat.wood, g, x, -0.09, 0));
        // 사용자 요청 2026-10-16: 파란 운반 상자 → 낮은 철제 트레이 (테두리 낮게, 부품 꽂이 칸 — 안의 부품이 잘 보임)
        mesh(new THREE.BoxGeometry(1.14, 0.02, 0.56), BM.wall, g, 0, -0.01, 0);
        [0.27, -0.27].forEach(z => mesh(new THREE.BoxGeometry(1.14, 0.07, 0.025), BM.wall, g, 0, 0.035, z));
        [0.56, -0.56].forEach(x => mesh(new THREE.BoxGeometry(0.025, 0.07, 0.56), BM.wall, g, x, 0.035, 0));
        [-0.15, -0.05, 0.05, 0.15].forEach(z => mesh(new THREE.BoxGeometry(1.08, 0.03, 0.012), BM.rib, g, 0, 0.015, z));
        [0.27, -0.27].forEach(z => mesh(new THREE.BoxGeometry(1.18, 0.012, 0.05), BM.rib, g, 0, 0.072, z));
        // LOT 꼬리표 (개선안 3): 바스켓 앞 모서리 위. 한 바스켓 = 한 LOT
        const tc = document.createElement('canvas'); tc.width = 160; tc.height = 48; const tt = new THREE.CanvasTexture(tc); tt.colorSpace = THREE.SRGBColorSpace;
        const tag = new THREE.Sprite(new THREE.SpriteMaterial({ map: tt, transparent: true, depthWrite: false })); tag.scale.set(0.55, 0.165, 1); tag.position.set(0, 0.3, 0.34); tag.visible = false; g.add(tag);
        const b = { g, items: Array(BCAP).fill(null), res: new Set(), at: null, ship: 0, lot: null, closed: false, tag, tc, tt, tagKey: '' }; boxes.push(b); return b;
      };
      const drawTag = (b) => {
        const on = !!b.lot && cnt(b) > 0; b.tag.visible = on; if (!on) return;
        const key = b.lot + '|' + b.closed; if (key === b.tagKey) return; b.tagKey = key;
        const g = b.tc.getContext('2d'); g.clearRect(0, 0, 160, 48); g.fillStyle = b.closed ? '#ffe7a8' : '#ffffff'; g.beginPath(); g.roundRect(2, 2, 156, 44, 8); g.fill();
        g.strokeStyle = '#2a55b8'; g.lineWidth = 3; g.stroke(); g.fillStyle = '#26303a'; g.font = '700 22px "Pretendard Variable", sans-serif'; g.textAlign = 'center';
        g.fillText('LOT ' + String(b.lot).replace(/^LOT-\d+-/, ''), 80, 32); b.tt.needsUpdate = true;
      };
      // 지금 OP-30(VF2)이 깎는 LOT = WIP-3 로 나오는 부품의 LOT (데이터 lot_no)
      const lotOf = (id) => { const E = this.liveT && this.liveT.equipment; return (E && E[this.EQ_OF[id]] && E[this.EQ_OF[id]].lot_no) || null; };
      const cnt = (b) => b ? b.items.reduce((a0, o) => a0 + (o ? 1 : 0), 0) : 0;
      const isEmpty = (b) => b && cnt(b) === 0 && b.res.size === 0;
      const isFull = (b) => b && cnt(b) >= BCAP && b.res.size === 0;
      const placeBox = (b, sp) => { b.g.position.set(sp.x, BOXY, sp.z); b.g.rotation.set(0, 0, 0); sp.box = b; sp.res = false; b.at = sp; if (!cnt(b) && !b.res.size) { b.lot = null; b.closed = false; } };
      const slotW = (sp, n) => { const l = slotL(n); return V(sp.x + l.x, BY, sp.z + l.z); };
      // 2026-10-18: 상자 자리 받침대(빈 레일·다리)를 없앰 — 상자는 컨베이어 벨트 위에 바로 놓임 (빈 레일이 벨트 위에 걸쳐 보였음)
      seg(Math.round(FEX * 1000) - 150, Math.round(FEX * 1000) + 150, 2880, 2950, false);
      // 사용자 요청 2026-10-16: 지게차를 빼고 상자 받침대 사이를 컨베이어로 이음 (덮개·유리 없는 열린 벨트)
      { const BELT = M(0x2a3035, { roughness: 0.85 }), RAIL = M(0xdfe4e8, { metalness: 0.7, roughness: 0.3 });
        const lane0 = (xa, xb, YL) => { box(xa, xb, YL - 320, YL + 320, 0.33, 0.372, BELT, convG); [-345, 345].forEach(d => box(xa, xb, YL + d - 25, YL + d + 25, 0.372, 0.42, RAIL, convG)); // 상자(깊이 580) 밖으로
          for (let x = xa; x < xb; x += 1500) [-290, 290].forEach(d => box(x - 30, x + 30, YL + d - 30, YL + d + 30, 0, 0.33, CM.leg, convG)); };
        lane0(Math.round((SB.S.x - 0.7) * 1000), Math.round((SB.WO.x + 0.7) * 1000), Math.round(-LZ * 1000)); // ㄷ자 앞쪽 = 바스켓 자리 두 곳 + 빈 바스켓 복귀 줄
        lane0(Math.round((SB.FG.x - 0.75) * 1000), Math.round((SB.FG.x + 0.75) * 1000), Math.round(-SB.FG.z * 1000)); } // FG 상자 자리
      // 세척기: 상자가 왼쪽 옆으로 들어가 오른쪽 옆으로 나옴 (사용자 요청 2026-10-19) — 앞자리 → 옆 → 안
      const WB = (this.MACH.wsh.bd || this.MACH.wsh.b), WZIN = D3 ? D3.wz : -4.45;
      const wPathIn = [[SB.WI.x, SB.WI.z], [SB.WI.x, WZIN], [XIN, WZIN]]; // 왼쪽 옆 한 줄로 뒤로 → 안으로
      const wPathOut = [[XOUT, WZIN], [SB.WO.x, WZIN], [SB.WO.x, SB.WO.z]]; // 오른쪽 옆으로 나와 앞으로
      { const BELT2 = M(0x2a3035, { roughness: 0.85 });
        [wPathIn, wPathOut].forEach(P => P.slice(1).forEach((q, i) => { const a = P[i], hw = 0.32;
          const x0 = Math.min(a[0], q[0]) - hw, x1 = Math.max(a[0], q[0]) + hw, z0 = Math.min(a[1], q[1]) - hw, z1 = Math.max(a[1], q[1]) + hw;
          box(Math.round(x0 * 1000), Math.round(x1 * 1000), Math.round(-z1 * 1000), Math.round(-z0 * 1000), 0.33, 0.372, BELT2, convG); })); }
      const along = (P, u) => { // 꺾인 길을 거리 비율 u로 따라감
        const L = P.slice(1).map((q, i) => Math.hypot(q[0] - P[i][0], q[1] - P[i][1])), T = L.reduce((a, c) => a + c, 0); let d = u * T;
        for (let i = 0; i < L.length; i++) { if (d <= L[i] || i === L.length - 1) { const k = L[i] ? Math.min(1, d / L[i]) : 1; return [P[i][0] + (P[i + 1][0] - P[i][0]) * k, P[i][1] + (P[i + 1][1] - P[i][1]) * k, P[i + 1][1] !== P[i][1]]; } d -= L[i]; }
        return [P[P.length - 1][0], P[P.length - 1][1], false]; };
      // washer batch doors
      const DY = D3 ? D3.dyw : 0; // 세척기 앞면 Y (데이터 3,800, 원본 3,700)
      const wDoors = [XIN, XOUT].map(x => {
        const X = Math.round(x * 1000);
        box(X - 720, X + 720, 3640 + DY, 3700 + DY, BOXY + 0.4, BOXY + 0.46, PMW.hood, convG);
        box(X - 720, X - 690, 3640 + DY, 3700 + DY, BOXY - 0.2, BOXY + 0.4, PMW.hood, convG); box(X + 690, X + 720, 3640 + DY, 3700 + DY, BOXY - 0.2, BOXY + 0.4, PMW.hood, convG);
        box(X - 690, X + 690, 3696 + DY, 3702 + DY, BOXY - 0.2, BOXY + 0.4, PMW.hole, convG).castShadow = false;
        const sh = box(X - 688, X + 688, 3655 + DY, 3672 + DY, BOXY - 0.19, BOXY + 0.39, PMW.shut, convG);
        return { sh, y0: sh.position.y, o: 0, want: 0 };
      });
      const FM = { body: M(0xf0b429, { roughness: 0.45, metalness: 0.15 }), dark: M(0x262c33, { roughness: 0.6 }), steel: M(0x9aa5af, { metalness: 0.75, roughness: 0.3 }), tire: M(0x15181c, { roughness: 0.9 }), beacon: new THREE.MeshBasicMaterial({ color: 0xff9a1f }) };
      const AZ = -1.0, AZB = -0.3, HIN = 0.42, HUP = 0.5;
      const FL = (() => {
        const g = new THREE.Group(); convG.add(g);
        mesh(new THREE.BoxGeometry(0.86, 0.5, 1.1), FM.body, g, 0, 0.42, 0.82);
        mesh(new THREE.BoxGeometry(0.9, 0.58, 0.3), FM.dark, g, 0, 0.5, 1.42);
        mesh(new THREE.BoxGeometry(0.42, 0.12, 0.36), FM.dark, g, 0, 0.73, 0.98);
        mesh(new THREE.BoxGeometry(0.42, 0.42, 0.06), FM.dark, g, 0, 0.98, 1.17);
        const sw = new THREE.Mesh(new THREE.TorusGeometry(0.11, 0.015, 8, 28), FM.dark); sw.rotation.x = -1.0; sw.position.set(0, 1.0, 0.55); g.add(sw);
        [[-0.38, 0.35], [0.38, 0.35], [-0.38, 1.15], [0.38, 1.15]].forEach(([x, z]) => mesh(new THREE.BoxGeometry(0.045, 1.4, 0.045), FM.dark, g, x, 1.32, z));
        mesh(new THREE.BoxGeometry(0.84, 0.05, 0.86), FM.dark, g, 0, 2.03, 0.75);
        mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.08, 16), FM.beacon, g, 0.3, 2.1, 1.05);
        const wheels = [];
        [[-0.42, 0.33, 0.26], [0.42, 0.33, 0.26], [-0.4, 1.25, 0.2], [0.4, 1.25, 0.2]].forEach(([x, z, rr]) => { const w0 = mesh(new THREE.CylinderGeometry(rr, rr, 0.17, 28), FM.tire, g, x, rr, z); w0.rotation.z = Math.PI / 2; wheels.push(w0); });
        [-0.3, 0.3].forEach(x => mesh(new THREE.BoxGeometry(0.07, 2.15, 0.09), FM.steel, g, x, 1.1, 0.12));
        [0.3, 1.2, 2.1].forEach(y => mesh(new THREE.BoxGeometry(0.66, 0.05, 0.06), FM.steel, g, 0, y, 0.12));
        const car = new THREE.Group(); car.position.set(0, 0.08, 0); g.add(car);
        mesh(new THREE.BoxGeometry(0.76, 0.06, 0.05), FM.dark, car, 0, 0.12, 0.05);
        mesh(new THREE.BoxGeometry(0.76, 0.06, 0.05), FM.dark, car, 0, 0.42, 0.05);
        [-0.25, 0.25].forEach(x => { mesh(new THREE.BoxGeometry(0.1, 0.04, 0.95), FM.dark, car, x, 0, -0.475); mesh(new THREE.BoxGeometry(0.1, 0.5, 0.04), FM.dark, car, x, 0.25, 0.02); });
        const fx0 = SB.WI.x + 0.9;
        g.position.set(fx0, 0, AZ);
        return { g, car, wheels, acts: [], cur: null, carry: null, pose: { x: fx0, z: AZ, yaw: 0, h: 0.08 }, rev: false };
      })();
      FL.g.visible = false; // 사용자 요청 2026-10-16: 지게차 없앰 — 아래 convMove/convStep이 대신 옮김
      const convMove = (src, dst) => { src.res = true; dst.res = true; FL.acts = [{ k: 'conv', src, dst }]; };
      const convStep = (dt) => {
        if (!FL.cur && FL.acts.length) { const c0 = FL.cur = FL.acts.shift(); c0.tm = 0; c0.b = c0.src.box; if (c0.b) { c0.src.box = null; c0.src.res = false; c0.b.at = null; FL.carry = c0.b; }
          c0.dx = Math.abs(c0.dst.x - c0.src.x); c0.dz = Math.abs(c0.dst.z - c0.src.z); c0.d = Math.max(2, (c0.dx + c0.dz) / 0.6); }
        const c0 = FL.cur; if (!c0) return;
        c0.tm += dt; const u = Math.min(1, c0.tm / c0.d), b = c0.b;
        if (b) { // 줄 따라 x 먼저, 끝에서 z (세척기 앞 갈래)
          const fx = (c0.dx + c0.dz) ? c0.dx / (c0.dx + c0.dz) : 1, zFirst = Math.abs(c0.src.z - SB.S.z) > 0.05;
          const a = sm(Math.min(1, u / Math.max(0.01, zFirst ? 1 - fx : fx))), c = sm(Math.max(0, (u - (zFirst ? 1 - fx : fx)) / Math.max(0.01, zFirst ? fx : 1 - fx)));
          const x = zFirst ? c0.src.x + (c0.dst.x - c0.src.x) * c : c0.src.x + (c0.dst.x - c0.src.x) * a, z = zFirst ? c0.src.z + (c0.dst.z - c0.src.z) * a : c0.src.z + (c0.dst.z - c0.src.z) * c;
          b.g.position.set(x, BOXY, z); }
        if (u >= 1) { if (b) placeBox(b, c0.dst); else c0.dst.res = false; FL.carry = null; FL.cur = null; }
      };
      const yawOf = (t, rev) => rev ? Math.atan2(t.x, t.z) : Math.atan2(-t.x, -t.z);
      const planMove = (src, dst) => {
        const A = [], pp = { ...FL.pose };
        const pathTo = (sp, hh) => {
          const x0 = pp.x, x1 = sp.x, s = Math.sign(x1 - x0) || 1;
          if (pp.z < AZ - 0.01) { A.push({ k: 'path', cp: new THREE.LineCurve3(V(x0, 0, pp.z), V(x0, 0, AZ)), rev: true }); pp.z = AZ; }
          const P1 = V(x0 - s * 0.7, 0, AZB), P2 = V(x1 - s * 0.7, 0, AZB);
          A.push({ k: 'path', cp: new THREE.QuadraticBezierCurve3(V(x0, 0, AZ), V(x0, 0, AZB), P1), rev: true });
          const cp = new THREE.CurvePath();
          if (Math.abs(P2.x - P1.x) > 0.01) cp.add(new THREE.LineCurve3(P1, P2));
          cp.add(new THREE.QuadraticBezierCurve3(P2, V(x1, 0, AZB), V(x1, 0, AZ)));
          cp.add(new THREE.LineCurve3(V(x1, 0, AZ), V(x1, 0, sp.ez)));
          A.push({ k: 'lf', h1: hh }); A.push({ k: 'path', cp, rev: false });
          pp.x = x1; pp.z = sp.ez;
        };
        pathTo(src, HIN); A.push({ k: 'grab', sp: src }); A.push({ k: 'lf', h1: HUP });
        A.push({ k: 'path', cp: new THREE.LineCurve3(V(pp.x, 0, pp.z), V(pp.x, 0, AZ)), rev: true }); pp.z = AZ;
        pathTo(dst, HUP); A.push({ k: 'lf', h1: HIN }); A.push({ k: 'drop', sp: dst });
        A.push({ k: 'path', cp: new THREE.LineCurve3(V(pp.x, 0, pp.z), V(pp.x, 0, AZ)), rev: true });
        A.push({ k: 'lf', h1: 0.08 });
        src.res = true; dst.res = true; FL.acts = A;
      };
      const flStep = (dt) => {
        if (!FL.cur && FL.acts.length) {
          const c0 = FL.cur = FL.acts.shift(); c0.tm = 0;
          if (c0.k === 'path') { c0.len = c0.cp.getLength(); c0.d = c0.len / (FL.carry ? 0.7 : 1.0) + 0.5; }
          else if (c0.k === 'lf') { c0.h0 = FL.pose.h; c0.d = Math.abs(c0.h1 - c0.h0) / 0.2 + 0.15; }
          else c0.d = 0.25;
        }
        const c0 = FL.cur, P0 = FL.pose; if (!c0) { FL.rev = false; return; }
        c0.tm += dt; const u = c0.d ? sm(Math.min(1, c0.tm / c0.d)) : 1;
        if (c0.k === 'path') {
          const p = c0.cp.getPointAt(u), tg = c0.cp.getTangentAt(Math.min(0.999, Math.max(0.001, u)));
          const dd = Math.hypot(p.x - P0.x, p.z - P0.z); FL.wheels.forEach(w0 => { w0.rotation.x += (c0.rev ? -dd : dd) / 0.23; });
          P0.x = p.x; P0.z = p.z; P0.yaw = yawOf(tg, c0.rev); FL.rev = c0.rev;
        } else if (c0.k === 'lf') P0.h = c0.h0 + (c0.h1 - c0.h0) * u;
        else if (c0.k === 'grab' && !c0.done) { c0.done = true; const b = c0.sp.box; if (b) { FL.car.attach(b.g); c0.sp.box = null; c0.sp.res = false; b.at = null; FL.carry = b; } }
        else if (c0.k === 'drop' && !c0.done) { c0.done = true; const b = FL.carry; if (b) { convG.attach(b.g); placeBox(b, c0.sp); FL.carry = null; } }
        FL.g.position.set(P0.x, 0, P0.z); FL.g.rotation.y = P0.yaw; FL.car.position.y = P0.h;
        if (c0.tm >= c0.d) FL.cur = null;
      };
      const WSH = { box: null, ph: 'idle', t: 0 }, FGS = { ph: 'fill', t: 0, b: null };
      const wBar = (() => {
        const cv = document.createElement('canvas'); cv.width = 320; cv.height = 72; const tx = new THREE.CanvasTexture(cv); tx.colorSpace = THREE.SRGBColorSpace;
        const s0 = new THREE.Sprite(new THREE.SpriteMaterial({ map: tx, transparent: true, depthWrite: false })); s0.scale.set(1.3, 0.29, 1); s0.position.set((XIN + XOUT) / 2, 1.7, -(WB[2] / 1000) + 0.1); s0.visible = false; convG.add(s0);
        let last = '';
        return (pr, ph) => {
          s0.visible = pr >= 0; if (pr < 0) return;
          const p = Math.min(1, pr), txt = ph === 'wait' ? '세척 끝 · 배출 대기' : ph === 'in' ? '세척기 투입' : ph === 'wash' ? '세척 · 헹굼 · 건조' : '배출', key = txt + Math.round(p * 50); if (key === last) return; last = key;
          const g = cv.getContext('2d'); g.clearRect(0, 0, 320, 72); g.fillStyle = 'rgba(10,16,24,0.8)'; g.beginPath(); g.roundRect(4, 4, 312, 64, 14); g.fill();
          g.fillStyle = '#ffffff'; g.font = '700 19px "Pretendard Variable", sans-serif'; g.textAlign = 'left'; g.fillText(txt, 18, 30); g.textAlign = 'right'; g.fillText(Math.round(p * 100) + '%', 302, 30);
          g.fillStyle = 'rgba(255,255,255,0.15)'; g.fillRect(18, 42, 284, 12); g.fillStyle = '#5fb8ff'; g.fillRect(18, 42, 284 * p, 12); tx.needsUpdate = true;
        };
      })();
      const wshStep = (dt, run) => {
        const W0 = WSH;
        const wb0 = SB.WI.box, ready = wb0 && (isFull(wb0) || (wb0.closed && !wb0.res.size && cnt(wb0) > 0)); // 30개 또는 LOT 끝
        if (W0.ph === 'idle' && ready && !SB.WI.res && run) { W0.box = SB.WI.box; SB.WI.box = null; W0.box.at = null; W0.ph = 'in'; W0.t = 0; }
        const b = W0.box; if (b && run) W0.t += dt;
        const xI0 = XIN, xO0 = XOUT, zIn = D3 ? D3.wz : -4.45, dz0 = SB.WI.z - zIn; // 데이터적용본: 세척기 자리에 맞춤
        if (W0.ph === 'in') { const u = sm(Math.min(1, W0.t / 6)), q = along(wPathIn, u); b.g.position.set(q[0], BOXY, q[1]); b.g.rotation.y = q[2] ? Math.PI / 2 : 0; if (W0.t >= 6) { b.g.rotation.y = 0; W0.ph = 'wash'; W0.t = 0; } }
        else if (W0.ph === 'wash') { const u = Math.min(1, W0.t / 18); b.g.position.set(xI0 + (xO0 - xI0) * u, BOXY, zIn); if (W0.t >= 18) { W0.ph = 'wait'; b.items.forEach(o => { if (o) o.material = pallets.w4[0].material; }); } }
        else if (W0.ph === 'wait') { if (!SB.WO.box && !SB.WO.res) { W0.ph = 'out'; W0.t = 0; SB.WO.res = true; } }
        else if (W0.ph === 'out') { const u = sm(Math.min(1, W0.t / 6)), q = along(wPathOut, u); b.g.position.set(q[0], BOXY, q[1]); b.g.rotation.y = q[2] ? Math.PI / 2 : 0; if (W0.t >= 6) { placeBox(b, SB.WO); W0.box = null; W0.ph = 'idle'; } }
        wDoors[0].want = 0; wDoors[1].want = 0; // 앞 유리문은 닫힌 채 — 상자는 옆으로 드나듦
        wDoors.forEach(D => { D.o += (D.want - D.o) * Math.min(1, dt * 4); D.sh.position.y = D.y0 + D.o * 0.62; });
        // 개선안 5: 세척기 위 진행 막대 (투입 0~20% · 세척 20~80% · 배출 대기 80% · 배출 80~100%)
        const pr = W0.ph === 'in' ? W0.t / 6 * 0.2 : W0.ph === 'wash' ? 0.2 + W0.t / 18 * 0.6 : W0.ph === 'wait' ? 0.8 : W0.ph === 'out' ? 0.8 + W0.t / 6 * 0.2 : -1;
        wBar(pr, W0.ph);
        this.wshBusy = W0.ph === 'wash'; this.wshAt = W0.box ? W0.box.g.position : null; // 실제 상자가 안에 있을 때만 세척 연출
        return W0.ph === 'wash';
      };
      const mkGauge = (sp, title) => {
        const cv = document.createElement('canvas'); cv.width = 320; cv.height = 112;
        const tx = new THREE.CanvasTexture(cv); tx.colorSpace = THREE.SRGBColorSpace;
        const s0 = new THREE.Sprite(new THREE.SpriteMaterial({ map: tx, transparent: true, depthWrite: false })); s0.scale.set(1.2, 0.42, 1); s0.position.set(sp.x, 1.25, sp.z); convG.add(s0);
        let last = '';
        return (n, msg, col) => {
          const key = n + '|' + msg; if (key === last) return; last = key;
          const g = cv.getContext('2d'); g.clearRect(0, 0, 320, 112); g.fillStyle = 'rgba(10,16,24,0.78)'; g.beginPath(); g.roundRect(4, 4, 312, 104, 16); g.fill();
          g.strokeStyle = col; g.lineWidth = 2; g.stroke();
          g.fillStyle = '#9fb1c2'; g.font = '600 17px "Pretendard Variable", sans-serif'; g.fillText(msg || title, 18, 32);
          g.fillStyle = '#ffffff'; g.font = '700 32px "Pretendard Variable", sans-serif'; g.fillText(n + ' / ' + BCAP, 18, 70);
          g.fillStyle = 'rgba(255,255,255,0.14)'; g.fillRect(18, 84, 284, 10); g.fillStyle = col; g.fillRect(18, 84, 284 * Math.min(1, n / BCAP), 10);
          tx.needsUpdate = true;
        };
      };
      (this.floorWip || []).forEach(F => { if (F.key === 'w3') F.m.position.x = SB.S.x - 0.6; }); // 바닥 WIP-3 글자 = 바스켓 자리 앞
      const gS = mkGauge(SB.S, 'WIP-3 · 세척 배치'), gW = mkGauge(SB.WO, 'WIP-4 · 측정 대기');
      // ===== AS/RS warehouse (x 26–33.6) =====
      let whStep = () => {};
      {
      const WG = new THREE.Group(); scene.add(WG);
      const RM = { up: M(0xaeb7bf, { metalness: 0.55, roughness: 0.4 }), beam: M(0x7b8a98, { metalness: 0.4, roughness: 0.45 }), wood: M(0xb08a5a, { roughness: 0.8 }), tote: M(0x5d7891, { roughness: 0.6 }), toteG: M(0x8a96a2, { roughness: 0.55 }), rail: M(0xb9c3cc, { metalness: 0.8, roughness: 0.25 }), crane: M(0xeef1f4, { roughness: 0.35, metalness: 0.3 }), dark: M(0x2a3138, { roughness: 0.6 }), floor: M(0xe6ebef, { roughness: 0.6, metalness: 0.05 }), strip: new THREE.MeshBasicMaterial({ color: 0xeaf6ff }) };
      const kraft = [0xb59a7a, 0xbea584, 0xac9172].map(c => M(c, { roughness: 0.9 }));
      const mkLbl = (txt) => { const c = document.createElement('canvas'); c.width = 128; c.height = 64; const g = c.getContext('2d'); g.fillStyle = '#f4f4f0'; g.fillRect(0, 0, 128, 64); g.fillStyle = '#1b1f24'; for (let x = 10; x < 118; x += 2 + ((x * 7 + txt.length) % 4)) g.fillRect(x, 8, (x % 3) + 1, 30); g.font = '700 13px "Pretendard Variable", sans-serif'; g.fillText(txt, 12, 56); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return new THREE.MeshBasicMaterial({ map: t }); };
      const lblMs = ['BIN-X-321', 'BIN-Y-456', 'BIN-4-321', 'BIN-Y-495'].map(mkLbl);
      const XO = this.LY ? this.LY.fg + 2.2 - 26.2 : 0; // 데이터적용본: 자동창고를 완성품 자리(FG-01) 동쪽으로
      { const fl = new THREE.Mesh(new THREE.PlaneGeometry(8.6, 16), RM.floor); fl.rotation.x = -Math.PI / 2; fl.position.set(29.6 + XO, 0.0015, -8.0); fl.receiveShadow = true; WG.add(fl);
        const ed = new THREE.Mesh(new THREE.PlaneGeometry(0.08, 16), new THREE.MeshBasicMaterial({ color: 0x29c6e6 })); ed.rotation.x = -Math.PI / 2; ed.position.set(25.4 + XO, 0.004, -8.0); WG.add(ed); }
      const m4 = new THREE.Matrix4(), q4 = new THREE.Quaternion(), s4 = new THREE.Vector3(), p4 = new THREE.Vector3(), e4 = new THREE.Euler();
      const inst = (geo, m, list) => { const im = new THREE.InstancedMesh(geo, m, Math.max(1, list.length)); list.forEach((t, i) => { p4.set(t[0], t[1], t[2]); s4.set(t[3] ?? 1, t[4] ?? 1, t[5] ?? 1); e4.set(0, t[6] || 0, 0); q4.setFromEuler(e4); m4.compose(p4, q4, s4); im.setMatrixAt(i, m4); }); im.count = list.length; im.receiveShadow = true; WG.add(im); return im; };
      const RX = [28.0 + XO, 30.4 + XO, 32.8 + XO], ZR0 = -4.6, BZL = 1.6, NBZ = 6, LVW = [0.15, 1.15, 2.15, 3.15], RTOP = 4.0, AXS = [29.2 + XO, 31.6 + XO];
      let sd = 11; const rnd = () => { sd = (sd * 9301 + 49297) % 233280; return sd / 233280; };
      const store = [];
      const ups = [], beams = [], pals = [], kr = [[], [], []], tb = [], tg = [], lbs = [[], [], [], []], brs = [];
      RX.forEach((rx, ri) => {
        for (let b = 0; b <= NBZ; b++) { const z = ZR0 - b * BZL; [-0.5, 0.5].forEach(dx => ups.push([rx + dx, RTOP / 2, z])); for (let k = 0; k < 3; k++) brs.push([rx, 0.65 + k * 1.1, z]); }
        for (let b = 0; b < NBZ; b++) {
          const zc = ZR0 - b * BZL - BZL / 2;
          [...LVW, RTOP - 0.05].forEach(hh => [-0.5, 0.5].forEach(dx => beams.push([rx + dx, hh - 0.05, zc])));
          LVW.forEach((hh, li) => {
            if (ri === 1 && b >= 1 && b <= 4 && li >= 1 && li <= 3) { store.push({ x: rx, z: zc, y: hh + 0.14, box: null, res: false }); return; }
            const v = rnd(); if (v > 0.92) return;
            pals.push([rx, hh + 0.06, zc]);
            if (v < 0.58) { const bh = 0.55 + rnd() * 0.35; kr[Math.floor(rnd() * 3)].push([rx, hh + 0.12 + bh / 2, zc, 0.95, bh, 1.25]); [-1, 1].forEach(sx => lbs[Math.floor(rnd() * 4)].push([rx + sx * 0.476, hh + 0.12 + bh * 0.6, zc + 0.3, 1, 1, 1, sx * Math.PI / 2])); }
            else if (v < 0.78) { tb.push([rx, hh + 0.29, zc]); if (rnd() < 0.7) tb.push([rx, hh + 0.64, zc]); }
            else { tg.push([rx, hh + 0.29, zc]); if (rnd() < 0.6) tg.push([rx, hh + 0.64, zc]); }
          });
        }
      });
      inst(new THREE.BoxGeometry(0.09, RTOP, 0.09), RM.up, ups);
      inst(new THREE.BoxGeometry(0.06, 0.1, BZL - 0.1), RM.beam, beams);
      inst(new THREE.BoxGeometry(1.0, 0.04, 0.04), RM.up, brs);
      inst(new THREE.BoxGeometry(1.0, 0.12, 1.3), RM.wood, pals);
      kr.forEach((l, i) => inst(new THREE.BoxGeometry(1, 1, 1), kraft[i], l));
      inst(new THREE.BoxGeometry(0.92, 0.34, 1.2), RM.tote, tb); inst(new THREE.BoxGeometry(0.92, 0.34, 1.2), RM.toteG, tg);
      lbs.forEach((l, i) => inst(new THREE.PlaneGeometry(0.34, 0.17), lblMs[i], l));
      AXS.forEach(ax => { mesh(new THREE.BoxGeometry(0.16, 0.06, 10.6), RM.rail, WG, ax, 0.03, -9.0); mesh(new THREE.BoxGeometry(0.2, 0.1, 10.6), RM.rail, WG, ax, RTOP + 0.15, -9.0); });
      { const wl = new THREE.PointLight(0xdcefff, 3, 12, 1.6); wl.position.set(30.4 + XO, 5.2, -7.0); WG.add(wl); }
      // conveyors
      const mkConv = (curve, hh, wd, mt) => {
        const L = curve.getLength(), n = Math.ceil(L / 0.13) + 1, im = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.035, 0.035, wd, 10), RM.rail, n), up0 = new THREE.Vector3(0, 1, 0), rl = [[], []];
        let i = 0; for (let s = 0; s <= L && i < n; s += 0.13) { const u = s / L, p = curve.getPointAt(u), t = curve.getTangentAt(u), ax = new THREE.Vector3(-t.z, 0, t.x).normalize(); q4.setFromUnitVectors(up0, ax); p4.set(p.x, hh - 0.04, p.z); m4.compose(p4, q4, s4.set(1, 1, 1)); im.setMatrixAt(i++, m4); [-1, 1].forEach((o, k) => rl[k].push(new THREE.Vector3(p.x + ax.x * o * wd / 2, hh + 0.03, p.z + ax.z * o * wd / 2)));
          if (Math.round(s / 0.13) % 12 === 0) [-1, 1].forEach(o => mesh(new THREE.BoxGeometry(0.07, hh - 0.1, 0.07), RM.up, WG, p.x + ax.x * o * (wd / 2 - 0.05), (hh - 0.1) / 2, p.z + ax.z * o * (wd / 2 - 0.05))); }
        im.count = i; WG.add(im);
        rl.forEach(pts => WG.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 160, 0.03, 6), mt || RM.beam)));
        return L;
      };
      const IH = 2.3, OH = 3.3;
      const inC = new THREE.CatmullRomCurve3([V(26.2 + XO, IH, -2.35), V(27.1 + XO, IH, -2.45), V(28.25 + XO, IH, -2.95), V(28.95 + XO, IH, -3.45), V(29.2 + XO, IH, -3.95)], false, 'centripetal');
      const outC = new THREE.CatmullRomCurve3([V(31.6 + XO, OH, -3.95), V(31.85 + XO, OH, -3.3), V(32.55 + XO, OH, -2.6), V(33.0 + XO, OH, -2.35)], false, 'centripetal');
      mkConv(inC, IH, 1.5); mkConv(outC, OH, 1.5);
      const lift = (sp, top) => { [[-0.78, -0.66], [0.78, -0.66], [-0.78, 0.66], [0.78, 0.66]].forEach(([dx, dz]) => mesh(new THREE.BoxGeometry(0.08, top + 0.6, 0.08), RM.up, WG, sp.x + dx, (top + 0.6) / 2, sp.z + dz)); mesh(new THREE.BoxGeometry(1.64, 0.08, 1.4), RM.beam, WG, sp.x, top + 0.6, sp.z); };
      lift(SB.WH, IH); lift(SB.ER, OH);
      // deco carton loop
      const cLoop = new THREE.CatmullRomCurve3([V(26.9 + XO, 6.1, -3.35), V(30.4 + XO, 6.1, -3.2), V(33.3 + XO, 6.1, -3.35), V(33.4 + XO, 6.1, -4.1), V(30.4 + XO, 6.1, -4.25), V(26.8 + XO, 6.1, -4.1)], true, 'centripetal');
      const CLL = cLoop.getLength();
      const ctn = []; for (let i = 0; i < 0; i++) { const g0 = new THREE.Group(); mesh(new THREE.BoxGeometry(0.42, 0.3, 0.36), kraft[i % 3], g0, 0, 0.15, 0); const lb = new THREE.Mesh(new THREE.PlaneGeometry(0.16, 0.08), lblMs[i % 4]); lb.position.set(0, 0.16, 0.181); g0.add(lb); WG.add(g0); ctn.push({ g: g0, s: (i / 18) * CLL }); }
      // stacker cranes
      const mkCrane = (ax) => {
        const g = new THREE.Group(); g.position.set(ax, 0, -6); WG.add(g);
        [-0.18, 0.18].forEach(dz => mesh(new THREE.BoxGeometry(0.22, RTOP + 0.1, 0.12), RM.crane, g, 0, (RTOP + 0.1) / 2, dz));
        mesh(new THREE.BoxGeometry(0.5, 0.35, 0.9), RM.dark, g, 0, 0.2, 0); mesh(new THREE.BoxGeometry(0.4, 0.2, 0.7), RM.crane, g, 0, RTOP, 0);
        mesh(new THREE.BoxGeometry(0.06, 0.1, 0.06), new THREE.MeshBasicMaterial({ color: 0xff9a1f }), g, 0, RTOP + 0.15, 0.2);
        const car = new THREE.Group(); g.add(car); mesh(new THREE.BoxGeometry(1.1, 0.07, 1.25), RM.dark, car, 0, -0.18, 0);
        const deco = mesh(new THREE.BoxGeometry(0.95, 0.6, 1.2), kraft[1], car, 0, 0.18, 0); deco.visible = false;
        return { g, car, deco, ax, z: -6, y: 1.3, tz: -6, ty: 1.3, wait: 0, task: null, box: null };
      };
      const CR = AXS.map(mkCrane);
      const crStep = (C, dt) => {
        const dz = C.tz - C.z, dy = C.ty - C.y;
        C.z += Math.sign(dz) * Math.min(Math.abs(dz), dt * Math.min(1.8, 0.25 + Math.abs(dz) * 1.4));
        C.y += Math.sign(dy) * Math.min(Math.abs(dy), dt * Math.min(0.8, 0.15 + Math.abs(dy) * 1.2));
        C.g.position.z = C.z; C.car.position.y = C.y;
        return Math.abs(dz) < 0.004 && Math.abs(dy) < 0.004;
      };
      const crIdle = (C, dt) => { if (C.wait > 0) { C.wait -= dt; return; } if (crStep(C, dt)) { C.wait = 4.5; C.deco.visible = !C.deco.visible; C.tz = ZR0 - BZL / 2 - Math.floor(rnd() * NBZ) * BZL; C.ty = LVW[Math.floor(rnd() * LVW.length)] + 0.14; } };
      const WHS = { inb: null, out: null, stored: 0, inCnt: 0 };
      // 창고 없앰: 창고 선반 빈 상자도 두지 않음
      ([] as number[]).forEach(i => { const b = mkBox(); const sl = store[i]; b.g.position.set(sl.x, sl.y, sl.z); b.g.rotation.y = Math.PI / 2; sl.box = b; b.wEmpty = true; b.at = null; });
      const signCv = document.createElement('canvas'); signCv.width = 512; signCv.height = 128;
      const signTx = new THREE.CanvasTexture(signCv); signTx.colorSpace = THREE.SRGBColorSpace;
      const sign = new THREE.Sprite(new THREE.SpriteMaterial({ map: signTx, transparent: true, depthWrite: false })); sign.scale.set(2.6, 0.65, 1); sign.position.set(30.4 + XO, 4.75, -4.3); WG.add(sign);
      let signKey = '';
      const drawSign = (stock, inCnt, msg) => { const k0 = stock + '|' + inCnt + '|' + msg; if (k0 === signKey) return; signKey = k0; const g = signCv.getContext('2d'); g.clearRect(0, 0, 512, 128); g.fillStyle = 'rgba(10,16,24,0.8)'; g.beginPath(); g.roundRect(4, 4, 504, 120, 18); g.fill(); g.strokeStyle = '#4fd2ea'; g.lineWidth = 2; g.stroke(); g.fillStyle = '#7fe3f5'; g.font = '700 22px "Pretendard Variable", sans-serif'; g.fillText('AS/RS WAREHOUSE · 자동 창고', 22, 40); g.fillStyle = '#ffffff'; g.font = '700 34px "Pretendard Variable", sans-serif'; g.fillText((1240 + stock) + ' / 2,000 SLOT', 22, 84); g.fillStyle = '#9fb1c2'; g.font = '600 18px "Pretendard Variable", sans-serif'; g.fillText(msg || ('오늘 입고 ' + inCnt + ' 박스'), 22, 112); signTx.needsUpdate = true; };
      whStep = (dt) => {
        const W0 = WHS;
        if (!W0.inb && SB.WH.box && !SB.WH.res) { const b = SB.WH.box; SB.WH.box = null; b.at = null; W0.inb = { b, ph: 'lift', t: 0 }; }
        const I = W0.inb;
        if (I) {
          I.t += dt; const b = I.b;
          if (I.ph === 'lift') { const u = sm(Math.min(1, I.t / 4)); b.g.position.set(SB.WH.x, BOXY + (IH + 0.14 - BOXY) * u, SB.WH.z); b.g.rotation.y = u * Math.PI / 2; if (I.t >= 4) { I.ph = 'conv'; I.t = 0; } }
          else if (I.ph === 'conv') { const u = Math.min(1, I.t / 9); const p = inC.getPointAt(sm(u)); b.g.position.set(p.x, IH + 0.14, p.z); if (u >= 1) { I.ph = 'wait'; } }
          else if (I.ph === 'wait') { const C = CR[0]; if (!C.task) { C.task = { kind: 'store', b, ph: 'go' }; C.tz = -3.95; C.ty = IH + 0.14; C.deco.visible = false; I.ph = 'handed'; } }
        }
        const C1 = CR[0];
        if (C1.task) { const T0 = C1.task;
          if (T0.ph === 'go') { if (crStep(C1, dt)) { C1.car.attach(T0.b.g); W0.inb = null; const sl = store.find(s0 => !s0.box && !s0.res); if (!sl) { T0.ph = 'hold'; } else { sl.res = true; T0.sl = sl; T0.ph = 'move'; C1.tz = sl.z; C1.ty = sl.y; } } }
          else if (T0.ph === 'hold') { const sl = store.find(s0 => !s0.box && !s0.res); if (sl) { sl.res = true; T0.sl = sl; T0.ph = 'move'; C1.tz = sl.z; C1.ty = sl.y; } }
          else if (T0.ph === 'move') { if (crStep(C1, dt)) { convG.attach(T0.b.g); T0.ph = 'shuttle'; T0.t = 0; T0.x0 = T0.b.g.position.x; } }
          else if (T0.ph === 'shuttle') { T0.t += dt; const u = sm(Math.min(1, T0.t / 2)); T0.b.g.position.x = T0.x0 + (T0.sl.x - T0.x0) * u; if (u >= 1) { T0.sl.box = T0.b; T0.sl.res = false; T0.b.stT = 0; T0.b.wEmpty = false; W0.inCnt++; C1.task = null; C1.wait = 0.8; } }
        } else crIdle(C1, dt);
        store.forEach(sl => { const b = sl.box; if (b && !b.wEmpty) { b.stT += dt; if (b.stT > 16) { b.items.forEach((o, i) => { if (o) { b.items[i] = null; convG.attach(o); release(o); } }); b.wEmpty = true; } } });
        const C2 = CR[1];
        if (!C2.task && !SB.ER.box && !SB.ER.res && !W0.out) { const sl = store.find(s0 => s0.box && s0.box.wEmpty); if (sl) { C2.task = { kind: 'pick', sl, ph: 'go' }; C2.tz = sl.z; C2.ty = sl.y; C2.deco.visible = false; sl.res = true; } }
        if (C2.task) { const T0 = C2.task;
          if (T0.ph === 'go') { if (crStep(C2, dt)) { T0.ph = 'shuttle'; T0.t = 0; T0.b = T0.sl.box; T0.x0 = T0.b.g.position.x; } }
          else if (T0.ph === 'shuttle') { T0.t += dt; const u = sm(Math.min(1, T0.t / 2)); T0.b.g.position.x = T0.x0 + (C2.ax - T0.x0) * u; if (u >= 1) { C2.car.attach(T0.b.g); T0.sl.box = null; T0.sl.res = false; T0.ph = 'front'; C2.tz = -3.95; C2.ty = OH + 0.14; } }
          else if (T0.ph === 'front') { if (crStep(C2, dt)) { convG.attach(T0.b.g); W0.out = { b: T0.b, ph: 'conv', t: 0 }; SB.ER.res = true; C2.task = null; C2.wait = 0.8; } }
        } else crIdle(C2, dt);
        const O = W0.out;
        if (O) { O.t += dt; const b = O.b;
          if (O.ph === 'conv') { const u = Math.min(1, O.t / 6); const p = outC.getPointAt(sm(u)); b.g.position.set(p.x, OH + 0.14, p.z); if (u >= 1) { O.ph = 'down'; O.t = 0; } }
          else if (O.ph === 'down') { const u = sm(Math.min(1, O.t / 5)); b.g.position.set(SB.ER.x, OH + 0.14 + (BOXY - OH - 0.14) * u, SB.ER.z); b.g.rotation.y = (1 - u) * Math.PI / 2; if (O.t >= 5) { placeBox(b, SB.ER); b.wEmpty = false; W0.out = null; } }
        }
        W0.stored = store.filter(s0 => s0.box && !s0.box.wEmpty).length;
        drawSign(W0.stored, W0.inCnt, I && I.ph !== 'handed' ? 'FG 박스 입고 중 →' : C1.task ? '스태커 크레인 적치 중' : O ? '빈 박스 출고 →' : '');
      };
      this.bgStep = (dt) => { ctn.forEach(c0 => { c0.s = (c0.s + dt * 0.5) % CLL; const u = c0.s / CLL, p = cLoop.getPointAt(u), t = cLoop.getTangentAt(u); c0.g.position.copy(p); c0.g.rotation.y = Math.atan2(t.x, t.z); }); };
      // 사용자 요청 2026-10-15: 자동창고(공장 밖)를 흐리게 — 라인이 먼저 보이게. 지금 붙은 것만 (나중에 들어오는 상자는 그대로)
      WG.visible = false; // 사용자 요청 2026-10-16: 오른쪽 창고 없앰 — 공정 라인만
      }
      const PM = { hood: M(0x9aa5af, { metalness: 0.55, roughness: 0.35 }), hole: new THREE.MeshBasicMaterial({ color: 0x0e1216 }), shut: M(0x3b4651, { metalness: 0.4, roughness: 0.4 }), lip: M(0xf2c230, { roughness: 0.5 }), lamp: new THREE.MeshBasicMaterial({ color: 0x22d36b }) };
      // 사용자 요청 2026-10-18: 컨베이어가 설비로 들어가는 통(터널·투입구 덮개)이 시야를 가려 투명 유리로
      const GL = (op) => new THREE.MeshStandardMaterial({ color: 0xdfe8ee, metalness: 0.1, roughness: 0.05, transparent: true, opacity: op, depthWrite: false, userData: { glass: 1 } });
      PM.hood = GL(0.18); PM.shut = GL(0.28); PM.hole = GL(0.06);
      const ports = [];
      const ZS = 3.36;
      const inc = (c, isIn) => { const L = isIn ? c.load : (c.unload || c.load), x = isIn ? c.xi : c.xo, ze = Math.abs(L.z) - 0.07; return { x, L, ze, rise: L.y - BY, run: ze - ZS }; };
      const yAt = (I, zAbs) => BY + I.rise * Math.max(0, Math.min(1, (zAbs - ZS) / I.run));
      const IB = { belt: M(0x2a3035, { roughness: 0.85 }), cleat: M(0x3d454d, { roughness: 0.7 }), side: M(0xdfe4e8, { metalness: 0.7, roughness: 0.3 }), frame: M(0x56626e, { metalness: 0.5, roughness: 0.4 }), motor: M(0x1f6fb2, { roughness: 0.4, metalness: 0.2 }), slide: M(0x8f99a2, { metalness: 0.7, roughness: 0.3 }), pul: M(0xc3cad0, { metalness: 0.85, roughness: 0.22 }), cover: M(0x46515b, { metalness: 0.4, roughness: 0.45 }), skirt: M(0x7d8892, { metalness: 0.45, roughness: 0.45 }), gasket: M(0x15191d, { roughness: 0.9 }) };
      const inclines = [], CSP = 0.13;
      const mkIncline = (c, isIn) => {
        const I = inc(c, isIn), len = Math.hypot(I.rise, I.run), ang = Math.atan2(I.rise, I.run);
        const along = (t0, t1) => { const tm = (t0 + t1) / 2, g = new THREE.Group(); g.position.set(I.x, BY - 0.075 - 0.012 + I.rise * tm, -(ZS + I.run * tm)); g.rotation.x = ang; convG.add(g); return { g, l: len * (t1 - t0) }; };
        const E0 = along(0, 1), g0 = E0.g, le = E0.l; // 벨트는 끝까지 (유리 터널 안에서도 보이게, 2026-10-18)
        mesh(new THREE.BoxGeometry(0.34, 0.016, le + 0.04), IB.belt, g0, 0, 0, 0);
        mesh(new THREE.BoxGeometry(0.4, 0.1, le + 0.04), IB.frame, g0, 0, -0.06, 0);
        [-0.195, 0.195].forEach(dx => mesh(new THREE.BoxGeometry(0.03, 0.12, le + 0.06), IB.side, g0, dx, 0.02, 0));
        const pg = new THREE.CylinderGeometry(0.04, 0.04, 0.34, 20), cvg = new THREE.CylinderGeometry(0.06, 0.06, 0.02, 20);
        { const zz = -(le / 2 + 0.03); const p0 = mesh(pg, IB.pul, g0, 0, -0.03, -zz); p0.rotation.z = Math.PI / 2; [-0.215, 0.215].forEach(dx => { const c0 = mesh(cvg, IB.cover, g0, dx, -0.03, -zz); c0.rotation.z = Math.PI / 2; }); }
        const cg = new THREE.Group(); g0.add(cg);
        for (let s = -le / 2; s <= le / 2 - 0.02; s += CSP) mesh(new THREE.BoxGeometry(0.32, 0.03, 0.012), IB.cleat, cg, 0, 0.022, s);
        cg.userData = { len: le, dir: isIn ? -1 : 1 };
        // 설비 안쪽 터널 상자는 없앰: 설비 벽·테이블을 뚫고 지나가 보였음 (2026-10-18). 안쪽은 설비 창으로 보임
        const mk = new THREE.Group(); mk.position.set(I.x + 0.24, BY - 0.13, -(ZS + 0.12)); convG.add(mk); mesh(new THREE.BoxGeometry(0.1, 0.12, 0.16), IB.motor, mk, 0, 0, 0);
        [0, 0.35].forEach(t => {
          const zA = t === 0 ? ZS + 0.05 : ZS + I.run * t; if (t > 0 && zA > c.fr - 0.3) return;
          const yy = yAt(I, zA) - 0.075 - 0.11;
          mesh(new THREE.BoxGeometry(0.46, 0.02, 0.2), CM.leg, convG, I.x, 0.01, -zA);
          [-0.17, 0.17].forEach(dx => mesh(new THREE.BoxGeometry(0.045, yy, 0.045), CM.leg, convG, I.x + dx, yy / 2, -zA));
          mesh(new THREE.BoxGeometry(0.36, 0.035, 0.035), CM.leg, convG, I.x, yy * 0.45, -zA);
          const br = mesh(new THREE.BoxGeometry(0.025, Math.hypot(0.34, yy * 0.45), 0.025), CM.leg, convG, I.x, yy * 0.225 + 0.02, -zA); br.rotation.z = Math.atan2(0.34, yy * 0.45);
        });
        { const tr = mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.34, 16), IB.pul, convG, I.x, BY - 0.075 - 0.03, -(ZS - 0.01)); tr.rotation.z = Math.PI / 2;
          mesh(new THREE.BoxGeometry(0.4, 0.06, 0.06), IB.frame, convG, I.x, BY - 0.075 - 0.075, -(ZS - 0.01)); }
        const sx = (I.L.x + I.x) / 2, sl = Math.hypot(I.L.x - I.x, 0.14) + 0.2;
        const slide = mesh(new THREE.BoxGeometry(Math.max(0.3, Math.abs(I.L.x - I.x) + 0.3), 0.025, 0.3), IB.slide, convG, sx, I.L.y - 0.09, -(I.ze + 0.07));
        inclines.push({ cg, len, dir: isIn ? -1 : 1, id: c, isIn });
        return I;
      };
      const port = (x, fr, I) => {
        const X = Math.round(x * 1000), F = Math.round(fr * 1000), D = 280;
        const dy = yAt(I, fr - 0.28) - BY, ex = Math.max(0, yAt(I, fr) - yAt(I, fr - 0.28) - 0.09), T = TOP + dy, H = 0.29 + ex;
        box(X - 235, X + 235, F - D, F, T + H, T + H + 0.025, PM.hood, convG);
        box(X - 235, X - 218, F - D, F, T - 0.035, T + H, PM.hood, convG); box(X + 218, X + 235, F - D, F, T - 0.035, T + H, PM.hood, convG);
        box(X - 218, X + 218, F - 14, F - 4, T - 0.03, T + H, PM.hole, convG).castShadow = false;
        box(X - 245, X + 245, F - D - 40, F - D + 40, T + H, T + H + 0.33, PM.hood, convG);
        box(X - 245, X + 245, F - D - 44, F - D - 40, T + H, T + H + 0.04, PM.lip, convG);
        const lampM = PM.lamp.clone(); box(X + 150, X + 210, F - D - 46, F - D - 40, T + H + 0.16, T + H + 0.21, lampM, convG).castShadow = false;
        box(X - 235, X + 235, F - D + 60, F, 0, T - 0.1, IB.skirt, convG);
        box(X - 235, X - 218, F - D, F - D + 60, 0, T - 0.035, IB.skirt, convG); box(X + 218, X + 235, F - D, F - D + 60, 0, T - 0.035, IB.skirt, convG);
        box(X - 232, X + 232, F - 8, F, T + H - 0.012, T + H + 0.004, IB.gasket, convG).castShadow = false;
        box(X - 232, X - 216, F - 8, F, T - 0.04, T + H, IB.gasket, convG).castShadow = false; box(X + 216, X + 232, F - 8, F, T - 0.04, T + H, IB.gasket, convG).castShadow = false;
        [[-245, T + H + 0.3], [245, T + H + 0.3], [-245, 0.12], [245, 0.12]].forEach(([dx, yb]) => cyl(X + dx, F - D - 41, yb - 0.01, yb + 0.01, 0.012, IB.cover));
        const sh = box(X - 214, X + 214, F - D - 9, F - D + 9, T + 0.005, T + H - 0.005, PM.shut, convG);
        ports.push({ x, z: -(F - D) / 1000, zIn: -F / 1000, sh, y0: sh.position.y, o: 0, lampM, yTop: T + H + 0.25, lift: H + 0.01 });
      };
      Object.keys(MC).forEach(id => { if (id === 'wsh') return; const c = MC[id]; if (c.xi != null) port(c.xi, c.fr, mkIncline(c, true)); port(c.xo, c.fr, mkIncline(c, false)); });
      convG.traverse(o => { if (o.material?.userData?.glass) o.castShadow = false; }); // 유리는 그림자 없음
      const lane = (x) => V(x, BY, LZ);
      const bufIn = (k) => [lane(xI(k)), V(xI(k), BY, BZE)];
      const bufOut = (k) => [pw(k, aO), V(xO(k), BY, BZE), lane(xO(k))];
      const isAir = (A, B) => { const dy = Math.abs(A.y - B.y), dh = Math.hypot(A.x - B.x, A.z - B.z); return dy > dh + 1e-4 || (A.y > BY + 0.01 && B.y > BY + 0.01); };
      const inS = (c) => V(c.xi, BY, -ZS);
      const inEnd = (c) => { const I = inc(c, true), zA = Math.max(ZS + 0.08, c.fr - 0.32); return V(c.xi, yAt(I, zA), -zA); };
      const loadPath = (c) => { const I = inc(c, true); return [inEnd(c), V(c.xi, I.L.y, -I.ze), V(I.L.x, I.L.y, -I.ze), I.L.clone()]; };
      const outPath = (c) => { const I = inc(c, false), U = I.L; return [U.clone(), V(U.x, U.y, -I.ze), V(c.xo, U.y, -I.ze), V(c.xo, BY, -ZS), lane(c.xo)]; };
      const job = (o, pts, done) => {
        const durs = []; for (let i = 1; i < pts.length; i++) { const d0 = pts[i].clone().sub(pts[i - 1]), vert = Math.abs(d0.y) > Math.hypot(d0.x, d0.z); durs.push(d0.length() / (vert ? 0.32 : 0.6) + 0.14); }
        o.position.copy(pts[0]); jobs.push({ o, pts, durs, seg: 0, t: 0, done });
      };
      const sm = (x) => x * x * (3 - 2 * x);
      const Q = {}; this.buf = {};
      const matOf = (k) => pallets[k][0].material;
      Object.keys(TR0).forEach(k => {
        Q[k] = []; const T0 = TT[k]; const n0 = Math.max(0, Math.min(CAP[k] - 2, Math.round((this.state.wip || {})[k] || 0)));
        for (let i = 0; i < n0; i++) { const p = (NP - 2 - i + NP) % NP, o = getItem(matOf(k)); T0.g.add(o); o.position.set(TRAD * Math.cos(p * PIT), BY, TRAD * Math.sin(p * PIT)); o.userData.p = p; T0.pockets[p] = o; Q[k].push(o); }
        this.buf[k] = n0;
      });
      const inbound = { w1: 0, w2: 0, w3: 0, w4: 0, fg: 0 };
      { const fillN = (b, n, m) => { for (let i = 0; i < n; i++) { const o = getItem(m); b.g.add(o); o.position.copy(slotL(i)); b.items[i] = o; } };
        const bS = mkBox(), bWO = mkBox(), bF = mkBox(), bE = mkBox();
        placeBox(bS, SB.S); placeBox(bWO, SB.WO); placeBox(bF, SB.FG); placeBox(bE, SB.E1); placeBox(mkBox(), SB.E2);
        fillN(bS, 24, pallets.w3[0].material); fillN(bWO, 6, pallets.w4[0].material); fillN(bF, 26, pallets.fg[0].material);
        const takeN = (b) => { for (const n of takeOrder) if (b.items[n]) return n; return -1; }; this.__takeN = takeN; }
      const ms = {}; Object.keys(MC).forEach(id => { ms[id] = { waiting: null, enroute: false, loaded: true, inPlace: true, hold: false, lastPh: null }; });
      this.msRef = ms;
      const startLoad = (id) => { const c = MC[id], S = ms[id], o = S.waiting; S.waiting = null; S.loaded = true; S.inPlace = false; job(o, loadPath(c), () => { release(o); S.inPlace = true; }); };
      this.convStep = (dt) => {
        const st0 = this.state.st || {}, B = this.buf;
        Object.keys(MC).forEach(id => {
          const c = MC[id], S = ms[id], ok = !NOWORK.has(st0[id]);
          if (id === 'wsh') return;
          if (id === 'cmm') {
            const Wb = SB.WO.box;
            if (ok && !S.waiting && !S.enroute && Wb && !SB.WO.res && cnt(Wb) > 0) {
              const n = this.__takeN(Wb), o = Wb.items[n]; Wb.items[n] = null; convG.attach(o); S.enroute = true;
              const p0 = o.position.clone(), mz = SB.WO.z;
              job(o, [p0, V(p0.x, BY, mz), V(SB.WO.x + 0.72, BY, mz), lane(SB.WO.x + 0.9), lane(c.xi), inS(c), inEnd(c)], () => { S.enroute = false; S.waiting = o; if (!S.loaded) startLoad(id); });
            }
          } else if (c.src && ok && !S.waiting && !S.enroute) {
            const T0 = TT[c.src];
            if (Q[c.src].length && !T0.outPending) {
              S.enroute = true; T0.outPending = true;
              T0.ops.push({ type: 'out', go: (o) => { T0.outPending = false; job(o, [...bufOut(c.src), lane(c.xi), inS(c), inEnd(c)], () => { S.enroute = false; S.waiting = o; if (!S.loaded) startLoad(id); }); } });
            }
          }
          const ph = this.phOf(id);
          if ((S.lastPh != null && ph < S.lastPh - 0.5) || S.hold) {
            S.hold = !!S.loaded && S.inPlace !== false;
            if (c.dst === 'w3' || c.dst === 'fg') {
              const sp = c.dst === 'w3' ? SB.S : SB.FG, ex = c.dst === 'w3' ? SEX : FEX, Sb = sp.box;
              // 개선안 3: WIP-3 바스켓에 다른 LOT이 오면 바스켓을 닫음 (30개 안 돼도 세척기로) — 부품은 다음 빈 바스켓까지 설비에서 기다림
              const lot = c.dst === 'w3' ? lotOf(id) : null;
              if (Sb && lot && Sb.lot && Sb.lot !== lot && cnt(Sb) + Sb.res.size > 0) Sb.closed = true;
              if (S.loaded && Sb && !sp.res && !Sb.closed && cnt(Sb) + Sb.res.size < BCAP) {
                let n = 0; while (n < BCAP && (Sb.items[n] || Sb.res.has(n))) n++;
                if (lot && !Sb.lot) Sb.lot = lot;
                Sb.res.add(n); const o = getItem(pallets[c.dst][0].material), sw = slotW(sp, n);
                const pth = c.dst === 'w3' ? [...outPath(c), lane(SB.S.x - 0.78), sw] : [...outPath(c), lane(ex), V(ex, BY, GAPZ), V(ex, BY, FRZ), V(sw.x, BY, FRZ), sw]; // WIP-3: 줄 끝에서 바스켓 칸으로 밀려 들어감
                job(o, pth, () => { Sb.res.delete(n); Sb.items[n] = o; Sb.g.attach(o); o.position.copy(slotL(n)); });
                S.hold = false; S.loaded = false; if (S.waiting) startLoad(id);
              }
              S.lastPh = ph; return;
            }
            const k = c.dst, T0 = TT[k], pend = T0.ops.filter(o0 => o0.type === 'in').length + (T0.cur && T0.cur.type === 'in' ? 1 : 0);
            if (S.loaded && Q[k].length + inbound[k] + pend < CAP[k]) {
              const o = getItem(matOf(k)); inbound[k]++;
              job(o, [...outPath(c), ...bufIn(k)], () => { inbound[k]--; T0.ops.push({ type: 'in', o }); });
              S.hold = false; S.loaded = !c.src;
              if (c.src && S.waiting) startLoad(id);
            }
          }
          S.lastPh = ph;
        });
        Object.keys(TT).forEach(k => {
          const T0 = TT[k];
          if (!T0.cur && T0.ops.length) {
            const op = T0.ops[0];
            if (op.type === 'out' && !Q[k].length) { T0.ops.shift(); }
            else {
              T0.ops.shift(); T0.cur = op; op.phase = 'rot';
              if (op.type === 'in') { let best = -1, bd = 99; for (let p = 0; p < NP; p++) if (!T0.pockets[p]) { const d0 = md(T0.phi - (aI - p * PIT)); if (d0 < bd) { bd = d0; best = p; } } op.p = best; op.target = T0.phi - bd; }
              else { op.p = Q[k][0].userData.p; op.target = T0.phi - md(T0.phi - (aO - op.p * PIT)); }
            }
          }
          const C0 = T0.cur;
          if (C0 && C0.phase === 'rot') {
            const d0 = T0.phi - C0.target, sp = Math.min(1.6, 0.4 + d0 * 2.2);
            T0.phi = d0 > 0.0005 ? Math.max(C0.target, T0.phi - sp * dt) : C0.target; T0.g.rotation.y = -T0.phi;
            if (T0.phi === C0.target) {
              C0.phase = 'xfer';
              if (C0.type === 'in') {
                const o = C0.o, p = C0.p;
                job(o, [V(xI(k), BY, BZE), pw(k, aI)], () => { T0.g.attach(o); o.userData.p = p; T0.pockets[p] = o; Q[k].push(o); T0.cur = null;
                  if (k === 'fg' && Q.fg.length >= CAP.fg) Q.fg.splice(0, CAP.fg - 2).forEach(o2 => { T0.pockets[o2.userData.p] = null; convG.attach(o2); release(o2); }); });
              } else {
                const o = Q[k].shift(); T0.pockets[o.userData.p] = null; convG.attach(o); T0.cur = null; C0.go(o);
              }
            }
          }
          if (T0.cur && T0.cur.type === 'in' && T0.cur.phase === 'rot') T0.cur.o.position.set(xI(k), BY, BZE);
        });
        Object.keys(Q).forEach(k => { B[k] = Q[k].length; });
        {
          const busy = !!(FL.cur || FL.acts.length), fr = (sp) => !sp.box && !sp.res, at = (sp) => sp.box && !sp.res ? sp.box : null;
          const emptySpot = () => [SB.E1, SB.E2].find(fr);
          const emptyBoxAt = () => [SB.ER, SB.E1, SB.E2].find(sp => at(sp) && isEmpty(sp.box));
          if (!busy) {
            let mvp = null;
            if (at(SB.S) && isFull(SB.S.box) && fr(SB.WI)) mvp = [SB.S, SB.WI];
            else if (fr(SB.S) && at(SB.E1) && isEmpty(SB.E1.box)) mvp = [SB.E1, SB.S];
            else if (fr(SB.E1) && at(SB.E2) && isEmpty(SB.E2.box)) mvp = [SB.E2, SB.E1]; // 복귀 줄: WO → E2 → E1 → S 한 칸씩
            else if (at(SB.WO) && isEmpty(SB.WO.box) && !ms.cmm.enroute) { const d0 = fr(SB.E2) ? SB.E2 : fr(SB.E1) ? SB.E1 : null; if (d0) mvp = [SB.WO, d0]; }
            else if (at(SB.ER) && isEmpty(SB.ER.box) && (fr(SB.FG) || fr(SB.S) || emptySpot())) { const d0 = fr(SB.FG) ? SB.FG : fr(SB.S) ? SB.S : emptySpot(); mvp = [SB.ER, d0]; }
            if (!mvp && fr(SB.S)) { const e0 = emptyBoxAt(); if (e0) mvp = [e0, SB.S]; }
            if (!mvp && fr(SB.FG)) { const e0 = emptyBoxAt(); if (e0) mvp = [e0, SB.FG]; }
            if (mvp) { if (mvp[0].box) mvp[0].box.ship = 0; convMove(mvp[0], mvp[1]); }
          }
          convStep(dt);
          { // 개선안 4: FG 만재 → 입고 대기 1.5초 → 상자를 앞(통로)으로 빼고 → 빈 상자를 넣음. 그동안 FG 자리는 잡아 둠(CMM은 기다림)
            const F0 = FGS; F0.t += dt;
            if (F0.ph === 'fill') { const fb = at(SB.FG); if (fb && isFull(fb)) { F0.ph = 'hold'; F0.t = 0; } }
            else if (F0.ph === 'hold' && F0.t > 1.5) { const fb = SB.FG.box; if (fb) { F0.b = fb; SB.FG.box = null; SB.FG.res = true; fb.at = null; F0.ph = 'out'; F0.t = 0; } else F0.ph = 'fill'; }
            else if (F0.ph === 'out') { const b = F0.b; b.g.position.z = SB.FG.z + 2.4 * sm(Math.min(1, F0.t / 1.4));
              if (F0.t >= 1.4) { b.items.forEach((o, i) => { if (o) { b.items[i] = null; convG.attach(o); release(o); } }); F0.ph = 'in'; F0.t = 0; } } // 완제품 입고 = 부품을 거둠, 같은 상자를 빈 상자로 다시 씀
            else if (F0.ph === 'in') { const b = F0.b; b.g.position.z = SB.FG.z + 2.4 * (1 - sm(Math.min(1, F0.t / 1.4))); if (F0.t >= 1.4) { placeBox(b, SB.FG); F0.b = null; F0.ph = 'fill'; } }
          }
          wshStep(dt, !NOWORK.has(st0.wsh));
          whStep(dt);
          B.w3 = cnt(SB.S.box); B.w4 = cnt(SB.WO.box) + (WSH.box ? cnt(WSH.box) : 0); B.fg = cnt(SB.FG.box);
          const carryS = !!FL.carry && FL.cur?.dst === SB.WI;
          const sN = SB.S.box ? cnt(SB.S.box) : 0;
          // LOT을 모르는 바스켓(처음 놓인 것·데이터 맞춤으로 채운 것)은 그 자리 설비의 지금 LOT으로
          [[SB.S.box, 'vf1'], [WSH.box, 'wsh'], [SB.WO.box, 'cmm']].forEach(([b, id]) => { if (b && !b.lot && cnt(b)) b.lot = lotOf(id); });
          boxes.forEach(drawTag);
          const sLot = SB.S.box && SB.S.box.lot ? ' · LOT ' + String(SB.S.box.lot).replace(/^LOT-\d+-/, '') : '';
          gS(carryS ? BCAP : sN, carryS ? '컨베이어 → 세척기 이송' : isFull(SB.S.box) ? '배치 완료 · 세척기로 이송' : SB.S.box && SB.S.box.closed ? `LOT 끝 · ${sN}개로 세척` : !SB.S.box ? '빈 박스 대기' : 'WIP-3' + sLot, carryS || isFull(SB.S.box) || (SB.S.box && SB.S.box.closed) ? '#22d36b' : '#4fd2ea');
          const wN = SB.WO.box ? cnt(SB.WO.box) : 0;
          gW(WSH.box ? cnt(WSH.box) : wN, WSH.ph === 'in' ? '세척기 투입' : WSH.ph === 'wash' ? '세척 · 헹굼 · 건조 중' : WSH.ph === 'out' ? '세척 완료 · 배출' : '', WSH.box ? '#5fb8ff' : '#4fd2ea');
          const fN = SB.FG.box ? cnt(SB.FG.box) : 0;
          this.fgBoxN = fN; // 입고 박스 개수는 검은 3D 판 대신 바닥 FG-01 글자로 (사용자 요청 2026-10-20)
          FM.beacon.color.setHex(busy && Math.sin(performance.now() / (FL.rev ? 70 : 140)) > 0 ? 0xffd27a : 0xff9a1f);
        }
        inclines.forEach(I0 => { const run0 = !NOWORK.has(st0[Object.keys(MC).find(k => MC[k] === I0.id)]); if (run0) { let z0 = I0.cg.position.z + I0.dir * 0.6 * dt; z0 = ((z0 % CSP) + CSP) % CSP; I0.cg.position.z = z0; } });
        ports.forEach(P0 => {
          let near = false;
          for (const J of jobs) { const p = J.o.position; if (p.y < (P0.yTop || TOP + 0.3) && Math.abs(p.x - P0.x) < 0.3 && p.z < P0.z + 0.42 && p.z > P0.zIn - 0.05) { const dz = Math.abs(p.z - P0.z); if (dz < 0.42) { near = true; break; } } }
          P0.o += ((near ? 1 : 0) - P0.o) * Math.min(1, dt * 7);
          P0.sh.position.y = P0.y0 + P0.o * (P0.lift || 0.3);
          P0.lampM.color.setHex(near ? 0xffb020 : 0x22d36b);
        });
        for (let j = jobs.length - 1; j >= 0; j--) {
          const J = jobs[j]; J.t += dt;
          while (J.seg < J.durs.length && J.t >= J.durs[J.seg]) { J.t -= J.durs[J.seg]; J.seg++; }
          if (J.seg >= J.durs.length) { J.o.position.copy(J.pts[J.pts.length - 1]); J.o.userData.grip.visible = false; jobs.splice(j, 1); J.done(); continue; }
          const A0 = J.pts[J.seg], B0 = J.pts[J.seg + 1];
          J.o.position.copy(A0).lerp(B0, sm(J.t / J.durs[J.seg]));
          gripAt(J.o, false);
        }
      };
      this.convHide = (hide) => {
        jobs.forEach(J => { J.o.visible = !hide; if (hide) J.o.userData.grip.visible = false; });
        Object.values(ms).forEach(S => { if (S.waiting) S.waiting.visible = !hide; });
        Object.values(Q).forEach(q => q.forEach(o => { o.visible = !hide; }));
        boxes.forEach(b => b.items.forEach(o => { if (o) o.visible = !hide; }));
        Object.values(TT).forEach(T0 => { T0.ops.forEach(o0 => { if (o0.o) o0.o.visible = !hide; }); if (T0.cur && T0.cur.o) T0.cur.o.visible = !hide; });
      };
      // 데이터적용본: 재공 자리의 부품 수를 데이터 재공 수에 맞춘다 (1.2초마다).
      // shortcut: 회전 재공 테이블은 원본 모델이라 11개, 상자는 30칸까지만 보인다 — 숫자는 재공 카드·2D 패널이 데이터 그대로 보인다
      this.reconcile = () => {
        const W = this.state.wip || {};
        ['w1', 'w2'].forEach(k => {
          const T0 = TT[k]; if (!T0) return;
          const want = Math.max(0, Math.min(CAP[k] - 1, Math.round(W[k] || 0)));
          while (Q[k].length < want) {
            let p = -1; for (let i = 0; i < NP; i++) if (!T0.pockets[i]) { p = i; break; }
            if (p < 0) break;
            const o = getItem(matOf(k)); T0.g.add(o); o.position.set(TRAD * Math.cos(p * PIT), BY, TRAD * Math.sin(p * PIT)); o.userData.p = p; T0.pockets[p] = o; Q[k].push(o);
          }
          while (Q[k].length > want && Q[k].length > (T0.outPending ? 1 : 0)) { const o = Q[k].pop(); T0.pockets[o.userData.p] = null; convG.attach(o); release(o); }
        });
        const fillBox = (sp, n0, k) => {
          const b = sp.box; if (!b || sp.res || b.res.size || b.closed) return; // LOT 끝으로 닫힌 바스켓엔 더 안 넣음
          const want = Math.max(0, Math.min(BCAP, Math.round(n0 || 0))); let n = cnt(b);
          for (let i = 0; i < BCAP && n < want; i++) if (!b.items[i]) { const o = getItem(pallets[k][0].material); b.g.add(o); o.position.copy(slotL(i)); b.items[i] = o; n++; }
          for (let i = BCAP - 1; i >= 0 && n > want; i--) if (b.items[i]) { const o = b.items[i]; b.items[i] = null; convG.attach(o); release(o); n--; }
        };
        fillBox(SB.S, W.w3, 'w3');
        if (!WSH.box) fillBox(SB.WO, W.w4, 'w4');
      };
      this.convAPI = { inS, boxPath: (c) => { const b = SB.S.box; let n = 0; if (b) while (n < BCAP - 1 && b.items[n]) n++; const sw = slotW(SB.S, n); return [...outPath(c), lane(SB.S.x - 0.78), sw]; },
        fgPath: (c) => { const b = SB.FG.box; let n = 0; if (b) while (n < BCAP - 1 && b.items[n]) n++; const sw = slotW(SB.FG, n); return [...outPath(c), lane(FEX), V(FEX, BY, GAPZ), V(FEX, BY, FRZ), V(sw.x, BY, FRZ), sw]; }, MC, WX, BY, lane, bufIn, bufOut, pw, aI, aO, PIT, Q, isAir, inEnd, loadPath, outPath, mkGrip, gripAt, SB, WZIN: D3 ? D3.wz : -4.45 };
    } catch (e) { console.error('[factory] conveyor', e); }
    const convPos = new THREE.Vector3();

    smoke = emitter(0x7d868f, 220, 0.13, 0.32); sparkFx = emitter(0xffa040, 160, 0.03);
    const hero = new THREE.Group(); hero.visible = false; scene.add(hero);
    const HM = { raw: M(0xaab1b8, { metalness: 0.35, roughness: 0.5 }), cut: M(0xd0d7dd, { metalness: 0.55, roughness: 0.28 }), shine: M(0xf4f8fb, { metalness: 0.6, roughness: 0.12 }), dark: M(0x262c33, { roughness: 0.6 }) };
    const forms = [];
    // 데이터적용본 투어 부품 (보기 쉽게 실제의 2배): 평각봉 → 152 토막 → 황삭 → 정삭(Ø45 H7 + M6 4개) → 측정 합격
    { const g0 = new THREE.Group(); mesh(new THREE.BoxGeometry(0.9, 0.038, 0.114), HM.raw, g0); forms.push(g0); }
    { const g0 = new THREE.Group(); mesh(new THREE.BoxGeometry(0.304, 0.038, 0.114), HM.raw, g0); forms.push(g0); }
    { const g0 = new THREE.Group(); mesh(new THREE.BoxGeometry(0.302, 0.038, 0.112), HM.raw, g0); mesh(new THREE.BoxGeometry(0.3, 0.004, 0.11), HM.shine, g0, 0, 0.021, 0); forms.push(g0); }
    const machined = (m1) => {
      const g0 = new THREE.Group();
      mesh(new THREE.BoxGeometry(0.3, 0.024, 0.11), m1, g0);
      mesh(new THREE.BoxGeometry(0.298, 0.004, 0.108), HM.shine, g0, 0, 0.013, 0);
      mesh(new THREE.CylinderGeometry(0.045, 0.045, 0.006, 32), HM.dark, g0, 0, 0.015, 0);
      [[-0.11, -0.036], [0.11, -0.036], [0.11, 0.036], [-0.11, 0.036]].forEach(([x, z]) => mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.006, 12), HM.dark, g0, x, 0.015, z));
      return g0;
    };
    forms.push(machined(HM.cut)); forms.push(machined(HM.shine));
    { const g0 = machined(HM.shine); const ok = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.009, 8, 64), new THREE.MeshBasicMaterial({ color: 0x22d36b })); ok.rotation.x = Math.PI / 2; ok.position.y = -0.03; g0.add(ok); forms.push(g0); }
    forms.forEach(f0 => { f0.visible = false; hero.add(f0); });
    const heroLight = new THREE.PointLight(0x9fe8ff, 0, 2.4, 1.4); heroLight.position.y = 0.4; hero.add(heroLight);
    const heroRing = new THREE.Mesh(new THREE.RingGeometry(0.2, 0.235, 48), new THREE.MeshBasicMaterial({ color: 0x29c6e6, transparent: true, opacity: 0.8, depthWrite: false, side: THREE.DoubleSide }));
    heroRing.rotation.x = -Math.PI / 2; heroRing.position.y = -0.085; hero.add(heroRing);
    const V3 = (x, y, z) => new THREE.Vector3(x, y, z);
    const arcP = (A, W, B) => {
      const up = (p, k) => p.clone().add(V3(0, k, 0));
      const pts = [A, up(A, 0.45)];
      if (W) pts.push(up(W, 0.35), W, up(W, 0.35)); else pts.push(A.clone().lerp(B, 0.5).add(V3(0, 0.8, 0)));
      pts.push(up(B, 0.45), B);
      return new THREE.CatmullRomCurve3(pts, false, 'centripetal');
    };
    const lineP = (A, B) => new THREE.LineCurve3(A, B);
    // 데이터적용본: 투어 지점도 옮긴 설비·데이터 재공 자리로
    const PLP = (id, v) => this.placePt(id, v), WZ = (k, d) => (this.LY ? (k === 'fg' ? this.LY.fg : this.LY.wip[k]) : d);
    const T_INF0 = PLP('inf', V3(1.2, 0.92, -4.35)), T_INF1 = PLP('inf', V3(4.4, 0.92, -4.35)), T_SAW = PLP('saw', V3(5.5, 0.92, -4.35)), T_W1 = V3(WZ('w1', 6.75), 0.56, -2.4), T_MIL = PLP('mil', V3(7.8, 1.25, -4.35)),
      T_W2 = V3(WZ('w2', 11.9), 0.56, -2.4), T_VF = PLP('vf1', V3(11.18, 1.13, -4.35)), T_W3 = V3(WZ('w3', 14.3), 0.56, -2.4), T_WS0 = PLP('wsh', V3(17.1, 0.8, -4.5)), T_WS1 = PLP('wsh', V3(20.5, 0.8, -4.5)),
      T_W4 = V3(WZ('w4', 20.8), 0.56, -2.4), T_CMM = PLP('cmm', V3(22.5, 1.12, -4.4)), T_FG = V3(WZ('fg', 24.0), 0.56, -2.4);
    const tourPaths = [lineP(T_INF0, T_INF1), lineP(T_INF1, T_SAW), arcP(T_SAW, T_W1, T_MIL), lineP(T_MIL, T_MIL.clone()), arcP(T_MIL, T_W2, T_VF), lineP(T_VF, T_VF.clone()),
      arcP(T_VF, T_W3, T_WS0), lineP(T_WS0, T_WS1), arcP(T_WS1, T_W4, T_CMM), lineP(T_CMM, T_CMM.clone()), arcP(T_CMM, null, T_FG)];
    const CA = this.convAPI;
    const poly = (pts) => {
      const cp = new THREE.CurvePath(); const clean = [pts[0]];
      for (let i = 1; i < pts.length; i++) if (pts[i].distanceTo(clean[clean.length - 1]) > 1e-4) clean.push(pts[i]);
      for (let i = 1; i < clean.length; i++) cp.add(new THREE.LineCurve3(clean[i - 1], clean[i]));
      cp.isPoly = true; return cp;
    };
    const heroGrip = CA ? CA.mkGrip() : null;
    const heroShim = { position: hero.position, userData: { grip: heroGrip } };
    this.buildTourPaths = () => {
      if (!CA) return;
      const { MC, lane, bufIn, bufOut, pw, aI, aO, PIT, inEnd, loadPath, outPath } = CA;
      const xfer = (from, k, to) => {
        const c0 = MC[from];
        const pts = [...outPath(c0), ...bufIn(k), pw(k, aI)];
        if (to) { for (let a = aI - PIT / 2; a > aO - Math.PI * 2 + 1e-3; a -= PIT / 2) pts.push(pw(k, a)); pts.push(...bufOut(k), lane(MC[to].xi), CA.inS(MC[to]), ...loadPath(MC[to])); }
        else for (let a = aI - PIT / 2; a >= aI - PIT * 3; a -= PIT / 2) pts.push(pw(k, a));
        return poly(pts);
      };
      const L = (id) => MC[id].load.clone();
      tourPaths[1] = lineP(T_INF1, L('saw'));
      tourPaths[2] = xfer('saw', 'w1', 'mil'); tourPaths[3] = lineP(L('mil'), L('mil'));
      tourPaths[4] = xfer('mil', 'w2', 'vf1'); tourPaths[5] = lineP(L('vf1'), L('vf1'));
      tourPaths[6] = poly([...CA.boxPath(MC.vf1)]);
      const wi = CA.SB.WI.x, wo = CA.SB.WO.x, wz = CA.WZIN;
      tourPaths[7] = lineP(new THREE.Vector3(wi, CA.BY, wz), new THREE.Vector3(wo, CA.BY, wz));
      tourPaths[8] = poly([new THREE.Vector3(wo, CA.BY, wz), new THREE.Vector3(wo, CA.BY, -3.1), new THREE.Vector3(wo + 0.72, CA.BY, -3.1), lane(wo + 0.9), lane(MC.cmm.xi), CA.inS(MC.cmm), ...[inEnd(MC.cmm)], ...loadPath(MC.cmm)]);
      tourPaths[9] = lineP(L('cmm'), L('cmm'));
      tourPaths[10] = poly(CA.fgPath(MC.cmm));
      [2, 4, 6, 8, 10].forEach(i => { this.TOUR[i].dur = Math.max(5, tourPaths[i].getLength() / 0.75); this.TOUR[i].mv = 'arc'; });
    };
    const tourChips = emitter(0xd8dee4, 140, 0.022), tourWater = emitter(0x6fbef5, 200, 0.02, 0.8);
    const markRig = (o) => { if (o && o.isObject3D) o.userData.rig = true; };
    Object.values(rigs).forEach(R => { if (Array.isArray(R)) R.forEach(markRig); else if (R && typeof R === 'object') Object.values(R).forEach(v0 => { if (Array.isArray(v0)) v0.forEach(markRig); else markRig(v0); }); });
    const agvG = new THREE.Group(); scene.add(agvG);
    const lanePts = []; for (let X = 1.0; X <= 24.2; X += 2.32) lanePts.push(V3(X, 0, -1.72)); lanePts.push(V3(24.75, 0, -2.4));
    for (let X = 24.2; X >= 1.0; X -= 2.32) lanePts.push(V3(X, 0, -3.08)); lanePts.push(V3(0.45, 0, -2.4));
    const lane = new THREE.CatmullRomCurve3(lanePts, true, 'centripetal');
    const ribTex = cvTex(64, 8, (g) => { g.fillStyle = 'rgba(79,210,234,0.15)'; g.fillRect(0, 0, 64, 8); g.fillStyle = 'rgba(120,235,255,0.95)'; g.fillRect(0, 0, 24, 8); });
    ribTex.wrapS = THREE.RepeatWrapping; const laneLen = lane.getLength(); ribTex.repeat.set(laneLen / 0.6, 1);
    const rib = new THREE.Mesh(new THREE.TubeGeometry(lane, 400, 0.07, 6, true), new THREE.MeshBasicMaterial({ map: ribTex, transparent: true, depthWrite: false, opacity: 0.9 }));
    rib.scale.y = 0.04; rib.position.y = 0.012; agvG.add(rib);
    const agvBody = M(0xe9edf0, { roughness: 0.35 }), agvAcc = M(0xf0b429, { roughness: 0.4 });
    const agvs = [0, 0.33, 0.66].map((u0, i) => {
      const a0 = new THREE.Group(); agvG.add(a0);
      mesh(new THREE.BoxGeometry(0.74, 0.16, 0.5), agvBody, a0, 0, 0.1, 0);
      mesh(new THREE.BoxGeometry(0.76, 0.05, 0.52), mat.dark, a0, 0, 0.03, 0);
      mesh(new THREE.BoxGeometry(0.6, 0.03, 0.44), agvAcc, a0, 0, 0.195, 0);
      mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.07, 18), mat.dark, a0, 0.3, 0.24, 0);
      const ledM = new THREE.MeshBasicMaterial({ color: 0x4fd2ea }); mesh(new THREE.BoxGeometry(0.02, 0.03, 0.4), ledM, a0, 0.375, 0.1, 0);
      if (i !== 1) { mesh(new THREE.BoxGeometry(0.5, 0.06, 0.38), mat.wood, a0, -0.03, 0.24, 0); for (let k = 0; k < 4; k++) mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.1, 16), mat.part, a0, -0.16 + (k % 2) * 0.26, 0.32, -0.09 + Math.floor(k / 2) * 0.18); }
      return { g: a0, u: u0 };
    });
    const holoG = new THREE.Group(); scene.add(holoG); holoG.visible = false;
    const holos = {};
    this.ORDER.forEach(id => {
      const b = this.MACH[id].bd || this.MACH[id].b, c = document.createElement('canvas'); c.width = 320; c.height = 128;
      const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
      sp.scale.set(2.6, 1.04, 1); sp.position.set((b[0] + b[1]) / 2000, b[5] + 1.05, -(b[2] + b[3]) / 2000); holoG.add(sp);
      const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.55, 8), new THREE.MeshBasicMaterial({ color: 0x4fd2ea, transparent: true, opacity: 0.6 }));
      beam.position.set(sp.position.x, b[5] + 0.3, sp.position.z); holoG.add(beam);
      holos[id] = { c, tex, sp, beam };
    });
    const STC = { RUN: '#34d27a', WARN: '#ffb020', ALARM: '#ff4d4d', IDLE: '#9aa7b4', SETUP: '#5b9cff' };
    const holoDraw = (effOf) => {
      this.ORDER.forEach(id => {
        const H = holos[id], g = H.c.getContext('2d'), e0 = effOf(id), col = STC[e0] || STC.RUN;
        const load = e0 === 'RUN' || e0 === 'WARN' ? ((this.state.m[id] || [])[0] ?? ({ inf: 42, mil: 71, cmm: 48 })[id] ?? 60) : 0;
        g.clearRect(0, 0, 320, 128);
        g.fillStyle = 'rgba(8,16,24,0.62)'; g.beginPath(); g.roundRect(4, 8, 312, 112, 18); g.fill();
        g.strokeStyle = 'rgba(79,210,234,0.55)'; g.lineWidth = 2; g.stroke();
        g.lineWidth = 9; g.strokeStyle = 'rgba(79,210,234,0.18)'; g.beginPath(); g.arc(64, 64, 36, 0, Math.PI * 2); g.stroke();
        g.strokeStyle = col; g.shadowColor = col; g.shadowBlur = 14; g.beginPath(); g.arc(64, 64, 36, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.max(0.02, load / 100)); g.stroke(); g.shadowBlur = 0;
        g.fillStyle = '#eafcff'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.font = '700 22px "Pretendard Variable", sans-serif'; g.fillText(load + '%', 64, 65);
        g.textAlign = 'left'; g.font = '700 26px "Pretendard Variable", sans-serif'; g.fillText(this.MACH[id].name, 118, 50);
        g.font = '600 18px "Pretendard Variable", sans-serif'; g.fillStyle = col; g.fillText((this.STAT[e0] || this.STAT.RUN).label + ' · ' + this.MACH[id].op, 118, 84);
        H.tex.needsUpdate = true; H.beam.material.color.set(col);
      });
    };
    const heatCv = document.createElement('canvas'); heatCv.width = 512; heatCv.height = 164;
    const heatTex = new THREE.CanvasTexture(heatCv); heatTex.colorSpace = THREE.SRGBColorSpace;
    const heat = new THREE.Mesh(new THREE.PlaneGeometry(28, 8), new THREE.MeshBasicMaterial({ map: heatTex, transparent: true, opacity: 0.85, depthWrite: false }));
    heat.rotation.x = -Math.PI / 2; heat.position.set(14, 0.022, -4); heat.visible = false; scene.add(heat);
    const heatDraw = (effOf) => {
      const g = heatCv.getContext('2d'); g.clearRect(0, 0, 512, 164); g.globalCompositeOperation = 'lighter';
      this.ORDER.forEach(id => {
        const b = this.MACH[id].bd || this.MACH[id].b, e0 = effOf(id);
        const load = e0 === 'ALARM' ? 100 : e0 === 'IDLE' ? 12 : e0 === 'WARN' ? 92 : ((this.state.m[id] || [])[0] ?? ({ inf: 40, mil: 70, cmm: 45 })[id] ?? 60);
        const cx = ((b[0] + b[1]) / 2) / 28000 * 512, cy = 164 - (((b[2] + b[3]) / 2) / 8000) * 164, k = load / 100, rad = 34 + load * 0.55;
        const gr = g.createRadialGradient(cx, cy, 0, cx, cy, rad);
        gr.addColorStop(0, 'rgba(255,' + Math.round(210 - 170 * k) + ',40,' + (0.3 + 0.6 * k).toFixed(2) + ')');
        gr.addColorStop(0.5, 'rgba(255,190,40,' + (0.12 + 0.3 * k).toFixed(2) + ')');
        gr.addColorStop(1, 'rgba(40,200,240,0)'); g.fillStyle = gr; g.beginPath(); g.arc(cx, cy, rad, 0, Math.PI * 2); g.fill();
      });
      g.globalCompositeOperation = 'source-over'; heatTex.needsUpdate = true;
    };
    let lastM = null, lastSt = null;
    const dirV = new THREE.Vector3(), cvec = new THREE.Vector3(), aT = new THREE.Vector3();
    // picking
    const ray = new THREE.Raycaster(), ndc = new THREE.Vector2(), el = renderer.domElement;
    const pick = (e) => {
      const r = el.getBoundingClientRect();
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ndc, camera);
      const hit = ray.intersectObjects(pickables, false)[0];
      return hit ? hit.object.userData.mid : null;
    };
    let down = null;
    el.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY]; });
    el.addEventListener('pointerup', e => {
      if (!this.intro && !this.tour.on && down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 5) { const id = pick(e); if (id) this.select(id); }
      down = null;
    });
    el.addEventListener('pointermove', e => {
      if (e.buttons) return;
      const id = pick(e);
      if (EMB) { el.style.cursor = id ? 'pointer' : 'grab'; return; }
      if (id !== this.hover) { this.hover = id; el.style.cursor = id ? 'pointer' : 'grab'; }
    });

    const clamp01 = (v) => Math.max(0, Math.min(1, v));
    const seg = (p, a, b) => clamp01((p - a) / (b - a));
    const ease = (s) => s * s * (3 - 2 * s);
    const tmpV = new THREE.Vector3(), tgtV = new THREE.Vector3();
    const clock = new THREE.Clock(), v = new THREE.Vector3(), a = new THREE.Vector3(), b = new THREE.Vector3();
    let uiAcc = 0;

    const animate = (dt, t) => {
      (this.floorWip || []).forEach(F => { // 바닥 재공 글자: 값이 바뀔 때만 다시 그림
        if (!F.m.parent) scene.add(F.m); // 장면 정리 때 떨어져 나가면 다시 붙임
        const n = F.key === 'fg' ? this.fgBoxN || 0 : Math.round(((this.state.wip || {})[F.key]) || 0), L0 = F.code && (this.state.wipLimits || {})[F.code], lim = L0 ? L0.limit : 30;
        const hot = !!(L0 && L0.warn && L0.warn_over != null && n > L0.warn_over), nd = this.liveT == null, k = `${n}|${lim}|${hot}|${nd}`;
        if (k === F.last) return; F.last = k;
        const c = F.cv.getContext('2d'); c.clearRect(0, 0, 512, 128);
        const col = F.code ? (hot ? '#c2570c' : '#2a323b') : '#1f7a45';
        c.globalAlpha = 1; c.fillStyle = col; c.textBaseline = 'alphabetic';
        c.font = '800 34px "Pretendard Variable", sans-serif'; const lab = F.code ? F.name : `${F.name} 입고 박스`; c.fillText(lab, 12, 92); let x = 24 + c.measureText(lab).width;
        c.font = '700 84px "Pretendard Variable", sans-serif'; const num = nd ? '—' : String(n); c.fillText(num, x, 96); x += c.measureText(num).width + 8;
        if (!nd) { c.globalAlpha = 0.75; c.font = '600 40px "Pretendard Variable", sans-serif'; c.fillText(`/${lim}`, x, 96); }
        F.tex.needsUpdate = true;
      });
      const ph = (id) => this.phOf(id);
      const run = (id) => this.state.st[id] === 'RUN';
      const pres = (id) => {
        if (this.tour.on) return false;
        if (this.props.dataMode) { const E = this.liveT && this.liveT.equipment[this.EQ_OF[id]]; return !!(E && E.parts_in > 0); } // 데이터: 설비 안에 부품이 있을 때만
        const S0 = this.msRef && this.msRef[id]; return !S0 || (S0.loaded && S0.inPlace !== false);
      };
      const pv = (id, p) => this.blocked(id) ? 0.97 : p;
      // INF + SAW
      const ps = ph('saw');
      if (rigs.rollers && ps < 0.2 && run('inf')) rigs.rollers.forEach(r => { r.rotation.y += dt * 8; });
      const S = rigs.saw;
      if (S) {
        const cl = ps < 0.2 ? 0 : ps < 0.3 ? ease(seg(ps, 0.2, 0.3)) : ps < 0.8 ? 1 : 1 - ease(seg(ps, 0.8, 0.9));
        S.jaw.position.z = -cl * 0.055;
        const dy = ps < 0.3 ? 0.42 : ps < 0.75 ? 0.42 * (1 - ease(seg(ps, 0.3, 0.75))) : ps < 0.9 ? 0.42 * ease(seg(ps, 0.75, 0.9)) : 0.42;
        S.head.position.y = dy;
        const cutting = ps > 0.3 && ps < 0.75;
        if (ps > 0.25 && ps < 0.88 && run('saw')) S.wheels.forEach(w => { w.rotation.x -= dt * 14; });
        S.piece.visible = ps > 0.72 || ps < 0.02;
        S.piece.position.x = S.piece.userData.x0 + (ps > 0.9 ? ease(seg(ps, 0.9, 1)) * 0.55 : 0);
        S.piece.position.y = 0.875 - (ps > 0.95 ? seg(ps, 0.95, 1) * 0.35 : 0);
        if (cutting && dy < 0.06 && run('saw')) S.sparks.spawn(tmpV.set(5.6, 0.9, -4.36), 160, dt, 0.9, 1.2, 0.5);
        S.sparks.step(dt, 6, 0.8);
      }
      // MIL
      const Mi = rigs.mil;
      if (Mi) {
        const p = ph('mil');
        const dz = p < 0.12 ? 0.3 : p < 0.22 ? 0.3 * (1 - ease(seg(p, 0.12, 0.22))) : p < 0.8 ? 0 : p < 0.9 ? 0.3 * ease(seg(p, 0.8, 0.9)) : 0.3;
        Mi.head.position.y = dz - 0.18; // 공작물 윗면 1.019 m (원본 1.2 m)
        const cut = p > 0.22 && p < 0.8;
        Mi.table.position.x = cut ? Math.sin(seg(p, 0.22, 0.8) * Math.PI * 4) * 0.16 : Mi.table.position.x * 0.9;
        if (p > 0.1 && p < 0.88 && run('mil')) Mi.tool.rotation.y += dt * 30;
        const tip = tmpV.set(7.8, 1.019, -4.35);
        if (cut && run('mil')) { Mi.chips.spawn(tip, 120, dt, 1.1, 0.9, 0.6); Mi.cool.spawn(tgtV.set(7.93, 1.3, -4.3), 180, dt, 0.3, -0.6, 0.5); }
        Mi.chips.step(dt, 5, 0.95); Mi.cool.step(dt, 4, 0.95);
        if (Mi.parts) {
          const v0 = pres('mil'), q = pv('mil', p), pr = q < 0.22 ? 0 : q < 0.8 ? seg(q, 0.22, 0.8) : 1;
          Mi.parts.forEach(m0 => { m0.visible = v0; });
          Mi.raw.visible = v0 && pr < 0.995; Mi.raw.scale.x = Math.max(0.001, 1 - pr); Mi.raw.position.x = Mi.rawX1 - Mi.rawW * (1 - pr) / 2;
        }
      }
      // VF2
      ['vf1', 'vf2'].forEach(id => {
        const R = rigs[id]; if (!R) return;
        const p = ph(id);
        let ox = 0.3, dz = 0.4, oz = 0;
        if (p < 0.1) { ox = 0.3; dz = 0.4; }
        else if (p < 0.2) { ox = -((R.wc - R.x0 - 250) / 1000); dz = 0.45; }
        else if (p < 0.55) { const s = seg(p, 0.2, 0.55); const r = 0.004 + 0.018 * s, an = s * Math.PI * 10; ox = r * Math.cos(an); oz = r * Math.sin(an); dz = 0; }
        else if (p < 0.85) {
          const s = seg(p, 0.55, 0.85);
          if (s < 0.5) { const u = (s * 2 * 4) % 4, q = u % 1, hx = 0.075, hz = 0.028, side = Math.floor(u);
            const pts = [[-hx, -hz], [hx, -hz], [hx, hz], [-hx, hz], [-hx, -hz]];
            ox = pts[side][0] + (pts[side + 1][0] - pts[side][0]) * q; oz = pts[side][1] + (pts[side + 1][1] - pts[side][1]) * q; dz = 0; }
          else { const u = (s - 0.5) * 2 * 4, hi = Math.min(3, Math.floor(u)), q = u - hi;
            const hp = [[-0.055, -0.018], [0.055, -0.018], [0.055, 0.018], [-0.055, 0.018]][hi];
            ox = hp[0]; oz = hp[1]; dz = 0.06 - 0.1 * Math.sin(q * Math.PI); }
        }
        if (!run(id)) { ox = 0.3; dz = 0.45; oz = 0; }
        const k = Math.min(1, dt * 7);
        R.o.x += (ox - R.o.x) * k; R.o.y += (dz - R.o.y) * k; R.o.z += (-oz - R.o.z) * k;
        R.head.position.set(R.o.x, R.o.y - 0.188, R.o.z); // 공작물 윗면 0.862 m (원본 1.05 m)에 공구 끝을 맞춤
        if (p > 0.1 && p < 0.2 && run(id)) R.car.rotation.x += dt * 2.5;
        if (p > 0.18 && p < 0.86 && run(id)) R.tool.rotation.y += dt * 40;
        const tip = tmpV.set(R.wc / 1000 + R.o.x, 0.862 + R.o.y, -4.35 + R.o.z);
        if (p > 0.2 && p < 0.85 && R.o.y < 0.07 && run(id)) {
          R.chips.spawn(tip, 140, dt, 1.0, 1.0, 0.6);
          R.cool.spawn(tgtV.set(tip.x + 0.12, tip.y + 0.18, tip.z + 0.05), 160, dt, 0.25, -0.7, 0.45);
        }
        if (p > 0.86 && p < 0.96 && run(id)) R.air.spawn(tgtV.set(R.wc / 1000, 1.15, -4.35), 120, dt, 1.4, 0.4, 0.5);
        R.chips.step(dt, 5, 0.8); R.cool.step(dt, 4, 0.8); R.air.step(dt, -0.5, 0.8);
        if (R.parts) {
          const v0 = pres(id), q = pv(id, p);
          R.parts.forEach(m0 => { m0.visible = v0; });
          const pr = q < 0.2 ? 0 : q < 0.55 ? seg(q, 0.2, 0.55) : 1, cs = q < 0.55 ? 0 : q < 0.85 ? seg(q, 0.55, 0.85) : 1;
          const rr = 0.004 + 0.0185 * pr, dep = Math.max(0.002, 0.0125 * pr); // Ø45 H7 관통 보링
          R.pocket.visible = v0 && pr > 0.005; R.pocket.scale.set(rr, dep, rr); R.pocket.position.y = 0.8635 - dep / 2;
          const cn = Math.min(1, cs * 2) * 4; R.strips.forEach((m0, i) => { m0.visible = v0 && cn > i + 0.15; });
          const hn = cs < 0.5 ? 0 : (cs - 0.5) * 2 * 4; R.holes.forEach((m0, i) => { m0.visible = v0 && hn > i + 0.55; });
        }
      });
      // WSH
      const Ws = rigs.wsh;
      if (Ws) {
        const p = ph('wsh');
        // 사용자 요청 2026-10-19: 빈 바구니가 혼자 도는 연출 없앰 — 3공정에서 온 상자가 안에 들어왔을 때만 물·김이 나옴
        const wOn = this.props.dataMode ? !!this.wshBusy : run('wsh');
        Ws.baskets.forEach((g, i) => { g.visible = !this.props.dataMode; g.position.x = 17.15 + ((p + i / 3) % 1) * 3.3; });
        const wa = this.props.dataMode && this.wshAt; // 데이터 화면: 물은 지금 씻기는 상자 위로
        if (wOn) (wa ? [-0.35, 0, 0.35].map(dx => wa.x + dx) : [17.95, 18.4, 19.0]).forEach(X => (wa ? [-0.3, 0, 0.3].map(dz => wa.z + dz) : [-4.25, -4.5, -4.75]).forEach(Z => Ws.water.spawn(tmpV.set(X, 1.21, Z), 40, dt, 0.35, -1.6, 0.6)));
        Ws.water.step(dt, 6, 0.6);
        if (wOn) Ws.mist.spawn(wa ? tmpV.set(wa.x + 0.6, 0.98, wa.z) : tmpV.set(19.6, 0.98, -4.5), 80, dt, 0.9, -0.3, 0.6);
        Ws.mist.step(dt, -0.2, 0.55);
      }
      // CMM
      const C = rigs.cmm;
      if (C) {
        const p = ph('cmm'); const cx = 22.5, cz = -4.4;
        let X = 22.5, Z = -5.0, H = 1.6, touch = false;
        // 측정 순서: Ø45 H7 구멍 → 길이·폭(옆면) → 두께·평면도(윗면 줄 스캔)
        if (p < 0.15) { const s = ease(seg(p, 0, 0.15)); X = cx; Z = -5.0 + (cz + 5.0) * s; H = 1.6 - 0.6 * s; }
        else if (p < 0.4) { const s = seg(p, 0.15, 0.4), an = s * Math.PI * 2; X = cx + Math.cos(an) * 0.02; Z = cz + Math.sin(an) * 0.02; H = 0.926; touch = (s * 8) % 1 < 0.35; }
        else if (p < 0.65) { const s = seg(p, 0.4, 0.65), an = s * Math.PI * 2; const lift = s < 0.08 ? 1 : 0; X = cx + Math.cos(an) * 0.077; Z = cz + Math.sin(an) * 0.029; H = lift ? 1.0 : 0.926; touch = !lift && (s * 8) % 1 < 0.35; }
        else if (p < 0.88) { const s = seg(p, 0.65, 0.88), row = Math.min(2, Math.floor(s * 3)), q = (s * 3) % 1; X = cx + (row % 2 ? 0.065 - q * 0.13 : -0.065 + q * 0.13); Z = cz + (row - 1) * 0.02; H = 0.933; touch = true; if (Math.hypot(X - cx, Z - cz) < 0.024) H = 0.94; }
        else { const s = ease(seg(p, 0.88, 1)); X = cx; Z = cz + (-5.0 - cz) * s; H = 1.25 + 0.35 * s; }
        const k = Math.min(1, dt * 6);
        C.tip.x += (X - C.tip.x) * k; C.tip.z += (Z - C.tip.z) * k; C.tip.y += (H - C.tip.y) * k;
        C.bridge.position.z = C.tip.z + C.ym / 1000;
        C.carr.position.x = C.tip.x - 22.5;
        C.ram.position.y = C.tip.y - 1.085;
        if (C.parts) { const v0 = pres('cmm'); C.parts.forEach(m0 => { m0.visible = v0; }); }
        C.probeM.color.setHex(touch ? 0x22d36b : 0xff3b30); C.probeM.emissive.setHex(touch ? 0x22d36b : 0xff3b30);
      }
    };

    const CC = { bgD: new THREE.Color(0x7a8998), bgN: new THREE.Color(0x0a0f15), black: new THREE.Color(0x05080c), flD: new THREE.Color(0x95a3b0), flN: new THREE.Color(0x10161d),
      inD: new THREE.Color(0xb3bec8), inN: new THREE.Color(0x151d26), wlD: new THREE.Color(0x6c7b8a), wlN: new THREE.Color(0x0c1117), coD: new THREE.Color(0x5fdcf2), coN: new THREE.Color(0x8ff4ff) };
    const cA = new THREE.Color(), heroPos = new THREE.Vector3(), fxOff = new THREE.Vector3(), camOff = new THREE.Vector3(), camGoal = new THREE.Vector3(), yAxis = new THREE.Vector3(0, 1, 0);
    const backOut = (x) => { const c1 = 1.4, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
    // 그림자 줄이기 (사용자 요청 2026-10-20 "그림자 줄이는 것부터"): 반지름 20cm 미만 물체(볼트·롤러·작은 판)는 그림자를 만들지 않음 — 1,715 → 약 840개. 받는 그림자는 그대로
    { const ws = new THREE.Vector3(); scene.traverse(o => { if (!o.isMesh || !o.castShadow || o.isInstancedMesh) return; const g = o.geometry; if (!g.boundingSphere) g.computeBoundingSphere(); o.getWorldScale(ws); if (g.boundingSphere.radius * Math.max(ws.x, ws.y, ws.z) < 0.2) o.castShadow = false; }); }
    const loop = () => {
      if (this.dead) return;
      cancelAnimationFrame(this.raf); this.raf = requestAnimationFrame(loop); this.lastFrame = performance.now();
      fit(); if (!viewSet) return;
      // 데이터적용본: 시연 시계가 일시정지면 3D 움직임도 멈춘다 (카메라 조작은 그대로)
      const FZ = this.props.dataMode && this.frozen ? 0 : 1;
      const rawDt = this.__dtO != null ? (clock.getDelta(), this.__dtO) : clock.getDelta(), dt = Math.min(rawDt, 0.05) * FZ, t = clock.elapsedTime, wallDt = Math.min(rawDt, 0.5);
      this.nightK = (this.nightK || 0) + ((this.state.night ? 1 : 0) - (this.nightK || 0)) * Math.min(1, Math.min(rawDt, 0.05) * 2.5);
      const sp = this.props.dataMode ? 1 : (this.props.flowSpeed ?? 1);
      const flowK = this.props.dataMode ? Math.min(3, Math.max(0.5, (this.speed || 60) / 60)) * FZ : (this.props.flowSpeed ?? 1);
      this.simT += dt * sp;
      const stt = this.state.st, wst = this.state.warn || {};
      const effOf = (id) => stt[id] === 'RUN' && wst[id] ? 'WARN' : stt[id];
      this.ORDER.forEach(id => { if (stt[id] === 'RUN' && this.canWork(id)) this.mt[id] = (this.mt[id] || 0) + dt * sp; });
      const LY = this.state.layers || {};
      flowG.visible = (this.props.showFlow ?? true) && !this.state.sel && LY.flow !== false;
      flows.forEach(f => f.parts.forEach((p, i) => { p.position.copy(f.curve.getPointAt(((this.simT * 1.1) / f.len + i / f.parts.length) % 1)); }));
      const blink = Math.sin(t * 9) > 0 ? 1.8 : 0.05;
      Object.keys(towers).forEach(id => {
        const s0 = effOf(id) || 'RUN', L = towers[id]; if (L.length < 3) return;
        const on = s0 === 'ALARM' ? [blink, 0.05, 0.05] : s0 === 'WARN' ? [0.05, Math.sin(t * 5) > 0 ? 1.6 : 0.1, 0.05] : s0 === 'MAINT' || s0 === 'NODATA' ? [0.05, 0.05, 0.05] : s0 === 'BLOCKED' ? [0.05, 1.2, 0.05] : s0 === 'IDLE' ? [0.05, 0.05, 0.25] : s0 === 'SETUP' ? [0.05, Math.sin(t * 6) > 0 ? 1.4 : 0.1, 0.05] : [0.05, 0.05, 1.1 + Math.sin(t * 3) * 0.4];
        // 처리 안 된 주의 알람이 있으면 신호등 노랑 깜빡임 (멈춤·가공 상태 불은 그대로) — 사용자 요청 2026-10-19
        if (s0 !== 'ALARM' && this.props.warnIds && this.props.warnIds.includes(id)) on[1] = Math.sin(t * 5) > 0 ? 1.6 : 0.1;
        L.forEach((m, i) => { m.emissiveIntensity = on[i]; m.opacity = on[i] > 0.3 ? 0.95 : 0.4; });
      });
      const K = this.keys;
      if (K && K.size && !this.intro && !this.tour.on) {
        const px = (K.has('d') ? 1 : 0) - (K.has('a') ? 1 : 0), py = (K.has('w') ? 1 : 0) - (K.has('s') ? 1 : 0);
        if (px || py) this.nav('pan', [px * dt * 6, py * dt * 6]);
        if (K.has('q')) this.nav('orbit', dt * 1.2);
        if (K.has('e')) this.nav('orbit', -dt * 1.2);
        if (K.has('+') || K.has('=')) this.nav('zoom', 1 - dt * 1.5);
        if (K.has('-')) this.nav('zoom', 1 + dt * 1.5);
      }
      if (!this.intro || this.intro.t > 5.4) try { animate(dt * sp, t); } catch (e) { if (!this.animErr) { this.animErr = 1; console.error('[factory] anim', e); } }
      const sel = this.state.sel;
      const bnP = this.props.dataMode ? this.state.bn : null;
      if (env.op30) { const on30 = bnP === 'OP-30'; env.op30.color.setHex(on30 ? 0xa996ef : 0x3c4752); }
      Object.keys(outlines).forEach(id => {
        const o = outlines[id], e0 = effOf(id), al = e0 === 'ALARM', wn = e0 === 'WARN';
        // 데이터 없음 = 설비를 테두리만 (SCR-04 상태 표), 병목 = 그 공정 설비에 연보라 테두리 (OP-30은 구역 테두리가 연보라, SCR-04 [5])
        const nd = e0 === 'NODATA', bnH = !!bnP && bnP !== 'OP-30' && this.MACH[id].op === bnP, mtH = e0 === 'MAINT'; // 정비 = 하늘색 테두리 깜빡임 (2026-10-20)
        o.visible = id === sel || (!sel && id === this.hover) || nd || bnH || mtH;
        o.userData.ln.visible = nd || bnH || mtH; // 사용자 요청 2026-10-16: 누르거나 올렸을 때 상자 테두리 선은 없앰 (데이터 없음·병목·정비 표시는 유지)
        o.userData.lm.color.setHex(al ? 0xe5484d : wn ? 0xf0a500 : nd ? 0x8a97a4 : bnH ? 0xa996ef : mtH ? 0x3cc8e6 : 0x7a52f0); o.userData.pm.color.setHex(al ? 0xff5a5f : wn ? 0xffc040 : nd ? 0xb8c0c8 : bnH ? 0xc9bdf5 : mtH ? 0x7fe3f5 : 0x9d7bff);
        o.userData.pm.opacity = al ? 0.2 + 0.14 * Math.sin(t * 8) : wn ? 0.16 + 0.1 * Math.sin(t * 3) : nd ? 0.08 : mtH ? 0.14 + 0.1 * Math.sin(t * 3) : 0.22;
        if (groups[id]) groups[id].visible = !nd;
        if (this.intro) o.visible = false;
      });
      if (this.ceilSigns) { // 3D 천장 표지판: 설비를 확대해 볼 때는 숨기고, 상태가 바뀔 때만 다시 그림. 주의(처리 안 된 주의 알람 포함)는 주황, 고장은 빨강 판
        if (this.ceilG) this.ceilG.visible = !sel && !this.intro && !this.tour.on;
        const LIGHT = { RUN: '#7fe0a6', SETUP: '#9cc0ff', BLOCKED: '#f5b27a' };
        this.ceilSigns.forEach(S => {
          let e0 = S.id === 'inf' ? 'INF' : S.id === 'rack' ? 'RACK' : (effOf(S.id) || 'NODATA');
          if (e0 !== 'ALARM' && e0 !== 'INF' && e0 !== 'RACK' && this.props.warnIds && this.props.warnIds.includes(S.id)) e0 = 'WARN';
          const bn = !!this.props.dataMode && ((this.bnIds || {})[this.state.bn] || []).includes(S.id) && e0 !== 'ALARM' && e0 !== 'WARN'; // 주의·고장이면 그 판은 주의가 우선
          const key = e0 + (bn ? '|bn' : ''); if (key === S.last) return; S.last = key; S.badge.visible = bn;
          const c = S.cv.getContext('2d'), W0 = S.cv.width, H0 = S.cv.height, al = e0 === 'ALARM', wn = e0 === 'WARN', sv = this.STV[e0];
          const fg = wn ? '#2a1a00' : '#ffffff';
          c.clearRect(0, 0, W0, H0); c.save(); c.beginPath(); c.roundRect(0, 0, W0, H0, 26); c.clip();
          c.fillStyle = al ? '#e5484d' : wn ? '#f0a500' : '#26303a'; c.fillRect(0, 0, W0, H0);
          if (!al && !wn) { c.fillStyle = e0 === 'INF' || e0 === 'RACK' ? '#8a97a4' : (this.STAT[e0] || this.STAT.NODATA).dot; c.fillRect(0, H0 - 24, W0, 24); }
          c.restore();
          c.textAlign = 'center'; c.textBaseline = 'alphabetic'; c.fillStyle = fg;
          c.font = '800 118px "Pretendard Variable", sans-serif'; c.fillText(S.id === 'rack' ? 'RACK-01' : this.MACH[S.id].name, W0 / 2, 134);
          c.font = '700 70px "Pretendard Variable", sans-serif';
          c.fillStyle = al || wn ? fg : LIGHT[e0] || '#c3cbd3';
          const st0 = e0 === 'INF' ? '투입 대' : e0 === 'RACK' ? '봉재 랙' : sv ? `${sv[0]} ${sv[1]}` : '';
          if (!bn) c.fillText(st0, W0 / 2, 230);
          else { // 상태 + 연보라 '· 병목' (달팽이는 판 아래 모서리의 동그란 배지)
            const tail = ' · 병목', w1 = c.measureText(st0).width, w2 = c.measureText(tail).width, x0 = (W0 - w1 - w2) / 2;
            c.textAlign = 'left'; c.fillText(st0, x0, 230); c.fillStyle = '#b9a8ff'; c.fillText(tail, x0 + w1, 230); }
          S.tex.needsUpdate = true;
        });
      }
      Object.keys(pads).forEach(id => { const e0 = effOf(id); pads[id].hatch.visible = e0 === 'MAINT'; pads[id].block.visible = e0 === 'BLOCKED'; });
      // 데이터적용본: 정비(MAINT) 중인 설비 앞에 정비 로봇(이브). 2026-10-20 사용자 요청: 크게, 통로에서 걸어 들어와 앞 컨베이어 게이트를 들고 지나 설비 앞에서 정비,
      // 정비가 끝나면 다시 게이트를 지나 통로로 나가서 사라짐. 일시정지면 같이 멈춤
      this.botT = (this.botT || 0) + dt;
      const GZ = -3.15, gates = this.gates || {};
      try { Object.keys(pads).forEach(id => {
        let R = bots[id]; const mt = effOf(id) === 'MAINT' && !this.intro, G0 = gates[id];
        if (!mt && (!R || !R.root.visible)) return;
        if (!R) { R = bots[id] = createRobot(THREE); R.root.scale.setScalar(2.4); R.root.visible = false; scene.add(R.root); } // 숨긴 채 시작해야 아래에서 통로 자리·목표를 잡는다 (안 하면 위치 NaN)
        if (mt && (!R.root.visible || R.st === 'out')) { // 정비 시작 (또는 나가다 다시 정비) → 통로에서 들어옴
          const b = this.MACH[id].bd || this.MACH[id].b, x = G0 ? G0.x : (b[0] + b[1]) / 2000;
          // 일하는 자리: 게이트 있는 설비 = 컨베이어와 설비 앞면 사이, 없으면(세척기 = 앞에 바스켓 줄) 바스켓 줄 앞 통로
          R.wz = G0 ? (-3.372 - b[2] / 1000) / 2 : GZ + 0.8; R.az = GZ + 1.9;
          if (!R.root.visible) R.root.position.set(x, 0, R.az);
          R.st = 'in'; R.root.visible = true; R.setMode(0);
        }
        if (!mt) R.st = 'out';
        const tz = R.st === 'out' ? R.az : R.wz, z0 = R.root.position.z, dz = tz - z0;
        if (R.st !== 'work') {
          const nz = z0 + Math.sign(dz) * Math.min(Math.abs(dz), 0.9 * dt), cross = (z) => Math.abs(z - GZ) < 0.42;
          if (!G0 || !cross(nz) || G0.a > 1.1) R.root.position.z = nz; // 게이트가 다 들릴 때까지 컨베이어 앞에서 기다림
          if (Math.abs(tz - R.root.position.z) < 0.01) { if (R.st === 'in') { R.st = 'work'; R.setMode(3); } else { R.root.visible = false; R.st = 'gone'; } }
        }
        if (G0) G0.want = R.root.visible && R.st !== 'work' && Math.abs(R.root.position.z - GZ) < 1.0;
        if (R.root.visible) R.update(this.botT, dt, this.camera);
      });
      Object.values(gates).forEach((G0: any) => { G0.a += ((G0.want ? 1.25 : 0) - G0.a) * Math.min(1, dt * 3); G0.piv.rotation.z = -G0.a; }); // 왼쪽 끝이 들림 (경첩 = 오른쪽 끝)
      } catch (e) { if (!this.botErr) { this.botErr = 1; console.error('[factory] robot', e); } } // 로봇 오류로 3D 그리기가 멈추지 않게
      // 정비 중 설비 바닥 모션 (사용자 요청 2026-10-20): 퍼져 나가는 고리 3개 + 도는 빛 부채 + 빗금판 흐름 (설비 테두리 깜빡임은 아래 outlines)
      const MF = this.maintFx || (this.maintFx = {});
      Object.keys(pads).forEach(id => {
        const on = effOf(id) === 'MAINT' && !this.intro; let F0 = MF[id];
        if (!on) { if (F0) F0.g.visible = false; return; }
        if (!F0) {
          const b = this.MACH[id].bd || this.MACH[id].b, w = (b[1] - b[0]) / 1000 + 0.3, d = (b[3] - b[2]) / 1000 + 0.3;
          const g = new THREE.Group(); g.position.set((b[0] + b[1]) / 2000, 0.03, -(b[2] + b[3]) / 2000); scene.add(g);
          const mk0 = (geo, op) => { const m0 = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: 0x3cc8e6, transparent: true, opacity: op, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide })); m0.rotation.x = -Math.PI / 2; m0.renderOrder = 2; g.add(m0); return m0; };
          const rings = [0, 1, 2].map(() => mk0(new THREE.RingGeometry(0.94, 1, 72), 0.6));
          const sweep = mk0(new THREE.CircleGeometry(1, 40, 0, Math.PI / 3), 0.28);
          F0 = MF[id] = { g, rings, sweep, w, d };
        }
        F0.g.visible = true;
        F0.rings.forEach((r0, i) => { const q = (t * 0.55 + i / 3) % 1, s1 = 0.35 + q * 0.95; r0.scale.set(F0.w * 0.62 * s1, F0.d * 0.62 * s1, 1); r0.material.opacity = 0.7 * (1 - q); });
        F0.sweep.scale.set(F0.w * 0.55, F0.d * 0.55, 1); F0.sweep.rotation.z += dt * 1.6;
        const h = pads[id].hatch; if (h.material.map) h.material.map.offset.x -= dt * 0.35; h.material.opacity = 0.65 + 0.25 * Math.sin(t * 3);
      });
      Object.keys(fx).forEach(id => {
        const F = fx[id], e0 = effOf(id), on = (e0 === 'ALARM' || e0 === 'WARN') && !this.intro, A = e0 === 'ALARM', G = groups[id];
        F.g.visible = on; F.ringG.visible = false;
        if (!on) { F.light.intensity = 0; if (G) { G.position.x = 0; G.position.z = 0; } return; }
        const col = A ? 0xff3b3b : 0xffb020;
        F.mats.forEach(m0 => m0.color.setHex(col)); F.light.color.setHex(col);
        F.beam.rotation.y += dt * (A ? 6.5 : 3);
        F.light.intensity = (A ? 7 : 3.5) * (0.55 + 0.45 * Math.sin(t * (A ? 11 : 4)));
        F.rings.forEach((rg, i) => { const q = ((t * (A ? 0.9 : 0.45)) + i / F.rings.length) % 1, s1 = 0.75 + q * 1.6; rg.scale.set(s1, s1, s1); rg.material.opacity = (A ? 0.6 : 0.45) * (1 - q); });
        if (A && G) {
          const p2 = t % 2.2, env = p2 < 0.45 ? 1 - p2 / 0.45 : 0;
          G.position.x = Math.sin(t * 70) * 0.02 * env; G.position.z = Math.cos(t * 53) * 0.012 * env;
          smoke.spawn(F.top, 26, dt, 0.25, 0.45, 2.4);
          if (env > 0.75) sparkFx.spawn(F.front, 420, dt, 1.8, 1.5, 0.55);
        } else if (G) {
          const p3 = t % 3.0; G.position.x = p3 < 0.25 ? Math.sin(t * 45) * 0.006 : 0; G.position.z = 0;
        }
      });
      if (smoke) { smoke.step(dt, -0.18); sparkFx.step(dt, 5, 0.03); }
      flows.forEach(f => {
        const act = (!f.src || stt[f.src] === 'RUN') && (!f.dst || stt[f.dst] === 'RUN');
        if (f.tube && act !== f.act) {
          f.act = act; f.tube.material.color.setHex(act ? 0x29c6e6 : 0xa3abb3); f.tube.material.emissiveIntensity = act ? 0.45 : 0;
          if (f.halo) f.halo.visible = act; f.cone.material = act ? f.coneOn : f.coneOff;
        }
        f.parts.forEach(p => { p.visible = act; });
      });
      const wp = this.state.wip;
      Object.keys(pallets).forEach(k => {
        const n = this.buf ? Math.min(24, this.buf[k] || 0) : Math.round(wp[k] || 0); pallets[k].forEach(m => { m.visible = false; });
        const rg = rings[k]; if (!rg || k === 'fg') return;
        const lv = n / 24;
        rg.material.color.setHex(lv > 0.6 ? 0xe5484d : lv > 0.35 ? 0xf0a500 : 0x3cc8e6);
        rg.material.opacity = lv > 0.6 ? 0.45 + 0.35 * Math.sin(t * 4) : 0.3;
        const sc = lv > 0.6 ? 1 + 0.05 * Math.sin(t * 4) : 1; rg.scale.set(sc, sc, sc);
      });
      uiAcc += dt;
      if (sel && uiAcc > 0.2) { uiAcc = 0; this.setState({ ph: this.phOf(sel) }); }
      let lightL = 1;
      if (this.intro) {
        const it = (this.intro.t += wallDt);
        lightL = it < 0.9 ? 0.03 : it < 1.4 ? (Math.random() < 0.18 ? 0.12 : 0.36) : it < 1.9 ? (Math.random() < 0.1 ? 0.45 : 0.7) : 1;
        env.panels.forEach((m0, i) => { m0.userData.on = it > 0.9 + i * 0.12; });
        const gp = clamp01((it - 0.3) / 1.4);
        env.grids.forEach(g0 => g0.g.setDrawRange(0, 2 * Math.floor((g0.n / 2) * gp)));
        const bp = clamp01((it - 1.8) / 1.0);
        env.glow.forEach(m0 => { m0.opacity = bp; }); if (env.core) env.core.opacity = bp;
        this.ORDER.forEach((id, i) => { const G = groups[id]; if (!G) return; const p0 = clamp01((it - 2.2 - i * 0.32) / 0.9); G.position.y = -(this.MACH[id].b[5] + 0.4) * (1 - backOut(p0)); });
        flows.forEach((f0, i) => {
          const rv = clamp01((it - 5.0 - i * 0.1) / 0.7);
          if (f0.tube) { const q = rv >= 1 ? Infinity : Math.floor((f0.tubeN * rv) / 48) * 48; f0.tube.geometry.setDrawRange(0, q); if (f0.halo) f0.halo.geometry.setDrawRange(0, q); }
          else if (f0.line) f0.line.geometry.setDrawRange(0, rv >= 1 ? Infinity : Math.floor(41 * rv));
          f0.cone.visible = rv >= 1; if (rv < 1) f0.parts.forEach(p0 => { p0.visible = false; });
        });
        const cu = ease(clamp01(it / 7.4));
        camera.position.copy(this.introCam.curve.getPoint(cu)); controls.target.copy(this.introCam.t0).lerp(this.introCam.t1, cu);
        if (it >= 7.8) {
          env.grids.forEach(g0 => g0.g.setDrawRange(0, Infinity)); env.glow.forEach(m0 => { m0.opacity = 1; }); if (env.core) env.core.opacity = 1;
          Object.values(groups).forEach(G => { G.position.y = 0; }); env.panels.forEach(m0 => { m0.userData.on = true; });
          flows.forEach(f0 => { if (f0.tube) { f0.tube.geometry.setDrawRange(0, Infinity); if (f0.halo) f0.halo.geometry.setDrawRange(0, Infinity); } if (f0.line) f0.line.geometry.setDrawRange(0, Infinity); f0.cone.visible = true; });
          const fin = this.presetPos('front'); camera.position.copy(fin.pos); controls.target.copy(fin.tgt);
          this.intro = null; controls.enabled = !this.tour.on; this.setState({ introOn: false, introRun: false });
        }
      }
      {
        const nk = this.nightK;
        cA.copy(CC.bgD).lerp(CC.bgN, nk).lerp(CC.black, 1 - lightL); scene.background.copy(cA); scene.fog.color.copy(cA);
        hemi.intensity = (0.55 - 0.43 * nk) * lightL; sun.intensity = (1.5 - 1.3 * nk) * lightL;
        if (env.floor) env.floor.color.copy(CC.flD).lerp(CC.flN, nk);
        if (env.inner) env.inner.color.copy(CC.inD).lerp(CC.inN, nk);
        if (env.wall) env.wall.color.copy(CC.wlD).lerp(CC.wlN, nk);
        env.panels.forEach(m0 => { m0.emissiveIntensity = m0.userData.on === false ? 0 : 0.4 - 0.4 * nk; m0.color.setScalar(1 - 0.85 * nk); });
        mat.screen.emissiveIntensity = (0.6 + 1.3 * nk) * Math.max(lightL, 0.15);
        env.grids.forEach(g0 => { g0.m.color.copy(g0.cd).lerp(g0.cn, nk); g0.m.opacity = Math.min(1, g0.op + 0.25 * nk); });
        if (env.core) env.core.color.copy(CC.coD).lerp(CC.coN, nk);
        if (env.halo) env.halo.opacity = 0.16 + 0.26 * nk;
        env.inLights.forEach(l0 => { l0.intensity = (5 + 7 * nk) * lightL; });
        flows.forEach(f0 => { if (f0.tube && f0.act) f0.tube.material.emissiveIntensity = 0.45 + 1.1 * nk; });
      }
      convG.visible = !this.intro || this.intro.t > 4.6;
      if (this.convHide) { const th = !!this.tour.on; if (th !== this.convHidden) { this.convHidden = th; this.convHide(th); } }
      if (this.bgStep && (!this.intro || this.intro.t > 4.6)) try { this.bgStep(Math.min(rawDt, 0.1) * FZ); } catch (e) { if (!this.bgErr) { this.bgErr = 1; console.error('[factory] bg', e); } }
      if (!this.intro && !this.tour.on && this.convStep) try { this.convStep(Math.min(rawDt, 0.1) * flowK); } catch (e) { if (!this.cvErr) { this.cvErr = 1; console.error('[factory] conv', e); } }
      if (this.props.dataMode && this.reconcile && !this.intro && !this.tour.on && performance.now() - (this.recT || 0) > 1200) { this.recT = performance.now(); try { this.reconcile(); } catch (e) { if (!this.rcErr) { this.rcErr = 1; console.error('[factory] reconcile', e); } } }
      { const stc = this.state.st || {}, v0 = 0.32 * (this.props.flowSpeed ?? 1);
        convRoutes.forEach(R => {
          const act = (!R.src || stc[R.src] === 'RUN') && (!R.dst || stc[R.dst] === 'RUN');
          if (act) R.p = (R.p + v0 * dt) % R.L;
          R.items.forEach((g0, k) => {
            let s = (R.p + k * R.L / R.n) % R.L; const sv = s; let i = 0;
            while (i < R.segs.length - 1 && s > R.segs[i]) { s -= R.segs[i]; i++; }
            convPos.copy(R.P3[i]).lerp(R.P3[i + 1], Math.min(1, s / R.segs[i])); g0.position.copy(convPos);
            const k0 = Math.max(0, Math.min(1, sv / 0.25, (R.L - sv) / 0.25)); g0.scale.setScalar(Math.max(0.001, k0));
          });
        }); }
      if (!this.intro) Object.keys(groups).forEach(id => { const G = groups[id], tg = (!sel && id === this.hover) ? 0.06 : 0; G.position.y += (tg - G.position.y) * Math.min(1, dt * 8); });
      const TR = this.tour;
      if (TR.on) {
        if (!TR.paused) TR.t += Math.min(rawDt, 0.25);
        const ST = this.TOUR; let acc = 0, idx = 0;
        for (idx = 0; idx < ST.length; idx++) { if (TR.t < acc + ST[idx].dur) break; acc += ST[idx].dur; }
        if (idx >= ST.length) { hero.visible = false; this.stopTour(); }
        else {
          const sg = ST[idx], u = clamp01((TR.t - acc) / sg.dur);
          const pu = sg.mv === 'arc' ? ease(u) : sg.mv === 'line' ? u : 0;
          tourPaths[idx].getPointAt(pu, heroPos); hero.position.copy(heroPos); hero.visible = true; hero.scale.setScalar(0.72);
          if (heroGrip) {
            const cp = tourPaths[idx]; let air = false;
            if (cp.isPoly && cp.curves.length) { const Ls = cp.getCurveLengths(), d0 = pu * cp.getLength(); let ci = Ls.findIndex(l => l >= d0); if (ci < 0) ci = Ls.length - 1; const c0 = cp.curves[ci]; air = CA.isAir(c0.v1, c0.v2); }
            else if (sg.mv === 'hold') air = false;
            CA.gripAt(heroShim, false);
          }
          const fi = sg.form2 != null && u >= sg.at ? sg.form2 : sg.form;
          forms.forEach((f0, i) => { f0.visible = i === fi; });
          heroLight.intensity = 1.4 + 2 * this.nightK;
          heroRing.material.opacity = 0.5 + 0.4 * Math.sin(t * 4);
          if (!TR.paused) {
            if (sg.fx === 'spark' && u > 0.25 && u < 0.6) sparkFx.spawn(fxOff.copy(heroPos).add(camOff.set(0.1, 0.06, 0)), 320, dt, 1.6, 1.4, 0.5);
            if (sg.fx === 'chips' && u > 0.2 && u < sg.at + 0.05) tourChips.spawn(fxOff.copy(heroPos).add(camOff.set(0, 0.09, 0)), 220, dt, 1.4, 1.2, 0.6);
            if (sg.fx === 'water' && u < 0.78) tourWater.spawn(fxOff.copy(heroPos).add(camOff.set((Math.random() - 0.5) * 0.3, 0.45, (Math.random() - 0.5) * 0.2)), 240, dt, 0.25, -1.8, 0.4);
          }
          const a0 = Math.sin(TR.t * 0.3) * 0.35 + (sg.mv === 'hold' ? u * 0.5 : 0);
          camOff.set(sg.cam[0] * 1.5, sg.cam[1] * 1.9 + 0.3, sg.cam[2] * 1.7).applyAxisAngle(yAxis, a0).multiplyScalar(Math.max(1, 1.5 / camera.aspect));
          camGoal.copy(heroPos).add(camOff);
          camera.position.lerp(camGoal, 0.06); controls.target.lerp(heroPos, 0.09);
          if (idx !== this.state.tourIdx || Math.abs((TR.lastUi ?? -9) - TR.t) > 0.25) { TR.lastUi = TR.t; this.setState({ tourIdx: idx, tourU: u }); }
        }
      } else if (hero.visible) { hero.visible = false; if (heroGrip) heroGrip.visible = false; }
      tourChips.step(dt, 5, 0.3); tourWater.step(dt, 6, 0.3);
      this.xr = (this.xr || 0) + ((this.tour.on ? 1 : 0) - (this.xr || 0)) * Math.min(1, dt * 3);
      { const xr = this.xr, xon = xr > 0.02;
        [mat.white, mat.green, mat.greenD, mat.grey].forEach(m0 => { if (m0.transparent !== xon) { m0.transparent = xon; m0.needsUpdate = true; } m0.opacity = 1 - 0.7 * xr; m0.depthWrite = xr < 0.4; }); }
      {
        const nk = this.nightK;
        if (bloom) { bloom.strength = 0.14 + 0.85 * nk; bloom.threshold = 0.9 - 0.62 * nk; bloom.radius = 0.45 + 0.2 * nk; }
        (env.lamps || []).forEach(m0 => { m0.emissiveIntensity = (0.7 + 0.8 * nk) * (this.intro ? lightL : 1); });
        Object.keys(leds).forEach(id => { const e0 = effOf(id); leds[id].color.setHex(e0 === 'ALARM' ? (Math.sin(t * 9) > 0 ? 0xff3b3b : 0x3a0d0d) : e0 === 'WARN' ? 0xffb020 : e0 === 'MAINT' ? 0x6b7580 : e0 === 'BLOCKED' ? 0xe8954a : e0 === 'IDLE' ? 0x8a97a4 : e0 === 'SETUP' ? 0x3b82f6 : 0x22d36b); });
        agvG.visible = false;
        if (agvG.visible) { ribTex.offset.x -= dt * 1.2; agvs.forEach(A => { A.u = (A.u + (dt * 0.55) / laneLen) % 1; lane.getPointAt(A.u, aT); A.g.position.copy(aT); const tg = lane.getTangentAt(A.u); A.g.rotation.y = Math.atan2(-tg.z, tg.x); }); }
        holoG.visible = !!LY.holo && !this.intro && !this.tour.on;
        heat.visible = !!LY.heat && !this.intro;
        if ((holoG.visible || heat.visible) && (this.state.m !== lastM || this.state.st !== lastSt || this.state.warn !== this.lastWarn || !this.drawn)) {
          lastM = this.state.m; lastSt = this.state.st; this.lastWarn = this.state.warn; this.drawn = true; holoDraw(effOf); heatDraw(effOf);
        }
        if (holoG.visible) Object.values(holos).forEach((H, i) => { H.sp.position.y += Math.sin(t * 1.6 + i) * 0.0015; });
        const exT = this.state.explode && sel ? sel : null;
        Object.keys(groups).forEach(id => {
          const G = groups[id], tg0 = id === exT ? 1 : 0, ud = G.userData;
          ud.ex = (ud.ex || 0) + (tg0 - (ud.ex || 0)) * Math.min(1, dt * 3.5);
          if (ud.ex < 0.0005 && !ud.exOn) return;
          const b = this.MACH[id].b; cvec.set((b[0] + b[1]) / 2000, 0, -(b[2] + b[3]) / 2000);
          if (!ud.exInit) { G.children.forEach(ch => { if (!ch.userData.rig) ch.userData.base = ch.position.clone(); }); ud.exInit = true; }
          const e = ease(clamp01(ud.ex));
          G.children.forEach(ch => { const bp = ch.userData.base; if (!bp) return; dirV.copy(bp).sub(cvec); dirV.y = 0; const len = dirV.length(); if (len > 1e-4) dirV.divideScalar(len); ch.position.copy(bp).addScaledVector(dirV, e * (0.12 + len * 0.42)); ch.position.y = bp.y + e * (0.06 + bp.y * 0.35); });
          ud.exOn = ud.ex > 0.0005; if (!ud.exOn) G.children.forEach(ch => { if (ch.userData.base) ch.position.copy(ch.userData.base); });
        });
        // 자동 화질 (2026-10-20 고침 — 사용자 "흐릿하거나 계단처럼 깨지고, 가끔 3D가 2D 배치도로 바뀌어"):
        // 처음 90프레임(셰이더 컴파일)은 빼고, 탭이 가려졌거나 한 프레임이 0.25초 넘게 멈춘 때(창 전환·로딩)는 재지 않는다.
        // 보이는 상태로 4초 재서 30fps 미만이면 빛 번짐·그림자만 끈다. 해상도는 낮추지 않고(흐려짐), 2D로도 넘기지 않는다
        if (!this.intro && !this.qDone && qual() === '자동' && !document.hidden && rawDt < 0.25 && (this.qW = (this.qW || 0) + 1) > 90) { this.qT = (this.qT || 0) + rawDt; this.qF = (this.qF || 0) + 1; if (this.qT > 4) { this.qDone = true; if (this.qF / this.qT < 30) { this.lowQ = true; renderer.shadowMap.enabled = false; scene.traverse(o => { if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach(m0 => { m0.needsUpdate = true; }); }); this.setState({ qNote: '저사양 모드 자동 적용 (빛 번짐·그림자 끔)' }); } } }
      }
      controls.autoRotate = !!this.props.autoRotate && !sel && !this.tour.on && !this.intro;
      if (this.goal) {
        const G0 = this.goal;
        if (!G0.from) { G0.from = camera.position.clone(); G0.tf = controls.target.clone(); G0.t = 0; const dd = G0.from.distanceTo(G0.pos); G0.mid = G0.from.clone().lerp(G0.pos, 0.5); G0.mid.y += Math.min(5, dd * 0.22); G0.dur = G0.dur || Math.min(1.9, 0.85 + dd * 0.035); }
        G0.t += Math.min(rawDt, 0.06) / G0.dur; const u = ease(clamp01(G0.t)), a1 = (1 - u) * (1 - u), b1 = 2 * (1 - u) * u, c1 = u * u;
        camera.position.set(G0.from.x * a1 + G0.mid.x * b1 + G0.pos.x * c1, G0.from.y * a1 + G0.mid.y * b1 + G0.pos.y * c1, G0.from.z * a1 + G0.mid.z * b1 + G0.pos.z * c1);
        controls.target.copy(G0.tf).lerp(G0.target, u);
        if (G0.t >= 1) this.goal = null;
      }
      { const tg = controls.target, cx = Math.max(-2, Math.min(39, tg.x)), cz = Math.max(-12, Math.min(1.5, tg.z)), cy = Math.max(0, Math.min(2.5, tg.y));
        const dx = cx - tg.x, dy = cy - tg.y, dz = cz - tg.z; if (dx || dy || dz) { tg.set(cx, cy, cz); camera.position.x += dx; camera.position.y += dy; camera.position.z += dz; }
        if (camera.position.y < 0.35) camera.position.y = 0.35; }
      if (this.maxDist) controls.maxDistance = (this.intro || this.tour.on) ? 60 : this.maxDist; // 인트로·투어 카메라는 먼 곳에서 시작
      controls.update(); doRender();
      place();
    };
    const place = () => {
      const sel = this.state.sel;
      const ov = this.ovRef.current; if (!ov) return;
      const Wd = host.clientWidth, Ht = host.clientHeight;
      a.set(12.5, 0, -4).project(camera); b.set(13.5, 0, -4).project(camera);
      const ppm = Math.hypot((a.x - b.x) * Wd / 2, (a.y - b.y) * Ht / 2);
      const fitS = (ppm * 3.1) / 186;
      const compact = !sel && fitS < 0.75;
      const s0 = sel ? 1 : compact ? Math.min(0.85, Math.max(0.75, (ppm * 3.1) / 130)) : Math.min(1.15, fitS);
      const s = EMB && !sel ? Math.max(1, s0) : s0; // 사용자 요청 2026-10-15: 이름표가 작아 안 읽혀서 최소 1배 (겹침은 아래 배치가 비켜 놓음)
      const nC = ov.querySelectorAll('[data-card]').length;
      if (compact !== this.compact || nC !== this.nCards) {
        this.compact = compact; this.nCards = nC;
        ov.querySelectorAll('[data-detail]').forEach(e => { e.style.display = compact ? 'none' : ''; });
        ov.querySelectorAll('[data-card]').forEach(e => { e.style.width = compact ? '124px' : ''; });
      }
      const full = this.state.detail === 'full', topV = this.state.view === 'top';
      const items = [];
      // 켜고 끌 때 깜빡이지 않고 0.2초 페이드 (visibility 도 같이 전이시켜 끝난 뒤 숨김)
      const setV = (e, on) => { if (!e._tr) { e._tr = 1; e.style.transition = 'opacity .2s, visibility .2s'; } e.style.visibility = on ? 'visible' : 'hidden'; e.style.opacity = on ? '1' : '0'; };
      // 이름표 3단계 (줌): 0 먼 거리=코드만, 1 중간=이름, 2 가까이/호버/주의·고장=이름+상태+공정. 경계에서 깜빡이지 않게 ±3 여유
      const LOD_T = [26, 40];
      const lodOf = (e) => { let l = e._lod; if (l == null) l = ppm < LOD_T[0] ? 0 : ppm < LOD_T[1] ? 1 : 2; else { while (l < 2 && ppm >= LOD_T[l] + 3) l++; while (l > 0 && ppm < LOD_T[l - 1] - 3) l--; } return (e._lod = l); };
      const setLod = (e, l) => {
        e.querySelectorAll('[data-lv]').forEach(d => { const w = +d.dataset.lv > l ? 'none' : ''; if (d.style.display !== w) d.style.display = w; });
        e.querySelectorAll('[data-lo]').forEach(d => { const w = l === 0 ? '' : 'none'; if (d.style.display !== w) d.style.display = w; });
      };
      ov.querySelectorAll('[data-anchor]').forEach(el => {
        const k = this.anch[el.dataset.anchor]; if (!k) return;
        const hide = () => { setV(el, false); };
        if (sel || this.intro || this.tour.on) return hide();
        const tier = el.dataset.tier || '', al = el.dataset.alert === '1', hv = !!el.dataset.mid && el.dataset.mid === this.hover;
        const show = tier === 'axis' ? (full || topV) : tier === 'zone' ? (full || ppm > 80) : tier === 'wip' ? (EMB || full || al) : tier === 'card' ? (((this.state.layers || {}).holo && !al) ? false : (full || al || hv)) : true;
        if (!show) return hide();
        v.set(k[0] / 1000, k[2], -k[1] / 1000).project(camera);
        if (v.z > 1 || Math.abs(v.x) > 1.3 || Math.abs(v.y) > 1.3) return hide();
        let x = (v.x + 1) / 2 * Wd; const y = (1 - v.y) / 2 * Ht;
        if (el.dataset.anchor === 'ax-y') x = Math.max(x, 60);
        const sc = el.dataset.noscale ? 1 : s;
        if (!isFinite(x) || !isFinite(y) || !isFinite(sc)) return hide();
        const pri = tier === 'fx' ? 0 : tier === 'card' ? (al ? 1 : 4) : tier === 'tag' ? (el.dataset.anchor === 'tag-rack' ? 4 : 2) : tier === 'wip' ? (al ? 2 : 3) : 9; // 봉재 랙 이름표는 겹치면 숨김 (설비 이름표가 먼저)
        let far = false;
        if (tier === 'tag') { const l0 = lodOf(el), l = hv || al ? 2 : l0; setLod(el, l); far = l === 0 && el.dataset.mid !== 'rack'; }
        items.push({ el, x, y, sc, ctr: el.dataset.align === 'center', hang: el.dataset.hang === '1', pri, up: tier === 'tag' && el.dataset.hang !== '1', far, rail: 0 });
      });
      // 먼 거리: 설비 이름표를 한 줄로 나란히 세우고 기둥(리더선)으로 설비에 잇는다 — 겹치지도, 설비를 가리지도 않음
      const fars = items.filter(i0 => i0.far);
      if (fars.length > 1) { const top0 = Math.min(...fars.map(i0 => i0.y)) - 30; fars.forEach(i0 => { i0.rail = top0 - i0.y; }); }
      items.sort((p, q) => p.pri - q.pri);
      const placed = [];
      const setCmp = (el, on) => { if (!!el._cmp === on) return; el._cmp = on; el.querySelectorAll('[data-detail]').forEach(d0 => { d0.style.display = on ? 'none' : ''; }); const cd = el.querySelector('[data-card]'); if (cd) cd.style.width = on ? '124px' : ''; };
      items.forEach(it => {
        let yy = it.y;
        const isCard = !!it.el.querySelector('[data-card]') || it.el.dataset.tier === 'tag';
        if (isCard && !compact) setCmp(it.el, false);
        if (it.pri < 9) {
          const MAXD = 110;
          // 먼 거리 한 줄 정렬(rail)분이 들어간 기준 위치
          const baseOf = (h0) => (it.hang ? it.y : it.ctr ? it.y - h0 / 2 : it.y - h0) + it.rail;
          const tryFit = () => {
            const w0 = it.el.offsetWidth * it.sc, h0 = it.el.offsetHeight * it.sc, x0 = it.x - w0 / 2;
            const base = baseOf(h0);
            const hits = (yt) => placed.some(p => x0 < p.x1 + 4 && x0 + w0 > p.x0 - 4 && yt < p.y1 + 3 && yt + h0 > p.y0 - 3);
            // 이름표는 위로만 비킨다 (아래로 내려가면 설비 몸체를 가림)
            const okY = (yt) => yt >= 140 && yt + h0 <= Ht - 64 && Math.abs(yt - base) <= MAXD && (!it.up || yt <= base + 0.5) && !hits(yt);
            // 위치 유지: 지난번에 비켜 선 자리가 아직 비어 있으면 그대로 (위/아래 번갈아 튀는 것 방지). 원래 자리가 40프레임 연속 비면 복귀
            const keep = it.el._tgt || 0, free0 = !hits(base);
            if (!free0) it.el._free = 0;
            if (keep && okY(base + keep) && (!free0 || (it.el._free = (it.el._free || 0) + 1) < 40)) return { x0, w0, h0, y0: base + keep, base };
            if (free0) { it.el._free = 0; return { x0, w0, h0, y0: base, base }; }
            const cands = [];
            placed.forEach(p => { if (x0 < p.x1 + 4 && x0 + w0 > p.x0 - 4) cands.push(p.y0 - 4 - h0, p.y1 + 4); });
            const ok = cands.filter(okY).sort((p, q) => Math.abs(p - base) - Math.abs(q - base));
            return ok.length ? { x0, w0, h0, y0: ok[0], base } : null;
          };
          let fit = tryFit();
          if (fit && fit.y0 !== fit.base && it.el.dataset.tier === 'tag' && !compact) { setCmp(it.el, true); fit = tryFit(); } // 한 줄 유지: 겹치면 상태 글자부터 접음
          if (fit && it.el.dataset.tier === 'tag') fit.y0 = fit.base; // 이름표는 위아래로 밀지 않고 같은 줄 유지
          if (!fit && isCard && !compact) { setCmp(it.el, true); fit = tryFit(); }
          if (!fit && it.pri >= 3) {
            const w0 = it.el.offsetWidth * it.sc, h0 = it.el.offsetHeight * it.sc;
            fit = { x0: it.x - w0 / 2, w0, h0, y0: baseOf(h0) };
            if (it.pri >= 4) { setV(it.el, false); it.el._dy = null; it.el._tgt = 0; return; }
          }
          if (!fit) { const w0 = it.el.offsetWidth * it.sc, h0 = it.el.offsetHeight * it.sc; fit = { x0: it.x - w0 / 2, w0, h0, y0: baseOf(h0) }; }
          const tgt0 = fit.y0 - baseOf(fit.h0); // 화면 안쪽으로 눌리기 전 값을 기억 (눌린 값이 굳지 않게)
          {
            const TOPS = this.safeTop || 150, BOTS = Ht - 70, M0 = 10;
            const y1c = Math.max(TOPS, Math.min(BOTS - fit.h0, fit.y0)), x1c = Math.max(M0, Math.min(Wd - M0 - fit.w0, fit.x0));
            const sh = Math.hypot(y1c - fit.y0, x1c - fit.x0);
            if (fit.h0 > BOTS - TOPS || (it.el.dataset.tier !== 'tag' && sh > Math.max(60, fit.h0 * 0.9) && it.pri >= 1)) { setV(it.el, false); it.el._dy = null; it.el._tgt = 0; return; }
            fit.y0 = y1c; it.x += x1c - fit.x0; fit.x0 = x1c;
          }
          it.el._tgt = tgt0;
          placed.push({ x0: fit.x0, x1: fit.x0 + fit.w0, y0: fit.y0, y1: fit.y0 + fit.h0 });
          const tgtY = it.hang ? fit.y0 : it.ctr ? fit.y0 + fit.h0 / 2 : fit.y0 + fit.h0;
          const dTgt = tgtY - it.y;
          it.el._dy = it.el._dy == null ? dTgt : it.el._dy + (dTgt - it.el._dy) * 0.25;
          yy = it.y + it.el._dy;
          // 이름표가 위로 비켜 서도 기둥을 설비 위 원래 지점까지 늘려 이어 준다 (떠 있는 느낌 방지)
          const ext = it.up && it.el.querySelector('[data-ext]');
          if (ext) {
            const up = Math.max(0, -it.el._dy) / it.sc, on = up > 4, bead = it.el.querySelector('[data-bead]');
            ext.style.display = on ? '' : 'none'; if (on) ext.style.height = (up + 6).toFixed(1) + 'px';
            if (bead) bead.style.opacity = on ? '0' : '';
          }
        } else {
          const w0 = it.el.offsetWidth, h0 = it.el.offsetHeight, x0 = it.x - w0 / 2, y0 = it.hang ? it.y : it.ctr ? it.y - h0 / 2 : it.y - h0;
          if (placed.some(p => x0 < p.x1 && x0 + w0 > p.x0 && y0 < p.y1 && y0 + h0 > p.y0)) { setV(it.el, false); return; }
        }
        setV(it.el, true);
        it.el.style.transform = `translate(${it.x.toFixed(1)}px,${yy.toFixed(1)}px) translate(-50%,${it.hang ? '0%' : it.ctr ? '-50%' : '-100%'}) scale(${it.sc.toFixed(3)})`;
      });
    };
    this.renderNow = () => { doRender(); place(); };
    this.safeTopT = setInterval(() => {
      const wr = this.wrapRef && this.wrapRef.current; if (!wr) return; const wb = wr.getBoundingClientRect();
      const hint = [...wr.querySelectorAll('span')].find(s0 => s0.textContent.includes('더블클릭'));
      const el0 = hint ? hint.parentElement : null; if (el0) this.safeTop = Math.max(110, el0.getBoundingClientRect().bottom - wb.top + 10);
    }, 800);
    if (this.state.introOn) this.startIntro();
    this.wd = setInterval(() => { if (!this.dead && performance.now() - (this.lastFrame || 0) > 400) { try { loop(); } catch (e) { if (!this.loopErr) { this.loopErr = 1; console.error('[factory] loop', e); } } } }, 250);
    this.__step = (n, d) => { this.__dtO = d; for (let i = 0; i < n; i++) loop(); this.__dtO = null; };
    loop();
  }

  shortMsg(id, s) {
    if (this.props.alarmText && (s === 'ALARM' || s === 'WARN')) return this.props.alarmText(id, s === 'ALARM' ? 'alarm' : 'warn'); // 적용본: 2D와 같은 알람 코드집 번호
    if (s === 'ALARM') return this.ISSUE[id].a[0] + ' · ' + this.ISSUE[id].a[1];
    if (s === 'WARN') return this.ISSUE[id].w[0] + ' · ' + this.ISSUE[id].w[1];
    if (s === 'IDLE') return '투입 대기 · WIP-3 재공 없음';
    if (s === 'SETUP') return '공구 교체 후 셋업 중';
    return '';
  }
  renderVals() {
    const { m, view, sel, ph, st, wip } = this.state;
    const S = this.STAT, warn = this.state.warn || {};
    const eff = (id) => st[id] === 'RUN' && warn[id] ? 'WARN' : st[id];
    const pick = (id) => () => this.select(id);
    const card = (id, mid, name, op, d, lifeLabel = 'Tool Life') => {
      if (this.props.dataMode) {
        // 데이터적용본: 부하 = 주축 부하(센서, OP-30만), 공구 = 사용률이 가장 높은 공구 (90% 이상 ▲, SCR-04 6c), 문구 = 알람 코드집·정지 사유
        const e0 = eff(mid) || 'NODATA', s = S[e0] || S.NODATA, al = e0 === 'ALARM', wn = e0 === 'WARN', dd = (m && m[mid]) || [];
        const tool = dd[1], hasTool = tool != null;
        return { id, mid, name, op, load: dd[0] != null ? dd[0] : '—', tool: hasTool ? tool : '—', toolW: hasTool ? Math.min(100, tool) + '%' : '0%',
          lifeLabel: hasTool ? `공구 ${dd[2]} 사용률${tool >= 90 ? ' ▲' : ''}` : '공구 기록 없음', loadLabel: dd[0] != null ? '주축 부하' : '부하 (센서 없음)', onSelect: pick(mid),
          stText: (this.STV[e0] || this.STV.NODATA)[1], stFg: s.fg, stDot: s.dot,
          bd: al ? '#e5484d' : wn ? '#f0a500' : 'var(--gbd)', bg: al ? 'var(--albg)' : wn ? 'var(--wnbg)' : 'var(--glass)', alert: e0 !== 'RUN' ? '1' : '0',
          anim: al ? 'cardShake 2.2s ease-in-out infinite, glowRed 1.1s ease-in-out infinite' : wn ? 'glowAmber 1.8s ease-in-out infinite' : 'none',
          bar: hasTool && tool >= 90 ? '#f0a500' : 'linear-gradient(90deg,#3a9fb0,#34c46e)',
          hasMsg: e0 !== 'RUN', msg: this.props.cardText ? this.props.cardText(mid, e0) : this.shortMsg(mid, e0), msgFg: s.fg, msgBg: s.bg };
      }
      const e0 = eff(mid), s = S[e0], t = mid === 'vf2' ? this.state.vf2Tool : d[1], al = e0 === 'ALARM', wn = e0 === 'WARN';
      return { id, mid, name, op, load: (e0 === 'RUN' || wn) ? d[0] : 0, tool: t, toolW: t + '%', lifeLabel, onSelect: pick(mid),
        stText: s.label, stFg: s.fg, stDot: s.dot,
        bd: al ? '#e5484d' : wn ? '#f0a500' : 'var(--gbd)', bg: al ? 'var(--albg)' : wn ? 'var(--wnbg)' : 'var(--glass)', alert: e0 !== 'RUN' ? '1' : '0',
        anim: al ? 'cardShake 2.2s ease-in-out infinite, glowRed 1.1s ease-in-out infinite' : wn ? 'glowAmber 1.8s ease-in-out infinite' : 'none',
        bar: t < 20 ? '#e5484d' : 'linear-gradient(90deg,#3a9fb0,#34c46e)',
        hasMsg: e0 !== 'RUN', msg: this.shortMsg(mid, e0), msgFg: s.fg, msgBg: s.bg };
    };
    const xTicks = [], yTicks = [];
    for (let X = 0; X <= 25000; X += 5000) xTicks.push({ id: 'xt' + X, label: X.toLocaleString('en-US') });
    for (let Y = 0; Y <= 8000; Y += 2000) yTicks.push({ id: 'yt' + Y, label: Y.toLocaleString('en-US') });
    const wipItem = (id, key, name, sub, kind) => {
      if (this.props.dataMode) {
        // 데이터적용본: 재공 수 = 시뮬레이터, 경고 = wip_buffer (20개 초과 주황, OP-20→30은 한도 30 도달, OP-30→40은 경고 없음). 빨강은 쓰지 않는다 (2.3 #2)
        const code = { w1: 'WIP-10-20', w2: 'WIP-20-30', w3: 'WIP-30-40', w4: 'WIP-40-50' }[key];
        const L0 = code && (this.state.wipLimits || {})[code];
        const n = Math.round((wip || {})[key] || 0), lim = L0 ? L0.limit : 30;
        const orange = !!(L0 && L0.warn && L0.warn_over != null && n > L0.warn_over);
        const base = kind === 'fg' ? { bg: 'rgba(226,246,234,0.94)', bd: '#4fb07a', fg: '#155a33', bar: '#4fb07a' }
          : kind === 'soak' ? { bg: 'rgba(238,236,250,0.94)', bd: '#8a84b8', fg: '#3d3770', bar: '#8a84b8' }
          : { bg: 'rgba(255,240,222,0.92)', bd: orange ? '#e8954a' : '#d9c3a8', fg: '#5e3208', bar: orange ? '#e8954a' : '#b9a58c' };
        const nd = this.liveT == null;
        return { id, name, n, orange, alert: orange ? '1' : '0', sub: nd ? '기록 없음' : sub + (code ? ` · 한도 ${lim}` : ''), cnt: nd ? '—' : (kind === 'fg' ? `오늘 ${n}` : n + ' 개'),
          barW: code ? Math.min(100, Math.round(n / lim * 100)) + '%' : '0%', bar: base.bar, bg: base.bg, bd: base.bd, fg: base.fg };
      }
      const n = key ? Math.round(wip[key]) : 3, lv = n / 24;
      const bott = kind === 'wip' && lv > 0.6, warn = kind === 'wip' && lv > 0.35;
      const base = kind === 'fg' ? { bg: 'rgba(226,246,234,0.94)', bd: '#4fb07a', fg: '#155a33', bar: '#4fb07a' }
        : kind === 'soak' ? { bg: 'rgba(238,236,250,0.94)', bd: '#8a84b8', fg: '#3d3770', bar: '#8a84b8' }
        : { bg: 'rgba(255,240,222,0.92)', bd: '#e8954a', fg: '#7a3f0c', bar: warn ? '#f0a500' : '#e8954a' };
      const nDoc = n, orange = key === 'w2' ? nDoc >= 30 : key === 'w3' ? false : nDoc > 20;
      return { id, name, n, orange, alert: warn ? '1' : '0', sub: bott ? '병목 · 적체' : sub, cnt: n + ' EA', barW: Math.min(100, Math.round(lv * 100)) + '%',
        bar: bott ? '#e5484d' : base.bar, bg: bott ? 'rgba(255,226,226,0.96)' : base.bg, bd: bott ? '#e5484d' : base.bd, fg: bott ? '#a01e23' : base.fg };
    };
    const nRun = this.ORDER.filter(k => st[k] === 'RUN').length;
    const nAlarm = this.ORDER.filter(k => st[k] === 'ALARM').length;
    const nWarn = this.ORDER.filter(k => eff(k) === 'WARN').length;
    const wipTotal = Math.round(wip.w1 + wip.w2 + wip.w3 + wip.w4);
    let d = { name: '', kr: '', op: '', desc: '', T: 0, elapsed: '0.0', progW: '0%', steps: [], params: [], inp: '', out: '', stText: '', stFg: '', stDot: '' };
    let info = { show: false, title: '', rows: [], guide: [], hasGuide: false, canRestart: false, btnLabel: '', bg: '', bd: '', fg: '' };
    if (sel) {
      const M = this.MACH[sel], s0 = eff(sel), SS = S[s0]; let idx = 0;
      M.steps.forEach((s, i) => { if (ph >= s[0]) idx = i; });
      const running = s0 === 'RUN' || s0 === 'WARN';
      d = { name: M.name, kr: M.kr, op: M.op, desc: M.desc, T: M.T, elapsed: (ph * M.T).toFixed(1), progW: (ph * 100).toFixed(1) + '%',
        inp: M.io[0], out: M.io[1], params: M.params.map(([k, v]) => ({ k, v })), stText: SS.label, stFg: SS.fg, stDot: SS.dot,
        steps: M.steps.map((s, i) => ({ n: String(i + 1).padStart(2, '0'), title: s[1], sub: s[2], isCur: i === idx,
          curLabel: running ? '진행 중' : '정지', curFg: SS.fg, curBg: SS.bg,
          rowBg: i === idx ? 'var(--chip)' : 'transparent',
          numBg: i === idx ? (running ? '#3d6fe0' : SS.dot) : i < idx ? '#dcf5e6' : 'var(--chip)',
          numFg: i === idx ? '#ffffff' : i < idx ? '#13994f' : 'var(--t3)',
          tFg: i <= idx ? 'var(--t1)' : 'var(--t3)' })) };
      const box = { bg: SS.bg, bd: SS.dot, fg: SS.fg };
      const IS = this.ISSUE[sel], AT = this.state.at || {};
      if (s0 === 'ALARM') info = { show: true, ...box, title: IS.a[0] + ' · ' + IS.a[1] + ' (고장)', canRestart: true, btnLabel: '조치 완료 · 재가동', hasGuide: true,
        rows: [{ k: '발생 시각', v: AT['a' + sel] || '-' }, { k: '감지', v: IS.a[2] }, { k: '추정 원인', v: IS.a[3] }, { k: '영향', v: this.IMPACT[sel] }],
        guide: (IS.ag || ['원인 부위 점검 · 이물 제거', '부품 교체 / 정비 후 원점 복귀', '시험 가공 1EA 후 재가동']).map((t, i) => ({ n: String(i + 1), t })) };
      else if (s0 === 'WARN') info = { show: true, ...box, title: IS.w[0] + ' · ' + IS.w[1] + ' (주의)', canRestart: true, btnLabel: '점검 완료 · 주의 해제', hasGuide: true,
        rows: [{ k: '감지 시각', v: AT['w' + sel] || '-' }, { k: '측정값', v: IS.w[2] }, { k: '추정 원인', v: IS.w[3] }, { k: '상태', v: '가동 유지 · 모니터링 중' }],
        guide: ['사이클 종료 후 해당 부위 점검', '추이 10분 모니터링', '한계 초과 시 정지 · 조치'].map((t, i) => ({ n: String(i + 1), t })) };
      else if (s0 === 'IDLE') info = { show: true, ...box, title: '투입 대기 (Starved)', canRestart: false, hasGuide: false, guide: [],
        rows: [{ k: '원인', v: 'WIP-3 재공 ' + Math.round(wip.w3) + 'EA' }, { k: '상류 상태', v: 'OP-30 처리 지연으로 공급 부족' }, { k: '자동 재개', v: 'WIP-3 ≥ 2EA 시' }] };
      else if (s0 === 'SETUP') info = { show: true, ...box, title: '셋업 중', canRestart: false, hasGuide: false, guide: [],
        rows: [{ k: '작업', v: '신규 T03 길이 측정 · 시험 가공' }, { k: '예상', v: '약 6초 후 재가동' }] };
    }
    const alarmId = this.ORDER.find(k => st[k] === 'ALARM');
    const issues = this.ORDER.filter(k => eff(k) === 'ALARM' || eff(k) === 'WARN')
      .sort((a, b) => (eff(a) === 'ALARM' ? 0 : 1) - (eff(b) === 'ALARM' ? 0 : 1))
      .map(k => { const A = eff(k) === 'ALARM'; return { id: 'fx-' + k, mid: k, name: this.MACH[k].name, tag: A ? '고장' : '주의', msg: A ? this.ISSUE[k].a[1] : this.ISSUE[k].w[1],
        fg: A ? '#a01e23' : '#7a4b00', bd: A ? '#e5484d' : '#f0a500', bg: A ? 'rgba(255,236,236,0.94)' : 'rgba(255,246,222,0.95)', dot: A ? '#e5484d' : '#f0a500',
        sym: A ? '⚠' : '▲', ring: A ? 'rgba(229,72,77,0.55)' : 'rgba(240,165,0,0.55)', bob: A ? 'fxBob 0.9s ease-in-out infinite' : 'fxBob 1.6s ease-in-out infinite',
        ringAnim: A ? 'fxRing 1.2s ease-out infinite' : 'fxRing 2s ease-out infinite',
        banAnim: A ? 'bannerShake 3s ease-in-out infinite' : 'none', onClick: pick(k) }; });
    return {
      nv: {
        up: this.holdNav('pan', [0, 0.25]).onPointerDown, down: this.holdNav('pan', [0, -0.25]).onPointerDown,
        left: this.holdNav('pan', [-0.25, 0]).onPointerDown, right: this.holdNav('pan', [0.25, 0]).onPointerDown,
        rotL: this.holdNav('orbit', 0.05).onPointerDown, rotR: this.holdNav('orbit', -0.05).onPointerDown,
        tiltU: this.holdNav('tilt', -0.035).onPointerDown, tiltD: this.holdNav('tilt', 0.035).onPointerDown,
        zin: this.holdNav('zoom', 0.94).onPointerDown, zout: this.holdNav('zoom', 1.06).onPointerDown, reset: () => this.nav('reset'),
      },
      wrapRef: this.wrapRef, stageRef: this.stageRef, ovRef: this.ovRef,
      ...(() => {
        const nt = this.state.night, TI = Math.min(this.state.tourIdx || 0, this.TOUR.length - 1), TS = this.TOUR[TI];
        return {
          introOn: this.state.introOn, introRun: this.state.introRun, uiOp: this.state.introOn ? '0' : '1',
          skipIntro: () => { if (this.intro) this.intro.t = 99; }, replayIntro: () => this.startIntro(),
          rootBg: this.state.introOn ? '#05080c' : nt ? '#0a0f15' : '#7a8998',
          ink: nt ? '#e6edf3' : '#121a22', ink2: nt ? '#9fb1c2' : '#1f2a35', bandWip: nt ? '#f3ad66' : '#5e3208', bandWork: nt ? '#86bdf0' : '#1d3d5c',
          toggleNight: () => this.setState(s => ({ night: !s.night })), nightLabel: nt ? '☀ 주간 모드' : '☾ 야간 모드',
          nightBg: nt ? '#e6edf3' : 'var(--glass)', nightFg: nt ? '#1c2530' : 'var(--t1)', nightIcon: nt ? '☀' : '☾', subShadow: nt ? 'rgba(0,0,0,0.85)' : 'rgba(255,255,255,0.6)',
          cv: nt ? { glass: 'rgba(16,23,32,0.66)', glass2: 'rgba(14,20,28,0.9)', gbd: 'rgba(140,180,210,0.22)', t1: '#e6edf3', t2: '#b6c4d1', t3: '#8ea0b1', chip: 'rgba(255,255,255,0.08)', sep: 'rgba(255,255,255,0.12)', albg: 'rgba(90,20,26,0.8)', wnbg: 'rgba(80,56,10,0.8)' }
            : { glass: 'rgba(255,255,255,0.62)', glass2: 'rgba(255,255,255,0.88)', gbd: 'rgba(255,255,255,0.9)', t1: '#1c2530', t2: '#44515e', t3: '#5b6876', chip: 'rgba(28,37,48,0.07)', sep: 'rgba(28,37,48,0.1)', albg: 'rgba(255,238,238,0.9)', wnbg: 'rgba(255,248,230,0.9)' },
          navOpen: this.state.navOpen, toggleNav: () => this.setState(s => ({ navOpen: !s.navOpen })),
          navBg: this.state.navOpen ? '#3d6fe0' : 'var(--glass)', navFg: this.state.navOpen ? '#ffffff' : 'var(--t1)',
          details: [['summary', '요약'], ['full', '전체']].map(([id, label]) => ({ label, onClick: () => this.setState({ detail: id }),
            bg: this.state.detail === id ? '#3d6fe0' : 'transparent', fg: this.state.detail === id ? '#ffffff' : 'var(--t2)' })),
          ...(() => {
            const sp = (arr) => { const a0 = arr.slice(-24); if (a0.length < 2) return ''; const lo = Math.min(...a0), hi = Math.max(...a0), rg = Math.max(1, hi - lo);
              return a0.map((v0, i) => (i * 52 / (a0.length - 1)).toFixed(1) + ',' + (16 - ((v0 - lo) / rg) * 14 - 1).toFixed(1)).join(' '); };
            const hs = this.state.hist; const wl = hs.wip, rising = wl.length > 3 && wl[wl.length - 1] > wl[wl.length - 4];
            const key = this.ORDER.filter(k => st[k] === 'ALARM').join(',');
            if (key !== this.lastAlarmKey) { if (key && key.length >= (this.lastAlarmKey || '').length) this.alarmSince = Date.now(); this.lastAlarmKey = key; }
            const fresh = this.alarmSince && Date.now() - this.alarmSince < 5000;
            return { uphPts: sp(hs.uph), wipPts: sp(hs.wip), wipStroke: rising ? '#e5484d' : '#3d6fe0',
              edgeAnim: fresh ? 'edgePulse 1.1s ease-in-out infinite' : 'edgePulseSoft 2.8s ease-in-out infinite' };
          })(),
          tourOn: this.state.tourOn, noTour: !this.state.tourOn, startTour: () => this.startTour(),
          tourPrev: () => this.tourJump(-1), tourNext: () => this.tourJump(1), tourToggle: () => this.tourPause(), tourStop: () => this.stopTour(),
          pauseLabel: this.state.tourPaused ? '▶' : '❚❚',
          tStep: String(TI + 1).padStart(2, '0') + ' / ' + this.TOUR.length, tK: TS.k, tT: TS.t, tD: TS.d,
          tourSegs: this.TOUR.map((s0, i) => ({ flex: String(s0.dur), fill: i < TI ? '100%' : i === TI ? Math.round((this.state.tourU || 0) * 100) + '%' : '0%' })),
          showEdge: !!this.ORDER.find(k => st[k] === 'ALARM') && !this.state.introOn && !this.state.tourOn,
        };
      })(),
      embedded: !!this.props.embedded,
      op30Bn: !!this.props.dataMode && this.state.bn === 'OP-30',
      // 측정 카드: 데이터적용본은 App이 시뮬레이터 측정값(결과 파일)으로 만든 줄 (props.cmmCard)
      cmmRows: (this.props.cmmCard && this.props.cmmCard.rows) || [['Ø45 H7', '45.000', '—', '—'], ['길이', '150.0', '—', '—'], ['폭', '55.0', '—', '—'], ['두께', '12.0', '—', '—']],
      cmmStats: (this.props.cmmCard && this.props.cmmCard.stats) || [['오늘 측정', '—'], ['불합격', '—']],
      clock: this.state.clock, uph: this.state.uph,
      showCards: this.props.showCards ?? true,
      hasSel: !!sel && !this.state.tourOn, d, info,
      restartSel: () => { if (!sel) return; if (eff(sel) === 'WARN') this.clearWarn(sel); else this.restart(sel); },
      closeSel: () => this.setView(this.state.view),
      selCmm: pick('cmm'),
      nRun, nAlarm, wipTotal,
      runFg: nRun < 7 ? '#e5484d' : 'var(--t1)', alarmFg: nAlarm ? '#e5484d' : 'var(--t1)',
      hasAlarm: !!alarmId, alarmName: alarmId ? this.MACH[alarmId].name : '', alarmAt: this.state.alarmAt,
      openAlarm: () => alarmId && this.select(alarmId),
      panelTop: '104px', issues, banners: (sel || this.state.tourOn || this.state.introOn) ? [] : issues, nWarn, warnFg: nWarn ? '#e09400' : 'var(--t3)',
      legendOpen: this.state.pop === 'legend', toggleLegend: () => this.setState(s => ({ pop: s.pop === 'legend' ? null : 'legend' })),
      legendBg: this.state.pop === 'legend' ? '#3d6fe0' : 'var(--glass)', legendFg: this.state.pop === 'legend' ? '#ffffff' : 'var(--t1)',
      presentOpen: this.state.pop === 'present', togglePresent: () => this.setState(s => ({ pop: s.pop === 'present' ? null : 'present' })),
      presentItems: [
        { label: '▶ 제품 투어', sub: '부품 하나를 따라 11단계 공정 안내', onClick: () => { this.setState({ pop: null }); this.startTour(); } },
        { label: '오프닝 재생', sub: '조명 점등 · 설비 등장 시네마틱', onClick: () => { this.setState({ pop: null }); this.startIntro(); } },
        { label: '주의 · 고장 시연', sub: '설비 이상 상황 재현', onClick: () => this.setState({ pop: 'demo' }) },
      ],
      layersOpen: this.state.pop === 'layers', toggleLayers: () => this.setState(s => ({ pop: s.pop === 'layers' ? null : 'layers' })),
      layersBg: this.state.pop === 'layers' ? '#3d6fe0' : 'var(--glass)', layersFg: this.state.pop === 'layers' ? '#ffffff' : 'var(--t1)',
      layerItems: [['bloom', '빛 번짐 (블룸)', '야간 모드에서 네온·경광등 발광'], ['holo', '홀로그램 게이지', '설비 위 3D 부하 게이지 (카드 대체)'], ['heat', '열화상 히트맵', '설비 부하·온도 분포'], ['flow', '물류 흐름선 (보조)', '컨베이어 위 이동 경로 표시']].map(([k, label, sub]) => {
        const L0 = this.state.layers || {}, on = k === 'holo' || k === 'heat' ? !!L0[k] : L0[k] !== false;
        return { label, sub, mark: on ? '✓' : '', boxBg: on ? '#3d6fe0' : 'transparent', boxBd: on ? '#3d6fe0' : 'var(--t3)', onClick: () => this.setState(s => ({ layers: { ...s.layers, [k]: !on } })) };
      }),
      qNote: this.state.qNote || ('품질: ' + (this.props.quality || '자동')),
      explodeLabel: this.state.explode ? '조립 보기' : '분해 보기', toggleExplode: () => { this.setState(s => ({ explode: !s.explode })); if (sel && !this.state.explode && this.camera) { const c0 = this.controls.target, off = this.camera.position.clone().sub(c0).multiplyScalar(1.35); this.goal = { pos: c0.clone().add(off), target: c0.clone() }; } },
      explodeBg: this.state.explode ? '#3d6fe0' : 'var(--chip)', explodeFg: this.state.explode ? '#ffffff' : 'var(--t1)',
      wide: !this.state.narrow, sparkDisp: this.state.narrow ? 'none' : 'block',
      demoOpen: this.state.pop === 'demo', toggleDemo: () => this.setState(s => ({ pop: s.pop === 'demo' ? null : 'demo' })),
      demoBg: this.state.pop === 'demo' ? '#3d6fe0' : 'var(--glass)', demoFg: this.state.pop === 'demo' ? '#ffffff' : 'var(--t1)',
      demoTargets: this.ORDER.map(id => { const on = this.state.demoT === id, e0 = eff(id);
        return { name: this.MACH[id].name, dot: S[e0].dot, onClick: () => this.setState({ demoT: id }),
          bg: on ? '#3d6fe0' : 'var(--chip)', fg: on ? '#ffffff' : 'var(--t1)', bd: on ? '#3d6fe0' : 'var(--sep)' }; }),
      demoName: this.MACH[this.state.demoT].name, demoStText: S[eff(this.state.demoT)].label, demoStFg: S[eff(this.state.demoT)].fg,
      demoWarnMsg: this.ISSUE[this.state.demoT].w[1], demoAlarmMsg: this.ISSUE[this.state.demoT].a[1],
      doWarn: () => this.demo('warn'), doAlarm: () => this.demo('alarm'), doFix: () => this.demo('fix'), doReset: () => this.demo('reset'),
      toggleFocus: () => this.setState(s => ({ demoFocus: !s.demoFocus })), focusMark: this.state.demoFocus ? '✓' : '', focusBg: this.state.demoFocus ? '#1c2530' : '#ffffff',
      xTicks, yTicks,
      cards: [
        card('card-saw', 'saw', 'SAW-01', 'OP-10 · 절단', m.saw),
        card('card-vf1', 'vf1', 'VF2-01', 'OP-30 · 가공', m.vf1),
        card('card-vf2', 'vf2', 'VF2-02', 'OP-30 · 가공', m.vf2),
        card('card-wsh', 'wsh', 'WSH-01', 'OP-40 · 세척', m.wsh, 'Filter Life'),
      ],
      tags: this.props.embedded // 앱 화면: 설비·봉재 랙 이름은 3D 천장 표지판(장면 안 판)으로 — 화면 위 이름표 없음
        ? []
        : [
        { id: 'tag-inf', mid: 'inf', name: 'INF-01', op: '투입 베드', dot: S[eff('inf')].dot, onSelect: pick('inf') },
        { id: 'tag-mil', mid: 'mil', name: 'MIL-01', op: 'OP-20', dot: S[eff('mil')].dot, onSelect: pick('mil') },
        { id: 'tag-rack', mid: 'rack', name: 'RACK-01', op: '봉재 랙', dot: '#8a97a4', onSelect: null },
      ],
      wips: this.props.dataMode ? [
        wipItem('wip-1', 'w1', 'WIP-1', 'OP-10→20', 'wip'),
        wipItem('wip-2', 'w2', 'WIP-2', 'OP-20→30', 'wip'),
        wipItem('wip-3', 'w3', 'WIP-3', 'OP-30→40', 'wip'),
        wipItem('wip-4', 'w4', 'WIP-4', 'OP-40→50', 'wip'),
        wipItem('fg-01', 'fg', 'FG-01', '완성 (OP-50 통과)', 'fg'), // 사용자 요청 2026-10-16: 보라색 SOAK-01 칩 없앰
      ] : [
        wipItem('wip-1', 'w1', 'WIP-1', '재공 자리', 'wip'),
        wipItem('wip-2', 'w2', 'WIP-2', '재공 자리', 'wip'),
        wipItem('wip-3', 'w3', 'WIP-3', '재공 자리', 'wip'),
        wipItem('wip-4', 'w4', 'WIP-4', '재공 자리', 'wip'),
        wipItem('fg-01', 'fg', 'FG-01', '완성품 자리', 'fg'),
      ],
      stepper: this.ORDER.map((id, i) => {
        const M = this.MACH[id], on = sel === id;
        return { name: M.name, label: this.state.narrow ? (id === 'inf' ? 'INF' : M.op) : M.name, op: M.op, dot: S[eff(id)].dot, arrow: i < this.ORDER.length - 1, onClick: pick(id),
          bg: on ? '#3d6fe0' : 'var(--glass)', fg: on ? '#ffffff' : 'var(--t1)', bd: on ? '#3d6fe0' : eff(id) === 'ALARM' ? '#e5484d' : eff(id) === 'WARN' ? '#f0a500' : 'var(--gbd)' };
      }),
      views: [['front', '정면'], ['iso', '아이소'], ['top', '평면'], ['wh', '창고']].map(([id, label]) => ({
        label, onClick: () => this.setView(id),
        bg: !sel && view === id ? '#3d6fe0' : 'transparent', fg: !sel && view === id ? '#ffffff' : 'var(--t2)',
      })),
    };
  }

  render() {
    const v: any = this.renderVals();
    return (
      <>
<div className={`relative w-full ${v.embedded ? 'h-full' : 'h-[100vh]'} min-h-[300px] overflow-hidden [font-family:'Pretendard_Variable',sans-serif] text-[color:var(--t1)]`} ref={v.wrapRef} style={{ background: v.rootBg, '--ink': v.ink, '--ink2': v.ink2, '--bw': v.bandWip, '--bk': v.bandWork, '--glass': v.cv.glass, '--glass2': v.cv.glass2, '--gbd': v.cv.gbd, '--t1': v.cv.t1, '--t2': v.cv.t2, '--t3': v.cv.t3, '--chip': v.cv.chip, '--sep': v.cv.sep, '--albg': v.cv.albg, '--wnbg': v.cv.wnbg } as any}>
  <div className="absolute inset-0 [cursor:grab]" ref={v.stageRef}></div>
  {v.showEdge && (<>
    <div className="absolute inset-0 pointer-events-none" style={{ animation: v.edgeAnim } as any}></div>
  </>)}

  <div className="absolute inset-0 pointer-events-none overflow-hidden" ref={v.ovRef}>
    {(v.xTicks || []).map((t: any, $index: number) => (<React.Fragment key={$index}>
      <div className="absolute left-0 top-0 invisible [font:500_12px_'Pretendard_Variable',sans-serif] text-[color:var(--ink2)]" data-tier="axis" data-anchor={t.id} data-noscale="1" data-align="center">{t.label}</div>
    </React.Fragment>))}
    {(v.yTicks || []).map((t: any, $index: number) => (<React.Fragment key={$index}>
      <div className="absolute left-0 top-0 invisible [font:500_12px_'Pretendard_Variable',sans-serif] text-[color:var(--ink2)]" data-tier="axis" data-anchor={t.id} data-noscale="1" data-align="center">{t.label}</div>
    </React.Fragment>))}
    <div className="absolute left-0 top-0 invisible text-[13px] font-medium text-[color:var(--ink2)] whitespace-nowrap" data-tier="axis" data-anchor="ax-x" data-noscale="1" data-align="center">X (mm) → 동쪽 · 공정 흐름</div>
    <div className="absolute left-0 top-0 invisible text-[13px] font-medium text-[color:var(--ink2)] whitespace-nowrap" data-tier="axis" data-anchor="ax-y" data-noscale="1" data-align="center">Y (mm) ↑ 북쪽</div>

    {/* OP-30 AREA BOUNDARY 글자 뺌 (사용자 요청 2026-10-19) — 재공 바닥 글자와 겹침, 점선·OP-30 이름표로 충분 */}
    <div className="absolute left-0 top-0 invisible [transform-origin:50%_50%] text-[12px] font-semibold text-[color:var(--ink)] whitespace-nowrap" data-tier="zone" data-anchor="z-exit" data-align="center">EXIT-1 비상구</div>
    <div className="absolute left-0 top-0 invisible [transform-origin:50%_50%] text-[12px] font-semibold text-[color:var(--ink)] whitespace-nowrap" data-tier="zone" data-anchor="z-door" data-align="center">DOOR-1 반입문</div>
    <div className="absolute left-0 top-0 invisible [transform-origin:50%_50%] text-[12px] font-semibold text-[color:var(--bw)] whitespace-nowrap" data-tier="zone" data-anchor="z-wip" data-align="center">재공 띠</div>
    <div className="absolute left-0 top-0 invisible [transform-origin:50%_50%] text-[12px] font-semibold text-[color:var(--bk)] whitespace-nowrap" data-tier="zone" data-anchor="z-work" data-align="center">작업 띠</div>
    <div className="absolute left-0 top-0 invisible [transform-origin:50%_50%] [font:500_11px_'Pretendard_Variable',sans-serif] text-[color:var(--ink2)] whitespace-nowrap" data-tier="zone" data-anchor="z-front" data-align="center">설비 앞면 선 Y 3,800</div>
    {/* 병목 표시는 위에서 비추는 주황 조명으로 (2026-10-19) — 판·칩은 설비·이름표를 가려서 뺌 */}

    {(v.wips || []).map((w: any, $index: number) => (<React.Fragment key={$index}>
      <div className="absolute left-0 top-0 invisible [transform-origin:50%_100%]" data-tier="wip" data-alert={w.alert} data-anchor={w.id}>
        <div className="flex flex-col items-stretch gap-[3px] min-w-[78px] p-[5px_9px_6px] rounded-[7px] [box-shadow:0_4px_12px_rgba(120,70,20,0.12)] whitespace-nowrap" style={{ background: w.bg, border: `1px solid ${w.bd}` } as any}>
          <div className="flex justify-between items-baseline gap-[8px]">
            <span className="[font:700_14px_'Pretendard_Variable',sans-serif]" style={{ color: w.fg } as any}>{w.name}</span>
            <span className="[font:700_14px_'Pretendard_Variable',sans-serif]" style={{ color: w.orange ? '#b45309' : w.fg } as any}>{w.cnt}</span>
          </div>
          <div className="h-[4px] rounded-[2px] bg-[var(--sep)] overflow-hidden"><div className="h-full rounded-[2px]" style={{ width: w.barW, background: w.bar } as any}></div></div>
          <span className="text-[12px] font-semibold" style={{ color: w.fg } as any}>{w.sub}</span>
        </div>
      </div>
    </React.Fragment>))}

    {(v.tags || []).map((g: any, $index: number) => (<React.Fragment key={$index}>
      <div className="absolute left-0 top-0 invisible [transform-origin:50%_100%] flex flex-col items-center" data-tier="tag" data-anchor={g.id} data-mid={g.mid}>
        <div className="pointer-events-auto cursor-pointer flex items-center gap-[8px] h-[34px] pl-[0px] pr-[11px] rounded-[7px] whitespace-nowrap overflow-hidden [box-shadow:0_3px_0_rgba(70,76,86,0.35),0_9px_16px_rgba(28,45,62,0.28)]" onClick={g.onSelect}
          style={{ backgroundColor: g.tagBg || '#ffffff', backgroundImage: 'linear-gradient(112deg,rgba(255,255,255,0) 30%,rgba(255,255,255,.7) 44%,rgba(255,255,255,0) 58%),linear-gradient(180deg,rgba(255,255,255,.7),rgba(255,255,255,0) 52%,rgba(60,66,76,.12))', border: `${g.tagBdw || 1}px ${g.tagDash ? 'dashed' : 'solid'} ${g.tagBd || '#c3cbd3'}` } as any}>
          <span className="self-stretch w-[6px]" style={{ background: g.dot } as any}></span>
          <span className={`${g.big ? 'text-[19px]' : 'text-[15px]'} font-bold text-[#1c2530] [font-family:'Pretendard_Variable',sans-serif]`}>{g.name}</span>
          {g.op && (<span className="[font:600_12px_'Pretendard_Variable',sans-serif] text-[#5d6b79]">{g.op}</span>)}
          {g.st && (<span data-detail className={`${g.big ? 'text-[22px] leading-none' : 'text-[13px]'} font-bold`} style={{ color: g.stFg } as any}>{g.st}</span>)}
          {g.bn && (<span data-detail className="text-[12px] font-bold p-[1px_6px] rounded-[4px] bg-[#fff1e0] text-[#b45309] [border:1.5px_solid_#e8954a]">▭ 병목</span>)}
        </div>
        <div className="w-[1.5px] h-[12px]" style={{ background: g.tagBd || '#c3cbd3' } as any}></div>
        <div className="w-[7px] h-[7px] rounded-[50%] bg-white [border:2px_solid_#1c2530]"></div>
      </div>
    </React.Fragment>))}

    {v.showCards && (<>
      {(v.cards || []).map((c: any, $index: number) => (<React.Fragment key={$index}>
        <div className="absolute left-0 top-0 invisible [transform-origin:50%_100%] flex flex-col items-center" data-tier="card" data-alert={c.alert} data-anchor={c.id} data-mid={c.mid}>
          <div className="pointer-events-auto cursor-pointer w-[178px] p-[10px_12px_12px] rounded-[11px] [backdrop-filter:blur(14px)_saturate(1.5)] [-webkit-backdrop-filter:blur(14px)_saturate(1.5)] [box-shadow:0_12px_30px_rgba(28,45,62,0.16),_inset_0_1px_0_rgba(255,255,255,0.95)] flex flex-col gap-[6px]" data-card="1" onClick={c.onSelect} style={{ animation: c.anim, background: c.bg, border: `1px solid ${c.bd}` } as any}>
            <div className="flex justify-between items-center gap-[8px] pb-[6px] [border-bottom:1px_solid_var(--sep)]">
              <span className="text-[14px] font-bold tracking-[-0.01em]">{c.name}</span>
              <span className="[font:600_10px_'Pretendard_Variable',sans-serif] text-[color:var(--t3)] p-[2px_6px] rounded-[4px] bg-[var(--chip)] whitespace-nowrap" data-detail="1">{c.op}</span>
            </div>
            <div className="flex justify-between items-center text-[12px] text-[color:var(--t2)]">
              <span>Status</span>
              <span className="flex items-center gap-[5px] [font:700_11px_'Pretendard_Variable',sans-serif]" style={{ color: c.stFg } as any}><span className="w-[6px] h-[6px] rounded-[50%] [animation:pulseDot_1.6s_ease-in-out_infinite]" style={{ background: c.stDot } as any}></span>{c.stText}</span>
            </div>
            {c.hasMsg && (<>
              <div className="text-[11px] font-semibold p-[4px_7px] rounded-[5px] leading-[1.35]" style={{ color: c.msgFg, background: c.msgBg } as any}>{c.msg}</div>
            </>)}
            <div className="flex justify-between text-[12px] text-[color:var(--t2)]">
              <span>{c.loadLabel || 'Machine Load'}</span>
              <span className="[font:600_12px_'Pretendard_Variable',sans-serif] text-[color:var(--t1)]">{c.load}{c.load === '—' ? '' : '%'}</span>
            </div>
            <div className="flex justify-between text-[12px] text-[color:var(--t2)]" data-detail="1">
              <span>{c.lifeLabel}</span>
              <span className="[font:600_12px_'Pretendard_Variable',sans-serif] text-[color:var(--t1)]">{c.tool}{c.tool === '—' ? '' : '%'}</span>
            </div>
            <div className="h-[5px] rounded-[3px] bg-[var(--sep)] overflow-hidden" data-detail="1">
              <div className="h-full rounded-[3px]" style={{ width: c.toolW, background: c.bar } as any}></div>
            </div>
          </div>
          <div className="w-[1px] h-[20px] bg-[rgba(28,37,48,0.35)]"></div>
          <div className="w-[7px] h-[7px] rounded-[50%] bg-[#1c2530] [border:2px_solid_#fff]"></div>
        </div>
      </React.Fragment>))}

      <div className="absolute left-0 top-0 invisible [transform-origin:50%_100%] flex flex-col items-center" data-tier="card" data-alert="0" data-anchor="card-cmm" data-mid="cmm">
        <div className="pointer-events-auto cursor-pointer w-[236px] p-[10px_12px_11px] rounded-[11px] bg-[var(--glass)] [backdrop-filter:blur(14px)_saturate(1.5)] [-webkit-backdrop-filter:blur(14px)_saturate(1.5)] [border:1px_solid_var(--gbd)] [box-shadow:0_12px_30px_rgba(28,45,62,0.16),_inset_0_1px_0_rgba(255,255,255,0.95)] flex flex-col gap-[7px]" data-card="1" onClick={v.selCmm}>
          <div className="flex justify-between items-center pb-[6px] [border-bottom:1px_solid_var(--sep)]">
            <span className="text-[14px] font-bold">CMM-01</span>
            <span className="[font:600_10px_'Pretendard_Variable',sans-serif] text-[color:var(--t3)] p-[2px_6px] rounded-[4px] bg-[var(--chip)]" data-detail="1">OP-50 · 품질 측정</span>
          </div>
          <div className="grid [grid-template-columns:1.1fr_1fr_1fr_auto] gap-x-[8px] gap-y-[4px] [font:500_11px_'Pretendard_Variable',sans-serif] text-[color:var(--t1)]" data-detail="1">
            <span className="[font-family:'Pretendard_Variable',sans-serif] text-[color:var(--t3)]">항목</span><span className="text-[color:var(--t3)] text-right">도면</span><span className="text-[color:var(--t3)] text-right">측정</span><span className="text-[color:var(--t3)]">판정</span>
            {v.cmmRows.map((r: any, i: number) => (<React.Fragment key={i}>
              <span className="[font-family:'Pretendard_Variable',sans-serif]">{r[0]}</span><span className="text-right">{r[1]}</span><span className="text-right">{r[2]}</span>
              <span className="font-bold" style={{ color: r[3] === '합격' ? '#13994f' : r[3] === '—' ? 'var(--t3)' : '#c62a2f' } as any}>{r[3]}</span>
            </React.Fragment>))}
          </div>
          <div className="flex flex-wrap gap-[4px_10px] justify-between pt-[6px] [border-top:1px_solid_var(--sep)] text-[11px] text-[color:var(--t2)]">
            {v.cmmStats.map((s: any, i: number) => (<span key={i}>{s[0]} <b className="[font-family:'Pretendard_Variable',sans-serif]" style={{ color: s[2] || 'var(--t1)' } as any}>{s[1]}</b></span>))}
          </div>
        </div>
        <div className="w-[1px] h-[20px] bg-[rgba(28,37,48,0.35)]"></div>
        <div className="w-[7px] h-[7px] rounded-[50%] bg-[#1c2530] [border:2px_solid_#fff]"></div>
      </div>
    </>)}
    {(v.issues || []).map((fx: any, $index: number) => (<React.Fragment key={$index}>
      <div className="absolute left-0 top-0 invisible [transform-origin:50%_50%]" data-tier="fx" data-anchor={fx.id} data-mid={fx.mid} data-align="center">
        <div className="relative w-[34px] h-[34px]" style={{ animation: fx.bob } as any}>
          <span className="absolute inset-0 rounded-[50%]" style={{ border: `2px solid ${fx.ring}`, animation: fx.ringAnim } as any}></span>
          <span className="absolute inset-0 rounded-[50%] flex items-center justify-center [font:800_19px_'Pretendard_Variable',sans-serif] text-[#ffffff]" style={{ background: fx.dot, boxShadow: `0 6px 16px ${fx.ring}` } as any}>{fx.sym}</span>
        </div>
      </div>
    </React.Fragment>))}
  </div>

  {!v.embedded && (<div className="absolute inset-0 pointer-events-none [transition:opacity_0.9s_ease]" style={{ opacity: v.uiOp } as any}>
  <div className="absolute top-[22px] left-[30px] flex flex-col gap-[8px] pointer-events-auto">
    <div className="[font-size:clamp(18px,_2.2vw,_30px)] font-semibold tracking-[-0.01em] text-[color:var(--ink)] max-w-[calc(100vw_-_560px)] min-w-[260px] text-balance">3D FACTORY PROCESS VISUALIZATION</div>
    <div className="flex gap-[10px] items-center text-[13px] text-[color:var(--ink2)] whitespace-nowrap" style={{ textShadow: `0 1px 6px ${v.subShadow}` } as any}>
      <span className="font-semibold text-[color:var(--ink)]">BRK-A100 라인 · 엔진 마운트 브래킷</span>
      <span className="w-[1px] h-[12px] bg-[#b7c0c9]"></span>
      <span className="[font-family:'Pretendard_Variable',sans-serif]">OP-10 → OP-50</span>
      <span className="w-[1px] h-[12px] bg-[#b7c0c9]"></span>
      <span>단위 mm</span>
    </div>
    <div className="flex items-center gap-[6px] flex-nowrap">
      <div className="flex gap-[2px] p-[3px] rounded-[9px] bg-[var(--glass)] [backdrop-filter:blur(14px)] [-webkit-backdrop-filter:blur(14px)] [border:1px_solid_var(--gbd)] [box-shadow:0_6px_18px_rgba(28,45,62,0.08)]">
        {(v.views || []).map((v: any, $index: number) => (<React.Fragment key={$index}>
          <button className="border-0 cursor-pointer p-[6px_13px] rounded-[7px] [font:600_12px_'Pretendard_Variable',sans-serif]" onClick={v.onClick} style={{ background: v.bg, color: v.fg } as any}>{v.label}</button>
        </React.Fragment>))}
      </div>
      <button className="cursor-pointer h-[32px] rounded-[9px] [border:1px_solid_var(--gbd)] [backdrop-filter:blur(14px)] [-webkit-backdrop-filter:blur(14px)] [font:600_12px_'Pretendard_Variable',sans-serif] whitespace-nowrap w-[34px] p-[0] text-[15px]" onClick={v.toggleNav} title="이동 · 회전 · 줌 도구" style={{ background: v.navBg, color: v.navFg } as any}>✥</button>
      <div className="flex gap-[2px] p-[3px] rounded-[9px] bg-[var(--glass)] [backdrop-filter:blur(14px)] [-webkit-backdrop-filter:blur(14px)] [border:1px_solid_var(--gbd)]">
        {(v.details || []).map((dm: any, $index: number) => (<React.Fragment key={$index}>
          <button className="border-0 cursor-pointer p-[6px_11px] rounded-[7px] [font:600_12px_'Pretendard_Variable',sans-serif] whitespace-nowrap" onClick={dm.onClick} style={{ background: dm.bg, color: dm.fg } as any}>{dm.label}</button>
        </React.Fragment>))}
      </div>
      <div className="relative">
        <button className="cursor-pointer flex items-center gap-[6px] h-[32px] p-[0_13px] rounded-[9px] border-0 bg-[#3d6fe0] text-[#ffffff] [font:700_12px_'Pretendard_Variable',sans-serif] [box-shadow:0_6px_16px_rgba(122,82,240,0.35)] whitespace-nowrap" onClick={v.togglePresent}>발표 모드<span className="text-[9px]">▾</span></button>
        {v.presentOpen && (<>
          <div className="absolute left-0 top-[calc(100%_+_6px)] w-[220px] flex flex-col gap-[2px] p-[8px] rounded-[10px] bg-[var(--glass2)] [backdrop-filter:blur(16px)] [-webkit-backdrop-filter:blur(16px)] [border:1px_solid_var(--gbd)] [box-shadow:0_14px_34px_rgba(28,45,62,0.2)] z-[5]">
            {(v.presentItems || []).map((pi: any, $index: number) => (<React.Fragment key={$index}>
              <button className="cursor-pointer flex flex-col items-start gap-[1px] p-[8px_10px] rounded-[7px] border-0 bg-[transparent] text-left [font-family:'Pretendard_Variable',sans-serif] hover:bg-[var(--chip)]" onClick={pi.onClick}>
                <span className="text-[13px] font-semibold text-[color:var(--t1)]">{pi.label}</span>
                <span className="text-[11px] text-[color:var(--t3)]">{pi.sub}</span>
              </button>
            </React.Fragment>))}
          </div>
        </>)}
      </div>
      <button className="cursor-pointer h-[32px] rounded-[9px] [border:1px_solid_var(--gbd)] [backdrop-filter:blur(14px)] [-webkit-backdrop-filter:blur(14px)] [font:600_12px_'Pretendard_Variable',sans-serif] whitespace-nowrap w-[34px] p-[0] text-[15px]" onClick={v.toggleNight} title={v.nightLabel} style={{ background: v.nightBg, color: v.nightFg } as any}>{v.nightIcon}</button>
    </div>
    <div className="flex gap-[10px] text-[11px] text-[color:var(--ink2)] whitespace-nowrap" style={{ textShadow: `0 1px 6px ${v.subShadow}` } as any}>
      <span>좌클릭 드래그 · 회전</span><span>우클릭 드래그 · 이동</span><span>휠 · 커서 위치로 확대</span><span>더블클릭 · 그 지점으로 이동</span>
    </div>
    {v.navOpen && (<>
  <div className="flex [align-self:flex-start] items-center gap-[2px] p-[3px] rounded-[10px] bg-[var(--glass)] [backdrop-filter:blur(14px)] [-webkit-backdrop-filter:blur(14px)] [border:1px_solid_var(--gbd)] [box-shadow:0_8px_22px_rgba(28,45,62,0.1)] [user-select:none] [touch-action:none]">
    <button className="cursor-pointer border-0 w-[28px] h-[28px] rounded-[7px] bg-[var(--chip)] text-[color:var(--t1)] text-[13px] font-semibold flex items-center justify-center" onPointerDown={v.nv.left} title="왼쪽 이동 (A)">◀</button><button className="cursor-pointer border-0 w-[28px] h-[28px] rounded-[7px] bg-[var(--chip)] text-[color:var(--t1)] text-[13px] font-semibold flex items-center justify-center" onPointerDown={v.nv.up} title="앞으로 (W)">▲</button><button className="cursor-pointer border-0 w-[28px] h-[28px] rounded-[7px] bg-[var(--chip)] text-[color:var(--t1)] text-[13px] font-semibold flex items-center justify-center" onPointerDown={v.nv.down} title="뒤로 (S)">▼</button><button className="cursor-pointer border-0 w-[28px] h-[28px] rounded-[7px] bg-[var(--chip)] text-[color:var(--t1)] text-[13px] font-semibold flex items-center justify-center" onPointerDown={v.nv.right} title="오른쪽 이동 (D)">▶</button>
    <span className="w-[1px] h-[20px] bg-[rgba(28,37,48,0.12)] m-[0_3px]"></span><button className="cursor-pointer border-0 w-[28px] h-[28px] rounded-[7px] bg-[var(--chip)] text-[color:var(--t1)] text-[13px] font-semibold flex items-center justify-center text-[15px]" onPointerDown={v.nv.rotL} title="왼쪽 회전 (Q)">↺</button><button className="cursor-pointer border-0 w-[28px] h-[28px] rounded-[7px] bg-[var(--chip)] text-[color:var(--t1)] text-[13px] font-semibold flex items-center justify-center text-[15px]" onPointerDown={v.nv.rotR} title="오른쪽 회전 (E)">↻</button><button className="cursor-pointer border-0 w-[28px] h-[28px] rounded-[7px] bg-[var(--chip)] text-[color:var(--t1)] text-[13px] font-semibold flex items-center justify-center" onPointerDown={v.nv.tiltU} title="위에서 보기">⤒</button><button className="cursor-pointer border-0 w-[28px] h-[28px] rounded-[7px] bg-[var(--chip)] text-[color:var(--t1)] text-[13px] font-semibold flex items-center justify-center" onPointerDown={v.nv.tiltD} title="옆에서 보기">⤓</button>
    <span className="w-[1px] h-[20px] bg-[rgba(28,37,48,0.12)] m-[0_3px]"></span><button className="cursor-pointer border-0 w-[28px] h-[28px] rounded-[7px] bg-[var(--chip)] text-[color:var(--t1)] text-[13px] font-semibold flex items-center justify-center text-[16px]" onPointerDown={v.nv.zin} title="확대 (+)">+</button><button className="cursor-pointer border-0 w-[28px] h-[28px] rounded-[7px] bg-[var(--chip)] text-[color:var(--t1)] text-[13px] font-semibold flex items-center justify-center text-[16px]" onPointerDown={v.nv.zout} title="축소 (−)">−</button>
    <span className="w-[1px] h-[20px] bg-[rgba(28,37,48,0.12)] m-[0_3px]"></span><button className="cursor-pointer border-0 w-[28px] h-[28px] rounded-[7px] bg-[var(--chip)] text-[color:var(--t1)] text-[13px] font-semibold flex items-center justify-center bg-[#1c2530] text-[#ffffff]" onClick={v.nv.reset} title="시점 초기화">⟲</button>
  </div>
    </>)}
  </div>

  <div className="absolute top-[22px] right-[24px] pointer-events-auto flex items-stretch rounded-[10px] bg-[var(--glass)] [backdrop-filter:blur(14px)] [-webkit-backdrop-filter:blur(14px)] [border:1px_solid_var(--gbd)] [box-shadow:0_8px_24px_rgba(28,45,62,0.1)]">
    <div className="flex flex-col gap-[3px] p-[10px_16px]">
      <span className="flex items-center gap-[6px] [font:700_10px_'Pretendard_Variable',sans-serif] text-[#13994f] tracking-[0.08em]"><span className="w-[6px] h-[6px] rounded-[50%] bg-[#1fbf63] [animation:pulseDot_1.6s_ease-in-out_infinite]"></span>LIVE</span>
      <span className="[font:600_16px_'Pretendard_Variable',sans-serif] whitespace-nowrap">{v.clock}</span>
    </div>
    <div className="w-[1px] bg-[var(--sep)]"></div>
    <div className="flex flex-col gap-[3px] p-[10px_16px]">
      <span className="text-[11px] text-[color:var(--t3)]">가동 설비</span>
      <span className="[font:600_16px_'Pretendard_Variable',sans-serif]" style={{ color: v.runFg } as any}>{v.nRun} / 6</span>
    </div>
    <div className="w-[1px] bg-[var(--sep)]"></div>
    <div className="flex flex-col gap-[3px] p-[10px_16px]">
      <span className="text-[11px] text-[color:var(--t3)]">알람</span>
      <span className="[font:600_16px_'Pretendard_Variable',sans-serif] whitespace-nowrap" style={{ color: v.alarmFg } as any}>{v.nAlarm} <span className="text-[11px]" style={{ color: v.warnFg } as any}>주의 {v.nWarn}</span></span>
    </div>
    <div className="w-[1px] bg-[var(--sep)]"></div>
    <div className="flex flex-col gap-[3px] p-[10px_16px]">
      <span className="text-[11px] text-[color:var(--t3)]">시간당 생산</span>
      <span className="flex items-center gap-[8px]"><span className="[font:600_16px_'Pretendard_Variable',sans-serif] whitespace-nowrap">{v.uph} <span className="text-[11px] text-[color:var(--t3)]">pcs</span></span><svg className="[overflow:visible]" width="52" height="18" viewBox="0 0 52 18" style={{ display: v.sparkDisp } as any}><polyline points={v.uphPts} fill="none" stroke="#3d6fe0" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" /></svg></span>
    </div>
    <div className="w-[1px] bg-[var(--sep)]"></div>
    <div className="flex flex-col gap-[3px] p-[10px_16px]">
      <span className="text-[11px] text-[color:var(--t3)]">재공 수량</span>
      <span className="flex items-center gap-[8px]"><span className="[font:600_16px_'Pretendard_Variable',sans-serif] whitespace-nowrap">{v.wipTotal} <span className="text-[11px] text-[color:var(--t3)]">EA</span></span><svg className="[overflow:visible]" width="52" height="18" viewBox="0 0 52 18" style={{ display: v.sparkDisp } as any}><polyline points={v.wipPts} fill="none" stroke={v.wipStroke} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" /></svg></span>
    </div>
  </div>

  <div className="absolute top-[90px] right-[24px] pointer-events-auto flex flex-col items-end gap-[6px]">
    {(v.banners || []).map((is: any, $index: number) => (<React.Fragment key={$index}>
      <button className="cursor-pointer flex items-center gap-[7px] h-[30px] p-[0_11px] rounded-[10px] [backdrop-filter:blur(12px)] [-webkit-backdrop-filter:blur(12px)] [box-shadow:0_8px_22px_rgba(28,45,62,0.14)] [font-family:'Pretendard_Variable',sans-serif] whitespace-nowrap" onClick={is.onClick} style={{ border: `1px solid ${is.bd}`, background: is.bg, color: is.fg, animation: is.banAnim } as any}>
        <span className="w-[8px] h-[8px] rounded-[50%] [animation:pulseDot_0.8s_ease-in-out_infinite]" style={{ background: is.dot } as any}></span>
        <span className="text-[12px] font-bold">{is.tag}</span>
        <span className="text-[12px] font-bold">{is.name}</span>
        <span className="text-[12px] font-medium">{is.msg} →</span>
      </button>
    </React.Fragment>))}
  </div>

      {v.demoOpen && (<>
        <div className="absolute left-[24px] bottom-[72px] pointer-events-auto w-[320px] max-w-[calc(100%_-_48px)] z-[2] flex flex-col gap-[12px] p-[14px] rounded-[10px] bg-[var(--glass2)] [backdrop-filter:blur(16px)] [-webkit-backdrop-filter:blur(16px)] [border:1px_solid_var(--gbd)] [box-shadow:0_14px_34px_rgba(28,45,62,0.18)] text-[12px] text-[color:var(--t2)]">
          <div className="flex justify-between items-center">
            <span className="text-[14px] font-bold text-[color:var(--t1)]">알람 시연</span>
            <span className="[font:700_11px_'Pretendard_Variable',sans-serif] whitespace-nowrap" style={{ color: v.demoStFg } as any}>{v.demoName} · {v.demoStText}</span>
          </div>
          <div className="flex flex-col gap-[6px]">
            <span className="text-[11px] font-bold tracking-[0.06em] text-[color:var(--t3)]">대상 설비</span>
            <div className="flex flex-wrap gap-[5px]">
              {(v.demoTargets || []).map((dt: any, $index: number) => (<React.Fragment key={$index}>
                <button className="cursor-pointer flex items-center gap-[5px] p-[5px_9px] rounded-[7px] [font:600_12px_'Pretendard_Variable',sans-serif] whitespace-nowrap" onClick={dt.onClick} style={{ border: `1px solid ${dt.bd}`, background: dt.bg, color: dt.fg } as any}>
                  <span className="w-[6px] h-[6px] rounded-[50%]" style={{ background: dt.dot } as any}></span>{dt.name}
                </button>
              </React.Fragment>))}
            </div>
          </div>
          <div className="grid [grid-template-columns:1fr_1fr] gap-[6px]">
            <button className="cursor-pointer flex flex-col items-start gap-[2px] p-[10px_11px] rounded-[9px] [border:1px_solid_#f0a500] bg-[#fff6de] text-[#7a4b00] [font-family:'Pretendard_Variable',sans-serif] text-left" onClick={v.doWarn}>
              <span className="flex items-center gap-[6px] text-[13px] font-bold"><span className="w-[8px] h-[8px] rounded-[50%] bg-[#f0a500]"></span>주의 발생</span>
              <span className="text-[11px] font-medium">{v.demoWarnMsg}</span>
            </button>
            <button className="cursor-pointer flex flex-col items-start gap-[2px] p-[10px_11px] rounded-[9px] [border:1px_solid_#e5484d] bg-[#ffe9e9] text-[#a01e23] [font-family:'Pretendard_Variable',sans-serif] text-left" onClick={v.doAlarm}>
              <span className="flex items-center gap-[6px] text-[13px] font-bold"><span className="w-[8px] h-[8px] rounded-[50%] bg-[#e5484d]"></span>고장 발생</span>
              <span className="text-[11px] font-medium">{v.demoAlarmMsg}</span>
            </button>
          </div>
          <div className="grid [grid-template-columns:1fr_1fr] gap-[6px]">
            <button className="cursor-pointer p-[8px_10px] rounded-[8px] border-0 bg-[#1c2530] text-[#ffffff] [font:700_12px_'Pretendard_Variable',sans-serif]" onClick={v.doFix}>선택 설비 복구</button>
            <button className="cursor-pointer p-[8px_10px] rounded-[8px] [border:1px_solid_rgba(28,37,48,0.15)] bg-[#ffffff] text-[color:var(--t1)] [font:700_12px_'Pretendard_Variable',sans-serif]" onClick={v.doReset}>전체 정상화</button>
          </div>
          <button className="cursor-pointer flex items-center gap-[8px] p-[0] border-0 bg-[transparent] text-[color:var(--t2)] [font:500_12px_'Pretendard_Variable',sans-serif]" onClick={v.toggleFocus}>
            <span className="w-[16px] h-[16px] rounded-[4px] [border:1.5px_solid_#1c2530] text-[#ffffff] flex items-center justify-center text-[11px] font-bold" style={{ background: v.focusBg } as any}>{v.focusMark}</span>
            발생 시 카메라 자동 포커스 · 상세 패널 열기
          </button>
        </div>
      </>)}
  {v.noTour && (<>
  <div className="absolute left-[24px] right-[24px] bottom-[18px] flex items-center gap-[12px] pointer-events-auto">
    <div className="flex-1 min-w-0 flex items-center gap-[4px] p-[4px] rounded-[11px] bg-[var(--glass)] [backdrop-filter:blur(14px)] [-webkit-backdrop-filter:blur(14px)] [border:1px_solid_var(--gbd)] [box-shadow:0_8px_22px_rgba(28,45,62,0.1)] [overflow-x:auto] [scrollbar-width:none]">
      <span className="flex-none text-[11px] font-bold tracking-[0.06em] text-[color:var(--t3)] p-[0_8px_0_6px]">공정</span>
      {(v.stepper || []).map((s: any, $index: number) => (<React.Fragment key={$index}>
        <div className="flex-none flex items-center gap-[4px]">
          <button className="cursor-pointer flex items-center gap-[5px] p-[5px_8px] rounded-[8px] [font-family:'Pretendard_Variable',sans-serif] whitespace-nowrap" onClick={s.onClick} style={{ border: `1px solid ${s.bd}`, background: s.bg, color: s.fg } as any}>
            <span className="w-[7px] h-[7px] rounded-[50%]" style={{ background: s.dot } as any}></span>
            <span className="text-[11px] font-bold">{s.label}</span>
          </button>
          {s.arrow && (<>
            <span className="text-[#3d6fe0] text-[10px] font-bold">›</span>
          </>)}
        </div>
      </React.Fragment>))}
    </div>
    <div className="flex-none relative">
      <button className="cursor-pointer h-[38px] p-[0_14px] flex items-center gap-[7px] rounded-[11px] [border:1px_solid_var(--gbd)] [backdrop-filter:blur(14px)] [-webkit-backdrop-filter:blur(14px)] [box-shadow:0_8px_22px_rgba(28,45,62,0.1)] [font:600_12px_'Pretendard_Variable',sans-serif] whitespace-nowrap" onClick={v.toggleDemo} style={{ background: v.demoBg, color: v.demoFg } as any}><span className="flex gap-[3px]"><span className="w-[7px] h-[7px] rounded-[50%] bg-[#f0a500]"></span><span className="w-[7px] h-[7px] rounded-[50%] bg-[#e5484d]"></span></span>알람 시연</button>
    </div>
    <div className="flex-none relative">
      <button className="cursor-pointer h-[38px] p-[0_14px] rounded-[11px] [border:1px_solid_var(--gbd)] [backdrop-filter:blur(14px)] [-webkit-backdrop-filter:blur(14px)] [box-shadow:0_8px_22px_rgba(28,45,62,0.1)] [font:600_12px_'Pretendard_Variable',sans-serif] whitespace-nowrap" onClick={v.toggleLayers} style={{ background: v.layersBg, color: v.layersFg } as any}>레이어</button>
      {v.layersOpen && (<>
        <div className="absolute right-0 bottom-[calc(100%_+_8px)] w-[280px] flex flex-col gap-[4px] p-[12px] rounded-[10px] bg-[var(--glass2)] [backdrop-filter:blur(16px)] [-webkit-backdrop-filter:blur(16px)] [border:1px_solid_var(--gbd)] [box-shadow:0_14px_34px_rgba(28,45,62,0.18)]">
          <span className="text-[11px] font-bold tracking-[0.06em] text-[color:var(--t3)] p-[0_4px_4px]">시각화 레이어</span>
          {(v.layerItems || []).map((ly: any, $index: number) => (<React.Fragment key={$index}>
            <button className="cursor-pointer flex items-center gap-[10px] p-[7px_6px] rounded-[8px] border-0 bg-[transparent] text-left [font-family:'Pretendard_Variable',sans-serif]" onClick={ly.onClick}>
              <span className="flex-none w-[18px] h-[18px] rounded-[5px] text-[#ffffff] flex items-center justify-center text-[11px] font-bold" style={{ border: `1.5px solid ${ly.boxBd}`, background: ly.boxBg } as any}>{ly.mark}</span>
              <span className="flex flex-col gap-[1px]">
                <span className="text-[13px] font-semibold text-[color:var(--t1)]">{ly.label}</span>
                <span className="text-[11px] text-[color:var(--t3)]">{ly.sub}</span>
              </span>
            </button>
          </React.Fragment>))}
          <span className="text-[11px] text-[color:var(--t3)] p-[6px_6px_0] [border-top:1px_solid_var(--sep)] mt-[4px]">{v.qNote}</span>
        </div>
      </>)}
    </div>
    <div className="flex-none relative">
      <button className="cursor-pointer h-[38px] p-[0_14px] rounded-[11px] [border:1px_solid_var(--gbd)] [backdrop-filter:blur(14px)] [-webkit-backdrop-filter:blur(14px)] [box-shadow:0_8px_22px_rgba(28,45,62,0.1)] [font:600_12px_'Pretendard_Variable',sans-serif] whitespace-nowrap" onClick={v.toggleLegend} style={{ background: v.legendBg, color: v.legendFg } as any}>범례 · 도움말</button>
      {v.legendOpen && (<>
        <div className="absolute right-0 bottom-[calc(100%_+_8px)] w-[300px] flex flex-col gap-[10px] p-[12px_14px] rounded-[10px] bg-[var(--glass2)] [backdrop-filter:blur(16px)] [-webkit-backdrop-filter:blur(16px)] [border:1px_solid_var(--gbd)] [box-shadow:0_14px_34px_rgba(28,45,62,0.16)] text-[12px] text-[color:var(--t2)]">
          <span className="text-[11px] font-bold tracking-[0.06em] text-[color:var(--t3)]">설비 상태</span>
          <div className="grid [grid-template-columns:1fr_1fr] gap-[6px_12px]">
            <span className="flex items-center gap-[7px]"><span className="w-[8px] h-[8px] rounded-[50%] bg-[#1fbf63]"></span>RUNNING 가동</span>
            <span className="flex items-center gap-[7px]"><span className="w-[8px] h-[8px] rounded-[50%] bg-[#f0a500]"></span>WARNING 주의</span>
            <span className="flex items-center gap-[7px]"><span className="w-[8px] h-[8px] rounded-[50%] bg-[#8a97a4]"></span>IDLE 대기</span>
            <span className="flex items-center gap-[7px]"><span className="w-[8px] h-[8px] rounded-[50%] bg-[#e5484d]"></span>ALARM 고장</span>
            <span className="flex items-center gap-[7px]"><span className="w-[8px] h-[8px] rounded-[50%] bg-[#3b82f6]"></span>SETUP 셋업</span>
          </div>
          <span className="text-[11px] font-bold tracking-[0.06em] text-[color:var(--t3)]">물류 · 영역</span>
          <div className="grid [grid-template-columns:1fr_1fr] gap-[6px_12px]">
            <span className="flex items-center gap-[7px]"><span className="w-[20px] h-[3px] rounded-[2px] bg-[#e23b3b]"></span>물류 흐름</span>
            <span className="flex items-center gap-[7px]"><span className="w-[20px] h-[3px] rounded-[2px] bg-[#a3abb3]"></span>흐름 정지</span>
            <span className="flex items-center gap-[7px]"><span className="w-[20px] h-[0] [border-top:2px_dashed_#e23b3b]"></span>보조 흐름</span>
            <span className="flex items-center gap-[7px]"><span className="w-[14px] h-[10px] [border:1.5px_dashed_#56616c] rounded-[2px]"></span>OP-30 셀</span>
            <span className="flex items-center gap-[7px]"><span className="w-[12px] h-[12px] rounded-[50%] [border:2px_solid_#e5484d]"></span>재공 적체 &gt;60%</span>
            <span className="flex items-center gap-[7px]"><span className="w-[20px] h-[4px] rounded-[2px] bg-[#4fd2ea]"></span>영역 경계</span>
          </div>
          <span className="text-[11px] font-bold tracking-[0.06em] text-[color:var(--t3)]">조작</span>
          <span className="leading-[1.5]">설비 클릭 → 상세 공정 · 드래그 회전 · 우클릭 이동 · 휠 줌 · WASD 이동 · Q/E 회전</span>
        </div>
      </>)}
    </div>
  </div>

  </>)}
  {v.hasSel && (<>
    <div className="absolute right-[24px] pointer-events-auto bottom-[72px] w-[340px] max-w-[calc(100%_-_48px)] flex flex-col rounded-[10px] bg-[var(--glass)] [backdrop-filter:blur(18px)_saturate(1.4)] [-webkit-backdrop-filter:blur(18px)_saturate(1.4)] [border:1px_solid_var(--gbd)] [box-shadow:0_18px_44px_rgba(28,45,62,0.18)] overflow-hidden" style={{ top: v.panelTop } as any}>
      <div className="flex flex-col gap-[8px] p-[16px_18px_14px] [border-bottom:1px_solid_rgba(28,37,48,0.08)]">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-[8px]">
            <span className="flex items-center gap-[5px] [font:700_11px_'Pretendard_Variable',sans-serif]" style={{ color: v.d.stFg } as any}><span className="w-[7px] h-[7px] rounded-[50%] [animation:pulseDot_1.6s_ease-in-out_infinite]" style={{ background: v.d.stDot } as any}></span>{v.d.stText}</span>
            <span className="[font:600_10px_'Pretendard_Variable',sans-serif] text-[color:var(--t3)] p-[2px_6px] rounded-[4px] bg-[var(--chip)]">{v.d.op}</span>
          </div>
          <button className="cursor-pointer h-[28px] p-[0_10px] rounded-[7px] border-0 [font:600_12px_'Pretendard_Variable',sans-serif] whitespace-nowrap ml-auto mr-[6px]" onClick={v.toggleExplode} style={{ background: v.explodeBg, color: v.explodeFg } as any}>{v.explodeLabel}</button>
          <button className="cursor-pointer w-[28px] h-[28px] rounded-[7px] border-0 bg-[var(--chip)] text-[color:var(--t1)] text-[16px] leading-[1]" onClick={v.closeSel}>×</button>
        </div>
        <div className="flex items-baseline gap-[10px]">
          <span className="text-[24px] font-bold tracking-[-0.01em]">{v.d.name}</span>
          <span className="text-[13px] text-[color:var(--t3)]">{v.d.kr}</span>
        </div>
        <span className="text-[13px] leading-[1.5] text-[color:var(--t2)] text-pretty">{v.d.desc}</span>
      </div>
      <div className="flex-1 min-h-[0] [overflow-y:auto] [overflow-x:hidden] flex flex-col gap-[16px] p-[14px_18px_18px]">
        {v.info.show && (<>
          <div className="flex flex-col gap-[8px] p-[12px] rounded-[10px]" style={{ background: v.info.bg, border: `1px solid ${v.info.bd}` } as any}>
            <span className="text-[13px] font-bold" style={{ color: v.info.fg } as any}>{v.info.title}</span>
            {(v.info.rows || []).map((ir: any, $index: number) => (<React.Fragment key={$index}>
              <div className="grid [grid-template-columns:62px_minmax(0,1fr)] gap-[8px] text-[12px]">
                <span className="text-[color:var(--t3)]">{ir.k}</span>
                <span className="text-[color:var(--t1)] font-semibold">{ir.v}</span>
              </div>
            </React.Fragment>))}
            {v.info.hasGuide && (<>
              <div className="flex flex-col gap-[4px] pt-[6px] [border-top:1px_solid_var(--sep)]">
                <span className="text-[11px] font-bold text-[color:var(--t3)]">조치 가이드</span>
                {(v.info.guide || []).map((gd: any, $index: number) => (<React.Fragment key={$index}>
                  <div className="flex items-center gap-[8px] text-[12px] text-[color:var(--t1)]">
                    <span className="w-[18px] h-[18px] rounded-[50%] flex items-center justify-center [font:700_10px_'Pretendard_Variable',sans-serif] bg-[#ffffff]" style={{ color: v.info.fg, border: `1px solid ${v.info.bd}` } as any}>{gd.n}</span>{gd.t}
                  </div>
                </React.Fragment>))}
              </div>
            </>)}
            {v.info.canRestart && (<>
              <button className="cursor-pointer mt-[2px] p-[9px_12px] rounded-[8px] border-0 bg-[#1c2530] text-[#ffffff] [font:700_13px_'Pretendard_Variable',sans-serif]" onClick={v.restartSel}>{v.info.btnLabel}</button>
            </>)}
          </div>
        </>)}
        <div className="flex flex-col gap-[7px]">
          <div className="flex justify-between items-baseline">
            <span className="text-[11px] font-semibold tracking-[0.06em] text-[color:var(--t3)]">사이클 진행</span>
            <span className="[font:600_12px_'Pretendard_Variable',sans-serif]">{v.d.elapsed}s / {v.d.T}s</span>
          </div>
          <div className="h-[6px] rounded-[3px] bg-[var(--sep)] overflow-hidden">
            <div className="h-full rounded-[3px] [background:linear-gradient(90deg,#3a9fb0,#34c46e)]" style={{ width: v.d.progW } as any}></div>
          </div>
        </div>
        <div className="flex flex-col gap-[2px]">
          <span className="text-[11px] font-semibold tracking-[0.06em] text-[color:var(--t3)] pb-[5px]">공정 단계</span>
          {(v.d.steps || []).map((st: any, $index: number) => (<React.Fragment key={$index}>
            <div className="grid [grid-template-columns:28px_minmax(0,1fr)] gap-[10px] [align-items:start] p-[7px_8px] rounded-[8px]" style={{ background: st.rowBg } as any}>
              <span className="w-[26px] h-[22px] rounded-[6px] flex items-center justify-center [font:700_11px_'Pretendard_Variable',sans-serif]" style={{ background: st.numBg, color: st.numFg } as any}>{st.n}</span>
              <div className="flex flex-col gap-[2px]">
                <div className="flex items-center gap-[6px]">
                  <span className="text-[13px] font-semibold" style={{ color: st.tFg } as any}>{st.title}</span>
                  {st.isCur && (<>
                    <span className="text-[10px] font-bold p-[1px_6px] rounded-[4px]" style={{ color: st.curFg, background: st.curBg } as any}>{st.curLabel}</span>
                  </>)}
                </div>
                <span className="text-[12px] text-[color:var(--t3)] leading-[1.4]">{st.sub}</span>
              </div>
            </div>
          </React.Fragment>))}
        </div>
        <div className="flex flex-col gap-[7px]">
          <span className="text-[11px] font-semibold tracking-[0.06em] text-[color:var(--t3)]">가공 조건</span>
          <div className="grid [grid-template-columns:1fr_1fr] gap-[6px]">
            {(v.d.params || []).map((pm: any, $index: number) => (<React.Fragment key={$index}>
              <div className="flex flex-col gap-[2px] p-[8px_10px] rounded-[8px] bg-[var(--chip)]">
                <span className="text-[11px] text-[color:var(--t3)]">{pm.k}</span>
                <span className="[font:600_13px_'Pretendard_Variable',sans-serif] text-[color:var(--t1)]">{pm.v}</span>
              </div>
            </React.Fragment>))}
          </div>
        </div>
        <div className="flex flex-col gap-[7px]">
          <span className="text-[11px] font-semibold tracking-[0.06em] text-[color:var(--t3)]">물류 연결</span>
          <div className="flex items-center gap-[8px] text-[12px]">
            <span className="p-[5px_9px] rounded-[6px] bg-[#fff0de] [border:1px_solid_#e8954a] text-[#7a3f0c] font-semibold">{v.d.inp}</span>
            <span className="text-[#e23b3b] font-bold">→</span>
            <span className="p-[5px_9px] rounded-[6px] bg-[#1c2530] text-[#fff] font-semibold">{v.d.name}</span>
            <span className="text-[#e23b3b] font-bold">→</span>
            <span className="p-[5px_9px] rounded-[6px] bg-[#fff0de] [border:1px_solid_#e8954a] text-[#7a3f0c] font-semibold">{v.d.out}</span>
          </div>
        </div>
      </div>
    </div>
  </>)}
  </div>)}

  {v.tourOn && (<>
    {/* 투어 설명 = 화면 아래 한 줄 띠 (사용자 요청 2026-10-20 "최대한 한줄로 길게 … 화면을 최대한 안가리도록"). 설명이 넘치면 … (마우스를 올리면 전체) */}
    <div className={`absolute left-[12px] ${v.embedded ? 'right-[244px]' : 'right-[12px]'} bottom-[10px] flex flex-col overflow-hidden rounded-[10px] bg-[var(--glass2)] [backdrop-filter:blur(16px)_saturate(1.4)] [-webkit-backdrop-filter:blur(16px)_saturate(1.4)] [border:1px_solid_var(--gbd)] [box-shadow:0_8px_24px_rgba(10,20,30,0.18)]`}>{/* 앱 안에서는 오른쪽 아래 [2D][전체][위][+][−] 버튼 줄(App.tsx) 앞에서 멈춤 */}
      <div className="flex items-center gap-[12px] p-[6px_8px_6px_8px]">
        <span className="flex-none [font:700_12px_'Pretendard_Variable',sans-serif] text-[#ffffff] bg-[#3d6fe0] p-[4px_8px] rounded-[6px] whitespace-nowrap">{v.tStep}</span>
        <span className="flex-none [font:700_11px_'Pretendard_Variable',sans-serif] tracking-[0.06em] text-[#2a55b8] whitespace-nowrap">{v.tK}</span>
        <span className="flex-none text-[16px] font-bold tracking-[-0.01em] text-[color:var(--t1)] whitespace-nowrap">{v.tT}</span>
        <span className="flex-1 min-w-0 truncate text-[13px] text-[color:var(--t2)]" title={v.tD}>{v.tD}</span>
        <div className="flex-none flex gap-[4px]">
          <button className="cursor-pointer w-[30px] h-[30px] rounded-[8px] border-0 bg-[var(--chip)] text-[color:var(--t1)] text-[12px]" onClick={v.tourPrev} title="이전 단계">◀◀</button>
          <button className="cursor-pointer w-[30px] h-[30px] rounded-[8px] border-0 bg-[#1c2530] text-[#ffffff] text-[12px]" onClick={v.tourToggle} title="일시정지 / 재생">{v.pauseLabel}</button>
          <button className="cursor-pointer w-[30px] h-[30px] rounded-[8px] border-0 bg-[var(--chip)] text-[color:var(--t1)] text-[12px]" onClick={v.tourNext} title="다음 단계">▶▶</button>
          <button className="cursor-pointer h-[30px] p-[0_10px] rounded-[8px] border-0 bg-[var(--chip)] text-[color:var(--t1)] [font:600_12px_'Pretendard_Variable',sans-serif]" onClick={v.tourStop} title="투어 종료">종료</button>
        </div>
      </div>
      <div className="flex gap-[2px]">{/* 진행 막대 = 띠 아래 가장자리 */}
        {(v.tourSegs || []).map((sg: any, $index: number) => (<React.Fragment key={$index}>
          <div className="h-[3px] bg-[rgba(28,37,48,0.12)] overflow-hidden" style={{ flex: sg.flex } as any}><div className="h-full bg-[#0fb5d4] rounded-[2px]" style={{ width: sg.fill } as any}></div></div>
        </React.Fragment>))}
      </div>
    </div>
  </>)}

  {v.introRun && (<>
    <div className="absolute inset-0 pointer-events-none flex items-center justify-center [animation:introTitle_6.4s_ease_forwards] [background:radial-gradient(ellipse_at_center,_rgba(5,8,12,0.6)_0%,_rgba(5,8,12,0)_62%)]">
      <div className="flex flex-col items-center gap-[14px] text-center text-[#ffffff] p-[0_24px]">
        <span className="[font:600_12px_'Pretendard_Variable',sans-serif] tracking-[0.32em] text-[#7fe3f5]">BRK-A100 LINE · DIGITAL TWIN</span>
        <span className="[font-size:clamp(28px,_4.6vw,_60px)] font-bold tracking-[-0.01em] leading-[1.05] [text-shadow:0_4px_30px_rgba(0,0,0,0.55)] text-balance max-w-[90vw]">3D FACTORY PROCESS VISUALIZATION</span>
        <span className="w-[140px] h-[2px] [background:linear-gradient(90deg,_rgba(79,210,234,0),_#4fd2ea,_rgba(79,210,234,0))]"></span>
        <span className="text-[14px] font-medium text-[#d6dee6] tracking-[0.04em]">엔진 마운트 브래킷 · OP-10 → OP-50 · 설비 6대 + 투입 대</span>
      </div>
    </div>
  </>)}
  {v.introOn && (<>
    <button className="absolute right-[24px] bottom-[22px] cursor-pointer p-[9px_16px] rounded-[9px] [border:1px_solid_rgba(255,255,255,0.35)] bg-[rgba(10,14,20,0.5)] text-[#ffffff] [font:600_12px_'Pretendard_Variable',sans-serif] [backdrop-filter:blur(8px)] [-webkit-backdrop-filter:blur(8px)] whitespace-nowrap" onClick={v.skipIntro}>건너뛰기 →</button>
  </>)}
</div>
</>
    );
  }
}
