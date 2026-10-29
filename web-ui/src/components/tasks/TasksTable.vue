<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Task } from '@/types/task.d.ts'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { 
  Play, 
  Square, 
  Pencil, 
  Trash2, 
  User, 
  BrainCircuit, 
  Keyboard,
  Clock,
  Layers,
  MapPin,
  RefreshCcw,
  Search
} from 'lucide-vue-next'
import { formatCountdown, formatNextRunAbsolute } from '@/lib/taskSchedule'

interface TaskRunInfo {
  task_id?: number
  task_name?: string
  status: string
  item_count: number
  finished_at: string
  error?: string | null
  reason?: string | null
  items_seen?: number
}

interface Props {
  tasks: Task[]
  isLoading: boolean
  stoppingIds?: Set<number>
  lastRuns?: Record<string, TaskRunInfo>
}

const props = defineProps<Props>()
const { t } = useI18n()
const isStopping = (id: number) => props.stoppingIds?.has(id) ?? false
const lastRunOf = (id: number) => props.lastRuns?.[String(id)]
const lastRunText = (id: number) => {
  const run = lastRunOf(id)
  if (!run?.finished_at) return ''
  const time = run.finished_at.slice(5, 16).replace('T', ' ')
  if (run.status === 'failed') return t('tasks.table.lastRunFailed', { time })
  if (run.item_count) return t('tasks.table.lastRun', { time, count: run.item_count })
  if (run.reason === 'search_empty') return t('tasks.table.lastRunSearchEmpty', { time })
  if (run.reason === 'all_filtered') return t('tasks.table.lastRunFiltered', { time, count: run.items_seen ?? 0 })
  return t('tasks.table.lastRunEmpty', { time })
}
const isKeywordMode = (task: Task) => task.decision_mode === 'keyword'
const nowMs = ref(Date.now())
let timer: number | null = null

onMounted(() => {
  timer = window.setInterval(() => {
    nowMs.value = Date.now()
  }, 1000)
})

onBeforeUnmount(() => {
  if (timer !== null) {
    window.clearInterval(timer)
  }
})

const resolveAccountStrategyLabel = (task: Task) => {
  if (task.account_strategy === 'rotate') return t('tasks.table.accountRotate')
  if (task.account_strategy === 'fixed') return t('tasks.table.accountFixed')
  return t('tasks.table.accountAuto')
}

const resolveAccountName = (task: Task) => {
  if (!task.account_state_file) return t('tasks.table.systemSelected')
  const segments = task.account_state_file.split('/')
  const filename = segments[segments.length - 1] || task.account_state_file
  return filename.replace('.json', '')
}

const resolveCountdownText = (task: Task) => {
  if (!task.cron) return t('tasks.table.manualTrigger')
  if (!task.enabled) return t('tasks.table.disabled')
  return formatCountdown(task.next_run_at, nowMs.value) || t('tasks.table.waitingSchedule')
}

const resolveCountdownTone = (task: Task) => {
  if (!task.cron) return 'text-slate-400'
  if (!task.enabled) return 'text-slate-400'
  return 'text-amber-600'
}

const resolveNextRunLabel = (task: Task) => {
  if (!task.cron || !task.enabled || !task.next_run_at) return null
  return formatNextRunAbsolute(task.next_run_at)
}

const emit = defineEmits<{
  (e: 'delete-task', taskId: number): void
  (e: 'run-task', taskId: number): void
  (e: 'stop-task', taskId: number): void
  (e: 'edit-task', task: Task): void
  (e: 'refresh-criteria', task: Task): void
  (e: 'toggle-enabled', task: Task, enabled: boolean): void
}>()
</script>

<template>
  <div class="app-surface overflow-hidden animate-fade-in">
    <div class="space-y-4 p-4 lg:hidden">
      <template v-if="isLoading && tasks.length === 0">
        <div class="flex min-h-40 flex-col items-center justify-center gap-2 text-slate-400">
          <RefreshCcw class="h-6 w-6 animate-spin" />
          <span class="text-sm font-medium italic">{{ t('tasks.table.syncing') }}</span>
        </div>
      </template>
      <template v-else-if="tasks.length === 0">
        <div class="flex min-h-40 flex-col items-center justify-center gap-2 text-slate-300">
          <Layers class="h-12 w-12 opacity-20" />
          <p class="text-sm font-bold">{{ t('tasks.table.empty') }}</p>
        </div>
      </template>
      <template v-else>
        <article
          v-for="task in tasks"
          :key="task.id"
          class="app-surface-subtle p-4"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0 space-y-2">
              <div class="flex flex-wrap items-center gap-2">
                <h3 class="truncate text-base font-black tracking-tight text-slate-900">
                  {{ task.task_name }}
                </h3>
                <Badge
                  variant="outline"
                  :class="[
                    'border-none px-2 py-0.5 text-[10px] font-black',
                    isKeywordMode(task) ? 'bg-blue-50 text-blue-600' : 'bg-emerald-50 text-emerald-600',
                  ]"
                >
                  <component :is="isKeywordMode(task) ? Keyboard : BrainCircuit" class="mr-1 h-3 w-3" />
                  {{ isKeywordMode(task) ? t('tasks.table.modeKeyword') : t('tasks.table.modeAi') }}
                </Badge>
              </div>

              <div class="flex flex-wrap items-center gap-2 text-sm text-slate-600">
                <div class="inline-flex items-center gap-1.5 rounded-md border border-slate-200/70 bg-slate-100/80 px-2 py-1 font-semibold">
                  <Search class="h-3.5 w-3.5 text-slate-400" />
                  {{ task.keyword }}
                </div>
                <span v-if="task.description" class="line-clamp-1 text-slate-500">
                  {{ task.description }}
                </span>
              </div>
            </div>

            <div class="flex flex-col items-end gap-2">
              <Switch
                :model-value="task.enabled"
                class="data-[state=checked]:bg-primary"
                :title="t('tasks.table.enabledHint')"
                @update:model-value="(val: boolean) => emit('toggle-enabled', task, val)"
              />
              <Badge
                variant="outline"
                :class="[
                  'whitespace-nowrap shrink-0',
                  task.is_running ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500',
                ]"
              >
                {{ task.is_running ? t('common.running') : t('common.idle') }}
              </Badge>
              <span
                v-if="lastRunText(task.id)"
                class="text-right text-[10px] font-medium"
                :class="lastRunOf(task.id)?.status === 'failed' ? 'text-rose-500' : 'text-slate-400'"
              >
                {{ lastRunText(task.id) }}
              </span>
            </div>
          </div>

          <div class="mt-4 grid gap-3 sm:grid-cols-2">
            <div class="rounded-xl border border-slate-200/70 bg-white/80 p-3">
              <p class="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                {{ t('tasks.table.headers.crawl') }}
              </p>
              <p class="mt-2 text-sm font-bold text-slate-700">
                ¥{{ task.min_price || 0 }} - {{ task.max_price || 'MAX' }}
              </p>
              <div class="mt-2 flex flex-wrap gap-1.5">
                <Badge variant="outline" class="border-slate-200/70 bg-slate-50 text-slate-500">
                  {{ task.personal_only ? t('tasks.table.personalOnly') : t('common.all') }}
                </Badge>
                <Badge variant="outline" class="border-slate-200/70 bg-slate-50 text-slate-500">
                  {{ task.free_shipping ? t('tasks.table.freeShipping') : t('common.all') }}
                </Badge>
                <Badge v-if="task.region" variant="outline" class="border-slate-200/70 bg-slate-50 text-slate-500">
                  <MapPin class="mr-1 h-3 w-3" />
                  {{ task.region }}
                </Badge>
              </div>
            </div>

            <div class="rounded-xl border border-slate-200/70 bg-white/80 p-3">
              <p class="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                {{ t('tasks.table.headers.schedule') }}
              </p>
              <p class="mt-2 text-sm font-bold" :class="resolveCountdownTone(task)">
                {{ resolveCountdownText(task) }}
              </p>
              <p v-if="resolveNextRunLabel(task)" class="mt-1 text-xs text-slate-500">
                {{ resolveNextRunLabel(task) }}
              </p>
              <div class="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span class="inline-flex items-center gap-1">
                  <Clock class="h-3.5 w-3.5" />
                  {{ task.cron || 'MANUAL' }}
                </span>
                <span class="inline-flex items-center gap-1">
                  <Layers class="h-3.5 w-3.5" />
                  {{ task.max_pages || 3 }}P
                </span>
              </div>
            </div>

            <div class="rounded-xl border border-slate-200/70 bg-white/80 p-3 sm:col-span-2">
              <p class="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                {{ t('tasks.form.accountStrategyLabel') }}
              </p>
              <p class="mt-2 text-sm font-semibold text-slate-700">
                {{ resolveAccountStrategyLabel(task) }} · {{ resolveAccountName(task) }}
              </p>
            </div>
          </div>

          <div class="mt-4 flex flex-wrap gap-2">
            <Button
              v-if="!task.is_running"
              size="sm"
              class="flex-1 min-w-[120px]"
              :class="task.enabled ? '' : 'pointer-events-none opacity-50'"
              :aria-label="`${t('tasks.table.start')} ${task.task_name}`"
              @click="emit('run-task', task.id)"
            >
              <Play class="mr-1 h-3.5 w-3.5 fill-current" />
              {{ t('tasks.table.start') }}
            </Button>
            <Button
              v-else
              size="sm"
              variant="destructive"
              class="flex-1 min-w-[120px]"
              :disabled="isStopping(task.id)"
              :aria-label="`${t('tasks.table.stop')} ${task.task_name}`"
              @click="emit('stop-task', task.id)"
            >
              <Square v-if="!isStopping(task.id)" class="mr-1 h-3.5 w-3.5 fill-current" />
              <RefreshCcw v-else class="mr-1 h-3.5 w-3.5 animate-spin" />
              {{ isStopping(task.id) ? t('tasks.table.stopping') : t('tasks.table.stop') }}
            </Button>
            <Button
              size="icon"
              variant="outline"
              class="size-10"
              :aria-label="`${t('common.edit')} ${task.task_name}`"
              @click="emit('edit-task', task)"
            >
              <Pencil class="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="outline"
              class="size-10 border-rose-200 text-rose-600 hover:bg-rose-50 hover:text-rose-700"
              :aria-label="`${t('common.delete')} ${task.task_name}`"
              @click="emit('delete-task', task.id)"
            >
              <Trash2 class="h-4 w-4" />
            </Button>
          </div>
        </article>
      </template>
    </div>

    <div class="hidden lg:block">
      <Table>
        <TableHeader class="bg-slate-50/50 border-b border-slate-100">
          <TableRow>
            <TableHead class="w-[80px] px-6 text-slate-500 font-bold uppercase text-[10px] tracking-wider text-center">{{ t('tasks.table.headers.status') }}</TableHead>
            <TableHead class="min-w-[360px] text-slate-500 font-bold uppercase text-[10px] tracking-wider text-left">{{ t('tasks.table.headers.details') }}</TableHead>
            <TableHead class="w-[200px] text-slate-500 font-bold uppercase text-[10px] tracking-wider text-left">{{ t('tasks.table.headers.crawl') }}</TableHead>
            <TableHead class="w-[150px] text-slate-500 font-bold uppercase text-[10px] tracking-wider text-center">{{ t('tasks.table.headers.schedule') }}</TableHead>
            <TableHead class="w-[160px] px-6 text-slate-500 font-bold uppercase text-[10px] tracking-wider text-right">{{ t('tasks.table.headers.actions') }}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <template v-if="isLoading && tasks.length === 0">
            <TableRow>
              <TableCell :colspan="5" class="h-32 text-center">
                <div class="flex flex-col items-center justify-center gap-2 text-slate-400">
                  <RefreshCcw class="w-6 h-6 animate-spin" />
                  <span class="text-sm font-medium italic">{{ t('tasks.table.syncing') }}</span>
                </div>
              </TableCell>
            </TableRow>
          </template>
          <template v-else-if="tasks.length === 0">
            <TableRow>
              <TableCell :colspan="5" class="h-40 text-center">
                <div class="flex flex-col items-center justify-center gap-2 text-slate-300">
                  <Layers class="w-12 h-12 opacity-20" />
                  <p class="text-sm font-bold">{{ t('tasks.table.empty') }}</p>
                </div>
              </TableCell>
            </TableRow>
          </template>
          <template v-else>
            <TableRow
              v-for="task in tasks"
              :key="task.id"
              class="group hover:bg-white/80 transition-all duration-300 border-b border-slate-100/50 last:border-0"
            >
            <!-- Column 1: Status -->
            <TableCell class="px-6 py-2 align-middle">
              <div class="flex flex-col items-center gap-2.5">
                <Switch
                  :model-value="task.enabled"
                  class="data-[state=checked]:bg-primary scale-90"
                  :title="t('tasks.table.enabledHint')"
                  @update:model-value="(val: boolean) => emit('toggle-enabled', task, val)"
                />
                <div class="flex items-center gap-1.5">
                  <div :class="[ 'w-1.5 h-1.5 rounded-full shadow-sm', task.is_running ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300' ]"></div>
                  <span :class="[ 'text-[9px] font-black tracking-widest uppercase', task.is_running ? 'text-emerald-600' : 'text-slate-400' ]">
                    {{ task.is_running ? t('tasks.table.statusActive') : t('tasks.table.statusIdle') }}
                  </span>
                </div>
              </div>
            </TableCell>

            <!-- Column 2: Task Info -->
            <TableCell class="py-2 align-middle">
              <div class="flex flex-col gap-1 py-0.5">
                <div class="flex items-center gap-2">
                  <span class="text-base font-black text-slate-800 tracking-tight group-hover:text-primary transition-colors">{{ task.task_name }}</span>
                  <Badge
                    variant="outline"
                    :class="[
                      'h-4 px-1.5 text-[9px] font-black border-none tracking-tighter',
                      isKeywordMode(task) ? 'bg-blue-50 text-blue-500' : 'bg-emerald-50 text-emerald-600'
                    ]"
                  >
                    <component :is="isKeywordMode(task) ? Keyboard : BrainCircuit" class="w-2.5 h-2.5 mr-1" />
                    {{ isKeywordMode(task) ? t('tasks.table.modeKeyword') : t('tasks.table.modeAi') }}
                  </Badge>
                </div>

                <div class="flex items-center gap-2 min-w-0">
                   <div class="flex items-center gap-1.5 bg-slate-100/80 text-slate-600 px-2 py-0.5 rounded-md text-[11px] font-bold border border-slate-200/50 shrink-0">
                      <Search class="w-3 h-3 text-slate-400" /> {{ task.keyword }}
                   </div>
                   <div v-if="task.description" class="text-[11px] text-slate-400 italic line-clamp-1 min-w-0" :title="task.description">
                      {{ task.description }}
                   </div>
                   <div class="ml-auto flex shrink-0 items-center gap-1 text-[10px] font-bold text-slate-400 uppercase tracking-tight" :title="`${resolveAccountStrategyLabel(task)} · ${resolveAccountName(task)}`">
                      <User class="w-3 h-3" /> {{ resolveAccountStrategyLabel(task) }}
                      <span class="h-1 w-1 rounded-full bg-slate-200"></span>
                      <span class="normal-case max-w-[90px] truncate font-medium">{{ resolveAccountName(task) }}</span>
                   </div>
                </div>
              </div>
            </TableCell>

            <!-- Column 3: Crawl Config -->
            <TableCell class="py-2 align-middle text-left">
              <div class="space-y-2">
                <div class="flex items-baseline gap-0.5">
                  <span class="text-[10px] font-bold text-slate-400 mr-1 italic">¥</span>
                  <span class="text-sm font-black text-slate-700 tracking-tighter">
                    {{ task.min_price || 0 }} <span class="text-slate-300 font-normal mx-0.5">-</span> {{ task.max_price || 'MAX' }}
                  </span>
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <Badge variant="outline" class="text-[9px] h-4 border-slate-100 text-slate-400 px-1.5 font-bold bg-white/40">
                    {{ task.personal_only ? t('tasks.table.personalOnly') : t('common.all') }}
                  </Badge>
                  <Badge variant="outline" class="text-[9px] h-4 border-slate-100 text-slate-400 px-1.5 font-bold bg-white/40">
                    {{ task.free_shipping ? t('tasks.table.freeShipping') : t('common.all') }}
                  </Badge>
                  <div v-if="task.region" class="flex items-center gap-0.5 text-[9px] font-bold text-slate-400 px-1.5 h-4 bg-slate-50/50 rounded border border-slate-100 truncate max-w-[80px]">
                    <MapPin class="w-2.5 h-2.5" /> {{ task.region }}
                  </div>
                </div>
              </div>
            </TableCell>

            <!-- Column 4: Cron & Pages -->
            <TableCell class="py-2 align-middle text-center">
              <div class="inline-flex flex-col items-center gap-1.5">
                <div class="flex items-center gap-1.5 bg-slate-100/50 border border-slate-200/30 px-2 py-1 rounded-lg" :title="t('tasks.table.pagesHint')">
                  <Clock class="w-3 h-3 text-slate-400" />
                  <span class="text-[11px] font-black text-slate-600 tracking-tight">{{ task.cron || 'MANUAL' }}</span>
                  <span class="flex items-center gap-0.5 text-[9px] font-black text-slate-400 uppercase tracking-widest">
                    <Layers class="w-3 h-3 opacity-50" /> {{ task.max_pages || 3 }}P
                  </span>
                </div>
                <div
                  class="px-2 py-1 rounded-md bg-amber-50/60 border border-amber-100/80 min-w-[112px]"
                  :class="!task.cron || !task.enabled ? 'bg-slate-50 border-slate-100' : ''"
                  :title="resolveNextRunLabel(task) || undefined"
                >
                  <div
                    class="text-[10px] font-black tracking-tight"
                    :class="resolveCountdownTone(task)"
                  >
                    {{ resolveCountdownText(task) }}
                  </div>
                  <div
                    v-if="resolveNextRunLabel(task)"
                    class="text-[9px] font-medium text-slate-400 mt-0.5"
                  >
                    {{ resolveNextRunLabel(task) }}
                  </div>
                </div>
                <div
                  v-if="lastRunText(task.id)"
                  class="text-[9px] font-semibold"
                  :class="lastRunOf(task.id)?.status === 'failed' ? 'text-rose-500' : 'text-slate-400'"
                  :title="lastRunOf(task.id)?.error || undefined"
                >
                  {{ lastRunText(task.id) }}
                </div>
              </div>
            </TableCell>

            <!-- Column 6: Actions -->
            <TableCell class="px-6 py-2 align-middle text-right">
              <div class="flex justify-end items-center gap-2">
                  <Button
                    v-if="!task.is_running"
                    size="sm" 
                    variant="default"
                    class="h-8 px-3 rounded-lg shadow-sm transition-all active:scale-95 text-white border-none"
                    :class="task.enabled ? 'bg-primary hover:bg-primary/90' : 'bg-slate-200 text-slate-400 pointer-events-none opacity-50'"
                    :aria-label="`${t('tasks.table.start')} ${task.task_name}`"
                    @click="emit('run-task', task.id)"
                  >
                  <Play class="w-3 h-3 mr-1.5 fill-current" />
                  <span class="font-bold text-[11px]">{{ t('tasks.table.start') }}</span>
                </Button>
                  <Button
                    v-else
                    size="sm"
                    variant="destructive"
                    class="h-8 px-3 rounded-lg shadow-sm active:scale-95 border-none"
                    :disabled="isStopping(task.id)"
                    :aria-label="`${t('tasks.table.stop')} ${task.task_name}`"
                    @click="emit('stop-task', task.id)"
                  >
                  <Square v-if="!isStopping(task.id)" class="w-3 h-3 mr-1.5 fill-current" />
                  <RefreshCcw v-else class="w-3 h-3 mr-1.5 animate-spin" />
                  <span class="font-bold text-[11px]">{{ isStopping(task.id) ? t('tasks.table.stopping') : t('tasks.table.stop') }}</span>
                </Button>

                <div class="flex items-center gap-0.5 ml-1">
                  <Button 
                    size="icon" 
                    variant="ghost" 
                    class="w-8 h-8 rounded-full text-slate-400 hover:text-primary hover:bg-primary/5 transition-colors" 
                    :aria-label="`${t('common.edit')} ${task.task_name}`"
                    :title="`${t('common.edit')} ${task.task_name}`"
                    @click="emit('edit-task', task)"
                  >
                    <Pencil class="w-3.5 h-3.5" />
                  </Button>
                  <Button 
                    size="icon" 
                    variant="ghost" 
                    class="w-8 h-8 rounded-full text-slate-400 hover:text-rose-500 hover:bg-rose-50 transition-colors" 
                    :aria-label="`${t('common.delete')} ${task.task_name}`"
                    :title="`${t('common.delete')} ${task.task_name}`"
                    @click="emit('delete-task', task.id)"
                  >
                    <Trash2 class="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            </TableCell>
            </TableRow>
          </template>
        </TableBody>
      </Table>
    </div>
  </div>
</template>

<style scoped>
:deep(td) {
  @apply py-3 px-4;
}
:deep(th) {
  @apply h-11 px-4;
}
</style>
