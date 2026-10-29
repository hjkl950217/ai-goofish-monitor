/** 一门语言就是一个目录：新增语言只需复制本目录并改 code/label，其他代码不用动。 */
export interface LocaleModule {
  code: string
  label: string
  shortLabel: string
  messages: Record<string, unknown>
}
