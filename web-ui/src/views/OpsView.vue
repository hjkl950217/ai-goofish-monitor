<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getOpsConfig, saveOpsConfig, listTraces, type TraceDir } from '@/api/ops'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { toast } from '@/components/ui/toast'
import { confirmSave } from '@/lib/confirm'
const { t } = useI18n()

const traceEnabled = ref(false)
const traceDir = ref('/tmp/agm-trace')
const debugCapture = ref('')
const isSaving = ref(false)
const isLoading = ref(false)
const traces = ref<TraceDir[]>([])

// 任务运行选项：任务跑在独立子进程里，每次启动重读 data/.env，保存后下一个任务就生效
const runtime = reactive({
  KEEP_TASK_IMAGES: true,
  REFRESH_TRACKED_ITEMS: true,
  AI_DEBUG_MODE: false,
  ENABLE_THINKING: false,
  ENABLE_RESPONSE_FORMAT: true,
  TASK_FAILURE_THRESHOLD: 3,
  TASK_FAILURE_PAUSE_SECONDS: 86400,
  TASK_LOG_RETENTION_DAYS: 7,
  AI_LOG_RETENTION_DAYS: 1,
  AGM_TRACE_MAX_MB: 200,
})

async function loadConfig() {
  try {
    const cfg = await getOpsConfig()
    const enabled = (cfg.AGM_BROWSER_TRACE || '').toLowerCase()
    traceEnabled.value = ['1', 'true', 'yes', 'on'].includes(enabled)
    traceDir.value = cfg.AGM_TRACE_DIR || '/tmp/agm-trace'
    debugCapture.value = cfg.AGM_DEBUG_CAPTURE || ''
    runtime.KEEP_TASK_IMAGES = !!cfg.KEEP_TASK_IMAGES
    runtime.REFRESH_TRACKED_ITEMS = !!cfg.REFRESH_TRACKED_ITEMS
    runtime.AI_DEBUG_MODE = !!cfg.AI_DEBUG_MODE
    runtime.ENABLE_THINKING = !!cfg.ENABLE_THINKING
    runtime.ENABLE_RESPONSE_FORMAT = !!cfg.ENABLE_RESPONSE_FORMAT
    runtime.TASK_FAILURE_THRESHOLD = Number(cfg.TASK_FAILURE_THRESHOLD ?? 3)
    runtime.TASK_FAILURE_PAUSE_SECONDS = Number(cfg.TASK_FAILURE_PAUSE_SECONDS ?? 86400)
    runtime.TASK_LOG_RETENTION_DAYS = Number(cfg.TASK_LOG_RETENTION_DAYS ?? 7)
    runtime.AI_LOG_RETENTION_DAYS = Number(cfg.AI_LOG_RETENTION_DAYS ?? 1)
    runtime.AGM_TRACE_MAX_MB = Number(cfg.AGM_TRACE_MAX_MB ?? 200)
  } catch (e) {
    toast({ title: t('ops.loadFailed'), description: (e as Error).message, variant: 'destructive' })
  }
}

async function loadTraces() {
  isLoading.value = true
  try {
    traces.value = await listTraces()
  } catch (e) {
    toast({ title: t('ops.traces.loadFailed'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isLoading.value = false
  }
}

async function handleSave() {
  if (!confirmSave()) return
  isSaving.value = true
  try {
    await saveOpsConfig({
      AGM_BROWSER_TRACE: traceEnabled.value ? 'true' : 'false',
      AGM_TRACE_DIR: traceDir.value.trim(),
      AGM_DEBUG_CAPTURE: debugCapture.value.trim(),
      ...runtime,
    })
    toast({ title: t('ops.saved') })
    await Promise.all([loadConfig(), loadTraces()])
  } catch (e) {
    toast({ title: t('ops.saveFailed'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isSaving.value = false
  }
}

function setNumber(
  key:
    | 'TASK_FAILURE_THRESHOLD'
    | 'TASK_FAILURE_PAUSE_SECONDS'
    | 'TASK_LOG_RETENTION_DAYS'
    | 'AI_LOG_RETENTION_DAYS'
    | 'AGM_TRACE_MAX_MB',
  value: string | number,
) {
  const parsed = Number(value)
  if (Number.isFinite(parsed) && parsed >= 0) {
    runtime[key] = Math.floor(parsed)
  }
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

onMounted(() => {
  loadConfig()
  loadTraces()
})
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-800">{{ t('ops.title') }}</h1>
      <p class="text-sm text-gray-500 mt-1">{{ t('ops.description') }}</p>
    </div>

    <Card class="app-surface mb-6 border-none">
      <CardHeader>
        <CardTitle>{{ t('ops.trace.title') }}</CardTitle>
        <CardDescription>{{ t('ops.trace.description') }}</CardDescription>
      </CardHeader>
      <CardContent class="space-y-4">
        <label class="flex items-center gap-2 text-sm">
          <input v-model="traceEnabled" type="checkbox" class="h-4 w-4" />
          {{ t('ops.trace.enabled') }}
        </label>
        <div class="grid gap-2">
          <Label>{{ t('ops.trace.dir') }}</Label>
          <Input v-model="traceDir" placeholder="/tmp/agm-trace" />
        </div>
      </CardContent>
    </Card>

    <Card class="app-surface mb-6 border-none">
      <CardHeader>
        <CardTitle>{{ t('ops.debugCapture.title') }}</CardTitle>
        <CardDescription>{{ t('ops.debugCapture.description') }}</CardDescription>
      </CardHeader>
      <CardContent class="grid gap-2">
        <Label>{{ t('ops.debugCapture.dir') }}</Label>
        <Input v-model="debugCapture" />
      </CardContent>
    </Card>

    <Card class="app-surface mb-6 border-none">
      <CardHeader>
        <CardTitle>{{ t('ops.runtime.title') }}</CardTitle>
        <CardDescription>{{ t('ops.runtime.description') }}</CardDescription>
      </CardHeader>
      <CardContent class="grid gap-4 md:grid-cols-2">
        <div class="flex items-start justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2">
          <div>
            <p class="text-sm font-medium text-slate-800">{{ t('ops.runtime.keepImages') }}</p>
            <p class="text-xs text-slate-500">{{ t('ops.runtime.keepImagesHint') }}</p>
          </div>
          <Switch
            :model-value="runtime.KEEP_TASK_IMAGES"
            @update:model-value="(value) => runtime.KEEP_TASK_IMAGES = !!value"
          />
        </div>

        <div class="flex items-start justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2">
          <div>
            <p class="text-sm font-medium text-slate-800">{{ t('ops.runtime.refreshTracked') }}</p>
            <p class="text-xs text-slate-500">{{ t('ops.runtime.refreshTrackedHint') }}</p>
          </div>
          <Switch
            :model-value="runtime.REFRESH_TRACKED_ITEMS"
            @update:model-value="(value) => runtime.REFRESH_TRACKED_ITEMS = !!value"
          />
        </div>

        <div class="flex items-start justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2">
          <div>
            <p class="text-sm font-medium text-slate-800">{{ t('ops.runtime.aiDebug') }}</p>
            <p class="text-xs text-slate-500">{{ t('ops.runtime.aiDebugHint') }}</p>
          </div>
          <Switch
            :model-value="runtime.AI_DEBUG_MODE"
            @update:model-value="(value) => runtime.AI_DEBUG_MODE = !!value"
          />
        </div>

        <div class="flex items-start justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2">
          <div>
            <p class="text-sm font-medium text-slate-800">{{ t('ops.runtime.enableThinking') }}</p>
            <p class="text-xs text-slate-500">{{ t('ops.runtime.enableThinkingHint') }}</p>
          </div>
          <Switch
            :model-value="runtime.ENABLE_THINKING"
            @update:model-value="(value) => runtime.ENABLE_THINKING = !!value"
          />
        </div>

        <div class="flex items-start justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2">
          <div>
            <p class="text-sm font-medium text-slate-800">{{ t('ops.runtime.enableResponseFormat') }}</p>
            <p class="text-xs text-slate-500">{{ t('ops.runtime.enableResponseFormatHint') }}</p>
          </div>
          <Switch
            :model-value="runtime.ENABLE_RESPONSE_FORMAT"
            @update:model-value="(value) => runtime.ENABLE_RESPONSE_FORMAT = !!value"
          />
        </div>

        <div class="grid gap-2 rounded-lg border border-slate-200 px-3 py-2">
          <Label for="failure-threshold">{{ t('ops.runtime.failureThreshold') }}</Label>
          <Input
            id="failure-threshold"
            type="number"
            min="0"
            :model-value="runtime.TASK_FAILURE_THRESHOLD"
            @update:model-value="(value) => setNumber('TASK_FAILURE_THRESHOLD', value as string)"
          />
          <p class="text-xs text-slate-500">{{ t('ops.runtime.failureThresholdHint') }}</p>
        </div>

        <div class="grid gap-2 rounded-lg border border-slate-200 px-3 py-2">
          <Label for="failure-pause">{{ t('ops.runtime.failurePause') }}</Label>
          <Input
            id="failure-pause"
            type="number"
            min="0"
            :model-value="runtime.TASK_FAILURE_PAUSE_SECONDS"
            @update:model-value="(value) => setNumber('TASK_FAILURE_PAUSE_SECONDS', value as string)"
          />
          <p class="text-xs text-slate-500">{{ t('ops.runtime.failurePauseHint') }}</p>
        </div>

        <div class="grid gap-2 rounded-lg border border-slate-200 px-3 py-2">
          <Label for="log-retention">{{ t('ops.runtime.logRetention') }}</Label>
          <Input
            id="log-retention"
            type="number"
            min="1"
            :model-value="runtime.TASK_LOG_RETENTION_DAYS"
            @update:model-value="(value) => setNumber('TASK_LOG_RETENTION_DAYS', value as string)"
          />
          <p class="text-xs text-slate-500">{{ t('ops.runtime.logRetentionHint') }}</p>
        </div>

        <div class="grid gap-2 rounded-lg border border-slate-200 px-3 py-2">
          <Label for="ai-log-retention">{{ t('ops.runtime.aiLogRetention') }}</Label>
          <Input
            id="ai-log-retention"
            type="number"
            min="1"
            :model-value="runtime.AI_LOG_RETENTION_DAYS"
            @update:model-value="(value) => setNumber('AI_LOG_RETENTION_DAYS', value as string)"
          />
          <p class="text-xs text-slate-500">{{ t('ops.runtime.aiLogRetentionHint') }}</p>
        </div>

        <div class="grid gap-2 rounded-lg border border-slate-200 px-3 py-2">
          <Label for="trace-max-mb">{{ t('ops.runtime.traceMaxMb') }}</Label>
          <Input
            id="trace-max-mb"
            type="number"
            min="1"
            :model-value="runtime.AGM_TRACE_MAX_MB"
            @update:model-value="(value) => setNumber('AGM_TRACE_MAX_MB', value as string)"
          />
          <p class="text-xs text-slate-500">{{ t('ops.runtime.traceMaxMbHint') }}</p>
        </div>
      </CardContent>
    </Card>

    <div class="mb-6 flex justify-end">
      <Button :disabled="isSaving" @click="handleSave">
        {{ isSaving ? t('common.saving') : t('ops.save') }}
      </Button>
    </div>

    <Card class="app-surface border-none">
      <CardHeader class="flex flex-row items-center justify-between gap-3">
        <div>
          <CardTitle>{{ t('ops.traces.title') }}</CardTitle>
          <CardDescription>{{ t('ops.traces.description') }}</CardDescription>
        </div>
        <Button variant="outline" size="sm" :disabled="isLoading" @click="loadTraces">
          {{ t('ops.traces.refresh') }}
        </Button>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{{ t('ops.traces.name') }}</TableHead>
              <TableHead>{{ t('ops.traces.time') }}</TableHead>
              <TableHead>{{ t('ops.traces.size') }}</TableHead>
              <TableHead>{{ t('ops.traces.files') }}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-if="isLoading">
              <TableCell colspan="4" class="h-20 text-center text-muted-foreground">{{ t('common.loading') }}</TableCell>
            </TableRow>
            <TableRow v-else-if="traces.length === 0">
              <TableCell colspan="4" class="h-20 text-center text-muted-foreground">{{ t('ops.traces.empty') }}</TableCell>
            </TableRow>
            <TableRow v-else v-for="trace in traces" :key="trace.name">
              <TableCell class="font-medium">{{ trace.name }}</TableCell>
              <TableCell class="text-sm text-gray-500">{{ trace.mtime }}</TableCell>
              <TableCell class="text-sm text-gray-500">{{ formatSize(trace.size) }}</TableCell>
              <TableCell class="text-sm text-gray-500">
                {{ trace.files.map((file) => `${file.name} (${formatSize(file.size)})`).join('，') }}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  </div>
</template>
