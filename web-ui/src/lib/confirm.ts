import { t } from '@/i18n'

/** 保存前确认，避免误点把当前表单值直接写盘。 */
export function confirmSave(): boolean {
  return window.confirm(t('common.confirmSave'))
}
