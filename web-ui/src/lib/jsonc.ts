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
