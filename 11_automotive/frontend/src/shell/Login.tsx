'use client';
// SCR-01 로그인 (페이지구조 v3 1장) — 아이디(U01~U12)와 비밀번호를 직접 친다 (사용자 요청 2026-10-24, 예전엔 이름 목록에서 고르면 0000이 채워졌다). 계정은 생성기/masters/app_user.csv.
// 백엔드 모드(기본, NEXT_PUBLIC_MOM_BACKEND≠0)면 backendApi.backendLogin으로 서버가 확인하고, 받은 토큰을 화면 API와 이브 채팅이 같이 쓴다. 꺼져 있으면 화면 안에서 비교만 한다.
import { useState } from 'react';
import { USERS, type UserRec } from './model';
import type { Role } from './data';
import Logo from './Logo';
import { BackendErr, backendLogin, backendMode } from './backendApi';

// 시연용: 모든 계정 비밀번호 0000 (사용자 결정 2026-10-15)
export const DEMO_PW = '0000';   // assistantApi.ts·App.tsx(새로고침 뒤 다시 로그인)도 같은 값을 쓴다

const HINT_ROLE: [Role, string][] = [['OPR', '작업자'], ['MNT', '보전'], ['SUP', '반장'], ['MGR', '관리자']];
// 시연 계정 안내 — 사용자 표에서 역할별 첫·끝 아이디를 뽑는다 (예: 작업자 U01~U06)
const hint = HINT_ROLE.map(([r, ko]) => { const ids = USERS.filter((u) => u.role === r).map((u) => u.id); return ids.length ? `${ko} ${ids[0]}${ids.length > 1 ? `~${ids[ids.length - 1]}` : ''}` : ''; }).filter(Boolean);
const BAD = '아이디 또는 비밀번호가 맞지 않습니다';   // 어느 쪽이 틀렸는지는 알려 주지 않는다

export default function Login({ onLogin }: { onLogin: (u: UserRec) => void }) {
  const [id, setId] = useState('');
  const [pw, setPw] = useState('');
  const [fail, setFail] = useState('');
  const [busy, setBusy] = useState(false);
  const go = async () => {
    if (busy) return;
    if (!id.trim() || !pw) return setFail('아이디와 비밀번호를 넣어 주세요');
    const pick = USERS.find((u) => u.id.toLowerCase() === id.trim().toLowerCase());
    if (!pick) return setFail(BAD);
    if (!backendMode()) {
      if (pw !== DEMO_PW) return setFail(BAD);
      return onLogin(pick);
    }
    // 화면 → 백엔드 전환 (C2): 백엔드가 비밀번호를 확인하고 토큰을 준다 (backendApi.ts)
    setBusy(true);
    try { await backendLogin(pick.id, pw); } catch (e) { setBusy(false); return setFail(e instanceof BackendErr && e.status === 401 ? BAD : '서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요'); }
    setBusy(false);
    onLogin(pick);
  };
  const field = 'flex h-12 w-full items-center rounded-full border border-line bg-white px-5 text-left text-card';

  return (
    <div className="flex min-h-screen items-center justify-center bg-ground p-4 text-ink">
      <form onSubmit={(e) => { e.preventDefault(); go(); }} className="flex w-full max-w-[420px] flex-col gap-3 rounded-card border border-line-soft bg-white p-8 shadow-md">
        <div className="mb-3 flex flex-col items-center gap-2"><h1 className="m-0"><Logo height={46} /></h1><span className="text-card text-ink-2">이브테크 제조운영관리 플랫폼</span></div>
        <input value={id} onChange={(e) => { setId(e.target.value); setFail(''); }} placeholder="아이디" aria-label="아이디" autoComplete="username" autoCapitalize="characters" spellCheck={false} autoFocus className={field} />
        <input type="password" value={pw} onChange={(e) => { setPw(e.target.value); setFail(''); }} placeholder="비밀번호" aria-label="비밀번호" autoComplete="current-password" className={field} />
        {fail && <p className="text-center text-small font-semibold text-crit" role="alert">{fail}</p>}
        <button type="submit" disabled={busy} className="mx-auto mt-2 h-12 w-[160px] rounded-full bg-brand text-card font-bold text-white hover:bg-brand-ink disabled:opacity-60">{busy ? '확인 중…' : '로그인'}</button>
        {USERS.length === 0
          ? <p className="mt-2 text-center text-small text-ink-2">가상 사용자 데이터가 없습니다 (생성기 확인)</p>
          // 역할 4개를 2×2로 — 한 줄로 붙이면 카드 폭을 넘쳤다 (2026-10-24)
          : <div className="mt-3 border-t border-line-soft pt-3 text-center text-small leading-relaxed text-ink-2"><p className="m-0">시연 계정 · 비밀번호 {DEMO_PW}</p>
              <p className="m-0 mt-1 grid grid-cols-2 gap-x-4">{hint.map((h) => <span key={h} className="whitespace-nowrap">{h}</span>)}</p></div>}
      </form>
    </div>
  );
}
