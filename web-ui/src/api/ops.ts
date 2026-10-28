import { http } from '@/lib/http'

export interface OpsConfig {
  AGM_DEBUG_CAPTURE: string
  AGM_BROWSER_TRACE: string
  AGM_TRACE_DIR: string
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
