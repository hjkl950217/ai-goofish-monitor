import type { LocaleModule } from '../../types'
import base from './base'
import extra from './extra'

const locale: LocaleModule = {
  code: 'en-US',
  label: 'English',
  shortLabel: 'EN',
  messages: { ...base, ...extra },
}

export default locale
