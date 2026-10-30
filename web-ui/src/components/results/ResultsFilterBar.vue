<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
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
  isLoading: boolean
  isReady: boolean
  minPrice?: number
  maxPrice?: number
  publishedDays?: number
  shipRegion?: string
  analysisStatus?: 'analyzed' | 'failed' | 'pending'
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
  (e: 'refresh'): void
  (e: 'export'): void
  (e: 'delete'): void
  (e: 'manage-blacklist'): void
  (e: 'reanalyze-finished'): void
  (e: 'update:minPrice', value: number | undefined): void
  (e: 'update:maxPrice', value: number | undefined): void
  (e: 'update:publishedDays', value: number | undefined): void
  (e: 'update:shipRegion', value: string): void
  (e: 'update:analysisStatus', value: 'analyzed' | 'failed' | 'pending' | undefined): void
}>()

// 接口快时不要把按钮闪成禁用态，加载超过 200ms 才置灰
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

function toNumberOrUndefined(value: string | number): number | undefined {
  const text = String(value ?? '').trim()
  if (!text) return undefined
  const parsed = Number(text)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined
}

function clearAdvanced() {
  emit('update:minPrice', undefined)
  emit('update:maxPrice', undefined)
  emit('update:publishedDays', undefined)
  emit('update:shipRegion', '')
  emit('update:analysisStatus', undefined)
}

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
</script>

<template>
  <div class="app-surface mb-3 p-4 sm:p-5">
    <!-- 结果集下拉只在窄屏保留，宽屏由左侧任务列表切换 -->
    <div class="mb-4 space-y-2 lg:hidden">
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

    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div class="space-y-1.5">
        <Label class="text-xs font-semibold text-slate-500">
          {{ t('results.filters.minPrice') }} / {{ t('results.filters.maxPrice') }}
        </Label>
        <div class="flex items-center gap-2">
          <Input
            :model-value="props.minPrice ?? ''"
            type="number"
            min="0"
            :aria-label="t('results.filters.minPrice')"
            :placeholder="t('results.filters.minPrice')"
            @update:model-value="(v) => emit('update:minPrice', toNumberOrUndefined(v))"
          />
          <span class="text-slate-300">-</span>
          <Input
            :model-value="props.maxPrice ?? ''"
            type="number"
            min="0"
            :aria-label="t('results.filters.maxPrice')"
            :placeholder="t('results.filters.maxPrice')"
            @update:model-value="(v) => emit('update:maxPrice', toNumberOrUndefined(v))"
          />
        </div>
      </div>

      <div class="space-y-1.5">
        <Label class="text-xs font-semibold text-slate-500">{{ t('results.filters.publishedWithin') }}</Label>
        <Select
          :model-value="props.publishedDays ? String(props.publishedDays) : 'any'"
          @update:model-value="(v) => emit('update:publishedDays', v === 'any' ? undefined : Number(v))"
        >
          <SelectTrigger class="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="any">{{ t('results.filters.publishedAny') }}</SelectItem>
            <SelectItem value="3">{{ t('results.filters.publishedDays', { days: 3 }) }}</SelectItem>
            <SelectItem value="7">{{ t('results.filters.publishedDays', { days: 7 }) }}</SelectItem>
            <SelectItem value="30">{{ t('results.filters.publishedDays', { days: 30 }) }}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div class="space-y-1.5">
        <Label class="text-xs font-semibold text-slate-500">{{ t('results.filters.shipRegion') }}</Label>
        <Input
          :model-value="props.shipRegion ?? ''"
          :placeholder="t('results.filters.shipRegionPlaceholder')"
          @update:model-value="(v) => emit('update:shipRegion', String(v ?? ''))"
        />
      </div>

      <div class="space-y-1.5">
        <Label class="text-xs font-semibold text-slate-500">{{ t('results.filters.analysisStatus') }}</Label>
        <Select
          :model-value="props.analysisStatus ?? 'any'"
          @update:model-value="(v) => emit('update:analysisStatus', v === 'any' ? undefined : (v as 'analyzed' | 'failed' | 'pending'))"
        >
          <SelectTrigger class="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="any">{{ t('results.filters.analysisAny') }}</SelectItem>
            <SelectItem value="analyzed">{{ t('results.filters.analysisAnalyzed') }}</SelectItem>
            <SelectItem value="failed">{{ t('results.filters.analysisFailed') }}</SelectItem>
            <SelectItem value="pending">{{ t('results.filters.analysisPending') }}</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>

    <div class="mt-3 flex flex-wrap items-center justify-between gap-2">
      <Button variant="ghost" size="sm" class="h-7 text-xs text-slate-500" @click="clearAdvanced">
        {{ t('results.filters.clearAdvanced') }}
      </Button>

      <div class="flex flex-wrap gap-2 justify-end">
        <Button @click="emit('refresh')" :disabled="isBusy">
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
          :disabled="isBusy || !props.selectedFile"
        >
          {{ t('results.filters.manageBlacklist') }}
        </Button>

        <Button
          variant="outline"
          @click="emit('export')"
          :disabled="isBusy || !props.selectedFile"
        >
          {{ t('results.filters.exportCsv') }}
        </Button>

        <Button
          variant="destructive"
          @click="emit('delete')"
          :disabled="isBusy || !props.selectedFile"
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
