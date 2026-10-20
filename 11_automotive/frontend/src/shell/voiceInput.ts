'use client';
// 채팅 마이크 버튼의 녹음 (2026-10-20). 누르고 있는 동안 녹음하고, 떼면 소리(Blob)를 onAudio 로 넘긴다. 서버 호출·화면은 Eve.tsx / assistantApi.ts.
//
// - 마이크는 보안 연결(https 또는 localhost)에서만 열린다. 아니면 micSupported() 가 false → 버튼은 꺼진 채 이유를 알려 준다.
// - 브라우저 기본 보정(잡음 억제·에코 제거·자동 이득)을 그대로 쓴다. 비교 시험용 스위치: 브라우저 콘솔에서 localStorage.setItem('voice:raw','1') 이면 셋 다 끄고 녹음한다
//   (지우면 기본으로 돌아간다). 어느 쪽이 인식이 더 나은지 정하면 이 스위치와 함께 정리한다 (기획 6장 4-1).
// - 소리는 메모리에만 있다가 올라가고 어디에도 저장하지 않는다.
import { useCallback, useEffect, useRef, useState } from 'react';

const MIME_PREFERENCE = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'];   // Chrome·Edge·Firefox = webm/opus, Safari = mp4 (서버가 내용으로 알아본다)

/** 녹음 형식 고르기: 브라우저가 지원하는 첫 번째. 없으면 '' (브라우저 기본) */
export function pickMime(isSupported: (t: string) => boolean): string {
  return MIME_PREFERENCE.find((t) => { try { return isSupported(t); } catch { return false; } }) ?? '';
}

/** 서버·네트워크가 돌려준 까닭 → 쉬운 한국어 안내 (화면에 보이는 글. 안쪽 사정은 싣지 않는다) */
export function voiceMessage(reason: string | null | undefined): string {
  switch (reason) {
    case 'too_short': return '너무 짧아요. 버튼을 누른 채로 말하고, 말이 끝나면 손을 떼 주세요.';
    case 'no_speech': case 'hallucination': case 'repeated': case 'hint_echo':
      return '잘 알아듣지 못했어요. 마이크에 조금 더 가까이서 다시 말해 주세요.';
    case 'AUDIO_TOO_LONG': case 'AUDIO_TOO_LARGE': return '녹음이 너무 길어요. 짧게 나눠서 말해 주세요.';
    case 'BAD_AUDIO': case 'EMPTY_AUDIO': return '녹음이 제대로 되지 않았어요. 다시 말해 주세요.';
    case 'VOICE_BUSY': return '다른 음성을 처리하는 중이에요. 잠시 뒤에 다시 눌러 주세요.';
    case 'VOICE_TIMEOUT': return '글자로 바꾸는 데 시간이 너무 걸렸어요. 다시 말해 주세요.';
    case 'VOICE_OFF': return '음성 입력이 꺼져 있어요. 글자로 입력해 주세요.';
    default: return '음성을 글자로 바꾸지 못했어요. 잠시 뒤 다시 하거나 글자로 입력해 주세요.';
  }
}

/** 이 브라우저·이 주소에서 마이크를 쓸 수 있는지 (클라이언트에서만 부른다) */
export function micSupported(): boolean {
  return typeof window !== 'undefined' && window.isSecureContext === true
    && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined';
}

function micErrorMessage(e: unknown): string {
  const name = e instanceof DOMException ? e.name : '';
  if (name === 'NotAllowedError' || name === 'SecurityError') return '마이크 사용이 막혀 있어요. 주소창 옆 자물쇠(또는 마이크 아이콘)에서 마이크를 허용해 주세요.';
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return '마이크를 찾지 못했어요. 마이크가 연결돼 있는지 확인해 주세요.';
  if (name === 'NotReadableError') return '마이크를 다른 프로그램이 쓰고 있어요. 닫고 다시 눌러 주세요.';
  return '마이크를 열지 못했어요. 다시 눌러 주세요.';
}

function audioConstraints(): MediaTrackConstraints | boolean {
  try {
    if (window.localStorage.getItem('voice:raw') === '1') return { echoCancellation: false, noiseSuppression: false, autoGainControl: false };
  } catch { /* 저장소가 막혀 있어도 기본으로 */ }
  return true;
}

export type MicState = 'idle' | 'recording';

/** 누르고 말하기 녹음. start()는 누를 때, stop()은 뗄 때. 너무 길면(maxSeconds) 저절로 멈춘다. 오류는 onError 에 쉬운 문장으로 */
export function useMic(opts: { maxSeconds: number; onAudio: (audio: Blob) => void; onError: (message: string) => void }) {
  const [state, setState] = useState<MicState>('idle');
  const phase = useRef<'idle' | 'starting' | 'recording'>('idle');
  const cancelled = useRef(false);                       // 마이크가 열리기 전에 이미 손을 뗐다
  const rec = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cb = useRef(opts);
  cb.current = opts;

  const release = useCallback(() => {
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    rec.current = null;
    phase.current = 'idle';
    setState('idle');
  }, []);

  const stop = useCallback(() => {
    if (phase.current === 'starting') { cancelled.current = true; return; }
    if (phase.current === 'recording' && rec.current && rec.current.state === 'recording') rec.current.stop();
  }, []);

  const start = useCallback(async () => {
    if (phase.current !== 'idle') return;
    phase.current = 'starting';
    cancelled.current = false;
    setState('recording');
    let s: MediaStream;
    try {
      s = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints() });
    } catch (e) {
      phase.current = 'idle'; setState('idle');
      cb.current.onError(micErrorMessage(e));
      return;
    }
    if (cancelled.current) {                             // 누르자마자 뗐다 — 녹음하지 않고 "너무 짧음"으로
      s.getTracks().forEach((t) => t.stop());
      phase.current = 'idle'; setState('idle');
      cb.current.onError(voiceMessage('too_short'));
      return;
    }
    stream.current = s;
    const mime = pickMime((t) => MediaRecorder.isTypeSupported(t));
    const chunks: Blob[] = [];
    let r: MediaRecorder;
    try { r = new MediaRecorder(s, mime ? { mimeType: mime } : undefined); } catch { release(); cb.current.onError(micErrorMessage(null)); return; }
    rec.current = r;
    r.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    r.onerror = () => { release(); cb.current.onError(micErrorMessage(null)); };
    r.onstop = () => {
      const type = r.mimeType || mime || 'audio/webm';
      release();
      const blob = new Blob(chunks, { type });
      if (blob.size === 0) cb.current.onError(voiceMessage('too_short')); else cb.current.onAudio(blob);
    };
    r.start();
    phase.current = 'recording';
    timer.current = setTimeout(stop, Math.max(3, cb.current.maxSeconds) * 1000);
  }, [release, stop]);

  useEffect(() => () => {                                 // 창이 닫히면 마이크를 놓는다 (녹음 중이어도 소리는 버린다)
    if (rec.current) { rec.current.onstop = null; rec.current.onerror = null; try { rec.current.stop(); } catch { /* 이미 멈춤 */ } }
    release();
  }, [release]);

  return { state, start, stop };
}
