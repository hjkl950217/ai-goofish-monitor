<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { toast } from '@/components/ui/toast'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useReanalyze } from '@/composables/useReanalyze'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Loader2, Sparkles, Trash2 } from 'lucide-vue-next'

interface FileOption {
  value: string
  label: string
  taskName?: string
}

interface Props {
  files: string[]
  fileOptions?: FileOption[]
  selectedFile: string | null
  aiRecommendedOnly: boolean
  keywordRecommendedOnly: boolean
  includeHidden: boolean
  sortBy: 'crawl_time' | 'publish_time' | 'price' | 'keyword_hit_count' | 'score'
  sortOrder: 'asc' | 'desc'
  isLoading: boolean
  isReady: boolean
  newCount?: number
}

const props = defineProps<Props>()
const { t } = useI18n()

const options = computed(() => {
  if (!props.isReady) {
    return []
  }
  if (props.fileOptions && props.fileOptions.length > 0) {
    return props.fileOptions
  }
  return props.files.map((file) => ({ value: file, label: file }))
})

const selectedLabel = computed(() => {
  if (!props.isReady) return t('results.filters.loadingTaskNames')
  if (options.value.length === 0) return t('results.filters.noResults')
  if (!props.selectedFile) return t('results.filters.chooseResult')
  const match = options.value.find((option) => option.value === props.selectedFile)
  return match ? match.label : t('results.filters.taskNameLabel', { task: t('common.unnamed') })
})

const labelClass = computed(() => {
  const classes = ['transition-opacity', 'duration-200']
  if (!props.isReady || !props.selectedFile || options.value.length === 0) {
    classes.push('text-muted-foreground')
  }
  classes.push(props.isReady ? 'opacity-100' : 'opacity-70')
  return classes.join(' ')
})

const isSelectDisabled = computed(() => !props.isReady || options.value.length === 0)

const emit = defineEmits<{
  (e: 'update:selectedFile', value: string): void
  (e: 'update:aiRecommendedOnly', value: boolean): void
  (e: 'update:keywordRecommendedOnly', value: boolean): void
  (e: 'update:includeHidden', value: boolean): void
  (e: 'update:sortBy', value: 'crawl_time' | 'publish_time' | 'price' | 'keyword_hit_count' | 'score'): void
  (e: 'update:sortOrder', value: 'asc' | 'desc'): void
  (e: 'refresh'): void
  (e: 'export'): void
  (e: 'delete'): void
  (e: 'manage-blacklist'): void
  (e: 'reanalyze-finished'): void
  (e: 'mark-all-seen'): void
}>()

const reanalyze = useReanalyze()
const reanalyzeState = computed(() => reanalyze.status.value)
const imageCacheState = computed(() => reanalyze.imageCache.value)
const isClearingImagesState = computed(() => reanalyze.isClearingImages.value)
const isReanalyzeOpen = ref(false)
const reanalyzeScope = ref<'pending' | 'all'>('pending')
const reanalyzeLimit = ref(20)
const reanalyzeWorkers = ref(3)
const isStarting = ref(false)
let unsubscribe: (() => void) | null = null

onMounted(() => {
  unsubscribe = reanalyze.subscribe((s) => {
    if (!s.running && isReanalyzeOpen.value) {
      // 完成后自动刷新结果列表
      emit('reanalyze-finished')
    }
  })
})
onUnmounted(() => {
  unsubscribe?.()
})

async function handleClearImages() {
  try {
    const result = await reanalyze.clearImageCache()
    toast({
      title: t('results.reanalyze.imagesCleared', { size: result.freed_size }),
    })
  } catch (e) {
    toast({
      title: t('results.reanalyze.imagesClearFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}

async function handleStartReanalyze() {
  isStarting.value = true
  try {
    await reanalyze.start({
      scope: reanalyzeScope.value,
      limit: reanalyzeLimit.value > 0 ? reanalyzeLimit.value : null,
      workers: reanalyzeWorkers.value,
    })
    toast({ title: t('results.reanalyze.started') })
  } catch (e) {
    toast({
      title: t('results.reanalyze.startFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isStarting.value = false
  }
}

async function handleCancelReanalyze() {
  try {
    await reanalyze.cancel()
    toast({ title: t('results.reanalyze.cancelling') })
  } catch (e) {
    toast({
      title: t('results.reanalyze.cancelFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}

function handleToggleAiRecommended(value: boolean) {
  emit('update:aiRecommendedOnly', value)
  if (value) {
    emit('update:keywordRecommendedOnly', false)
  }
}

function handleToggleKeywordRecommended(value: boolean) {
  emit('update:keywordRecommendedOnly', value)
  if (value) {
    emit('update:aiRecommendedOnly', false)
  }
}
</script>

<template>
  <div class="app-surface mb-6 p-4 sm:p-5">
    <div class="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
      <div class="space-y-2">
        <Label class="text-xs font-semibold text-slate-500">{{ t('results.title') }}</Label>
        <Select
          :model-value="props.selectedFile || undefined"
          @update:model-value="(value) => emit('update:selectedFile', value as string)"
        >
          <SelectTrigger class="w-full" :disabled="isSelectDisabled">
            <span :class="labelClass">
              {{ selectedLabel }}
            </span>
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="option in options" :key="option.value" :value="option.value">
              {{ option.label }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div class="space-y-2">
        <Label class="text-xs font-semibold text-slate-500">{{ t('results.filters.sortByCrawlTime') }}</Label>
        <Select
          :model-value="props.sortBy"
          @update:model-value="(value) => emit('update:sortBy', value as any)"
        >
          <SelectTrigger class="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="crawl_time">{{ t('results.filters.sortByCrawlTime') }}</SelectItem>
            <SelectItem value="publish_time">{{ t('results.filters.sortByPublishTime') }}</SelectItem>
            <SelectItem value="price">{{ t('results.filters.sortByPrice') }}</SelectItem>
            <SelectItem value="keyword_hit_count">{{ t('results.filters.sortByKeywordHits') }}</SelectItem>
            <SelectItem value="score">{{ t('results.filters.sortByScore') }}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div class="space-y-2">
        <Label class="text-xs font-semibold text-slate-500">{{ t('results.filters.asc') }} / {{ t('results.filters.desc') }}</Label>
        <Select
          :model-value="props.sortOrder"
          @update:model-value="(value) => emit('update:sortOrder', value as any)"
        >
          <SelectTrigger class="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="desc">{{ t('results.filters.desc') }}</SelectItem>
            <SelectItem value="asc">{{ t('results.filters.asc') }}</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>

    <div class="mt-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div class="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <div class="flex items-center space-x-2">
          <Checkbox
            id="ai-recommended-only"
            :model-value="props.aiRecommendedOnly"
            @update:modelValue="(value) => handleToggleAiRecommended(value === true)"
          />
          <Label for="ai-recommended-only" class="cursor-pointer">{{ t('results.filters.aiOnly') }}</Label>
        </div>

        <div class="flex items-center space-x-2">
          <Checkbox
            id="keyword-recommended-only"
            :model-value="props.keywordRecommendedOnly"
            @update:modelValue="(value) => handleToggleKeywordRecommended(value === true)"
          />
          <Label for="keyword-recommended-only" class="cursor-pointer">{{ t('results.filters.keywordOnly') }}</Label>
        </div>

        <div class="flex items-center space-x-2">
          <Checkbox
            id="include-hidden"
            :model-value="props.includeHidden"
            @update:modelValue="(value) => emit('update:includeHidden', value === true)"
          />
          <Label for="include-hidden" class="cursor-pointer">{{ t('results.filters.includeHidden') }}</Label>
        </div>

        <div v-if="props.newCount" class="flex items-center gap-2">
          <span class="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-700">
            {{ t('results.filters.newCount', { count: props.newCount }) }}
          </span>
          <Button variant="ghost" size="sm" class="h-7 text-xs" @click="emit('mark-all-seen')">
            {{ t('results.filters.markAllSeen') }}
          </Button>
        </div>
      </div>

      <div class="flex flex-wrap gap-2 lg:justify-end">
        <Button @click="emit('refresh')" :disabled="props.isLoading">
          {{ t('common.refresh') }}
        </Button>

        <Button
          variant="outline"
          @click="isReanalyzeOpen = true; reanalyze.fetchImageCache()"
          :disabled="reanalyzeState.running"
        >
          <Loader2 v-if="reanalyzeState.running" class="mr-1 h-4 w-4 animate-spin" />
          <Sparkles v-else class="mr-1 h-4 w-4" />
          {{ reanalyzeState.running
            ? t('results.reanalyze.running', { done: reanalyzeState.done, total: reanalyzeState.total })
            : t('results.reanalyze.action') }}
        </Button>

        <Button
          variant="outline"
          @click="emit('manage-blacklist')"
          :disabled="props.isLoading || !props.selectedFile"
        >
          {{ t('results.filters.manageBlacklist') }}
        </Button>

        <Button
          variant="outline"
          @click="emit('export')"
          :disabled="props.isLoading || !props.selectedFile"
        >
          {{ t('results.filters.exportCsv') }}
        </Button>

        <Button
          variant="destructive"
          @click="emit('delete')"
          :disabled="props.isLoading || !props.selectedFile"
        >
          {{ t('results.filters.deleteResult') }}
        </Button>
      </div>
    </div>
  </div>

    <Dialog v-model:open="isReanalyzeOpen">
      <DialogContent class="max-w-lg">
        <DialogHeader>
          <DialogTitle>{{ t('results.reanalyze.title') }}</DialogTitle>
          <DialogDescription>{{ t('results.reanalyze.description') }}</DialogDescription>
        </DialogHeader>

        <div class="space-y-4">
          <div v-if="reanalyzeState.running" class="rounded-xl border border-emerald-100 bg-emerald-50/60 p-3 text-sm">
            <div class="flex items-center justify-between">
              <span class="font-semibold text-emerald-700">
                {{ reanalyzeState.done }} / {{ reanalyzeState.total }}
              </span>
              <span class="text-xs text-emerald-600">
                {{ t('results.reanalyze.progress', { ok: reanalyzeState.ok, failed: reanalyzeState.failed }) }}
              </span>
            </div>
            <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white">
              <div
                class="h-full rounded-full bg-emerald-500 transition-all"
                :style="{ width: reanalyzeState.total ? `${(reanalyzeState.done / reanalyzeState.total) * 100}%` : '0%' }"
              ></div>
            </div>
            <p v-if="reanalyzeState.recent.length" class="mt-2 max-h-24 overflow-auto text-xs text-emerald-700/80">
              {{ reanalyzeState.recent.slice(-6).join('  ·  ') }}
            </p>
          </div>

          <div v-else-if="reanalyzeState.message" class="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
            {{ reanalyzeState.message }}
          </div>

          <div class="space-y-2">
            <Label class="text-xs font-semibold text-slate-500">{{ t('results.reanalyze.scopeLabel') }}</Label>
            <div class="flex flex-col gap-2 sm:flex-row">
              <label class="flex flex-1 cursor-pointer items-start gap-2 rounded-lg border p-2.5 text-sm"
                     :class="reanalyzeScope === 'pending' ? 'border-emerald-300 bg-emerald-50/60' : 'border-slate-200'">
                <input v-model="reanalyzeScope" type="radio" value="pending" class="mt-0.5" :disabled="reanalyzeState.running" />
                <span>
                  <span class="block font-medium">{{ t('results.reanalyze.scopePending') }}</span>
                  <span class="block text-xs text-slate-500">{{ t('results.reanalyze.scopePendingHint') }}</span>
                </span>
              </label>
              <label class="flex flex-1 cursor-pointer items-start gap-2 rounded-lg border p-2.5 text-sm"
                     :class="reanalyzeScope === 'all' ? 'border-emerald-300 bg-emerald-50/60' : 'border-slate-200'">
                <input v-model="reanalyzeScope" type="radio" value="all" class="mt-0.5" :disabled="reanalyzeState.running" />
                <span>
                  <span class="block font-medium">{{ t('results.reanalyze.scopeAll') }}</span>
                  <span class="block text-xs text-slate-500">{{ t('results.reanalyze.scopeAllHint') }}</span>
                </span>
              </label>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1.5">
              <Label class="text-xs font-semibold text-slate-500">{{ t('results.reanalyze.limit') }}</Label>
              <Input v-model.number="reanalyzeLimit" type="number" min="0" :disabled="reanalyzeState.running" />
            </div>
            <div class="space-y-1.5">
              <Label class="text-xs font-semibold text-slate-500">{{ t('results.reanalyze.workers') }}</Label>
              <Input v-model.number="reanalyzeWorkers" type="number" min="1" max="8" :disabled="reanalyzeState.running" />
            </div>
          </div>

          <div class="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2">
            <div class="min-w-0">
              <p class="text-xs font-semibold text-slate-600">{{ t('results.reanalyze.imageCache') }}</p>
              <p class="truncate text-[11px] text-slate-400">
                <template v-if="imageCacheState">
                  {{ imageCacheState.total_size }} · {{ imageCacheState.file_count }} {{ t('results.reanalyze.imageUnit') }}
                </template>
                <template v-else>{{ t('results.reanalyze.loading') }}</template>
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              class="ml-3 shrink-0 text-rose-600 hover:bg-rose-50"
              :disabled="isClearingImagesState || reanalyzeState.running || !imageCacheState?.file_count"
              @click="handleClearImages"
            >
              <Loader2 v-if="isClearingImagesState" class="mr-1 h-3.5 w-3.5 animate-spin" />
              <Trash2 v-else class="mr-1 h-3.5 w-3.5" />
              {{ t('results.reanalyze.clearImages') }}
            </Button>
          </div>

          <p class="text-xs text-slate-400">{{ t('results.reanalyze.note') }}</p>
        </div>

        <DialogFooter>
          <Button
            v-if="reanalyzeState.running"
            variant="outline"
            @click="handleCancelReanalyze"
          >
            {{ t('results.reanalyze.cancel') }}
          </Button>
          <Button
            v-else
            :disabled="isStarting"
            @click="handleStartReanalyze"
          >
            <Loader2 v-if="isStarting" class="mr-1 h-4 w-4 animate-spin" />
            {{ t('results.reanalyze.start') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
</template>
