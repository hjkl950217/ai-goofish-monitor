import { http } from '@/lib/http'

export interface ModelCheckStatus {
  running: boolean
  total: number
  done: number
  matched: number
  removed: number
  failed: number
  message: string
  started_at: string | null
  finished_at: string | null
  recent: string[]
}

export async function getModelCheckStatus(): Promise<ModelCheckStatus> {
  return await http('/api/model-check/status')
}

export async function startModelCheck(workers = 3): Promise<{ message: string; status: ModelCheckStatus }> {
  return await http('/api/model-check/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ workers }),
  })
}

export async function cancelModelCheck(): Promise<{ message: string; status: ModelCheckStatus }> {
  return await http('/api/model-check/cancel', { method: 'POST' })
}
