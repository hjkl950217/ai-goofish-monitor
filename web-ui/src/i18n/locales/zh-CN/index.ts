import type { LocaleModule } from '../../types'
import base from './base'
import extra from './extra'

const locale: LocaleModule = {
  code: 'zh-CN',
  label: '中文',
  shortLabel: '中',
  messages: { ...base, ...extra },
}

export default locale
