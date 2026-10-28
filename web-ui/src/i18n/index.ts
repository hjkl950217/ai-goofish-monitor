import { computed, watch } from 'vue'
import { createI18n, useI18n } from 'vue-i18n'
import zhCN from '@/i18n/messages/zh-CN'
import enUS from '@/i18n/messages/en-US'

export type AppLocale = 'zh-CN' | 'en-US'

const LOCALE_STORAGE_KEY = 'app_locale'
const DEFAULT_LOCALE: AppLocale = 'zh-CN'
const SUPPORTED_LOCALES: AppLocale[] = ['zh-CN', 'en-US']

function resolveInitialLocale(): AppLocale {
  const saved = localStorage.getItem(LOCALE_STORAGE_KEY)
  if (saved && SUPPORTED_LOCALES.includes(saved as AppLocale)) {
    return saved as AppLocale
  }
  const browserLocale = navigator.language.toLowerCase()
  return browserLocale.startsWith('zh') ? 'zh-CN' : 'en-US'
}

export const i18n = createI18n({
  legacy: false,
  locale: resolveInitialLocale(),
  fallbackLocale: DEFAULT_LOCALE,
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
})

export function setLocale(locale: AppLocale) {
  i18n.global.locale.value = locale
}

export function useLocale() {
  const { locale } = useI18n()
  const currentLocale = computed(() => locale.value as AppLocale)

  function toggleLocale(nextLocale: AppLocale) {
    locale.value = nextLocale
  }

  return {
    locale: currentLocale,
    toggleLocale,
    supportedLocales: SUPPORTED_LOCALES,
  }
}

export function t(key: string, params?: Record<string, unknown>) {
  return params ? i18n.global.t(key, params) : i18n.global.t(key)
}

export function formatNumber(value: number, options?: Intl.NumberFormatOptions) {
  return new Intl.NumberFormat(i18n.global.locale.value, options).format(value)
}

/** 全站统一用东八区显示时间，避免浏览器所在时区不同导致同一数据两个时间。 */
const STATION_TIME_ZONE = 'Asia/Shanghai'
const STATION_OFFSET = '+08:00'

/**
 * 后端存的是不带时区的本地时间（"2026-10-28T16:59:36.393270"、"2026-10-19 13:34"），
 * 直接 new Date 会按浏览器时区解析。这里补上 +08:00，保证在东八区之外也显示同一时刻。
 */
export function toStationDate(value: string | Date): Date {
  if (value instanceof Date) return value
  let text = String(value).trim()
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$/.test(text)) {
    text = text.replace(' ', 'T')
  }
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(text)) {
    text = `${text}${STATION_OFFSET}`
  }
  return new Date(text)
}

export function formatDateTime(
  value: string | Date,
  options: Intl.DateTimeFormatOptions = {},
) {
  const date = toStationDate(value)
  return new Intl.DateTimeFormat(i18n.global.locale.value, {
    timeZone: STATION_TIME_ZONE,
    ...options,
  }).format(date)
}

/** 统一成 yyyy-MM-dd HH:mm:ss（东八区）。空值返回「—」，无法解析时原样返回。 */
export function formatLocalDateTime(
  value: string | Date | null | undefined,
): string {
  if (value === null || value === undefined || value === '') return '—'
  const date = toStationDate(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: STATION_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)
  const pick = (type: string) => parts.find((part) => part.type === type)?.value ?? ''
  return `${pick('year')}-${pick('month')}-${pick('day')} ${pick('hour')}:${pick('minute')}:${pick('second')}`
}

export function formatRelativeTimeFromNow(value: string | null | undefined) {
  if (!value) return t('time.justNow')
  const timestamp = toStationDate(value).getTime()
  if (Number.isNaN(timestamp)) return t('time.justNow')
  const diffMinutes = Math.max(1, Math.round((Date.now() - timestamp) / 60000))
  if (diffMinutes < 60) return t('time.minutesAgo', { count: diffMinutes })
  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) return t('time.hoursAgo', { count: diffHours })
  const diffDays = Math.round(diffHours / 24)
  return t('time.daysAgo', { count: diffDays })
}

watch(
  () => i18n.global.locale.value,
  (locale) => {
    localStorage.setItem(LOCALE_STORAGE_KEY, locale)
    document.documentElement.lang = locale
  },
  { immediate: true },
)
