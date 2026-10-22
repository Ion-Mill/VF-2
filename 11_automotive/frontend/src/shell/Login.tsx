'use client';
// SCR-01 로그인 (페이지구조 v3 1장) — 아이디를 누르면 가상 사용자 12명 이름 목록, 고르면 비밀번호 0000이 채워진다 (생성기/masters/app_user.csv).
import { useState } from 'react';
import { USERS, type UserRec } from './model';
import Logo from './Logo';

// 시연용: 모든 계정 비밀번호 0000 (사용자 결정 2026-10-15)
export const DEMO_PW = '0000';   // assistantApi.ts(이브 채팅의 백엔드 로그인)도 같은 값을 쓴다

export default function Login({ onLogin }: { onLogin: (u: UserRec) => void }) {
  const [id, setId] = useState('');
  const [pw, setPw] = useState('');
  const [open, setOpen] = useState(false);
  const [fail, setFail] = useState('');
  const pick = USERS.find((u) => u.id === id);
  const go = () => {
    if (!pick) return setFail('아이디를 골라 주세요');
    if (pw !== DEMO_PW) return setFail('비밀번호가 맞지 않습니다');
    onLogin(pick);
  };
  const field = 'flex h-12 w-full items-center rounded-full border border-line bg-white px-5 text-left text-card';

  return (
    <div className="flex min-h-screen items-center justify-center bg-ground p-4 text-ink">
      <form onSubmit={(e) => { e.preventDefault(); go(); }} className="flex w-full max-w-[420px] flex-col gap-3 rounded-card border border-line-soft bg-white p-8 shadow-md">
        <div className="mb-3 flex flex-col items-center gap-2"><h1 className="m-0"><Logo height={46} /></h1><span className="text-card text-ink-2">이브테크 제조운영관리 플랫폼</span></div>
        <div className="relative">
          <button type="button" onClick={() => setOpen((o) => !o)} aria-haspopup="listbox" aria-expanded={open} className={`${field} justify-between`}>
            <span className={pick ? '' : 'text-ink-3'}>{pick ? pick.name : '아이디'}</span><span className="text-ink-3">▾</span>
          </button>
          {open && (
            <ul role="listbox" className="absolute left-0 right-0 top-[52px] z-10 max-h-[360px] overflow-y-auto rounded-card border border-line-soft bg-white py-1 shadow-lg">
              {USERS.length === 0 && <li className="px-5 py-3 text-body text-ink-2">가상 사용자 데이터가 없습니다 (생성기 확인)</li>}
              {USERS.map((u) => (
                <li key={u.id} role="option" aria-selected={u.id === id}>
                  <button type="button" onClick={() => { setId(u.id); setPw(DEMO_PW); setOpen(false); setFail(''); }}
                    className={`flex h-11 w-full items-center px-5 text-left text-card hover:bg-tile ${u.id === id ? 'font-bold text-brand-ink' : ''}`}>{u.name}</button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="비밀번호" aria-label="비밀번호" className={field} />
        {fail && <p className="text-center text-small font-semibold text-crit">{fail}</p>}
        <button type="submit" className="mx-auto mt-2 h-12 w-[160px] rounded-full bg-brand text-card font-bold text-white hover:bg-brand-ink">로그인</button>
      </form>
    </div>
  );
}
