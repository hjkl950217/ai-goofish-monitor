<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { ResultItem } from '@/types/result.d.ts'
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import Badge from '@/components/ui/badge/Badge.vue'
import { toast } from '@/components/ui/toast/use-toast'
import { useFavorites } from '@/composables/useFavorites'
import { ExternalLink, TrendingUp, TrendingDown, Info, User, Clock, CheckCircle2, XCircle, AlertCircle, EyeOff, Eye, MapPin, CalendarDays, Heart, Tag, RefreshCw, Loader2 } from 'lucide-vue-next'
import { formatLocalDateTime } from '@/i18n'
import LazyImage from './LazyImage.vue'

interface Props {
  item: ResultItem
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'toggle-block', item: ResultItem): void
  (e: 'refreshed'): void
}>()
const { t } = useI18n()

const info = props.item.item_info
const seller = props.item.seller_info ?? {}
const ai = props.item.ai_analysis
const priceInsight = props.item.price_insight

const isRecommended = ai?.is_recommended === true
const recommendationStatus = computed(() => {
  if (ai?.is_recommended === true) return { label: t('results.card.strongRecommend'), color: 'bg-emerald-500', icon: CheckCircle2, text: 'text-emerald-600', bg: 'bg-emerald-50' }
  if (ai?.is_recommended === false) return { label: t('results.card.notRecommended'), color: 'bg-rose-500', icon: XCircle, text: 'text-rose-600', bg: 'bg-rose-50' }
  return { label: t('results.card.pending'), color: 'bg-amber-500', icon: AlertCircle, text: 'text-amber-600', bg: 'bg-amber-50' }
})

const imageUrl = info.images?.[0] || info.main_image || ''
const crawlTime = formatLocalDateTime(props.item.crawl_time)
const rawMatchScore = ai?.value_score
const hasMatchScore = typeof rawMatchScore === 'number' && Number.isFinite(rawMatchScore)
const matchScore = hasMatchScore ? Math.max(0, Math.min(100, rawMatchScore)) : 0
const isHidden = computed(() => props.item._effective_hidden === true || props.item._status === 'hidden')
const isExpired = computed(() => props.item._status === 'expired')
const initialPrice = props.item._initial_price
const currentPrice = props.item._current_price
const priceDelta = computed(() => {
  if (typeof initialPrice !== 'number' || typeof currentPrice !== 'number') return 0
  return Math.round((currentPrice - initialPrice) * 100) / 100
})
const deltaTone = computed(() => (priceDelta.value < 0 ? 'text-emerald-600' : 'text-rose-600'))
const formattedDelta = computed(() => {
  const abs = Math.abs(priceDelta.value)
  return Number.isInteger(abs) ? `¥${abs}` : `¥${abs.toFixed(2)}`
})
const isRuleHidden = computed(() => props.item._hidden_reason === 'rule')
const canToggleBlock = computed(() => props.item._hidden_reason !== 'rule' && props.item._hidden_reason !== 'expired')
const hiddenLabel = computed(() => {
  if (props.item._hidden_reason === 'rule') return t('results.card.blacklisted')
  if (props.item._hidden_reason === 'expired') return t('results.card.expired')
  return t('results.card.hidden')
})

const expanded = ref(false)

interface SellerBadge {
  label: string
  value: string
  tone: string
}

const cleanText = (value?: string) => (value ?? '').trim()

const hasValue = (value?: string | number | null) => {
  const text = String(value ?? '').trim()
  return text !== '' && text !== '-' && text !== '暂无' && text !== 'N/A' && text !== '0'
}

const publishTime = cleanText(info.publish_time).replace(/^\d{4}-/, '')
const shipRegion = cleanText(info.shipping_area)
const viewCount = info.view_count
const wantCount = info['want_count']
const productTags = Array.isArray(info.tags) ? info.tags : []

const listingStats = computed(() => {
  const list = Array.isArray(seller['seller_items']) ? seller['seller_items'] : []
  let onSale = 0
  let sold = 0
  for (const entry of list) {
    if (entry?.status === '在售') onSale += 1
    else if (entry?.status === '已售') sold += 1
  }
  const total = Number.parseInt(String(seller['seller_listing_counts'] ?? ''), 10)
  return { onSale, sold, total: Number.isNaN(total) ? onSale + sold : total }
})

const shortCredit = (value: string) => value.replace(/^(卖家|买家)?信用/, '') || value

const creditTone = (value: string) => {
  if (/(较差|很差|差评)/.test(value)) return 'text-rose-600'
  if (/(中等|一般)/.test(value)) return 'text-amber-600'
  if (/(极好|优秀|良好)/.test(value)) return 'text-emerald-600'
  return 'text-slate-600'
}

const rateTone = (rate: string) => {
  const value = Number.parseFloat(rate)
  if (Number.isNaN(value)) return 'text-slate-600'
  if (value >= 99) return 'text-emerald-600'
  if (value >= 90) return 'text-amber-600'
  return 'text-rose-600'
}

const sellerBadges = computed<SellerBadge[]>(() => {
  const badges: SellerBadge[] = []
  const stats = listingStats.value
  if (stats.onSale || stats.sold) {
    const base = `${stats.onSale} / ${stats.sold}`
    badges.push({
      label: t('results.card.sellerListings'),
      value: stats.total > stats.onSale + stats.sold
        ? t('results.card.listingsTotal', { value: base, total: stats.total })
        : base,
      tone: stats.sold > 0 ? 'text-emerald-600' : 'text-slate-600',
    })
  }
  const credit = cleanText(seller['seller_credit_level'])
  badges.push({
    label: t('results.card.sellerCredit'),
    value: hasValue(credit) ? shortCredit(credit) : t('results.card.noData'),
    tone: hasValue(credit) ? creditTone(credit) : 'text-slate-400',
  })
  const zhima = cleanText(seller['seller_zhima_credit'])
  badges.push({
    label: t('results.card.zhimaCredit'),
    value: hasValue(zhima) ? shortCredit(zhima) : t('results.card.noData'),
    tone: hasValue(zhima) ? creditTone(zhima) : 'text-slate-400',
  })
  const buyerCredit = cleanText(seller['buyer_credit_level'])
  badges.push({
    label: t('results.card.buyerCredit'),
    value: hasValue(buyerCredit) ? shortCredit(buyerCredit) : t('results.card.noData'),
    tone: hasValue(buyerCredit) ? creditTone(buyerCredit) : 'text-slate-400',
  })
  const member = cleanText(seller['seller_registered_years'])
  badges.push({
    label: t('results.card.memberAge'),
    value: hasValue(member) ? member.replace(/^来闲鱼/, '') : t('results.card.noData'),
    tone: hasValue(member) ? 'text-slate-600' : 'text-slate-400',
  })
  const rate = cleanText(seller['seller_good_rate'])
  const count = cleanText(seller['seller_good_ratings'])
  if (hasValue(rate) && count && count !== '0/0') {
    badges.push({
      label: t('results.card.sellerRating'),
      value: `${count} · ${rate}`,
      tone: rateTone(rate),
    })
  } else {
    badges.push({
      label: t('results.card.sellerRating'),
      value: t('results.card.noData'),
      tone: 'text-slate-400',
    })
  }
  return badges
})

const router = useRouter()
const detailPath = computed(() => `/results/item/${encodeURIComponent(info.item_id)}`)
function openDetail(event: MouseEvent) {
  event.preventDefault()
  event.stopPropagation()
  void router.push(detailPath.value)
}

const fav = useFavorites()
const favOn = computed(() => fav.isFavorite(info.item_id))
const favPending = computed(() => fav.isPending(info.item_id))

onMounted(() => {
  fav.load().catch(() => {})
})

async function onToggleFavorite() {
  if (favPending.value) return
  try {
    await fav.load()
    await fav.toggle(props.item)
  } catch (error) {
    toast({
      title: t('results.card.favoriteFailed'),
      description: error instanceof Error ? error.message : String(error),
      variant: 'destructive',
    })
  }
}

const refreshing = ref(false)

// 手动拉一次详情：图片、标题、描述、价格都会更新
async function onRefresh() {
  const id = String(info.item_id ?? '')
  if (!id || refreshing.value) return
  refreshing.value = true
  try {
    const filename = props.item._meta?.result_filename
    const query = filename ? `?result_filename=${encodeURIComponent(filename)}` : ''
    const res = await fetch(`/api/items/${encodeURIComponent(id)}/refresh${query}`, { method: 'POST' })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || `HTTP ${res.status}`)
    }
    toast({ title: t('results.card.refreshDone') })
    emit('refreshed')
  } catch (error) {
    toast({
      title: t('results.card.refreshFailed'),
      description: error instanceof Error ? error.message : String(error),
      variant: 'destructive',
    })
  } finally {
    refreshing.value = false
  }
}
</script>

<template>
  <!-- 半透明 + 背景模糊会让每张卡片各自成层，几百张时滚动只重绘不合成，这里用纯白底代替 -->
  <Card class="group flex flex-col h-full border-none shadow-glass hover:shadow-card-hover transition-shadow duration-300 rounded-2xl overflow-hidden bg-white" :class="{ 'opacity-50': isHidden }">
    <!-- Image Header -->
    <div class="relative aspect-[4/3] overflow-hidden">
      <div class="absolute inset-0 bg-slate-200 animate-pulse" v-if="!imageUrl"></div>
      <LazyImage
        v-else
        :src="imageUrl"
        :alt="info.title"
        class="h-full w-full cursor-zoom-in object-cover transition-[transform,opacity] duration-500 group-hover:scale-110"
        @click="openDetail"
      />
      <!-- Hidden overlay -->
      <div v-if="isHidden" class="absolute inset-0 bg-black/30 flex items-center justify-center">
        <span class="text-white/80 text-xs font-semibold uppercase tracking-wider">{{ hiddenLabel }}</span>
      </div>
      <!-- Overlays -->
      <div class="absolute top-3 left-3 flex gap-2">
        <Badge v-if="isExpired" variant="secondary" class="bg-slate-700/85 text-white border-none backdrop-blur-md shadow-sm">
          {{ t('results.card.priceOffline') }}
        </Badge>
        <Badge v-if="isRecommended && !isHidden" variant="default" class="bg-emerald-500/90 backdrop-blur-md border-none shadow-sm">
          {{ t('results.card.curated') }}
        </Badge>
        <Badge v-if="isRuleHidden" variant="secondary" class="bg-slate-900/75 text-white border-none backdrop-blur-md shadow-sm">
          {{ t('results.card.blacklisted') }}
        </Badge>
      </div>
      <div class="absolute top-3 right-3 flex gap-1.5">
        <button
          type="button"
          :disabled="refreshing"
          :title="t('results.card.refresh')"
          :aria-label="t('results.card.refresh')"
          @click.stop="onRefresh"
          class="flex rounded-full bg-white/30 p-1.5 text-white backdrop-blur-md border border-white/40 shadow-sm transition-opacity disabled:cursor-wait disabled:opacity-60 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-visible:opacity-100 hover:bg-white/50"
        >
          <Loader2 v-if="refreshing" class="w-4 h-4 animate-spin" />
          <RefreshCw v-else class="w-4 h-4" />
        </button>
        <button
          type="button"
          :disabled="favPending"
          :aria-pressed="favOn"
          :title="favOn ? t('results.card.favorited') : t('results.card.favorite')"
          @click.stop="onToggleFavorite"
          class="flex rounded-full p-1.5 backdrop-blur-md border shadow-sm transition-colors disabled:opacity-60 disabled:cursor-wait"
          :class="favOn ? 'bg-rose-500/90 border-white/50 text-white' : 'bg-white/30 border-white/40 text-white hover:bg-white/50'"
        >
          <Heart class="w-4 h-4" :class="favOn ? 'fill-white' : ''" />
        </button>
        <button
          v-if="canToggleBlock"
          type="button"
          @click="emit('toggle-block', props.item)"
          :aria-label="isHidden ? t('results.card.unblock') : t('results.card.block')"
          class="flex rounded-full bg-white/30 p-1.5 text-white backdrop-blur-md border border-white/40 shadow-sm opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:focus-visible:opacity-100 hover:bg-white/50"
        >
          <EyeOff v-if="!isHidden" class="w-4 h-4" />
          <Eye v-else class="w-4 h-4" />
        </button>
         <a
           :href="info.link"
           target="_blank"
           rel="noopener noreferrer"
           :aria-label="t('results.card.detail')"
           class="flex rounded-full bg-white/30 p-1.5 text-white backdrop-blur-md border border-white/40 shadow-sm opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:focus-visible:opacity-100"
         >
            <ExternalLink class="w-4 h-4" />
         </a>
      </div>
    </div>

    <CardHeader class="px-4 pt-3 pb-1">
      <div class="flex justify-between items-start gap-3">
        <CardTitle class="text-base font-semibold text-slate-800 line-clamp-2 leading-snug flex-grow">
          <a
            href="#"
            class="cursor-pointer hover:text-primary transition-colors"
            :title="t('itemDetail.openLocal')"
            @click="openDetail"
          >
            {{ info.title }}
          </a>
        </CardTitle>
      </div>
      <div class="flex items-baseline gap-1 mt-1">
        <span
          class="text-2xl font-bold tracking-tight"
          :class="isExpired ? 'text-slate-400' : 'text-rose-600'"
        >{{ info.price }}</span>
        <span v-if="hasValue(info['original_price'])" class="text-xs text-slate-400 line-through mb-1">{{ info['original_price'] }}</span>
      </div>
      <div v-if="priceDelta !== 0" class="flex items-center gap-1 text-[11px]">
        <component :is="priceDelta < 0 ? TrendingDown : TrendingUp" class="w-3.5 h-3.5 shrink-0" :class="deltaTone" />
        <span class="text-slate-400">{{ t('results.card.priceSinceAdded') }}</span>
        <span class="font-semibold" :class="deltaTone">{{ priceDelta < 0 ? '-' : '+' }}{{ formattedDelta }}</span>
      </div>
    </CardHeader>

    <CardContent class="px-4 pb-3 pt-1 flex-grow">
      <!-- Product Facts -->
      <div class="rounded-xl bg-slate-50/60 border border-slate-100/70 p-2.5 mb-2">
        <div class="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px] text-slate-600">
          <span class="flex items-center gap-1.5 min-w-0">
            <CalendarDays class="w-3.5 h-3.5 shrink-0 text-slate-400" />
            <span class="min-w-0 truncate text-slate-400">{{ t('results.card.publishTime') }}</span>
            <span class="shrink-0 font-semibold">{{ publishTime || '—' }}</span>
          </span>
          <span class="flex items-center gap-1.5 min-w-0">
            <MapPin class="w-3.5 h-3.5 shrink-0 text-slate-400" />
            <span class="shrink-0 text-slate-400">{{ t('results.card.shipsFrom') }}</span>
            <span class="truncate font-semibold">{{ hasValue(shipRegion) ? shipRegion : '—' }}</span>
          </span>
          <span class="flex items-center gap-1.5 min-w-0">
            <Eye class="w-3.5 h-3.5 shrink-0 text-slate-400" />
            <span class="shrink-0 text-slate-400">{{ t('results.card.views') }}</span>
            <span class="truncate font-semibold">{{ hasValue(viewCount) ? viewCount : '—' }}</span>
          </span>
          <span class="flex items-center gap-1.5 min-w-0">
            <Heart class="w-3.5 h-3.5 shrink-0 text-rose-400" />
            <span class="shrink-0 text-slate-400">{{ t('results.card.wanted') }}</span>
            <span class="truncate font-semibold">{{ hasValue(wantCount) ? wantCount : '—' }}</span>
          </span>
        </div>
        <div v-if="productTags.length" class="mt-1.5 flex flex-wrap gap-1">
          <span
            v-for="tag in productTags"
            :key="tag"
            class="inline-flex items-center gap-1 rounded-md border border-slate-200/70 bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-600"
          >
            <Tag class="w-3 h-3 text-slate-400" />{{ tag }}
          </span>
        </div>
      </div>

      <!-- AI Insight Section -->
      <div class="rounded-xl p-2.5 border border-slate-100" :class="recommendationStatus.bg">
        <div class="flex items-center justify-between mb-1.5">
          <div class="flex items-center gap-2">
            <component :is="recommendationStatus.icon" class="w-4 h-4" :class="recommendationStatus.text" />
            <span class="text-sm font-bold" :class="recommendationStatus.text">{{ recommendationStatus.label }}</span>
            <span
              v-if="ai?.error"
              class="rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-bold text-rose-600"
              :title="ai.error"
            >{{ t('results.card.analysisFailed') }}</span>
            <span
              v-else-if="!ai?.reason"
              class="rounded bg-slate-200/70 px-1.5 py-0.5 text-[10px] font-bold text-slate-600"
            >{{ t('results.card.pendingAnalysis') }}</span>
          </div>
          <div class="flex items-center gap-1">
             <span class="text-[10px] font-medium uppercase tracking-wider text-slate-400">{{ t('results.card.aiMatch') }}</span>
             <span class="text-sm font-black" :class="recommendationStatus.text">{{ hasMatchScore ? `${matchScore}%` : '—' }}</span>
          </div>
        </div>
        
        <div class="w-full h-1.5 bg-white/50 rounded-full overflow-hidden mb-2">
          <div 
            class="h-full transition-all duration-1000 ease-out rounded-full" 
            :class="recommendationStatus.color"
            :style="{ width: hasMatchScore ? `${matchScore}%` : '0%' }"
          ></div>
        </div>

        <p class="text-xs leading-relaxed text-slate-600" :class="{ 'line-clamp-2': !expanded }">
           {{ ai?.reason || t('results.card.analyzing') }}
        </p>
        
        <button
          type="button"
          v-if="ai?.reason && ai.reason.length > 50"
          @click="expanded = !expanded" 
          class="mt-1 text-[10px] font-bold uppercase text-primary/70 hover:text-primary transition-colors flex items-center gap-1"
        >
          {{ expanded ? t('results.card.collapse') : t('results.card.expand') }}
          <Info class="w-3 h-3" />
        </button>
      </div>

      <!-- Price Stats Grid -->
      <div v-if="priceInsight?.observation_count" class="mt-2.5 grid grid-cols-2 gap-2">
        <div class="bg-slate-50/50 p-2 rounded-xl border border-slate-100/50 group/stat">
          <div class="flex items-center gap-1.5 text-[10px] font-medium text-slate-400 mb-0.5">
            <TrendingUp class="w-3 h-3" /> {{ t('results.card.marketAvg') }}
          </div>
          <div class="text-sm font-bold text-slate-700">
            {{ priceInsight.market_avg_price ? `¥${priceInsight.market_avg_price}` : '—' }}
          </div>
        </div>
        <div class="bg-slate-50/50 p-2 rounded-xl border border-slate-100/50">
          <div class="flex items-center gap-1.5 text-[10px] font-medium text-slate-400 mb-0.5">
            <TrendingDown class="w-3 h-3" /> {{ t('results.card.ownLow') }}
          </div>
          <div class="text-sm font-bold text-slate-700">
            {{ priceInsight.min_price ? `¥${priceInsight.min_price}` : '—' }}
          </div>
        </div>
      </div>
      <!-- Seller Reputation -->
      <div v-if="sellerBadges.length" class="mt-2.5 flex flex-wrap gap-1">
        <span
          v-for="badge in sellerBadges"
          :key="badge.label"
          :title="`${badge.label}: ${badge.value}`"
          class="inline-flex max-w-full items-baseline gap-1 rounded-full border border-slate-100 bg-white/70 px-2 py-0.5 text-[10px]"
        >
          <span class="shrink-0 text-slate-400">{{ badge.label }}</span>
          <span class="truncate font-semibold" :class="badge.tone">{{ badge.value }}</span>
        </span>
      </div>
    </CardContent>

    <CardFooter class="px-4 py-2 bg-slate-50/30 border-t border-slate-100/60 flex items-center justify-between text-[10px]">
      <div class="flex items-center gap-3 text-slate-400">
        <div class="flex items-center gap-1">
          <User class="w-3 h-3" />
          <span class="truncate max-w-[60px]">{{ seller.seller_nickname || info.seller_nickname || t('results.card.anonymous') }}</span>
        </div>
        <div class="flex items-center gap-1">
          <Clock class="w-3 h-3" />
          <span>{{ crawlTime }}</span>
        </div>
      </div>
      <a :href="info.link" target="_blank" rel="noopener noreferrer" class="flex items-center gap-1 text-primary font-bold hover:gap-1.5 transition-all">
        {{ t('results.card.detail') }} <ExternalLink class="w-3 h-3" />
      </a>
    </CardFooter>
  </Card>
</template>
