<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Loader2, ArrowLeft, ExternalLink, ImageOff, Package } from 'lucide-vue-next'
import type { ResultItem } from '@/types/result.d.ts'

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
const info = computed(() => item.value?.商品信息 ?? ({} as ResultItem['商品信息']))
const seller = computed(() => item.value?.卖家信息 ?? {})
const ai = computed(() => item.value?.ai_analysis)
const priceInsight = computed(() => item.value?.price_insight)

const statusTone = computed(() => {
  const status = String(info.value?.商品状态 ?? '')
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
      rows.push({ label, value: key === '卖家注册时长' ? value.replace(/^来闲鱼/, '') : value })
    }
  }
  push('卖家昵称', t('itemDetail.nickname'))
  push('卖家信用等级', t('itemDetail.sellerCredit'))
  push('卖家芝麻信用', t('itemDetail.zhimaCredit'))
  push('买家信用等级', t('itemDetail.buyerCredit'))
  push('卖家注册时长', t('itemDetail.memberAge'))
  push('作为卖家的好评率', t('itemDetail.sellerRate'))
  push('作为卖家的好评数', t('itemDetail.sellerRateCount'))
  push('卖家收到的评价总数', t('itemDetail.reviewCount'))
  push('卖家在售/已售商品数', t('itemDetail.listings'))
  return rows
})

const productTags = computed(() => (Array.isArray(info.value?.商品标签) ? info.value!.商品标签 : []) as string[])

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

onMounted(load)
watch(itemId, load)
</script>

<template>
  <div class="space-y-5">
    <div class="flex items-center justify-between gap-3">
      <Button variant="ghost" @click="router.back()">
        <ArrowLeft class="mr-1 h-4 w-4" /> {{ t('itemDetail.back') }}
      </Button>
      <a
        v-if="info.商品链接"
        :href="info.商品链接"
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex items-center text-sm text-primary hover:underline"
      >
        <ExternalLink class="mr-1 h-4 w-4" /> {{ t('itemDetail.openOnXianyu') }}
      </a>
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

        <Card v-if="info.商品描述">
          <CardHeader class="pb-2">
            <CardTitle class="text-base">{{ t('itemDetail.description') }}</CardTitle>
          </CardHeader>
          <CardContent>
            <p class="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{{ info.商品描述 }}</p>
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
                <span class="text-xs font-semibold text-slate-700">{{ entry.key }}</span>
                <Badge v-if="entry.status" class="text-[10px]" variant="secondary">{{ entry.status }}</Badge>
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
            <h1 class="text-base font-semibold leading-snug text-slate-800">{{ info.商品标题 }}</h1>
            <div class="flex items-center gap-2">
              <span class="text-2xl font-bold text-rose-600">{{ formatPrice(info.当前售价) }}</span>
              <span v-if="info['商品原价'] && info['商品原价'] !== '暂无'" class="text-xs text-slate-400 line-through">
                {{ info['商品原价'] }}
              </span>
            </div>
            <div class="flex flex-wrap gap-1.5">
              <Badge v-if="info.商品状态" :class="statusTone">{{ info.商品状态 }}</Badge>
              <Badge v-for="tag in productTags" :key="tag" variant="secondary">{{ tag }}</Badge>
            </div>

            <dl class="grid grid-cols-2 gap-x-3 gap-y-2 border-t border-slate-100 pt-3 text-xs">
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">{{ t('results.card.publishTime') }}</dt>
                <dd class="truncate font-medium text-slate-700">{{ info.发布时间 || '—' }}</dd>
              </div>
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">{{ t('results.card.shipsFrom') }}</dt>
                <dd class="truncate font-medium text-slate-700">{{ info.发货地区 || '—' }}</dd>
              </div>
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">{{ t('results.card.views') }}</dt>
                <dd class="font-medium text-slate-700">{{ info.浏览量 ?? '—' }}</dd>
              </div>
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">{{ t('results.card.wanted') }}</dt>
                <dd class="font-medium text-slate-700">{{ info['“想要”人数'] ?? '—' }}</dd>
              </div>
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">{{ t('itemDetail.collected') }}</dt>
                <dd class="font-medium text-slate-700">{{ info.商品收藏数 ?? '—' }}</dd>
              </div>
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">{{ t('itemDetail.soldCount') }}</dt>
                <dd class="font-medium text-slate-700">{{ info.商品已售数 ?? '—' }}</dd>
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
              {{ t('itemDetail.analyzedAt') }}: {{ ai.backfilled_at || item.爬取时间 }}
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
                  ['avg_price', t('itemDetail.marketAvg')],
                  ['median_price', t('itemDetail.marketMedian')],
                  ['min_price', t('itemDetail.marketLow')],
                  ['max_price', t('itemDetail.marketHigh')],
                  ['historical_low', t('itemDetail.historicalLow')],
                ]"
                :key="row[0]"
                class="flex justify-between gap-2"
              >
                <dt class="text-slate-400">{{ row[1] }}</dt>
                <dd class="font-medium text-slate-700">
                  {{ priceInsight[row[0] as keyof typeof priceInsight] ?? '—' }}
                </dd>
              </div>
            </dl>
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