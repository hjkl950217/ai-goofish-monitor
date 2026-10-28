/**
 * AI 逐项判定（criteria_analysis）的中文映射。
 *
 * key 由 prompts/base_prompt.txt 的输出格式固定，改 prompt 时要同步改这里；
 * 未知 key 原样显示，不会因为新增标准而丢内容。
 */

export const CRITERIA_LABELS: Record<string, string> = {
  model_chip: '型号配置',
  battery_health: '电池健康',
  condition: '车况成色',
  history: '事故历史',
  seller_type: '卖家画像',
  shipping: '物流交易',
  seller_credit: '卖家信用',
}

export const CRITERIA_STATUS_LABELS: Record<string, string> = {
  PASS: '通过',
  FAIL: '不通过',
  NEEDS_MANUAL_CHECK: '需核实',
  WARN: '需注意',
  UNCERTAIN: '不确定',
}

const STATUS_TONES: Record<string, string> = {
  PASS: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  FAIL: 'bg-rose-50 text-rose-700 border-rose-200',
  NEEDS_MANUAL_CHECK: 'bg-amber-50 text-amber-700 border-amber-200',
  WARN: 'bg-amber-50 text-amber-700 border-amber-200',
}

export function criteriaLabel(key: string): string {
  return CRITERIA_LABELS[key] ?? key
}

export function criteriaStatusLabel(status: string): string {
  const normalized = String(status || '').trim().toUpperCase()
  return CRITERIA_STATUS_LABELS[normalized] ?? status
}

export function criteriaStatusTone(status: string): string {
  const normalized = String(status || '').trim().toUpperCase()
  return STATUS_TONES[normalized] ?? 'bg-slate-100 text-slate-600 border-slate-200'
}
