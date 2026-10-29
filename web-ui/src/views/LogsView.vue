<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLogs } from '@/composables/useLogs'
import { useTasks } from '@/composables/useTasks'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/components/ui/toast'

const { t } = useI18n()
const { tasks } = useTasks()
const { logs, isAutoRefresh, clearLogs, toggleAutoRefresh, fetchLogs, setTaskId, setAllMode, isAllMode, loadLatest, loadPrevious, isFetchingHistory, hasMoreHistory } = useLogs()
const logContainer = ref<HTMLElement | null>(null)
const autoScroll = ref(true)
const isClearDialogOpen = ref(false)
const selectedTaskId = ref('')
const isPrepending = ref(false)
const lastScrollTop = ref(0)
const lastScrollHeight = ref(0)
const keyword = ref('')
const levelFilter = ref<'all' | 'error' | 'warn' | 'info' | 'debug'>('all')
const showDelay = ref(false)

type LogLevel = 'error' | 'warn' | 'info' | 'debug'

function detectLevel(line: string): LogLevel {
  if (/\b(ERROR|CRITICAL|Traceback|Exception)\b/.test(line) || /错误|失败|异常|超时/.test(line)) return 'error'
  if (/\b(WARN|WARNING)\b/.test(line) || /警告/.test(line)) return 'warn'
  if (line.includes('[延迟]')) return 'debug'
  return 'info'
}

const allLines = computed(() => (logs.value ? logs.value.split('\n') : []))
const delayLineCount = computed(() => allLines.value.filter((line) => line.includes('[延迟]')).length)
const filteredLines = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return allLines.value.filter((line) => {
    if (!showDelay.value && line.includes('[延迟]')) return false
    if (levelFilter.value !== 'all' && detectLevel(line) !== levelFilter.value) return false
    if (kw && !line.toLowerCase().includes(kw)) return false
    return true
  })
})

const levelClass = (line: string) => {
  const level = detectLevel(line)
  if (level === 'error') return 'text-rose-400'
  if (level === 'warn') return 'text-amber-300'
  if (level === 'debug') return 'text-slate-500'
  return 'text-gray-100'
}

const levelTone = (line: string) => {
  const level = detectLevel(line)
  if (level === 'error') return 'bg-rose-500/20 text-rose-300'
  if (level === 'warn') return 'bg-amber-500/20 text-amber-200'
  if (level === 'debug') return 'bg-slate-500/20 text-slate-400'
  return 'bg-slate-600/20 text-slate-300'
}

// Auto-scroll logic
watch(logs, async () => {
  if (isPrepending.value) {
    await nextTick()
    if (logContainer.value) {
      const delta = logContainer.value.scrollHeight - lastScrollHeight.value
      logContainer.value.scrollTop = lastScrollTop.value + delta
    }
    isPrepending.value = false
    return
  }
  if (autoScroll.value) {
    await nextTick()
    scrollToBottom()
  }
})

watch(tasks, (list) => {
  if (!list.length) {
    selectedTaskId.value = ''
    setTaskId(null)
    return
  }
  if (selectedTaskId.value === 'all') return
  if (selectedTaskId.value && list.some((task) => String(task.id) === selectedTaskId.value)) {
    return
  }
  const running = list.find((task) => task.is_running)
  const fallback = list[0]
  if (!fallback) {
    selectedTaskId.value = ''
    setTaskId(null)
    return
  }
  selectedTaskId.value = String(running ? running.id : fallback.id)
}, { immediate: true })

watch(selectedTaskId, (taskId) => {
  if (taskId === 'all') {
    setAllMode()
    fetchLogs()
    return
  }
  const resolvedTaskId = taskId ? Number(taskId) : null
  setTaskId(resolvedTaskId)
  if (resolvedTaskId) {
    loadLatest(50)
  }
})

function scrollToBottom() {
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

async function handleScroll() {
  if (!logContainer.value) return
  if (!hasMoreHistory.value || isFetchingHistory.value) return
  if (logContainer.value.scrollTop > 120) return
  lastScrollTop.value = logContainer.value.scrollTop
  lastScrollHeight.value = logContainer.value.scrollHeight
  isPrepending.value = true
  await loadPrevious(50)
}

async function handleLoadEarlier() {
  lastScrollTop.value = logContainer.value?.scrollTop ?? 0
  lastScrollHeight.value = logContainer.value?.scrollHeight ?? 0
  isPrepending.value = true
  await loadPrevious(200)
}

function exportLogs() {
  if (!filteredLines.value.length) {
    toast({ title: t('logs.exportEmpty') })
    return
  }
  const blob = new Blob([filteredLines.value.join('\n')], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '')
  link.href = url
  link.download = `logs-${stamp}.txt`
  link.click()
  URL.revokeObjectURL(url)
}

function openClearDialog() {
  isClearDialogOpen.value = true
}

async function handleClearLogs() {
  try {
    await clearLogs()
    toast({ title: t('logs.logsCleared') })
  } catch (e) {
    toast({
      title: t('logs.clearFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isClearDialogOpen.value = false
  }
}
</script>

<template>
  <div class="flex h-[calc(100vh-100px)] flex-col gap-4">
    <div class="app-surface p-4">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-center">
        <h1 class="text-2xl font-bold text-gray-800">{{ t('logs.title') }}</h1>
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Label class="text-sm text-gray-600">{{ t('logs.task') }}</Label>
          <Select v-model="selectedTaskId">
            <SelectTrigger class="w-full sm:w-[260px]">
              <SelectValue :placeholder="t('logs.selectTask')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{{ t('logs.allTasks') }}</SelectItem>
              <SelectItem v-for="task in tasks" :key="task.id" :value="String(task.id)">
                {{ task.task_name }}{{ task.is_running ? t('logs.taskRunningSuffix') : '' }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div class="flex flex-col gap-3 md:flex-row md:flex-wrap md:items-center md:justify-end">
        <Button variant="outline" size="sm" :disabled="!selectedTaskId" @click="fetchLogs">
          {{ t('common.refresh') }}
        </Button>

        <div class="flex items-center space-x-2">
          <Switch id="auto-refresh" :model-value="isAutoRefresh" @update:model-value="toggleAutoRefresh" />
          <Label for="auto-refresh">{{ t('logs.autoRefresh') }}</Label>
        </div>

        <div class="flex items-center space-x-2">
          <Switch id="auto-scroll" v-model="autoScroll" />
          <Label for="auto-scroll">{{ t('logs.autoScroll') }}</Label>
        </div>

        <Button variant="outline" size="sm" :disabled="!filteredLines.length" @click="exportLogs">
          {{ t('logs.export') }}
        </Button>

        <Button variant="destructive" size="sm" :disabled="!selectedTaskId || isAllMode" @click="openClearDialog">
          {{ t('logs.clearLogs') }}
        </Button>
      </div>
    </div>
    </div>

    <div class="app-surface flex flex-wrap items-center gap-3 px-4 py-2">
      <Input
        v-model="keyword"
        class="h-8 w-full sm:w-[220px]"
        :placeholder="t('logs.keywordPlaceholder')"
      />
      <Select v-model="levelFilter">
        <SelectTrigger class="h-8 w-full sm:w-[130px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{{ t('logs.levelAll') }}</SelectItem>
          <SelectItem value="error">{{ t('logs.levelError') }}</SelectItem>
          <SelectItem value="warn">{{ t('logs.levelWarn') }}</SelectItem>
          <SelectItem value="info">{{ t('logs.levelInfo') }}</SelectItem>
          <SelectItem value="debug">{{ t('logs.levelDebug') }}</SelectItem>
        </SelectContent>
      </Select>
      <div class="flex items-center space-x-2">
        <Switch id="show-delay" v-model="showDelay" />
        <Label for="show-delay" class="text-xs text-gray-600">{{ t('logs.showDelay') }}</Label>
      </div>
      <span class="text-xs text-gray-500">
        {{ t('logs.lineCount', { shown: filteredLines.length, total: allLines.length }) }}
      </span>
      <span v-if="!showDelay && delayLineCount" class="text-xs text-gray-400">
        {{ t('logs.delayHidden', { count: delayLineCount }) }}
      </span>
      <Button
        v-if="hasMoreHistory"
        variant="ghost"
        size="sm"
        class="ml-auto h-7 text-xs"
        :disabled="isFetchingHistory"
        @click="handleLoadEarlier"
      >
        {{ isFetchingHistory ? t('common.loading') : t('logs.loadEarlier') }}
      </Button>
    </div>

    <Card class="app-surface flex flex-1 flex-col overflow-hidden border-none">
      <CardContent class="flex-1 p-0 relative">
        <div
          ref="logContainer"
          @scroll="handleScroll"
          class="absolute inset-0 overflow-auto bg-gray-950 py-2 font-mono text-[13px] leading-5"
        >
          <div
            v-for="(line, index) in filteredLines"
            :key="index"
            class="flex gap-2 px-4 hover:bg-white/5"
            :class="levelClass(line)"
          >
            <span class="w-[52px] shrink-0 text-[10px] font-bold uppercase tracking-wide" :class="levelTone(line)">
              {{ detectLevel(line) }}
            </span>
            <span class="whitespace-pre-wrap break-all">{{ line }}</span>
          </div>
          <div v-if="!filteredLines.length" class="px-4 py-6 text-center text-slate-500">
            {{ allLines.length ? t('logs.emptyFiltered') : t('logs.empty') }}
          </div>
        </div>
      </CardContent>
    </Card>

    <Dialog v-model:open="isClearDialogOpen">
      <DialogContent class="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>{{ t('logs.dialogTitle') }}</DialogTitle>
          <DialogDescription>
            {{ t('logs.dialogDescription') }}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="isClearDialogOpen = false">{{ t('common.cancel') }}</Button>
          <Button variant="destructive" @click="handleClearLogs">{{ t('logs.confirmClear') }}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
