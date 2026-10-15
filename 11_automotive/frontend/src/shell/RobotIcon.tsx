'use client';
// 이브 아이콘 = 로봇 3D 모델 (src/components/robot3d.js, 로봇 3D 모델링.zip). 작은 WebGL 캔버스 하나를 30fps로 그림.
// 창 머리·토스트의 작은 로봇은 이 캔버스를 한 번 찍은 그림(onSnap)을 씀 — WebGL 화면을 여러 개 만들지 않으려고.
import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { createRobot } from '../components/robot3d';

export default function RobotIcon({ mode, size, onSnap, onFail }: { mode: 0 | 1 | 2 | 3; size: number; onSnap?: (url: string) => void; onFail?: () => void }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const modeRef = useRef(mode);
  modeRef.current = mode;
  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true, alpha: true, preserveDrawingBuffer: true }); }
    catch { onFail?.(); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(size, size, false);
    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight(0xffffff, 0xd8d2c4, 1.0));
    const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(4, 7, 5); scene.add(key);
    const fill = new THREE.DirectionalLight(0xfff4e6, 0.5); fill.position.set(-5, 3, -4); scene.add(fill);
    const R = createRobot(THREE, { bubble: false });
    scene.add(R.root);
    const cam = new THREE.PerspectiveCamera(30, 1, 0.05, 20); // 머리~몸 0.95 m가 꽉 차게
    cam.position.set(0, 0.62, 1.85); cam.lookAt(0, 0.43, 0);
    let raf = 0, last = performance.now(), acc = 0, t = 0, snapped = !onSnap;
    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const dt = Math.min(0.1, (now - last) / 1000); last = now; acc += dt;
      if (acc < 1 / 30) return;
      R.setMode(modeRef.current); R.update(t += acc, acc, cam); acc = 0;
      renderer.render(scene, cam);
      if (!snapped && t > 0.8) { snapped = true; onSnap?.(cv.toDataURL('image/png')); }
    };
    raf = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(raf); renderer.dispose(); renderer.forceContextLoss(); };
  }, [size]); // eslint-disable-line react-hooks/exhaustive-deps
  return <canvas ref={ref} width={size} height={size} style={{ width: size, height: size, display: 'block' }} aria-hidden="true" />;
}
