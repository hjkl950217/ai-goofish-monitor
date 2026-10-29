/** 去掉 // 与 /* *\/ 注释和尾逗号，用于在浏览器里校验 JSONC。字符串内部不处理。 */
export function stripJsonc(text: string): string {
  return stripTrailingCommas(stripComments(text.replace(/^﻿/, '')))
}

function stripComments(text: string): string {
  let out = ''
  let i = 0
  let inString = false
  let escape = false
  while (i < text.length) {
    const ch = text[i]
    if (inString) {
      out += ch
      if (escape) escape = false
      else if (ch === '\\') escape = true
      else if (ch === '"') inString = false
      i += 1
      continue
    }
    if (ch === '"') {
      inString = true
      out += ch
      i += 1
      continue
    }
    if (ch === '/' && i + 1 < text.length) {
      const next = text[i + 1]
      if (next === '/') {
        while (i < text.length && text[i] !== '\n' && text[i] !== '\r') i += 1
        continue
      }
      if (next === '*') {
        i += 2
        while (i + 1 < text.length && !(text[i] === '*' && text[i + 1] === '/')) i += 1
        i += 2
        continue
      }
    }
    out += ch
    i += 1
  }
  return out
}

function stripTrailingCommas(text: string): string {
  let out = ''
  let i = 0
  let inString = false
  let escape = false
  while (i < text.length) {
    const ch = text[i]
    if (inString) {
      out += ch
      if (escape) escape = false
      else if (ch === '\\') escape = true
      else if (ch === '"') inString = false
      i += 1
      continue
    }
    if (ch === '"') {
      inString = true
      out += ch
      i += 1
      continue
    }
    if (ch === ',') {
      let j = i + 1
      while (j < text.length && /\s/.test(text[j] ?? '')) j += 1
      if (j < text.length && (text[j] === '}' || text[j] === ']')) {
        i += 1
        continue
      }
    }
    out += ch
    i += 1
  }
  return out
}

/** 校验并返回错误信息；合法时返回空串。 */
export function validateJsonc(text: string): string {
  if (!text.trim()) return ''
  try {
    JSON.parse(stripJsonc(text))
    return ''
  } catch (error) {
    return (error as Error).message
  }
}

// ------------------------------------------------------------------ 格式化

type JsoncToken = {
  kind: 'open' | 'close' | 'comma' | 'colon' | 'string' | 'literal' | 'lineComment' | 'blockComment'
  text: string
  /** 前面出现过换行，用于判断行尾注释是否跟随上一行 */
  nlBefore: boolean
}

function tokenizeJsonc(text: string): JsoncToken[] {
  const tokens: JsoncToken[] = []
  let i = 0
  let nlBefore = false
  const push = (kind: JsoncToken['kind'], value: string) => {
    tokens.push({ kind, text: value, nlBefore })
    nlBefore = false
  }
  while (i < text.length) {
    const ch = text[i]
    if (ch === ' ' || ch === '\t' || ch === '\r' || ch === '\n' || ch === '﻿') {
      if (ch === '\n' || ch === '\r') nlBefore = true
      i += 1
      continue
    }
    if (ch === '"') {
      let j = i + 1
      while (j < text.length) {
        if (text[j] === '\\') { j += 2; continue }
        if (text[j] === '"') { j += 1; break }
        j += 1
      }
      push('string', text.slice(i, j))
      i = j
      continue
    }
    if (ch === '/' && text[i + 1] === '/') {
      let j = text.indexOf('\n', i)
      if (j < 0) j = text.length
      push('lineComment', text.slice(i, j).trimEnd())
      i = j
      continue
    }
    if (ch === '/' && text[i + 1] === '*') {
      const end = text.indexOf('*/', i + 2)
      const j = end < 0 ? text.length : end + 2
      push('blockComment', text.slice(i, j))
      i = j
      continue
    }
    if (ch === '{' || ch === '[') { push('open', ch); i += 1; continue }
    if (ch === '}' || ch === ']') { push('close', ch); i += 1; continue }
    if (ch === ',') { push('comma', ch); i += 1; continue }
    if (ch === ':') { push('colon', ch); i += 1; continue }
    let j = i
    while (j < text.length && !' \t\r\n{}[],:"/'.includes(text[j] ?? '')) j += 1
    if (j === i) j += 1
    push('literal', text.slice(i, j))
    i = j
  }
  return tokens
}

/** 不含嵌套对象也不含注释、且不太长的数组保持一行；返回结尾下标，否则 -1。 */
function inlineArrayEnd(tokens: JsoncToken[], start: number): number {
  let width = 1
  for (let i = start + 1; i < tokens.length; i += 1) {
    const token = tokens[i] as JsoncToken
    if (token.kind === 'close') return token.text === ']' && width <= 80 ? i : -1
    if (token.kind !== 'string' && token.kind !== 'literal' && token.kind !== 'comma') return -1
    width += token.text.length + 2
  }
  return -1
}

/** 按两空格缩进重排 JSONC，保留注释和键顺序；值本身不改写。 */
export function formatJsonc(text: string): string {
  const tokens = tokenizeJsonc(text)
  const lines: string[] = []
  let line = ''
  let indent = 0
  let i = 0

  const pad = () => '  '.repeat(indent)
  const newline = () => {
    lines.push(line.trimEnd())
    line = pad()
  }

  while (i < tokens.length) {
    const token = tokens[i] as JsoncToken
    if (token.kind === 'lineComment') {
      if (line.trim()) line += ' '
      line += token.text
      newline()
      i += 1
      continue
    }
    if (token.kind === 'blockComment') {
      const parts = token.text.split('\n')
      if (parts.length > 1) {
        if (line.trim()) newline()
        line += (parts[0] ?? '').trimEnd()
        for (const part of parts.slice(1)) {
          newline()
          line += part.trim()
        }
        newline()
      } else {
        line += (line.trim() ? ' ' : '') + token.text + ' '
      }
      i += 1
      continue
    }
    if (token.kind === 'open') {
      const close = token.text === '{' ? '}' : ']'
      const next = tokens[i + 1]
      if (next && next.kind === 'close' && next.text === close) {
        line += token.text + close
        i += 2
        continue
      }
      if (token.text === '[') {
        const end = inlineArrayEnd(tokens, i)
        if (end > 0) {
          const items = tokens.slice(i + 1, end).filter((t) => t.kind === 'string' || t.kind === 'literal')
          line += `[${items.map((t) => t.text).join(', ')}]`
          i = end + 1
          continue
        }
      }
      line += token.text
      indent += 1
      newline()
      i += 1
      continue
    }
    if (token.kind === 'close') {
      indent = Math.max(0, indent - 1)
      if (line.trim()) newline()
      else line = pad()
      line += token.text
      i += 1
      continue
    }
    if (token.kind === 'comma') {
      line += ','
      // 同一行后面的注释跟着这一行走，不要另起一行
      const next = tokens[i + 1]
      const trailingComment = next && !next.nlBefore
        && (next.kind === 'lineComment' || next.kind === 'blockComment')
      if (!trailingComment) newline()
      i += 1
      continue
    }
    if (token.kind === 'colon') {
      line += ': '
      i += 1
      continue
    }
    line += token.text
    i += 1
  }

  if (line.trim()) lines.push(line.trimEnd())

  // 去掉紧跟在 } / ] 前的尾逗号
  const cleaned = lines.map((item, index) => {
    if (!/,\s*$/.test(item)) return item
    const next = lines.slice(index + 1).find((candidate) => candidate.trim())
    return next && /^[}\]]/.test(next.trim()) ? item.replace(/,\s*$/, '') : item
  })
  return cleaned.join('\n') + '\n'
}

