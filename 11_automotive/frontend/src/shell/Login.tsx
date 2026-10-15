'use client';
// SCR-01 로그인 — 가상 사용자 12명 중 하나를 고른다 (생성기/masters/app_user.csv).
import { useState } from 'react';
import { ROLE_NAME, SHIFT_NAME, USERS, type UserRec } from './model';

export default function Login({ onLogin }: { onLogin: (u: UserRec) => void }) {
  const [id, setId] = useState<string>('');
  const [pw, setPw] = useState('');
  const [fail, setFail] = useState(false);
  const pick = USERS.find((u) => u.id === id);
  const go = () => { if (pick) onLogin(pick); else setFail(true); };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#e9ecef] p-4 text-[#26303a]">
      <div className="w-full max-w-[560px] rounded-xl border border-slate-300 bg-white p-6 shadow-md">
        <h1 className="text-[20px] font-bold">AI 운영 비서 · BRK-A100 절삭가공 라인</h1>

        <h2 className="mb-2 mt-5 text-[14px] font-bold">사용자 고르기</h2>
        {USERS.length === 0 ? (
          <p className="text-[13px] text-slate-500">가상 사용자 데이터가 없습니다 (생성기 확인)</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {USERS.map((u) => (
              <li key={u.id}>
                <label className={`flex min-h-[44px] cursor-pointer items-center gap-3 rounded-md border px-3 text-[14px] ${id === u.id ? 'border-[#0f9fbd] bg-[#e8f6fa]' : 'border-slate-200 hover:bg-slate-50'}`}>
                  <input type="radio" name="user" checked={id === u.id} onChange={() => { setId(u.id); setFail(false); }} />
                  <span className="font-semibold">{u.name}</span>
                  <span className="text-slate-600">{ROLE_NAME[u.role]} {u.role}</span>
                  <span className="text-slate-500">· {SHIFT_NAME[u.shift]}{u.procs.length ? ` · ${u.procs.join('·')}` : ''}</span>
                </label>
              </li>
            ))}
          </ul>
        )}

        <label className="mt-4 flex flex-col gap-1 text-[13px] font-semibold">비밀번호
          <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="로그인 방식은 기술 회의 뒤에 정합니다"
            className="h-11 rounded-md border border-slate-300 px-3 font-normal" />
        </label>

        {fail && <p className="mt-2 text-[13px] font-semibold text-[#c62a2f]">로그인하지 못했습니다 — 사용자를 골라 주세요</p>}

        <button onClick={go} className="mt-4 h-12 w-full rounded-md bg-[#1c2530] text-[15px] font-bold text-white">로그인</button>
        <p className="mt-3 text-[12px] text-slate-500">시연 모드 ● 켜짐 — 시뮬레이터 시계 (10/1 08:00부터, 배속·사건 버튼은 상단 [시연 ▾])</p>
      </div>
    </div>
  );
}
