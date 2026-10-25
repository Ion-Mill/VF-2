// 영상용 덧그림 (앱 코드는 건드리지 않음): 이브 커서 + 강조 박스. 페이지에 init script 로 들어간다.
// v4 (2026-10-25): 박스가 화면 요소를 매 프레임 따라간다(boxTrack) — 스크롤·화면 이동에 맞고, 대상이 사라지면 같이 사라진다.
(() => {
  if (window.__ov) return;
  const IMG = { idle: '__IDLE__', click: '__CLICK__' }, SIZE = 60, HX = __HX__, HY = __HY__;
  const css = document.createElement('style');
  css.textContent = `
    #__cur{position:fixed;left:0;top:0;width:${SIZE}px;height:${SIZE}px;z-index:2147483647;pointer-events:none;display:none;transform-origin:${HX}px ${HY}px}
    #__box{position:fixed;z-index:2147483646;pointer-events:none;border:3px solid #1d4ed8;border-radius:12px;box-shadow:0 0 0 2px #fff;opacity:0;
      transition:opacity .2s ease,box-shadow .2s ease;animation:__p 1.5s ease-in-out infinite}
    #__box.mv{transition:left .3s ease,top .3s ease,width .3s ease,height .3s ease,opacity .2s ease,box-shadow .2s ease}
    #__box.dim{box-shadow:0 0 0 2px #fff,0 0 0 9999px rgba(10,20,40,.42)}
    @keyframes __p{0%,100%{outline:0 solid rgba(29,78,216,0)}50%{outline:7px solid rgba(29,78,216,.22)}}`;
  const mk = () => {
    document.head.appendChild(css);
    const cur = document.createElement('img'); cur.id = '__cur'; cur.src = IMG.idle; document.body.appendChild(cur);
    const box = document.createElement('div'); box.id = '__box'; document.body.appendChild(box);
    const place = (x, y) => { cur.style.display = 'block'; cur.style.left = (x - HX) + 'px'; cur.style.top = (y - HY) + 'px'; };
    document.addEventListener('mousemove', (e) => place(e.clientX, e.clientY), true);
    let track = null, mvTimer = 0;
    const setRect = (x, y, w, h) => { box.style.left = x + 'px'; box.style.top = y + 'px'; box.style.width = w + 'px'; box.style.height = h + 'px'; };
    const gone = (el) => { if (!el.isConnected) return true; const r = el.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return true;
      const cs = getComputedStyle(el); return cs.visibility === 'hidden' || cs.display === 'none'; };
    const loop = () => {                      // 대상 요소를 따라간다. 사라지면 박스도 지운다
      if (track) {
        if (gone(track.el)) { box.style.opacity = 0; box.classList.remove('dim'); track = null; }
        else { const r = track.el.getBoundingClientRect(), p = track.pad; setRect(r.left - p, r.top - p, r.width + p * 2, r.height + p * 2); }
      }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
    const moved = () => { box.classList.add('mv'); clearTimeout(mvTimer); mvTimer = setTimeout(() => box.classList.remove('mv'), 380); };
    window.__ov = {
      place,
      press(on) { cur.src = on ? IMG.click : IMG.idle; cur.style.transform = on ? 'scale(.94)' : 'scale(1)'; },
      // 화면 요소에 붙는 박스 (권장)
      boxTrack(el, pad, dim) {
        if (+box.style.opacity > 0) moved();
        track = { el, pad: pad ?? 8 }; box.style.opacity = 1; box.classList.toggle('dim', !!dim);
      },
      // 좌표로 치는 박스 (3D 화면처럼 요소가 없는 곳)
      box(x, y, w, h, dim) { track = null; if (+box.style.opacity > 0) moved(); setRect(x, y, w, h); box.style.opacity = 1; box.classList.toggle('dim', !!dim); },
      hide() { track = null; box.style.opacity = 0; box.classList.remove('dim'); },
      visible() { return +box.style.opacity > 0; },
    };
  };
  if (document.body) mk(); else document.addEventListener('DOMContentLoaded', mk);
})();
