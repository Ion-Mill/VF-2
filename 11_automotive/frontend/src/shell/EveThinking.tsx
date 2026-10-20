// @ts-nocheck
'use client';
// 이브가 답을 만드는 동안 (사용자 선택 2026-10-19): 책을 넘겨 읽고, 머리 위 생각 구름에서 지침카드·알람 코드집·정비 기록을 찾고(…), 찾으면 ✓.
// 로봇 = robot3d.js 그대로, 책·구름·눈 움직임만 덧붙임. 시안: claude.ai/artifact/L22vfMbqj8YsGCNa6u5BxD
import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { createRobot } from '../components/robot3d';

function setup(cv) {
  const size = +cv.dataset.size, mode = +cv.dataset.mode;
  cv.width = cv.height = size; cv.style.width = cv.style.height = size + 'px';
  let renderer, stop = false; try { renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true, alpha: true }); } catch { return; }
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2)); renderer.setSize(size, size, false);
  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd8d2c4, 1.0));
  const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(4, 7, 5); scene.add(key);
  const R = createRobot(THREE, { bubble: false }); scene.add(R.root); R.setMode(mode);
  let book = null, arms = [], headG = null, pages = [], eyesG = [], eyeBase = [], eyeMat = null, glowMat = null;
  if (cv.dataset.book) {
    arms = ['shoulder_L', 'shoulder_R'].map(n => R.root.getObjectByName(n)); headG = R.root.getObjectByName('head_group');
    eyesG = ['eye_L', 'eye_R'].map(n => R.root.getObjectByName(n)); eyeBase = eyesG.map(e => e && e.position.clone()); eyeMat = R.root.getObjectByName('eye_L_arc')?.material; glowMat = R.root.getObjectByName('eye_L_glow')?.material;
    book = new THREE.Group(); book.position.set(0, 0.36, 0.2); book.rotation.x = -0.75; R.root.add(book);
    const cover = new THREE.MeshStandardMaterial({ color: 0x2f5fa8, roughness: 0.6 }), paper = new THREE.MeshStandardMaterial({ color: 0xf6f2e6, roughness: 0.9, side: THREE.DoubleSide });
    [-1, 1].forEach(s => { const c = new THREE.Mesh(new THREE.BoxGeometry(0.13, 0.006, 0.17), cover); c.position.set(s * 0.066, -0.004, 0); c.rotation.z = -s * 0.12; book.add(c);
      const pg = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.012, 0.16), paper); pg.position.set(s * 0.062, 0.006, 0); pg.rotation.z = -s * 0.12; book.add(pg); });
    for (let i = 0; i < 2; i++) { const piv = new THREE.Group(); book.add(piv); const pm = new THREE.Mesh(new THREE.PlaneGeometry(0.12, 0.155), paper); pm.rotation.x = -Math.PI / 2; pm.position.x = 0.06; piv.add(pm); piv.position.y = 0.013; pages.push(piv); }
    const lineM = new THREE.MeshBasicMaterial({ color: 0x9aa3ad });
    const cc = document.createElement('canvas'); cc.width = 320; cc.height = 256; const cx2 = cc.getContext('2d'), ct = new THREE.CanvasTexture(cc); let lastCloud = '';
    var drawCloud = (kind) => { if (!kind || kind === lastCloud) return; lastCloud = kind; const c = cx2; c.clearRect(0, 0, 320, 256);
      c.fillStyle = '#ffffff'; c.strokeStyle = '#cfd6dd'; c.lineWidth = 5;
      const puffs = [[160, 100, 70], [95, 115, 50], [225, 115, 50], [120, 60, 45], [200, 60, 45], [160, 140, 55]];
      puffs.forEach(([x, y, r]) => { c.beginPath(); c.arc(x, y, r, 0, 7); c.fill(); c.stroke(); }); puffs.forEach(([x, y, r]) => { c.beginPath(); c.arc(x, y, r - 4, 0, 7); c.fill(); });
      [[70, 205, 16], [40, 235, 10]].forEach(([x, y, r]) => { c.beginPath(); c.arc(x, y, r, 0, 7); c.fill(); c.stroke(); });
      if (kind.startsWith('dots')) { c.fillStyle = '#5b6570'; [120, 160, 200].forEach((x, i) => { c.globalAlpha = 0.35 + 0.65 * (((Date.now() / 300) | 0) % 3 === i ? 1 : 0); c.beginPath(); c.arc(x, 105, 11, 0, 7); c.fill(); }); c.globalAlpha = 1; }
      else if (kind === 'check') { c.strokeStyle = '#2f9e5b'; c.lineWidth = 18; c.lineCap = 'round'; c.lineJoin = 'round'; c.beginPath(); c.moveTo(115, 105); c.lineTo(150, 138); c.lineTo(210, 72); c.stroke(); }
      else { const col = { card: '#6a43e0', code: '#c2570c', rec: '#2f9e5b' }[kind], lab = { card: '지침카드', code: '알람 코드집', rec: '정비 기록' }[kind];
        c.fillStyle = '#fff'; c.strokeStyle = col; c.lineWidth = 6; c.beginPath(); c.roundRect(125, 45, 70, 86, 8); c.fill(); c.stroke();
        c.fillStyle = col; c.fillRect(125, 45, 70, 18); c.fillStyle = '#c3cad2'; [80, 96, 112].forEach(y => c.fillRect(137, y, 46, 7));
        c.fillStyle = '#26303a'; c.font = '800 26px "Malgun Gothic",sans-serif'; c.textAlign = 'center'; c.fillText(lab, 160, 168); }
      ct.needsUpdate = true; };
    var cloud = new THREE.Sprite(new THREE.SpriteMaterial({ map: ct, depthTest: false })); cloud.scale.set(0.36, 0.29, 1); cloud.position.set(0.3, 0.86, 0.05); R.root.add(cloud);
    [-1, 1].forEach(s => { for (let k = 0; k < 5; k++) { const ln = new THREE.Mesh(new THREE.PlaneGeometry(0.085, 0.006), lineM); ln.rotation.x = -Math.PI / 2; ln.rotation.z = 0; ln.position.set(s * 0.062, 0.0135 + (s < 0 ? 0.002 : 0.002), -0.055 + k * 0.026); book.add(ln); } });
  }
  const cam = new THREE.PerspectiveCamera(30, 1, 0.05, 20); cam.position.set(cv.dataset.book ? 0.35 : 0, cv.dataset.book ? 0.85 : 0.62, cv.dataset.book ? 1.95 : 1.85); cam.lookAt(0, cv.dataset.book ? 0.56 : 0.43, 0);
  let t = 0, last = performance.now(); // ?t= 로 특정 장면 확인
  const loop = (now) => { if (stop) return; requestAnimationFrame(loop); const dt = Math.max(0, Math.min(0.1, ((now || performance.now()) - last) / 1000)) || 0; last = now || performance.now(); t += dt;
    if (cv.dataset.nod) R.root.rotation.x = Math.sin(t * 3) * 0.06;
    if (cv.dataset.spin) R.root.rotation.y = Math.sin(t * 0.8) * 0.6;
    R.update(t, dt, cam);
    if (book) { // 8초 한 바퀴: 읽기 → 빠르게 넘겨 찾기 → 턱 괴고 생각(?) → 찾았다(!) 손가락으로 짚기 → 다시 읽기
      const T = t % 8, sm = (x) => x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x), seg = (a0, a1) => sm((T - a0) / (a1 - a0));
      const chin = seg(3.4, 3.9) * (1 - seg(5.0, 5.4)), point = seg(5.2, 5.6) * (1 - seg(6.6, 7.0)), lean = 0.32 + point * 0.12;
      if (arms[0]) { arms[0].rotation.x = -1.05 + Math.sin(t * 1.3) * 0.03; arms[0].rotation.z = 0.32 + chin * 0.12; }
      if (arms[1]) { arms[1].rotation.x = -1.05 + chin * -1.45 + point * -0.35; arms[1].rotation.z = -0.32 + chin * 0.95 + point * 0.25; }
      if (headG) {
        const scan = T < 2.4 || T > 7.0 ? Math.sin(t * 1.8) * 0.2 : 0, flipLook = T >= 2.4 && T < 3.4 ? Math.sin(t * 9) * 0.06 : 0;
        headG.rotation.x = lean * (1 - chin) - 0.08 * chin; headG.rotation.y = scan + flipLook + chin * 0.25; headG.rotation.z = chin * Math.sin(t * 1.4) * 0.18 + chin * 0.14;
      }
      // 책장: 등(가운데)을 축으로 위로 들려 왼쪽으로 넘어감 (반대로 돌던 것 고침)
      const flipAt = (k) => { if (T < 2.4 || T >= 3.4) { const f = ((t % 2.2) / 2.2 - 0.2) / 0.55; return k ? 0 : sm(f); } const f = ((T - 2.4) * 3 + k * 0.5) % 1; return sm(f / 0.7); };
      pages.forEach((pg, k) => { pg.rotation.z = flipAt(k) * Math.PI * 0.94; pg.visible = flipAt(k) > 0.01 && flipAt(k) < 0.99; });
      book.rotation.x = -0.75 + Math.sin(t * 1.3) * 0.03 - chin * 0.15; book.rotation.z = chin * 0.12;
      // 눈: 읽을 땐 가늘게 아래로·글줄 따라 좌우, 넘길 땐 빠르게 두리번, 생각할 땐 위로 치켜뜨고 한쪽만 찡그림, 찾으면 커지며 초록 반짝
      const found = T > 5.0 && T < 6.2 ? Math.max(0, 1 - Math.abs(T - 5.25) * 2.2) : 0, flipping = T >= 2.4 && T < 3.4;
      eyesG.forEach((e, i) => { if (!e) return; const b = eyeBase[i], s = i ? 1 : -1;
        const read = 1 - chin, dx = read * (flipping ? Math.sin(t * 14) * 0.009 : Math.sin(t * 1.8) * 0.007) + chin * 0.006;
        const dy = read * -0.012 + chin * 0.012;
        e.position.set(b.x + dx, b.y + dy, b.z);
        let sy = read * (flipping ? 0.75 : 0.5) + chin * (s < 0 ? 0.55 : 1.05), sx = 1;
        if (found > 0) { sy = 0.6 + found * 0.85; sx = 1 + found * 0.3; }
        const bl = (t % 3.7) < 0.14 ? 0.12 : 1; e.scale.set(sx, sy * bl, 1); e.rotation.z = chin * s * -0.18; });
      if (eyeMat && found > 0.05) { eyeMat.color.setHex(0x3fe08a); eyeMat.emissive.setHex(0x2ee87a).multiplyScalar(1.6); if (glowMat) { glowMat.color.setHex(0x2ee87a); glowMat.opacity = 0.5 * found; } }
      if (headG && found > 0) headG.rotation.x = headG.rotation.x * (1 - found) - 0.12 * found; // 찾으면 고개 번쩍
      // 생각 구름: 찾는 동안 문서 아이콘이 넘어가고, 생각할 땐 …, 찾으면 ✓
      cloud.visible = true; cloud.position.y = 0.86 + Math.sin(t * 2) * 0.012; cloud.scale.set(0.36 + found * 0.04, 0.29 + found * 0.03, 1);
      drawCloud(T > 5.0 && T < 6.6 ? 'check' : chin > 0.3 ? 'dots' + (((t * 3.3) | 0) % 3) : ['card', 'code', 'rec'][((Math.floor(t / 0.9) % 3) + 3) % 3]);
    }
    renderer.render(scene, cam); };
  requestAnimationFrame(loop);
  return () => { stop = true; renderer && renderer.dispose(); renderer && renderer.forceContextLoss(); };
}

const STEPS = ['알람 코드집을 넘겨 보는 중…', '지침카드를 찾는 중…', '정비 기록을 확인하는 중…', '답을 정리하는 중…'];
export default function EveThinking({ size = 220 }: { size?: number }) {
  const ref = useRef<HTMLCanvasElement>(null), [i, setI] = useState(0);
  useEffect(() => { const cv = ref.current; if (!cv) return; return setup(cv); }, []);
  useEffect(() => { const id = setInterval(() => setI((x) => x + 1), 1600); return () => clearInterval(id); }, []);
  return (
    <div className="flex flex-col items-center gap-1 py-2" role="status" aria-label="답변을 만드는 중">
      <canvas ref={ref} data-size={size} data-mode="0" data-book="1" aria-hidden="true" />
      <span className="ma-typing text-[13px]">{STEPS[i % STEPS.length]}</span>
    </div>);
}
