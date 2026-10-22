// 화면 요약에 보낼 정보판 글자 (2026-10-21). 보이는 글자 전부가 아니라 data-summary-panel 칸만 모은다.
// 안전 고정 서식(data-summary-skip)은 빼고 그 자리에 한 줄만 남긴다. 화면 문구·디자인은 바꾸지 않는다.

export const SCREEN_QUESTION = /(?:이|지금|현재)\s*(?:화면|페이지).*(?:설명|요약|정리|뭐야|뭐지|뭔지)|여기.*(?:뭐가|뭐\s*떠|요약)/
const BLOCK = /\d{3,4}|뭐부터|잠금|표지|위험|권한/
const SKIP_MARK = '[안전 작업 칸 — 요약하지 않음]'
const MAX_CHARS = 6000

export function isScreenQuestion(question: string): boolean {
  const q = question.trim()
  return SCREEN_QUESTION.test(q) && !BLOCK.test(q)
}

export function joinPanels(chunks: { text: string; skipped: boolean }[]): string {
  const seen = new Set<string>()
  const lines: string[] = []
  let blank = 0
  for (const chunk of chunks) {
    const raw = chunk.skipped ? SKIP_MARK : chunk.text
    for (const ln of raw.replace(/\r\n/g, '\n').split('\n')) {
      const s = ln.replace(/[ \t]+/g, ' ').trim()
      if (!s) {
        blank += 1
        if (blank <= 1 && lines.length) lines.push('')
        continue
      }
      blank = 0
      if (seen.has(s)) continue
      seen.add(s)
      lines.push(s)
    }
  }
  let out = lines.join('\n').trim()
  if (out.length > MAX_CHARS) out = out.slice(0, MAX_CHARS).trimEnd() + '\n(이하 생략)'
  return out
}

/** 한 칸의 보이는 글자. 줄바꿈으로 붙이지 않고 한 줄로 잇는다. %·/90처럼 숫자에 붙는 기호는 띄우지 않는다. */
function fieldLine(el: Element): string {
  const name = (el.getAttribute('data-summary-field') ?? '').trim()
  const bits: string[] = []
  const walk = (node: Node) => {
    if (node.nodeType === 3) {
      const s = (node.textContent ?? '').replace(/\s+/g, ' ').trim()
      if (s) bits.push(s)
      return
    }
    if (node.nodeType !== 1) return
    const child = node as Element
    if (child.hasAttribute('data-summary-skip')) return
    const start = bits.length
    for (const c of child.childNodes) walk(c)
    const aria = child.getAttribute('aria-label')
    if (aria && !bits.slice(start).includes(aria) && aria !== bits.slice(start).join('')) bits.push(aria)
  }
  walk(el)
  const body = name && bits[0] === name ? bits.slice(1) : bits
  let value = ''
  for (const part of body) {
    const glue = part === '%' || part.startsWith('/') || part.startsWith(':') || value.endsWith('/')
    value = !value ? part : glue ? value + part : `${value} ${part}`
  }
  if (name === '작업지시') return value ? `작업지시 ${body.join(', ')}` : ''
  if (!name) return value
  return value ? `${name} ${value}` : name
}

/** screenCode(SCR-04 등)와 같은 data-summary-panel 칸의 글자. 다른 화면 칸은 넣지 않는다. */
export function collectScreenText(screenCode: string, root: ParentNode = document): string {
  const code = screenCode.replace(/[^A-Za-z0-9-]/g, '')
  if (!code) return ''
  const panels = [...root.querySelectorAll(`[data-summary-panel="${code}"]`)]
  const chunks = panels.map((panel) => {
    const copy = panel.cloneNode(true) as Element
    const skips = [...copy.querySelectorAll('[data-summary-skip]')]
    skips.forEach((el) => el.parentNode?.removeChild(el))
    const fields = [...copy.querySelectorAll('[data-summary-field]')]
    const text = fields.length
      ? fields.map(fieldLine).filter(Boolean).join('\n')
      : 'innerText' in copy && typeof (copy as HTMLElement).innerText === 'string'
        ? (copy as HTMLElement).innerText
        : (copy.textContent ?? '')
    const parts: { text: string; skipped: boolean }[] = [{ text, skipped: false }]
    if (skips.length > 0) parts.push({ text: '', skipped: true })
    return parts
  })
  return joinPanels(chunks.flat())
}
