<script setup lang="ts">
import type { ResultItem } from '@/types/result.d.ts'
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import ResultCard from './ResultCard.vue'

interface Props {
  results: ResultItem[]
  isLoading: boolean
}

const props = defineProps<Props>()
const { t } = useI18n()

const emit = defineEmits<{
  (e: 'toggle-block', item: ResultItem): void
  (e: 'refreshed'): void
}>()
const skeletonItems = Array.from({ length: 8 }, (_, index) => index)

// 一次只挂 15 张卡片，滚到底部附近再挂下一批；500 条数据也不会一口气建 6 万多节点
const PAGE_SIZE = 15
const visibleCount = ref(PAGE_SIZE)
const visibleResults = computed(() => props.results.slice(0, visibleCount.value))
const hasMore = computed(() => visibleCount.value < props.results.length)
const sentinel = ref<HTMLElement | null>(null)

// 换筛选、排序或换文件后回到第一批；只屏蔽/取消屏蔽某条时列表头没变，保留已展开的数量
watch(() => [props.results.length, props.results[0]?.item_info.item_id], () => {
  visibleCount.value = PAGE_SIZE
})

let observer: IntersectionObserver | undefined
watch(sentinel, (el) => {
  observer?.disconnect()
  if (!el) return
  // 一批 15 张至少有 800px 高，触发一次就会离开观察区，不用怕连续触发
  observer = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) {
      visibleCount.value += PAGE_SIZE
    }
  }, { rootMargin: '800px 0px' })
  observer.observe(el)
}, { flush: 'post' })
onUnmounted(() => observer?.disconnect())

// 请求很快时不要整片变淡，避免刷新像闪一下；超过 200ms 才提示加载中
const isBusy = ref(false)
let busyTimer: ReturnType<typeof setTimeout> | undefined
watch(() => props.isLoading, (loading) => {
  clearTimeout(busyTimer)
  if (!loading) {
    isBusy.value = false
    return
  }
  busyTimer = setTimeout(() => {
    isBusy.value = true
  }, 200)
}, { immediate: true })
onUnmounted(() => clearTimeout(busyTimer))
</script>

<template>
  <!-- 已有数据时刷新只降透明度，不换成骨架，避免页面高度突变导致滚动位置跳动 -->
  <div
    :aria-busy="isBusy"
    class="transition-opacity duration-200"
    :class="{ 'opacity-50': isBusy && results.length > 0 }"
  >
    <div
      v-if="isLoading && results.length === 0"
      class="grid gap-4 grid-cols-[repeat(auto-fill,minmax(15rem,1fr))]"
      aria-live="polite"
    >
      <div
        v-for="item in skeletonItems"
        :key="item"
        class="app-surface overflow-hidden"
      >
        <div class="aspect-[4/3] animate-pulse bg-slate-200/70"></div>
        <div class="space-y-3 p-4">
          <div class="h-5 w-4/5 animate-pulse rounded bg-slate-200/70"></div>
          <div class="h-7 w-1/3 animate-pulse rounded bg-slate-200/70"></div>
          <div class="rounded-xl border border-slate-100 bg-slate-50/80 p-3">
            <div class="h-4 w-1/2 animate-pulse rounded bg-slate-200/70"></div>
            <div class="mt-3 h-2 w-full animate-pulse rounded bg-slate-200/70"></div>
            <div class="mt-3 h-4 w-full animate-pulse rounded bg-slate-200/70"></div>
            <div class="mt-2 h-4 w-3/4 animate-pulse rounded bg-slate-200/70"></div>
          </div>
        </div>
      </div>
    </div>
    <div v-else-if="results.length === 0" class="app-surface text-center py-12 text-gray-500">
      {{ t('results.grid.empty') }}
    </div>
    <div v-else class="grid gap-4 grid-cols-[repeat(auto-fill,minmax(15rem,1fr))]">
      <div v-for="item in visibleResults" :key="item.item_info.item_id" class="h-full">
        <ResultCard
          :item="item"
          @toggle-block="emit('toggle-block', $event)"
          @refreshed="emit('refreshed')"
        />
      </div>
      <div v-if="hasMore" ref="sentinel" class="col-span-full h-px" aria-hidden="true"></div>
    </div>
  </div>
</template>
