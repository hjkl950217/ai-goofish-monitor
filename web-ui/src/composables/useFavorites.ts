import { readonly, ref } from 'vue'
import type { ResultItem } from '@/types/result.d.ts'

interface FavoriteItem {
  item_id: string
  link: string
  title?: string
  created_at: string
}

const ids = ref<Set<string>>(new Set())
const loaded = ref(false)
const pending = ref<Set<string>>(new Set())
let loadPromise: Promise<void> | null = null

async function load(): Promise<void> {
  if (loaded.value) return
  if (loadPromise) return loadPromise
  loadPromise = (async () => {
    try {
      const res = await fetch('/api/favorites')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = (await res.json()) as { favorites: FavoriteItem[] }
      ids.value = new Set(data.favorites.map((f) => f.item_id))
      loaded.value = true
    } finally {
      loadPromise = null
    }
  })()
  return loadPromise
}

function isFavorite(itemId: string): boolean {
  return ids.value.has(itemId)
}

function isPending(itemId: string): boolean {
  return pending.value.has(itemId)
}

async function toggle(item: ResultItem): Promise<boolean> {
  const { item_id: itemId, link, title } = item.item_info
  if (!itemId || pending.value.has(itemId)) return isFavorite(itemId)
  const wasFavorite = isFavorite(itemId)
  pending.value.add(itemId)
  try {
    const res = await fetch(`/api/favorites/${encodeURIComponent(itemId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: wasFavorite ? 'remove' : 'add',
        link,
        title,
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as { favorited: boolean }
    if (data.favorited) ids.value.add(itemId)
    else ids.value.delete(itemId)
    return data.favorited
  } finally {
    pending.value.delete(itemId)
  }
}

export function useFavorites() {
  return {
    favorites: readonly(ids),
    load,
    isFavorite,
    isPending,
    toggle,
  }
}