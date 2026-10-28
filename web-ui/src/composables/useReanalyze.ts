import { ref } from 'vue'

export interface ReanalyzeStatus {
  running: boolean
  scope: string
  total: number
  done: number
  ok: number
  failed: number
  message: string
  started_at: string | null
  finished_at: string | null
  recent: string[]
}

const status = ref<ReanalyzeStatus>({
  running: false,
  scope: '',
  total: 0,
  done: 0,
  ok: 0,
  failed: 0,
  message: '',
  started_at: null,
  finished_at: null,
  recent: [],
})

let timer: ReturnType<typeof setInterval> | null = null
const listeners = new Set<(s: ReanalyzeStatus) => void>()

async function fetchStatus(): Promise<void> {
  try {
    const res = await fetch('/api/reanalyze/status')
    if (!res.ok) return
    const data = (await res.json()) as ReanalyzeStatus
    status.value = data
    listeners.forEach((fn) => fn(data))
    if (!data.running && timer) {
      clearInterval(timer)
      timer = null
    }
  } catch {
    /* 忽略状态轮询错误 */
  }
}

function subscribe(fn: (s: ReanalyzeStatus) => void): () => void {
  listeners.add(fn)
  void fetchStatus()
  return () => listeners.delete(fn)
}

async function start(payload: {
  scope: 'pending' | 'all' | 'selected'
  limit?: number | null
  workers?: number
  item_ids?: string[] | null
}): Promise<void> {
  const res = await fetch('/api/reanalyze/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error((data as { detail?: string }).detail || `HTTP ${res.status}`)
  }
  await fetchStatus()
  if (!timer) timer = setInterval(fetchStatus, 1500)
}

async function cancel(): Promise<void> {
  await fetch('/api/reanalyze/cancel', { method: 'POST' })
  await fetchStatus()
}

// ------------------------------------------------------------ 图片缓存

export interface ImageCacheStats {
  total_size: string
  total_bytes: number
  file_count: number
  task_count: number
  dirs: { name: string; task: string; files: number; size: string }[]
}

const imageCache = ref<ImageCacheStats | null>(null)
const isClearingImages = ref(false)

async function fetchImageCache(): Promise<ImageCacheStats | null> {
  try {
    const res = await fetch('/api/reanalyze/images/stats')
    if (!res.ok) return null
    const data = (await res.json()) as ImageCacheStats
    imageCache.value = data
    return data
  } catch {
    return null
  }
}

async function clearImageCache(): Promise<{ freed_size: string; removed: string[] }> {
  isClearingImages.value = true
  try {
    const res = await fetch('/api/reanalyze/images', { method: 'DELETE' })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error((data as { detail?: string }).detail || `HTTP ${res.status}`)
    }
    const data = (await res.json()) as { freed_size: string; removed: string[] }
    await fetchImageCache()
    return data
  } finally {
    isClearingImages.value = false
  }
}

export function useReanalyze() {
  return {
    status,
    fetchStatus,
    subscribe,
    start,
    cancel,
    imageCache,
    isClearingImages,
    fetchImageCache,
    clearImageCache,
  }
}