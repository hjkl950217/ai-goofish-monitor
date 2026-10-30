<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowDown, ArrowUp } from 'lucide-vue-next'

type SortField = 'price' | 'keyword_hit_count' | 'score' | 'publish_time' | 'crawl_time'
type SortOrder = 'asc' | 'desc'
type FilterMode = 'default' | 'ai' | 'hidden' | 'all'

const props = defineProps<{ sortBy: SortField; sortOrder: SortOrder; filterMode: FilterMode }>()
const emit = defineEmits<{
  (e: 'update:sortBy', value: SortField): void
  (e: 'update:sortOrder', value: SortOrder): void
  (e: 'update:filterMode', value: FilterMode): void
}>()

const { t } = useI18n()

const sortItems = computed<{ value: SortField; label: string }[]>(() => [
  { value: 'price', label: t('results.sortRail.price') },
  { value: 'keyword_hit_count', label: t('results.sortRail.hits') },
  { value: 'score', label: t('results.sortRail.score') },
  { value: 'publish_time', label: t('results.sortRail.publish') },
  { value: 'crawl_time', label: t('results.sortRail.crawl') },
])

const filterModes = computed<{ value: FilterMode; label: string }[]>(() => [
  { value: 'default', label: t('results.sortRail.modeDefault') },
  { value: 'ai', label: t('results.sortRail.modeAi') },
  { value: 'hidden', label: t('results.sortRail.modeHidden') },
  { value: 'all', label: t('results.sortRail.modeAll') },
])

// 点未选中的项切换排序字段，点当前项翻转升降序
function select(value: SortField) {
  if (props.sortBy === value) {
    emit('update:sortOrder', props.sortOrder === 'desc' ? 'asc' : 'desc')
    return
  }
  emit('update:sortBy', value)
}
</script>

<template>
  <!-- 页面容器带 animate-fade-in 的 transform，会让 fixed 相对容器定位，必须挂到 body -->
  <Teleport to="body">
    <aside
      class="app-surface fixed right-3 top-1/2 z-30 hidden w-[76px] -translate-y-1/2 flex-col p-1 lg:flex"
      :aria-label="t('results.sortRail.title')"
    >
      <p class="px-1 pb-1 pt-0.5 text-[11px] font-semibold tracking-[0.12em] text-slate-600">
        {{ t('results.sortRail.title') }}
      </p>
      <button
        v-for="item in sortItems"
        :key="item.value"
        type="button"
        class="flex items-center justify-between gap-1 rounded-lg px-1 py-1.5 text-[11px] leading-4 transition-colors"
        :class="sortBy === item.value
          ? 'bg-primary/10 font-semibold text-primary'
          : 'text-slate-500 hover:bg-slate-100'"
        :aria-pressed="sortBy === item.value"
        :title="t('results.sortRail.hint')"
        @click="select(item.value)"
      >
        <span class="truncate">{{ item.label }}</span>
        <component
          :is="sortOrder === 'asc' ? ArrowUp : ArrowDown"
          v-if="sortBy === item.value"
          class="h-2.5 w-2.5 shrink-0"
        />
      </button>

      <div class="my-1 border-t border-slate-100"></div>

      <p class="px-1 pb-1 text-[11px] font-semibold tracking-[0.12em] text-slate-600">
        {{ t('results.sortRail.filterTitle') }}
      </p>
      <button
        v-for="mode in filterModes"
        :key="mode.value"
        type="button"
        class="rounded-lg px-1 py-1 text-left text-[11px] leading-4 transition-colors"
        :class="filterMode === mode.value
          ? 'bg-primary/10 font-semibold text-primary'
          : 'text-slate-500 hover:bg-slate-100'"
        :aria-pressed="filterMode === mode.value"
        @click="emit('update:filterMode', mode.value)"
      >
        {{ mode.label }}
      </button>
    </aside>
  </Teleport>
</template>
