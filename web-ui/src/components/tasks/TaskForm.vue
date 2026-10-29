<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Task, TaskGenerateRequest } from '@/types/task.d.ts'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/components/ui/toast'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import TaskRegionSelector from '@/components/tasks/TaskRegionSelector.vue'

type FormMode = 'create' | 'edit'
type EmittedData = TaskGenerateRequest | Partial<Task>
const AUTO_ACCOUNT_VALUE = '__auto__'
const EMPTY_CRON_VALUE = '__manual__'

const props = defineProps<{
  mode: FormMode
  initialData?: Task | null
  accountOptions?: { name: string; path: string }[]
  defaultAccount?: string
  defaultValues?: Partial<TaskGenerateRequest & Partial<Task>>
  /** 表单 id 必须唯一：新建与编辑弹窗同时挂载时，按钮的 form 属性才不会串 */
  formId?: string
}>()

const formId = computed(() => props.formId || 'task-form')

const emit = defineEmits<{
  (e: 'submit', data: EmittedData): void
  (e: 'update:dirty', dirty: boolean): void
}>()
const { t } = useI18n()

const form = ref<any>({})
const formSnapshot = ref('')
const activeTab = ref<'basic' | 'prompt'>('basic')
const currentSnapshot = () => JSON.stringify([form.value, keywordRulesInput.value])
const accountStrategy = ref<'auto' | 'fixed' | 'rotate'>('auto')
const selectedAccountStateFile = ref(AUTO_ACCOUNT_VALUE)
const keywordRulesInput = ref('')
const cronMode = ref<'preset' | 'custom'>('preset')

// 常用 cron 预设选项
const cronPresets = computed(() => [
  { value: EMPTY_CRON_VALUE, label: t('tasks.form.cron.manual') },
  { value: '*/5 * * * *', label: t('tasks.form.cron.every5Minutes') },
  { value: '*/15 * * * *', label: t('tasks.form.cron.every15Minutes') },
  { value: '*/30 * * * *', label: t('tasks.form.cron.every30Minutes') },
  { value: '0 * * * *', label: t('tasks.form.cron.hourly') },
  { value: '0 */2 * * *', label: t('tasks.form.cron.every2Hours') },
  { value: '0 */6 * * *', label: t('tasks.form.cron.every6Hours') },
  { value: '0 8 * * *', label: t('tasks.form.cron.daily8') },
  { value: '0 12 * * *', label: t('tasks.form.cron.daily12') },
  { value: '0 18 * * *', label: t('tasks.form.cron.daily18') },
  { value: '0 20 * * *', label: t('tasks.form.cron.daily20') },
  { value: '0 8,12,18 * * *', label: t('tasks.form.cron.daily81218') },
  { value: '0 9 * * 1-5', label: t('tasks.form.cron.weekday9') },
  { value: '0 10 * * 6,0', label: t('tasks.form.cron.weekend10') },
])

// 判断 cron 值是否为预设值
function isPresetCronValue(value: string): boolean {
  if (!value) return true
  return cronPresets.value.some((preset) => preset.value === value)
}

// 判断当前 cron 是否为预设值
const isPresetCron = computed(() => isPresetCronValue(form.value.cron))

// 预设选择的值
const presetCronValue = computed({
  get: () => {
    if (!isPresetCron.value) return EMPTY_CRON_VALUE
    return form.value.cron || EMPTY_CRON_VALUE
  },
  set: (val: string) => { form.value.cron = val === EMPTY_CRON_VALUE ? '' : val },
})
const accountStrategyOptions = computed(() => [
  { value: 'auto', label: t('tasks.form.accountStrategy.auto'), description: t('tasks.form.accountStrategy.autoDescription') },
  { value: 'fixed', label: t('tasks.form.accountStrategy.fixed'), description: t('tasks.form.accountStrategy.fixedDescription') },
  { value: 'rotate', label: t('tasks.form.accountStrategy.rotate'), description: t('tasks.form.accountStrategy.rotateDescription') },
])

function parseKeywordText(text: string): string[] {
  const values = String(text || '')
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0)

  const seen = new Set<string>()
  const deduped: string[] = []
  for (const value of values) {
    const key = value.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push(value)
  }
  return deduped
}

watch(() => [props.mode, props.initialData, props.defaultValues, props.defaultAccount], () => {
  const defaultValues = props.defaultValues || {}
  if (props.mode === 'edit' && props.initialData) {
    form.value = {
      ...props.initialData,
      ...defaultValues,
      account_strategy:
        defaultValues.account_strategy ||
        props.initialData.account_strategy ||
        (props.initialData.account_state_file ? 'fixed' : 'auto'),
      account_state_file:
        defaultValues.account_state_file ||
        props.initialData.account_state_file ||
        AUTO_ACCOUNT_VALUE,
      analyze_images: defaultValues.analyze_images ?? props.initialData.analyze_images ?? true,
      free_shipping: defaultValues.free_shipping ?? props.initialData.free_shipping ?? true,
      new_publish_option:
        defaultValues.new_publish_option || props.initialData.new_publish_option || '__none__',
      region: defaultValues.region || props.initialData.region || '',
      decision_mode: defaultValues.decision_mode || props.initialData.decision_mode || 'ai',
    }
    keywordRulesInput.value = (defaultValues.keyword_rules || props.initialData.keyword_rules || []).join('\n')
    // 编辑模式下，根据 cron 值判断模式
    const cronVal = defaultValues.cron ?? props.initialData.cron ?? ''
    cronMode.value = isPresetCronValue(cronVal) ? 'preset' : 'custom'
  } else {
    form.value = {
      task_name: '',
      keyword: '',
      description: '',
      analyze_images: true,
      max_pages: 3,
      personal_only: true,
      min_price: undefined,
      max_price: undefined,
      cron: '',
      account_strategy: props.defaultAccount ? 'fixed' : 'auto',
      account_state_file: props.defaultAccount || AUTO_ACCOUNT_VALUE,
      free_shipping: true,
      new_publish_option: '__none__',
      region: '',
      decision_mode: 'ai',
      ...defaultValues,
    }
    if (!form.value.account_strategy) {
      form.value.account_strategy = props.defaultAccount ? 'fixed' : 'auto'
    }
    if (!form.value.account_state_file) {
      form.value.account_state_file = props.defaultAccount || AUTO_ACCOUNT_VALUE
    }
    if (!form.value.new_publish_option) {
      form.value.new_publish_option = '__none__'
    }
    keywordRulesInput.value = ''
    if (defaultValues.keyword_rules && defaultValues.keyword_rules.length > 0) {
      keywordRulesInput.value = defaultValues.keyword_rules.join('\n')
    }
    // 创建模式下，根据默认值判断模式
    const cronVal = defaultValues.cron ?? ''
    cronMode.value = isPresetCronValue(cronVal) ? 'preset' : 'custom'
  }

  accountStrategy.value = form.value.account_strategy || (props.defaultAccount ? 'fixed' : 'auto')
  selectedAccountStateFile.value =
    form.value.account_state_file || props.defaultAccount || AUTO_ACCOUNT_VALUE
  formSnapshot.value = currentSnapshot()
}, { immediate: true, deep: true })

watch([form, keywordRulesInput], () => {
  if (!formSnapshot.value) return
  emit('update:dirty', currentSnapshot() !== formSnapshot.value)
}, { deep: true })

watch(accountStrategy, (value) => {
  form.value.account_strategy = value
  if (value === 'fixed') {
    form.value.account_state_file = selectedAccountStateFile.value || props.defaultAccount || AUTO_ACCOUNT_VALUE
    return
  }
  form.value.account_state_file = null
})

watch(selectedAccountStateFile, (value) => {
  if (accountStrategy.value !== 'fixed') return
  form.value.account_state_file = value || props.defaultAccount || AUTO_ACCOUNT_VALUE
})

function handleAccountStrategyChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value as 'auto' | 'fixed' | 'rotate'
  accountStrategy.value = value
}

function handleAccountStateFileChange(event: Event) {
  selectedAccountStateFile.value = (event.target as HTMLSelectElement).value || AUTO_ACCOUNT_VALUE
}

function handleSubmit() {
  if (!form.value.task_name || !form.value.keyword) {
    activeTab.value = 'basic'
    toast({
      title: t('tasks.form.validation.incomplete'),
      description: t('tasks.form.validation.nameAndKeywordRequired'),
      variant: 'destructive',
    })
    return
  }

  const decisionMode = form.value.decision_mode || 'ai'
  if (decisionMode === 'ai' && !String(form.value.description || '').trim()) {
    activeTab.value = 'prompt'
    toast({
      title: t('tasks.form.validation.incomplete'),
      description: t('tasks.form.validation.aiDescriptionRequired'),
      variant: 'destructive',
    })
    return
  }

  const keywordRules = parseKeywordText(keywordRulesInput.value)
  if (decisionMode === 'keyword' && keywordRules.length === 0) {
    activeTab.value = 'prompt'
    toast({
      title: t('tasks.form.validation.keywordRuleIncomplete'),
      description: t('tasks.form.validation.keywordRuleRequired'),
      variant: 'destructive',
    })
    return
  }

  // Filter out fields that shouldn't be sent in update requests
  const { id, is_running, next_run_at, ...submitData } = form.value as any
  const currentAccountStrategy = accountStrategy.value || 'auto'
  if (currentAccountStrategy === 'fixed') {
    const currentAccountStateFile = selectedAccountStateFile.value || AUTO_ACCOUNT_VALUE
    if (currentAccountStateFile === AUTO_ACCOUNT_VALUE) {
      activeTab.value = 'basic'
      toast({
        title: t('tasks.form.validation.accountStrategyIncomplete'),
        description: t('tasks.form.validation.fixedAccountRequired'),
        variant: 'destructive',
      })
      return
    }
    submitData.account_state_file = currentAccountStateFile
  } else {
    submitData.account_state_file = null
  }

  if (typeof submitData.region === 'string') {
    const normalized = submitData.region
      .trim()
      .split('/')
      .map((part: string) => part.trim().replace(/(省|市)$/u, ''))
      .filter((part: string) => part.length > 0)
      .join('/')
    // 省下拉里的「全国」代表不筛选，与后端约定一致
    submitData.region = normalized === '全国' ? '' : normalized
  }

  if (submitData.new_publish_option === '__none__') {
    submitData.new_publish_option = ''
  }

  submitData.decision_mode = decisionMode
  submitData.account_strategy = currentAccountStrategy
  submitData.analyze_images = submitData.analyze_images !== false
  submitData.keyword_rules = decisionMode === 'keyword' ? keywordRules : []
  if (decisionMode === 'keyword' && !submitData.description) {
    submitData.description = ''
  }

  emit('submit', submitData)
}
</script>

<template>
  <form :id="formId" class="flex min-h-0 flex-1 flex-col" @submit.prevent="handleSubmit">
    <Tabs v-model="activeTab" class="flex min-h-0 flex-1 flex-col">
      <TabsList class="grid w-full shrink-0 grid-cols-2">
        <TabsTrigger value="basic">{{ t('tasks.form.tabs.basic') }}</TabsTrigger>
        <TabsTrigger value="prompt">{{ t('tasks.form.tabs.prompt') }}</TabsTrigger>
      </TabsList>

      <TabsContent value="basic" class="mt-4 min-h-0 flex-1 overflow-y-auto pr-1">
        <div class="grid grid-cols-1 gap-x-4 gap-y-5 sm:grid-cols-2">
          <div class="grid gap-2 sm:col-span-2 sm:grid-cols-[7rem_1fr] sm:items-center">
            <Label for="task-name">{{ t('tasks.form.taskName') }} <span class="text-rose-500">*</span></Label>
            <Input id="task-name" v-model="form.task_name" :placeholder="t('tasks.form.taskNamePlaceholder')" required />
          </div>

          <div class="grid gap-2 sm:col-span-2 sm:grid-cols-[7rem_1fr] sm:items-center">
            <Label for="keyword">{{ t('tasks.form.keyword') }} <span class="text-rose-500">*</span></Label>
            <Input id="keyword" v-model="form.keyword" :placeholder="t('tasks.form.keywordPlaceholder')" required />
          </div>

          <div class="grid gap-2 sm:col-span-2 sm:grid-cols-[7rem_1fr] sm:items-center">
            <Label>{{ t('tasks.form.decisionMode') }}</Label>
            <Select v-model="form.decision_mode">
              <SelectTrigger>
                <SelectValue :placeholder="t('tasks.form.decisionModePlaceholder')" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ai">{{ t('tasks.form.aiMode') }}</SelectItem>
                <SelectItem value="keyword">{{ t('tasks.form.keywordMode') }}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div class="grid gap-2 sm:col-span-2 sm:grid-cols-[7rem_1fr] sm:items-center">
            <Label>{{ t('tasks.form.priceRange') }}</Label>
            <div class="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
              <Input type="number" v-model="form.min_price" :aria-label="t('tasks.form.minPrice')" :placeholder="t('tasks.form.minPrice')" />
              <span>-</span>
              <Input type="number" v-model="form.max_price" :aria-label="t('tasks.form.maxPrice')" :placeholder="t('tasks.form.maxPrice')" />
            </div>
          </div>

          <div class="grid gap-2 sm:col-span-2 sm:grid-cols-[7rem_1fr] sm:items-center">
            <Label for="max-pages">{{ t('tasks.form.maxPages') }}</Label>
            <Input id="max-pages" v-model.number="form.max_pages" type="number" />
          </div>

          <div class="grid gap-2 sm:col-span-2 sm:grid-cols-[7rem_1fr] sm:items-center">
            <Label for="cron">{{ t('tasks.form.schedule') }}</Label>
            <div class="space-y-2">
              <Tabs v-model="cronMode" class="w-full">
                <TabsList class="grid w-full grid-cols-2">
                  <TabsTrigger value="preset">{{ t('tasks.form.cronPresetTab') }}</TabsTrigger>
                  <TabsTrigger value="custom">{{ t('tasks.form.cronCustomTab') }}</TabsTrigger>
                </TabsList>
                <TabsContent value="preset">
                  <Select v-model="presetCronValue">
                    <SelectTrigger>
                      <SelectValue :placeholder="t('tasks.form.cronPlaceholder')" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem v-for="preset in cronPresets" :key="preset.value" :value="preset.value">
                        {{ preset.label }}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </TabsContent>
                <TabsContent value="custom">
                  <Input
                    id="cron"
                    v-model="form.cron"
                    :placeholder="t('tasks.form.cronCustomPlaceholder')"
                  />
                  <p class="text-xs text-slate-500 mt-1">
                    {{ t('tasks.form.cronCustomHintLine1') }}
                  </p>
                  <p class="text-xs text-slate-500">
                    {{ t('tasks.form.cronCustomHintLine2') }}
                  </p>
                </TabsContent>
              </Tabs>
              <p v-if="!form.cron" class="text-xs text-amber-600">
                {{ t('tasks.form.cronManualHint') }}
              </p>
            </div>
          </div>

          <div class="grid gap-2 sm:col-span-2 sm:grid-cols-[7rem_1fr] sm:items-center">
            <Label>{{ t('tasks.form.accountStrategyLabel') }}</Label>
            <div class="space-y-2">
              <select
                :value="accountStrategy"
                class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                @change="handleAccountStrategyChange"
              >
                <option v-for="option in accountStrategyOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
              <p class="text-xs text-slate-500">
                {{ accountStrategyOptions.find((option) => option.value === accountStrategy)?.description }}
              </p>
            </div>
          </div>

          <div v-if="accountStrategy === 'fixed'" class="grid gap-2 sm:col-span-2 sm:grid-cols-[7rem_1fr] sm:items-center">
            <Label>{{ t('tasks.form.fixedAccount') }}</Label>
            <select
              :value="selectedAccountStateFile"
              class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              @change="handleAccountStateFileChange"
            >
              <option :value="AUTO_ACCOUNT_VALUE">{{ t('tasks.form.selectAccount') }}</option>
              <option v-for="account in accountOptions || []" :key="account.path" :value="account.path">
                {{ account.name }}
              </option>
            </select>
          </div>

          <label
            v-if="form.decision_mode === 'ai'"
            class="flex items-center justify-between gap-3 rounded-xl border border-slate-200/70 bg-white/60 px-3 py-2.5"
            :title="t('tasks.form.analyzeImagesHint')"
          >
            <span class="text-sm font-medium text-slate-700">{{ t('tasks.form.analyzeImages') }}</span>
            <Switch v-model="form.analyze_images" />
          </label>
          <label class="flex items-center justify-between gap-3 rounded-xl border border-slate-200/70 bg-white/60 px-3 py-2.5">
            <span class="text-sm font-medium text-slate-700">{{ t('tasks.form.personalOnly') }}</span>
            <Switch v-model="form.personal_only" />
          </label>
          <label class="flex items-center justify-between gap-3 rounded-xl border border-slate-200/70 bg-white/60 px-3 py-2.5">
            <span class="text-sm font-medium text-slate-700">{{ t('tasks.form.freeShipping') }}</span>
            <Switch v-model="form.free_shipping" />
          </label>

          <div class="grid gap-2 sm:col-span-2 sm:grid-cols-[7rem_1fr] sm:items-center">
            <Label>{{ t('tasks.form.newPublish') }}</Label>
            <Select v-model="form.new_publish_option">
              <SelectTrigger>
                <SelectValue :placeholder="t('tasks.form.publishOptions.none')" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">{{ t('tasks.form.publishOptions.none') }}</SelectItem>
                <SelectItem value="最新">{{ t('tasks.form.publishOptions.latest') }}</SelectItem>
                <SelectItem value="1天内">{{ t('tasks.form.publishOptions.oneDay') }}</SelectItem>
                <SelectItem value="3天内">{{ t('tasks.form.publishOptions.threeDays') }}</SelectItem>
                <SelectItem value="7天内">{{ t('tasks.form.publishOptions.sevenDays') }}</SelectItem>
                <SelectItem value="14天内">{{ t('tasks.form.publishOptions.fourteenDays') }}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div class="grid gap-2 sm:col-span-2 sm:grid-cols-[7rem_1fr] sm:items-center">
            <Label>{{ t('tasks.form.region') }}</Label>
            <div class="space-y-1">
              <TaskRegionSelector v-model="form.region" />
              <p class="text-xs text-slate-500">{{ t('tasks.form.regionHint') }}</p>
            </div>
          </div>
        </div>
      </TabsContent>

      <TabsContent value="prompt" class="mt-4 flex min-h-0 flex-1 flex-col">
        <template v-if="form.decision_mode === 'keyword'">
          <p class="mb-2 text-xs text-slate-500">{{ t('tasks.form.keywordRulesHint') }}</p>
          <Textarea
            v-model="keywordRulesInput"
            class="min-h-[200px] flex-1"
            :placeholder="t('tasks.form.keywordRulesPlaceholder')"
          />
        </template>
        <template v-else>
          <p class="mb-2 text-xs text-slate-500">{{ t('tasks.form.promptScopeHint') }}</p>
          <Textarea
            id="description"
            v-model="form.description"
            class="min-h-[140px]"
            :placeholder="t('tasks.form.descriptionPlaceholder')"
          />
          <p class="mt-1 text-xs text-slate-500">{{ t('tasks.form.descriptionHint') }}</p>

          <div class="mt-3 flex items-baseline justify-between gap-2">
            <span class="text-sm font-medium text-slate-700">{{ t('tasks.form.criteria') }}</span>
            <span class="text-xs text-slate-400">{{ t('tasks.form.criteriaHint') }}</span>
          </div>
          <Textarea
            v-model="form.criteria_text"
            class="mt-1 min-h-[200px] flex-1"
            :placeholder="t('tasks.form.criteriaPlaceholder')"
          />
        </template>
      </TabsContent>
    </Tabs>
  </form>
</template>
