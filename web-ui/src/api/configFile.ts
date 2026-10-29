import { http } from '@/lib/http'

export interface RawConfig {
  path: string
  content: string
}

export async function getRawConfig(): Promise<RawConfig> {
  return await http('/api/config/raw')
}

export async function saveRawConfig(content: string): Promise<{ message: string }> {
  return await http('/api/config/raw', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
}
