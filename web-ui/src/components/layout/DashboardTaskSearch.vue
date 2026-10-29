<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { FileText, LoaderCircle, Search, Sparkles } from 'lucide-vue-next'
import Badge from '@/components/ui/badge/Badge.vue'
import * as resultsApi from '@/api/results'
import * as taskApi from '@/api/tasks'
import { useWebSocket } from '@/composables/useWebSocket'
import type { Task } from '@/types/task.d.ts'

const MAX_RESULTS = 6

interface ResultOption {
  file: string
  taskName: string
  keyword: string
}

const router = useRouter()
const { t } = useI18n()
const { on } = useWebSocket()
const rootRef = ref<HTMLElement | null>(null)
const query = ref('')
const options = ref<ResultOption[]>([])
const isLoading = ref(false)
const error = ref('')
const isOpen = ref(false)
const highlightedIndex = ref(0)

const normalizedQuery = computed(() => query.value.trim().toLowerCase())

const visibleOptions = computed(() => {
  const list = normalizedQuery.value
    ? options.value.filter((option) => matchesOption(option, normalizedQuery.value))
    : options.value
  return list.slice(0, MAX_RESULTS)
})

const panelTitle = computed(() => (
  normalizedQuery.value ? t('tasks.search.matchingTasks') : t('tasks.search.recentTasks')
))

const shouldShowPanel = computed(() => (
  isOpen.value && (
    isLoading.value ||
    Boolean(error.value) ||
    visibleOptions.value.length > 0 ||
    Boolean(normalizedQuery.value)
  )
))

function normalizeKeyword(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, '_')
}

function keywordFromFile(file: string) {
  return file.replace(/_full_data\.jsonl$/i, '').toLowerCase()
}

function matchesOption(option: ResultOption, value: string) {
  return [option.taskName, option.file, option.keyword]
    .some((field) => field.toLowerCase().includes(value))
}

async function fetchOptions() {
  isLoading.value = true
  error.value = ''
  try {
    const [files, tasks] = await Promise.all([
      resultsApi.getResultFiles(),
      taskApi.getAllTasks(),
    ])
    const nameByKeyword: Record<string, string> = {}
    tasks.forEach((task: Task) => {
      if (task.keyword) nameByKeyword[normalizeKeyword(task.keyword)] = task.task_name
    })
    options.value = files.map((file) => {
      const keyword = keywordFromFile(file)
      return { file, keyword, taskName: nameByKeyword[keyword] || file }
    })
  } catch (e) {
    error.value = e instanceof Error ? e.message : t('tasks.search.loadFailed')
  } finally {
    isLoading.value = false
  }
}

function ensureLoaded() {
  if (options.value.length || isLoading.value) return
  fetchOptions()
}

function openPanel() {
  ensureLoaded()
  isOpen.value = true
}

function closePanel() {
  isOpen.value = false
  highlightedIndex.value = 0
}

function selectOption(option: ResultOption) {
  closePanel()
  query.value = ''
  router.push({ name: 'Results', query: { file: option.file } })
}

function moveHighlight(direction: 1 | -1) {
  if (!visibleOptions.value.length) return
  const lastIndex = visibleOptions.value.length - 1
  const nextIndex = highlightedIndex.value + direction
  if (nextIndex < 0) {
    highlightedIndex.value = lastIndex
    return
  }
  if (nextIndex > lastIndex) {
    highlightedIndex.value = 0
    return
  }
  highlightedIndex.value = nextIndex
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    closePanel()
    return
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    openPanel()
    moveHighlight(1)
    return
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault()
    openPanel()
    moveHighlight(-1)
    return
  }
  if (event.key === 'Enter' && visibleOptions.value.length) {
    event.preventDefault()
    const selected = visibleOptions.value[highlightedIndex.value]
    if (selected) {
      selectOption(selected)
    }
  }
}

function handlePointerDown(event: MouseEvent) {
  if (!rootRef.value) return
  const target = event.target
  if (target instanceof Node && !rootRef.value.contains(target)) {
    closePanel()
  }
}

watch(normalizedQuery, () => {
  highlightedIndex.value = 0
  if (!query.value.trim()) return
  openPanel()
})

on('results_updated', fetchOptions)
on('tasks_updated', fetchOptions)

onMounted(() => {
  document.addEventListener('mousedown', handlePointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handlePointerDown)
})
</script>

<template>
  <div ref="rootRef" class="relative w-full">
    <Search class="absolute left-3 top-1/2 z-10 -translate-y-1/2 w-4 h-4 text-slate-400 transition-colors" />
    <input
      v-model="query"
      type="text"
      :placeholder="t('tasks.search.placeholder')"
      class="w-full h-10 rounded-xl border border-slate-200/60 bg-slate-100/60 pl-10 pr-16 text-sm text-slate-700 transition-all outline-none focus:border-primary/40 focus:bg-white focus:ring-2 focus:ring-primary/15"
      @focus="openPanel"
      @keydown="handleKeydown"
    />
    <kbd class="absolute right-3 top-1/2 -translate-y-1/2 rounded border border-slate-300 bg-white px-1.5 py-0.5 text-[10px] text-slate-400 shadow-sm">
      ESC
    </kbd>

    <transition name="search-panel">
      <div
        v-if="shouldShowPanel"
        class="absolute inset-x-0 top-[calc(100%+0.75rem)] overflow-hidden rounded-[28px] border border-slate-200/80 bg-white/95 shadow-[0_28px_70px_rgba(15,23,42,0.16)] backdrop-blur-xl"
      >
        <div class="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <div>
            <p class="text-xs font-black uppercase tracking-[0.24em] text-slate-400">{{ panelTitle }}</p>
            <p class="mt-1 text-xs text-slate-500">
              {{ normalizedQuery ? t('tasks.search.resultCount', { count: visibleOptions.length }) : t('tasks.search.enterHint') }}
            </p>
          </div>
          <Badge variant="outline" class="border-slate-200 bg-slate-50 text-[10px] text-slate-500">
            {{ t('routes.results') }}
          </Badge>
        </div>

        <div v-if="isLoading" class="flex items-center gap-2 px-4 py-6 text-sm text-slate-500">
          <LoaderCircle class="h-4 w-4 animate-spin text-primary" />
          {{ t('tasks.search.loading') }}
        </div>

        <div v-else-if="error" class="px-4 py-6 text-sm text-rose-600">
          {{ error }}
        </div>

        <div v-else-if="visibleOptions.length === 0" class="px-4 py-6">
          <p class="text-sm font-semibold text-slate-700">{{ t('tasks.search.emptyTitle') }}</p>
          <p class="mt-1 text-xs text-slate-500">{{ t('tasks.search.emptyDescription') }}</p>
        </div>

        <div v-else class="divide-y divide-slate-100">
          <button
            v-for="(option, index) in visibleOptions"
            :key="option.file"
            class="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors"
            :class="index === highlightedIndex ? 'bg-primary/10 text-slate-900' : 'hover:bg-slate-50 text-slate-800'"
            @mouseenter="highlightedIndex = index"
            @click="selectOption(option)"
          >
            <FileText
              class="mt-0.5 h-4 w-4 shrink-0"
              :class="index === highlightedIndex ? 'text-primary' : 'text-slate-400'"
            />
            <div class="min-w-0 flex-1">
              <div class="flex items-center justify-between gap-3">
                <p class="truncate text-sm font-bold">{{ option.taskName }}</p>
                <Badge
                  variant="outline"
                  class="shrink-0 text-[10px]"
                  :class="index === highlightedIndex ? 'border-primary/30 bg-primary/10 text-primary' : 'border-slate-200 text-slate-500'"
                >
                  {{ t('tasks.search.openResult') }}
                </Badge>
              </div>
              <p
                class="mt-1 truncate font-mono text-xs"
                :class="index === highlightedIndex ? 'text-slate-600' : 'text-slate-500'"
              >
                {{ option.file }}
              </p>
              <p
                v-if="option.keyword"
                class="mt-1 truncate text-xs"
                :class="index === highlightedIndex ? 'text-slate-500' : 'text-slate-400'"
              >
                {{ option.keyword }}
              </p>
            </div>
          </button>
        </div>

        <div class="flex items-center justify-between border-t border-slate-100 bg-slate-50/80 px-4 py-3 text-[11px] text-slate-500">
          <div class="flex items-center gap-2">
            <Sparkles class="h-3.5 w-3.5 text-primary" />
            {{ t('tasks.search.footerHint') }}
          </div>
          <div class="hidden items-center gap-2 md:flex">
            <span>{{ t('tasks.search.keyboardUpDown') }}</span>
            <span>{{ t('tasks.search.keyboardEnter') }}</span>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.search-panel-enter-active,
.search-panel-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.search-panel-enter-from,
.search-panel-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
