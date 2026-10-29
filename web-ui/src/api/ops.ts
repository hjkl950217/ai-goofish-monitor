import { http } from '@/lib/http'

export interface OpsConfig {
  AGM_DEBUG_CAPTURE: string
  AGM_BROWSER_TRACE: string
  AGM_TRACE_DIR: string
  // 任务运行选项：保存后对下一个任务生效
  KEEP_TASK_IMAGES: boolean
  REFRESH_TRACKED_ITEMS: boolean
  AI_DEBUG_MODE: boolean
  ENABLE_THINKING: boolean
  ENABLE_RESPONSE_FORMAT: boolean
  TASK_FAILURE_THRESHOLD: number
  TASK_FAILURE_PAUSE_SECONDS: number
  TASK_LOG_RETENTION_DAYS: number
}

export interface TraceFile {
  name: string
  size: number
}

export interface TraceDir {
  name: string
  path: string
  size: number
  mtime: string
  files: TraceFile[]
}

export async function getOpsConfig(): Promise<OpsConfig> {
  return await http('/api/ops/config')
}

export async function saveOpsConfig(payload: OpsConfig): Promise<{ message: string }> {
  return await http('/api/ops/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function listTraces(): Promise<TraceDir[]> {
  return await http('/api/ops/traces')
}
