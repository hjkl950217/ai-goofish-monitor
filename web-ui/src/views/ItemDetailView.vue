<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Loader2, ArrowLeft, ExternalLink, ImageOff, Package, TrendingDown, TrendingUp, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-vue-next'
import type { ResultItem } from '@/types/result.d.ts'
import { criteriaLabel, criteriaStatusLabel, criteriaStatusTone } from '@/constants/criteria'
import { formatLocalDateTime } from '@/i18n'
import { getResultContent } from '@/api/results'
import { toast } from '@/components/ui/toast/use-toast'

interface ItemImage {
  name: string
  task: string
  index: number | null
  size: number
  url: string
}

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const item = ref<ResultItem | null>(null)
const images = ref<ItemImage[]>([])
const isLoading = ref(true)
const error = ref('')
const activeImage = ref<number>(0)
const lightboxOpen = ref(false)

const itemId = computed(() => String(route.params.itemId ?? ''))
const info = computed(() => item.value?.item_info ?? ({} as ResultItem['item_info']))
const seller = computed(() => item.value?.seller_info ?? {})
const ai = computed(() => item.value?.ai_analysis)
const priceInsight = computed(() => item.value?.price_insight)

const isExpired = computed(() => item.value?._status === 'expired' || item.value?._meta?.status === 'expired')
const initialPrice = computed(() => item.value?._meta?.initial_price ?? item.value?._initial_price ?? null)
const currentPrice = computed(() => item.value?._meta?.price ?? item.value?._current_price ?? null)
const priceDelta = computed(() => {
  const first = initialPrice.value
  const latest = currentPrice.value
  if (typeof first !== 'number' || typeof latest !== 'number') return 0
  return Math.round((latest - first) * 100) / 100
})
const deltaTone = computed(() => (priceDelta.value < 0 ? 'text-emerald-600' : 'text-rose-600'))
const formattedDelta = computed(() => {
  const abs = Math.abs(priceDelta.value)
  return Number.isInteger(abs) ? `¥${abs}` : `¥${abs.toFixed(2)}`
})

const statusTone = computed(() => {
  const status = String(info.value?.status ?? '')
  if (status === '在线') return 'bg-emerald-50 text-emerald-700'
  if (status === '卖掉了' || status === '已下架') return 'bg-rose-50 text-rose-700'
  return 'bg-slate-100 text-slate-600'
})

const currentImage = computed(() => images.value[activeImage.value] ?? null)

const riskTags = computed(() => (Array.isArray(ai.value?.risk_tags) ? ai.value!.risk_tags : []) as string[])

const criteriaEntries = computed(() => {
  const criteria = ai.value?.criteria_analysis
  if (!criteria || typeof criteria !== 'object') return []
  return Object.entries(criteria as Record<string, unknown>).map(([key, value]) => {
    if (value && typeof value === 'object') {
      const obj = value as { status?: string; comment?: string; evidence?: string }
      return { key, status: obj.status ?? '', comment: obj.comment ?? '', evidence: obj.evidence ?? '' }
    }
    return { key, status: '', comment: String(value), evidence: '' }
  })
})

const sellerRows = computed(() => {
  const rows: { label: string; value: string }[] = []
  const push = (key: string, label: string) => {
    const raw = seller.value[key as keyof typeof seller.value]
    const value = raw == null ? '' : String(raw).trim()
    if (value && value !== '暂无' && value !== '-') {
      rows.push({ label, value: key === 'seller_registered_years' ? value.replace(/^来闲鱼/, '') : value })
    }
  }
  push('seller_nickname', t('itemDetail.nickname'))
  push('seller_credit_level', t('itemDetail.sellerCredit'))
  push('seller_zhima_credit', t('itemDetail.zhimaCredit'))
  push('buyer_credit_level', t('itemDetail.buyerCredit'))
  push('seller_registered_years', t('itemDetail.memberAge'))
  push('seller_good_rate', t('itemDetail.sellerRate'))
  push('seller_good_ratings', t('itemDetail.sellerRateCount'))
  push('seller_rating_total', t('itemDetail.reviewCount'))
  push('seller_listing_counts', t('itemDetail.listings'))
  return rows
})

const productTags = computed(() => (Array.isArray(info.value?.tags) ? info.value!.tags : []) as string[])

const EMPTY_VALUES = new Set(['', '-', '暂无', 'N/A', 'null', 'undefined'])
function display(value: unknown): string {
  if (value === null || value === undefined) return '—'
  const text = String(value).trim()
  return EMPTY_VALUES.has(text) ? '—' : text
}

async function load() {
  if (!itemId.value) return
  isLoading.value = true
  error.value = ''
  activeImage.value = 0
  try {
    const [itemRes, imgRes] = await Promise.all([
      fetch(`/api/items/${encodeURIComponent(itemId.value)}`),
      fetch(`/api/items/${encodeURIComponent(itemId.value)}/images`),
    ])
    if (!itemRes.ok) throw new Error(t('itemDetail.notFound'))
    item.value = (await itemRes.json()) as ResultItem
    if (imgRes.ok) {
      const data = (await imgRes.json()) as { images: ItemImage[] }
      images.value = data.images ?? []
    }
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    isLoading.value = false
  }
}

function formatPrice(value?: string | number): string {
  if (value == null) return '—'
  const text = String(value).trim()
  return text && text !== '暂无' ? text : '—'
}

const neighborIds = ref<{ prev: string | null; next: string | null }>({ prev: null, next: null })

async function loadNeighbors() {
  const filename = item.value?._meta?.result_filename
  if (!filename) return
  try {
    const data = await getResultContent(filename, { limit: 500, page: 1 })
    const ids = (data.items || []).map((row) =>
      String(row.item_info?.item_id ?? row._meta?.item_id ?? ''),
    )
    const index = ids.indexOf(itemId.value)
    neighborIds.value = {
      prev: index > 0 ? ids[index - 1] ?? null : null,
      next: index >= 0 && index < ids.length - 1 ? ids[index + 1] ?? null : null,
    }
  } catch {
    neighborIds.value = { prev: null, next: null }
  }
}

function goItem(id: string | null) {
  if (!id) return
  router.push({ name: 'ItemDetail', params: { itemId: id } })
}

const refreshing = ref(false)

// 手动拉一次详情：标题、描述、价格、图片都会更新，不重跑 AI
async function refreshLatest() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    const res = await fetch(`/api/items/${encodeURIComponent(itemId.value)}/refresh`, { method: 'POST' })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || `HTTP ${res.status}`)
    }
    await load()
    toast({ title: t('itemDetail.refreshDone') })
  } catch (e) {
    toast({
      title: t('itemDetail.refreshFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    refreshing.value = false
  }
}

onMounted(load)
watch(itemId, load)
watch(item, () => {
  loadNeighbors()
})
</script>

<template>
  <div class="space-y-5">
    <div class="flex items-center justify-between gap-3">
      <Button variant="ghost" @click="router.back()">
        <ArrowLeft class="mr-1 h-4 w-4" /> {{ t('itemDetail.back') }}
      </Button>
      <div class="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          :disabled="!neighborIds.prev"
          :title="t('itemDetail.prevItem')"
          :aria-label="t('itemDetail.prevItem')"
          @click="goItem(neighborIds.prev)"
        >
          <ChevronLeft class="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          :disabled="!neighborIds.next"
          :title="t('itemDetail.nextItem')"
          :aria-label="t('itemDetail.nextItem')"
          @click="goItem(neighborIds.next)"
        >
          <ChevronRight class="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          :disabled="refreshing"
          :title="t('itemDetail.refresh')"
          @click="refreshLatest"
        >
          <Loader2 v-if="refreshing" class="mr-1 h-4 w-4 animate-spin" />
          <RefreshCw v-else class="mr-1 h-4 w-4" />
          {{ refreshing ? t('itemDetail.refreshing') : t('itemDetail.refresh') }}
        </Button>
        <a
          v-if="info.link"
          :href="info.link"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center text-sm text-primary hover:underline"
        >
          <ExternalLink class="mr-1 h-4 w-4" /> {{ t('itemDetail.openOnXianyu') }}
        </a>
      </div>
    </div>

    <div v-if="isLoading" class="flex items-center justify-center py-20 text-slate-400">
      <Loader2 class="mr-2 h-5 w-5 animate-spin" /> {{ t('common.loading') }}
    </div>

    <div v-else-if="error" class="app-surface py-16 text-center text-rose-600">
      {{ error }}
    </div>

    <div v-else-if="item" class="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
      <!-- 左栏：图片 + 描述 -->
      <div class="space-y-5">
        <Card>
          <CardHeader class="pb-3">
            <CardTitle class="text-base">{{ t('itemDetail.images') }} ({{ images.length }})</CardTitle>
          </CardHeader>
          <CardContent>
            <div v-if="currentImage" class="space-y-3">
              <button
                type="button"
                class="block w-full overflow-hidden rounded-xl border border-slate-100 bg-slate-50"
                @click="lightboxOpen = true"
              >
                <img :src="currentImage.url" :alt="`${itemId}-${currentImage.index}`" class="max-h-[520px] w-full object-contain" />
              </button>
              <div v-if="images.length > 1" class="flex flex-wrap gap-2">
                <button
                  v-for="(img, idx) in images"
                  :key="img.name"
                  type="button"
                  class="h-16 w-16 overflow-hidden rounded-lg border-2 transition-colors"
                  :class="idx === activeImage ? 'border-emerald-500' : 'border-transparent hover:border-slate-300'"
                  @click="activeImage = idx"
                >
                  <img :src="img.url" :alt="`thumb-${idx}`" class="h-full w-full object-cover" loading="lazy" />
                </button>
              </div>
            </div>
            <div v-else class="flex flex-col items-center gap-2 rounded-xl border border-dashed border-slate-200 py-14 text-slate-400">
              <ImageOff class="h-7 w-7" />
              <p class="text-sm">{{ t('itemDetail.noImages') }}</p>
              <p class="text-xs">{{ t('itemDetail.noImagesHint') }}</p>
            </div>
          </CardContent>
        </Card>

        <Card v-if="info.description">
          <CardHeader class="pb-2">
            <CardTitle class="text-base">{{ t('itemDetail.description') }}</CardTitle>
          </CardHeader>
          <CardContent>
            <p class="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{{ info.description }}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-base">{{ t('itemDetail.aiCriteria') }}</CardTitle>
          </CardHeader>
          <CardContent class="space-y-3">
            <div
              v-for="entry in criteriaEntries"
              :key="entry.key"
              class="rounded-lg border border-slate-100 bg-slate-50/60 p-3"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="text-xs font-semibold text-slate-700">{{ criteriaLabel(entry.key) }}</span>
                <Badge v-if="entry.status" class="text-[10px] border" :class="criteriaStatusTone(entry.status)" variant="secondary">{{ criteriaStatusLabel(entry.status) }}</Badge>
              </div>
              <p v-if="entry.comment" class="mt-1.5 text-xs leading-relaxed text-slate-600">{{ entry.comment }}</p>
              <p v-if="entry.evidence" class="mt-1 text-[11px] leading-relaxed text-slate-400">{{ entry.evidence }}</p>
            </div>
            <p v-if="!criteriaEntries.length" class="text-sm text-slate-400">—</p>
          </CardContent>
        </Card>
      </div>

      <!-- 右栏：概要 -->
      <div class="space-y-5">
        <Card>
          <CardContent class="space-y-3 pt-4">
            <h1 class="text-base font-semibold leading-snug text-slate-800">{{ info.title }}</h1>
            <div class="flex items-center gap-2">
              <span class="text-2xl font-bold" :class="isExpired ? 'text-slate-400' : 'text-rose-600'">{{ formatPrice(info.price) }}</span>
              <span v-if="info['original_price'] && info['original_price'] !== '暂无'" class="text-xs text-slate-400 line-through">
                {{ info['original_price'] }}
              </span>
            </div>
            <div v-if="priceDelta !== 0" class="flex items-center gap-1 text-xs">
              <component :is="priceDelta < 0 ? TrendingDown : TrendingUp" class="w-4 h-4" :class="deltaTone" />
              <span class="text-slate-400">{{ t('results.card.priceSinceAdded') }}</span>
              <span class="font-semibold" :class="deltaTone">{{ priceDelta < 0 ? '-' : '+' }}{{ formattedDelta }}</span>
            </div>
            <div class="flex flex-wrap gap-1.5">
              <Badge v-if="info.status" :class="statusTone">{{ info.status }}</Badge>
              <Badge v-for="tag in productTags" :key="tag" variant="secondary">{{ tag }}</Badge>
            </div>

            <dl class="grid grid-cols-2 gap-x-3 gap-y-2 border-t border-slate-100 pt-3 text-xs">
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">{{ t('results.card.publishTime') }}</dt>
                <dd class="truncate font-medium text-slate-700">{{ formatLocalDateTime(info.publish_time) }}</dd>
              </div>
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">{{ t('results.card.shipsFrom') }}</dt>
                <dd class="truncate font-medium text-slate-700">{{ display(info.shipping_area) }}</dd>
              </div>
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">{{ t('results.card.views') }}</dt>
                <dd class="font-medium text-slate-700">{{ display(info.view_count) }}</dd>
              </div>
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">{{ t('results.card.wanted') }}</dt>
                <dd class="font-medium text-slate-700">{{ display(info['want_count']) }}</dd>
              </div>
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">{{ t('itemDetail.collected') }}</dt>
                <dd class="font-medium text-slate-700">{{ display(info.favorite_count) }}</dd>
              </div>
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">{{ t('itemDetail.soldCount') }}</dt>
                <dd class="font-medium text-slate-700">{{ display(info.sold_count) }}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card v-if="ai">
          <CardHeader class="pb-2">
            <CardTitle class="flex items-center justify-between text-base">
              <span>{{ t('itemDetail.aiVerdict') }}</span>
              <span
                class="text-sm font-black"
                :class="ai.is_recommended ? 'text-emerald-600' : 'text-rose-600'"
              >
                {{ ai.value_score != null ? `${ai.value_score}%` : '—' }}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent class="space-y-3">
            <Badge :class="ai.is_recommended ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'">
              {{ ai.is_recommended ? t('results.card.strongRecommend') : t('results.card.notRecommended') }}
            </Badge>
            <p class="text-sm leading-relaxed text-slate-700">{{ ai.reason }}</p>
            <p v-if="ai.value_summary" class="rounded-lg bg-slate-50 p-2.5 text-xs leading-relaxed text-slate-600">
              {{ ai.value_summary }}
            </p>
            <div v-if="riskTags.length" class="flex flex-wrap gap-1.5">
              <Badge v-for="tag in riskTags" :key="tag" variant="outline" class="text-rose-600">
                {{ tag }}
              </Badge>
            </div>
            <p class="text-[11px] text-slate-400">
              {{ t('itemDetail.analyzedAt') }}: {{ formatLocalDateTime(ai.backfilled_at || item?.crawl_time) }}
            </p>
          </CardContent>
        </Card>

        <Card v-if="priceInsight">
          <CardHeader class="pb-2">
            <CardTitle class="text-base">{{ t('itemDetail.priceInsight') }}</CardTitle>
          </CardHeader>
          <CardContent>
            <dl class="space-y-1.5 text-xs">
              <div v-for="row in [
                  ['market_avg_price', t('itemDetail.marketAvg')],
                  ['market_median_price', t('itemDetail.marketMedian')],
                  ['avg_price', t('itemDetail.ownAvg')],
                  ['median_price', t('itemDetail.ownMedian')],
                  ['min_price', t('itemDetail.historicalLow')],
                  ['max_price', t('itemDetail.historicalHigh')],
                ]"
                :key="row[0]"
                class="flex justify-between gap-2"
              >
                <dt class="text-slate-400">{{ row[1] }}</dt>
                <dd class="font-medium text-slate-700">
                  {{ display(priceInsight[row[0] as keyof typeof priceInsight]) }}
                </dd>
              </div>
            </dl>
            <p class="mt-3 text-[11px] leading-relaxed text-slate-400">
              {{ t('itemDetail.priceSourceNote') }}
            </p>
          </CardContent>
        </Card>

        <Card v-if="sellerRows.length">
          <CardHeader class="pb-2">
            <CardTitle class="text-base">{{ t('itemDetail.sellerInfo') }}</CardTitle>
          </CardHeader>
          <CardContent>
            <dl class="space-y-1.5 text-xs">
              <div v-for="row in sellerRows" :key="row.label" class="flex justify-between gap-3">
                <dt class="shrink-0 text-slate-400">{{ row.label }}</dt>
                <dd class="truncate font-medium text-slate-700">{{ row.value }}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardContent class="pt-4 text-[11px] text-slate-400">
            <div class="flex items-center gap-1.5">
              <Package class="h-3.5 w-3.5" />
              {{ t('itemDetail.sourceFile') }}: {{ item._meta?.result_filename }}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>

    <!-- 大图查看 -->
    <div
      v-if="lightboxOpen && currentImage"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      @click.self="lightboxOpen = false"
    >
      <img :src="currentImage.url" :alt="`${itemId}-${currentImage.index}`" class="max-h-full max-w-full object-contain" />
      <button
        type="button"
        class="absolute right-4 top-4 rounded-full bg-white/20 px-3 py-1.5 text-sm text-white hover:bg-white/30"
        @click="lightboxOpen = false"
      >
        {{ t('common.close') }}
      </button>
    </div>
  </div>
</template>