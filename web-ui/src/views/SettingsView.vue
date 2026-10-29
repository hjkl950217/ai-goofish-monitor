<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useSettings } from '@/composables/useSettings'
import type { NotificationSettingsUpdate, NotificationTestResponse } from '@/api/settings'
import { getNotificationHistory, type NotificationHistoryItem } from '@/api/settings'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/components/ui/toast'
import { getPromptContent, listPrompts, updatePrompt } from '@/api/prompts'
import { getModelCheckStatus, startModelCheck, cancelModelCheck } from '@/api/modelCheck'
import type { ModelCheckStatus } from '@/api/modelCheck'
import NotificationSettingsPanel from '@/components/settings/NotificationSettingsPanel.vue'
import RotationSettingsPanel from '@/components/settings/RotationSettingsPanel.vue'
import { getRawConfig, saveRawConfig } from '@/api/configFile'
import { validateJsonc } from '@/lib/jsonc'
const { t } = useI18n()

function formatBytes(bytes?: number | null) {
  if (!bytes || bytes < 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${index === 0 ? value : value.toFixed(1)} ${units[index]}`
}

function formatNearestExpiry(timestamp?: number | null) {
  if (!timestamp) return t('settings.status.noAccounts')
  const days = Math.ceil((timestamp * 1000 - Date.now()) / 86400000)
  if (days <= 0) return t('accounts.list.expiryExpired')
  return t('settings.status.nearestExpiry', { days })
}

function expiryTone(timestamp?: number | null) {
  if (!timestamp) return 'text-gray-500'
  const days = Math.ceil((timestamp * 1000 - Date.now()) / 86400000)
  if (days <= 3) return 'text-rose-600 font-semibold'
  if (days <= 7) return 'text-amber-600'
  return 'text-green-700'
}

const {
  notificationSettings,
  aiSettings,
  rotationSettings,
  systemStatus,
  isLoading,
  isSaving,
  isReady,
  error,
  refreshStatus,
  saveNotificationSettings,
  testNotification,
  saveAiSettings,
  saveRotationSettings,
  testAiConnection
} = useSettings()

const activeTab = ref('ai')
const route = useRoute()
const validTabs = new Set(['notifications', 'ai', 'rotation', 'status', 'prompts', 'config'])

const promptFiles = ref<string[]>([])
const selectedPrompt = ref<string | null>(null)
const promptContent = ref('')
const isPromptLoading = ref(false)
const isPromptSaving = ref(false)
const promptError = ref<string | null>(null)

const rawConfig = ref('')
const rawConfigPath = ref('')
const rawConfigError = ref('')
const isRawConfigLoading = ref(false)
const isRawConfigSaving = ref(false)

async function loadRawConfig() {
  isRawConfigLoading.value = true
  rawConfigError.value = ''
  try {
    const data = await getRawConfig()
    rawConfig.value = data.content
    rawConfigPath.value = data.path
  } catch (e) {
    rawConfigError.value = (e as Error).message
  } finally {
    isRawConfigLoading.value = false
  }
}

async function handleSaveRawConfig() {
  const message = validateJsonc(rawConfig.value)
  if (message) {
    rawConfigError.value = message
    return
  }
  isRawConfigSaving.value = true
  rawConfigError.value = ''
  try {
    await saveRawConfig(rawConfig.value)
    notifySuccess(t('settings.configFile.saved'))
    await loadRawConfig()
  } catch (e) {
    rawConfigError.value = (e as Error).message
  } finally {
    isRawConfigSaving.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'config' && !rawConfig.value && !isRawConfigLoading.value) {
    void loadRawConfig()
  }
})

function notifySuccess(title: string, description?: string) {
  toast({ title, description })
}

function notifyError(title: string, description?: string) {
  toast({ title, description, variant: 'destructive' })
}

const notificationHistory = ref<NotificationHistoryItem[]>([])

async function loadNotificationHistory() {
  try {
    const data = await getNotificationHistory(30)
    notificationHistory.value = data.records ?? []
  } catch {
    notificationHistory.value = []
  }
}

async function handleSaveNotifications(payload: NotificationSettingsUpdate) {
  try {
    await saveNotificationSettings(payload)
    notifySuccess(t('settings.notifications.saved'))
  } catch (e) {
    notifyError(t('settings.notifications.saveFailed'), (e as Error).message)
  }
}

async function handleTestNotification(payload: {
  channel?: string
  settings: NotificationSettingsUpdate
}): Promise<NotificationTestResponse> {
  try {
    const result = await testNotification(payload)
    await loadNotificationHistory()
    return result
  } catch (e) {
    notifyError(t('settings.notifications.testFailed'), (e as Error).message)
    throw e
  }
}

async function handleSaveAi() {
  try {
    await saveAiSettings()
    notifySuccess(t('settings.ai.saved'))
  } catch (e) {
    notifyError(t('settings.ai.saveFailed'), (e as Error).message)
  }
}

async function handleSaveRotation() {
  try {
    await saveRotationSettings()
    notifySuccess(t('settings.rotation.saved'))
  } catch (e) {
    notifyError(t('settings.rotation.saveFailed'), (e as Error).message)
  }
}

async function handleTestAi() {
  try {
    const res = await testAiConnection()
    notifySuccess(t('settings.ai.testSuccess'), res.message)
  } catch (e) {
    notifyError(t('settings.ai.testFailed'), (e as Error).message)
  }
}

async function handleTestModelCheck() {
  try {
    const res = await testAiConnection('model_check')
    notifySuccess(t('settings.ai.testSuccess'), res.message)
  } catch (e) {
    notifyError(t('settings.ai.testFailed'), (e as Error).message)
  }
}

// ---------------------------------------------------------------- 历史型号校验

const modelCheckStatus = ref<ModelCheckStatus | null>(null)
const isModelCheckBusy = ref(false)
let pollTimer: number | null = null

function schedulePoll() {
  if (pollTimer !== null) return
  pollTimer = window.setTimeout(async () => {
    pollTimer = null
    await refreshModelCheckStatus()
  }, 2000)
}

async function refreshModelCheckStatus() {
  try {
    modelCheckStatus.value = await getModelCheckStatus()
    if (modelCheckStatus.value.running) schedulePoll()
  } catch {
    // 进度查询失败不打扰用户，下一次轮询再试
  }
}

async function handleStartModelCheck() {
  isModelCheckBusy.value = true
  try {
    const res = await startModelCheck()
    modelCheckStatus.value = res.status
    schedulePoll()
  } catch (e) {
    notifyError(t('settings.ai.modelCheck.historyStart'), (e as Error).message)
  } finally {
    isModelCheckBusy.value = false
  }
}

async function handleCancelModelCheck() {
  try {
    const res = await cancelModelCheck()
    modelCheckStatus.value = res.status
  } catch (e) {
    notifyError(t('settings.ai.modelCheck.historyCancel'), (e as Error).message)
  }
}

onMounted(() => {
  refreshModelCheckStatus()
  loadNotificationHistory()
})
onUnmounted(() => {
  if (pollTimer !== null) window.clearTimeout(pollTimer)
})

async function fetchPrompts() {
  isPromptLoading.value = true
  promptError.value = null
  try {
    const files = await listPrompts()
    promptFiles.value = files

    if (selectedPrompt.value && files.includes(selectedPrompt.value)) {
      return
    }

    const lastSelected = localStorage.getItem('lastSelectedPrompt')
    if (lastSelected && files.includes(lastSelected)) {
      selectedPrompt.value = lastSelected
      return
    }

    selectedPrompt.value = files[0] || null
  } catch (e) {
    promptError.value = (e as Error).message || t('settings.prompts.promptListFailed')
  } finally {
    isPromptLoading.value = false
  }
}

async function handleSavePrompt() {
  if (!selectedPrompt.value) {
    notifyError(t('settings.prompts.selectPromptFile'))
    return
  }
  isPromptSaving.value = true
  try {
    const res = await updatePrompt(selectedPrompt.value, promptContent.value)
    notifySuccess(t('settings.prompts.saveSuccess'), res.message)
  } catch (e) {
    notifyError(t('settings.prompts.saveFailed'), (e as Error).message)
  } finally {
    isPromptSaving.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'prompts') {
    fetchPrompts()
  }
})

watch(
  () => route.query.tab,
  (tab) => {
    if (typeof tab === 'string' && validTabs.has(tab)) {
      activeTab.value = tab
    }
  },
  { immediate: true }
)

watch(selectedPrompt, async (value) => {
  if (!value) {
    promptContent.value = ''
    return
  }
  localStorage.setItem('lastSelectedPrompt', value)
  isPromptLoading.value = true
  promptError.value = null
  try {
    const data = await getPromptContent(value)
    promptContent.value = data.content
  } catch (e) {
    promptError.value = (e as Error).message || t('settings.prompts.promptContentFailed')
  } finally {
    isPromptLoading.value = false
  }
})
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-gray-800 mb-6">{{ t('settings.title') }}</h1>
    
    <div v-if="error" class="app-alert-error mb-4" role="alert">
      {{ error.message }}
    </div>

    <Tabs v-model="activeTab" class="w-full">
      <TabsList class="mb-4 flex w-full flex-nowrap justify-start gap-1 overflow-x-auto rounded-xl bg-slate-100 p-1">
        <TabsTrigger class="shrink-0" value="ai">{{ t('settings.tabs.ai') }}</TabsTrigger>
        <TabsTrigger class="shrink-0" value="rotation">{{ t('settings.tabs.rotation') }}</TabsTrigger>
        <TabsTrigger class="shrink-0" value="notifications">{{ t('settings.tabs.notifications') }}</TabsTrigger>
        <TabsTrigger class="shrink-0" value="status">{{ t('settings.tabs.status') }}</TabsTrigger>
        <TabsTrigger class="shrink-0" value="prompts">{{ t('settings.tabs.prompts') }}</TabsTrigger>
        <TabsTrigger class="shrink-0" value="config">{{ t('settings.tabs.configFile') }}</TabsTrigger>
      </TabsList>

      <!-- AI Tab -->
      <TabsContent value="ai">
        <Card>
          <CardHeader>
            <CardTitle>{{ t('settings.ai.title') }}</CardTitle>
            <CardDescription>{{ t('settings.ai.description') }}</CardDescription>
          </CardHeader>
          <CardContent v-if="isReady" class="space-y-4">
            <div class="grid gap-2">
              <Label>API Base URL</Label>
              <Input v-model="aiSettings.OPENAI_BASE_URL" placeholder="https://api.openai.com/v1" />
            </div>
            <div class="grid gap-2">
              <Label>API Key</Label>
              <Input
                v-model="aiSettings.OPENAI_API_KEY"
                type="password"
                :placeholder="t('settings.ai.keyPlaceholder')"
              />
              <p class="text-xs text-gray-500">
                {{ systemStatus?.env_file.openai_api_key_set ? t('settings.ai.keyConfigured') : t('settings.ai.keyMissing') }}
              </p>
            </div>
            <div class="grid gap-2">
              <Label>{{ t('settings.ai.modelName') }}</Label>
              <Input v-model="aiSettings.OPENAI_MODEL_NAME" placeholder="gpt-3.5-turbo" />
            </div>
            <div class="grid gap-2">
              <Label>{{ t('settings.ai.proxy') }}</Label>
              <Input v-model="aiSettings.PROXY_URL" placeholder="http://127.0.0.1:7890" />
            </div>

            <!-- 型号判断模型 -->
            <div class="space-y-4 border-t pt-4">
              <div>
                <h3 class="font-medium">{{ t('settings.ai.modelCheck.title') }}</h3>
                <p class="mt-1 text-xs text-gray-500">{{ t('settings.ai.modelCheck.description') }}</p>
              </div>
              <label class="flex items-center gap-2 text-sm">
                <input v-model="aiSettings.MODEL_CHECK_ENABLED" type="checkbox" class="h-4 w-4" />
                {{ t('settings.ai.modelCheck.enabled') }}
              </label>
              <p v-if="aiSettings.MODEL_CHECK_PROMPT_EXISTS === false" class="text-xs text-amber-600">
                {{ t('settings.ai.modelCheck.promptMissing') }}
              </p>
              <div class="grid gap-2">
                <Label>{{ t('settings.ai.modelCheck.baseUrl') }}</Label>
                <Input v-model="aiSettings.MODEL_CHECK_BASE_URL" placeholder="留空复用上面的地址" />
              </div>
              <div class="grid gap-2">
                <Label>{{ t('settings.ai.modelCheck.apiKey') }}</Label>
                <Input v-model="aiSettings.MODEL_CHECK_API_KEY" type="password" :placeholder="t('settings.ai.keyPlaceholder')" />
                <p class="text-xs text-gray-500">
                  {{ aiSettings.MODEL_CHECK_API_KEY_SET ? t('settings.ai.modelCheck.apiKeySet') : t('settings.ai.modelCheck.apiKeyMissing') }}
                </p>
              </div>
              <div class="grid gap-2">
                <Label>{{ t('settings.ai.modelCheck.modelName') }}</Label>
                <Input v-model="aiSettings.MODEL_CHECK_MODEL_NAME" placeholder="留空复用上面的模型" />
              </div>
              <div class="grid gap-2">
                <Label>{{ t('settings.ai.modelCheck.proxy') }}</Label>
                <Input v-model="aiSettings.MODEL_CHECK_PROXY_URL" placeholder="留空复用上面的代理" />
              </div>
              <div class="grid gap-2">
                <Label>{{ t('settings.ai.modelCheck.prefilter') }}</Label>
                <Input v-model="aiSettings.MODEL_CHECK_PREFILTER_REGEX" placeholder="M1\s*[-‑_]?\s*100" />
                <p class="text-xs text-gray-500">{{ t('settings.ai.modelCheck.prefilterHint') }}</p>
              </div>
            </div>
          </CardContent>
          <CardContent v-else class="py-8 text-sm text-gray-500">
            {{ t('settings.ai.loading') }}
          </CardContent>
          <CardFooter v-if="isReady" class="flex flex-wrap gap-2">
            <Button variant="outline" @click="handleTestAi" :disabled="isSaving">{{ t('settings.ai.testConnection') }}</Button>
            <Button variant="outline" @click="handleTestModelCheck" :disabled="isSaving">{{ t('settings.ai.modelCheck.test') }}</Button>
            <Button @click="handleSaveAi" :disabled="isSaving">{{ t('settings.ai.save') }}</Button>
          </CardFooter>
        </Card>

        <Card class="mt-4">
          <CardHeader>
            <CardTitle>{{ t('settings.ai.modelCheck.historyTitle') }}</CardTitle>
            <CardDescription>{{ t('settings.ai.modelCheck.historyDescription') }}</CardDescription>
          </CardHeader>
          <CardContent class="space-y-3">
            <div class="flex flex-wrap items-center gap-3 text-sm">
              <span :class="modelCheckStatus?.running ? 'font-medium text-amber-600' : 'text-slate-500'">
                {{ modelCheckStatus?.running ? t('settings.ai.modelCheck.historyRunning') : t('settings.ai.modelCheck.historyIdle') }}
              </span>
              <span v-if="modelCheckStatus" class="text-slate-500">
                {{ modelCheckStatus.done }}/{{ modelCheckStatus.total }}
                · 匹配 {{ modelCheckStatus.matched }}
                · 删除 {{ modelCheckStatus.removed }}
                · 未判出 {{ modelCheckStatus.failed }}
              </span>
            </div>
            <p v-if="modelCheckStatus?.message" class="text-xs text-slate-500">{{ modelCheckStatus.message }}</p>
            <div
              v-if="modelCheckStatus?.recent?.length"
              class="max-h-40 overflow-y-auto rounded-lg bg-slate-50 p-2 text-xs text-slate-600"
            >
              <p v-for="(line, idx) in modelCheckStatus.recent.slice(-10)" :key="idx">{{ line }}</p>
            </div>
          </CardContent>
          <CardFooter class="flex gap-2">
            <Button v-if="!modelCheckStatus?.running" :disabled="isModelCheckBusy" @click="handleStartModelCheck">
              {{ t('settings.ai.modelCheck.historyStart') }}
            </Button>
            <Button v-else variant="outline" @click="handleCancelModelCheck">
              {{ t('settings.ai.modelCheck.historyCancel') }}
            </Button>
          </CardFooter>
        </Card>
      </TabsContent>

      <!-- Rotation Tab -->
      <TabsContent value="rotation">
        <RotationSettingsPanel
          :settings="rotationSettings"
          :is-ready="isReady"
          :is-saving="isSaving"
          @save="handleSaveRotation"
        />
      </TabsContent>

      <!-- Notifications Tab -->
      <TabsContent value="notifications">
        <NotificationSettingsPanel
          :settings="notificationSettings"
          :is-ready="isReady"
          :is-saving="isSaving"
          :save-settings="handleSaveNotifications"
          :test-settings="handleTestNotification"
        />

        <Card class="mt-4">
          <CardHeader>
            <CardTitle>{{ t('settings.notificationHistory.title') }}</CardTitle>
            <CardDescription>{{ t('settings.notificationHistory.description') }}</CardDescription>
          </CardHeader>
          <CardContent>
            <p v-if="notificationHistory.length === 0" class="text-sm text-gray-500">
              {{ t('settings.notificationHistory.empty') }}
            </p>
            <ul v-else class="divide-y divide-slate-100">
              <li
                v-for="(item, index) in notificationHistory"
                :key="`${item.time}-${item.channel}-${index}`"
                class="flex items-center justify-between gap-3 py-2 text-sm"
              >
                <span class="min-w-0 truncate">
                  <span class="font-medium">{{ item.label || item.channel }}</span>
                  <span class="text-gray-500"> · {{ item.title || '—' }}</span>
                  <span v-if="item.is_test" class="ml-1 rounded bg-slate-100 px-1 text-[10px] text-slate-500">
                    {{ t('settings.notificationHistory.test') }}
                  </span>
                </span>
                <span class="flex shrink-0 items-center gap-2">
                  <span class="text-xs text-gray-400">{{ item.time.replace('T', ' ') }}</span>
                  <span
                    class="text-xs font-bold"
                    :class="item.success ? 'text-green-600' : 'text-rose-600'"
                    :title="item.message"
                  >
                    {{ item.success ? t('settings.notificationHistory.sent') : t('settings.notificationHistory.failed') }}
                  </span>
                </span>
              </li>
            </ul>
          </CardContent>
        </Card>
      </TabsContent>

      <!-- Status Tab -->
      <TabsContent value="status">
        <Card>
          <CardHeader>
            <CardTitle>{{ t('settings.status.title') }}</CardTitle>
            <div class="flex justify-end">
                <Button variant="outline" size="sm" @click="refreshStatus" :disabled="isLoading">{{ t('settings.status.refresh') }}</Button>
            </div>
          </CardHeader>
          <CardContent>
            <div v-if="systemStatus" class="space-y-6">
              <!-- Scraper Process Status -->
              <div class="flex items-center justify-between border-b pb-4">
                <div>
                  <h3 class="font-medium">{{ t('settings.status.scraper') }}</h3>
                  <p class="text-sm text-gray-500">{{ t('settings.status.scraperDescription') }}</p>
                </div>
                <span :class="systemStatus.scraper_running ? 'text-green-600 font-bold bg-green-50 px-3 py-1 rounded-full' : 'text-gray-500 bg-gray-100 px-3 py-1 rounded-full'">
                  {{ systemStatus.scraper_running ? t('common.running') : t('common.idle') }}
                </span>
              </div>

              <!-- Env Config Status -->
              <div>
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h3 class="font-medium">{{ t('settings.status.env') }}</h3>
                        <p class="text-sm text-gray-500">{{ t('settings.status.envDescription') }}</p>
                    </div>
                    <span :class="systemStatus.env_file.exists ? 'text-green-600 font-bold bg-green-50 px-3 py-1 rounded-full' : 'text-red-600 font-bold bg-red-50 px-3 py-1 rounded-full'">
                        {{ systemStatus.env_file.exists ? t('settings.status.loaded') : t('settings.status.missing') }}
                    </span>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="p-3 border rounded-lg" :class="systemStatus.env_file.openai_api_key_set ? 'bg-green-50 border-green-200' : 'bg-yellow-50 border-yellow-200'">
                        <div class="flex justify-between items-center">
                            <span class="font-medium text-sm">OpenAI API Key</span>
                            <span class="text-xs font-bold" :class="systemStatus.env_file.openai_api_key_set ? 'text-green-700' : 'text-yellow-700'">
                                {{ systemStatus.env_file.openai_api_key_set ? t('common.active') : t('common.inactive') }}
                            </span>
                        </div>
                    </div>
                    
                    <div class="p-3 border rounded-lg" :class="systemStatus.configured_notification_channels?.length ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'">
                         <div class="flex justify-between items-center">
                            <span class="font-medium text-sm">{{ t('settings.status.channels') }}</span>
                             <span class="text-xs font-bold" :class="systemStatus.configured_notification_channels?.length ? 'text-green-700' : 'text-gray-500'">
                                {{ systemStatus.configured_notification_channels?.length ? t('common.active') : t('common.inactive') }}
                            </span>
                        </div>
                         <div class="text-xs text-gray-500 mt-1">
                            {{ systemStatus.configured_notification_channels?.join(', ') || t('settings.status.none') }}
                        </div>
                    </div>
                </div>
              </div>

              <!-- Runtime, Storage & Accounts -->
              <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div class="p-3 border rounded-lg">
                  <div class="flex justify-between items-center">
                    <span class="font-medium text-sm">{{ t('settings.status.version') }}</span>
                    <span class="text-xs font-bold text-gray-600">{{ systemStatus.app?.version || t('settings.status.unknown') }}</span>
                  </div>
                  <p class="mt-1 text-xs text-gray-500">
                    {{ t('settings.status.uptime', { hours: Math.floor((systemStatus.app?.uptime_seconds || 0) / 3600) }) }}
                  </p>
                  <p v-if="systemStatus.app?.frontend_built_at" class="text-xs text-gray-500">
                    {{ t('settings.status.frontendBuilt') }}：{{ systemStatus.app.frontend_built_at.replace('T', ' ') }}
                  </p>
                </div>

                <div class="p-3 border rounded-lg">
                  <div class="flex justify-between items-center">
                    <span class="font-medium text-sm">{{ t('settings.status.database') }}</span>
                    <span class="text-xs font-bold text-gray-600">{{ formatBytes(systemStatus.database?.size_bytes) }}</span>
                  </div>
                  <p class="mt-1 break-all text-xs text-gray-500">{{ systemStatus.database?.path }}</p>
                </div>

                <div class="p-3 border rounded-lg">
                  <div class="flex justify-between items-center">
                    <span class="font-medium text-sm">{{ t('settings.status.backups') }}</span>
                    <span class="text-xs font-bold" :class="systemStatus.backups?.count ? 'text-green-700' : 'text-amber-700'">
                      {{ systemStatus.backups?.count
                        ? t('settings.status.backupsCount', { count: systemStatus.backups.count })
                        : t('settings.status.noBackup') }}
                    </span>
                  </div>
                  <p v-if="systemStatus.backups?.latest" class="mt-1 break-all text-xs text-gray-500">
                    {{ t('settings.status.backupsLatest') }}：{{ systemStatus.backups.latest }}
                  </p>
                </div>

                <div class="p-3 border rounded-lg">
                  <div class="flex justify-between items-center">
                    <span class="font-medium text-sm">{{ t('settings.status.accounts') }}</span>
                    <span class="text-xs font-bold text-gray-600">
                      {{ t('settings.status.accountsCount', { count: systemStatus.accounts?.count ?? 0 }) }}
                    </span>
                  </div>
                  <p class="mt-1 text-xs" :class="expiryTone(systemStatus.accounts?.nearest_expires_at)">
                    {{ formatNearestExpiry(systemStatus.accounts?.nearest_expires_at) }}
                  </p>
                </div>
              </div>

              <p v-if="systemStatus.disk" class="text-xs text-gray-500">
                {{ t('settings.status.diskUsage', {
                  percent: systemStatus.disk.used_percent,
                  free: formatBytes(systemStatus.disk.free_bytes),
                }) }}
              </p>
            </div>
            <div v-else class="text-center py-8 text-gray-500">
                {{ t('settings.status.fetching') }}
            </div>
          </CardContent>
        </Card>
      </TabsContent>

      <!-- Prompt Tab -->
      <TabsContent value="prompts">
        <Card>
          <CardHeader>
            <CardTitle>{{ t('settings.prompts.title') }}</CardTitle>
            <CardDescription>{{ t('settings.prompts.description') }}</CardDescription>
          </CardHeader>
          <CardContent class="space-y-4">
            <div v-if="promptError" class="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded">
              {{ promptError }}
            </div>

            <div class="grid gap-2">
              <Label>{{ t('settings.prompts.selectFile') }}</Label>
              <Select
                :model-value="selectedPrompt || undefined"
                @update:model-value="(value) => selectedPrompt = value as string"
              >
                <SelectTrigger>
                  <SelectValue :placeholder="t('settings.prompts.placeholder')" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="file in promptFiles" :key="file" :value="file">
                    {{ file }}
                  </SelectItem>
                </SelectContent>
              </Select>
              <p v-if="!promptFiles.length && !isPromptLoading" class="text-sm text-gray-500">
                {{ t('settings.prompts.none') }}
              </p>
            </div>

            <div class="grid gap-2">
              <Label>{{ t('settings.prompts.content') }}</Label>
              <Textarea
                v-model="promptContent"
                class="min-h-[240px]"
                :disabled="!selectedPrompt || isPromptLoading"
                :placeholder="t('settings.prompts.contentPlaceholder')"
              />
            </div>
          </CardContent>
          <CardFooter>
            <Button :disabled="isPromptSaving || !selectedPrompt" @click="handleSavePrompt">
              {{ isPromptSaving ? t('common.saving') : t('settings.prompts.save') }}
            </Button>
          </CardFooter>
        </Card>
      </TabsContent>

      <!-- Config File Tab -->
      <TabsContent value="config">
        <Card>
          <CardHeader>
            <CardTitle>{{ t('settings.configFile.title') }}</CardTitle>
            <CardDescription>{{ t('settings.configFile.description') }}</CardDescription>
          </CardHeader>
          <CardContent class="space-y-3">
            <div
              v-if="rawConfigError"
              class="whitespace-pre-wrap rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
            >
              {{ rawConfigError }}
            </div>
            <p class="font-mono text-xs text-gray-500">
              {{ rawConfigPath || t('settings.configFile.pathUnknown') }}
            </p>
            <Textarea
              v-model="rawConfig"
              class="min-h-[420px] font-mono text-xs"
              spellcheck="false"
              :disabled="isRawConfigLoading"
              :placeholder="t('settings.configFile.placeholder')"
            />
            <p class="text-xs text-gray-500">{{ t('settings.configFile.hint') }}</p>
          </CardContent>
          <CardFooter class="flex gap-2">
            <Button variant="outline" :disabled="isRawConfigLoading" @click="loadRawConfig">
              {{ t('settings.configFile.reload') }}
            </Button>
            <Button :disabled="isRawConfigSaving || isRawConfigLoading" @click="handleSaveRawConfig">
              {{ isRawConfigSaving ? t('common.saving') : t('settings.configFile.save') }}
            </Button>
          </CardFooter>
        </Card>
      </TabsContent>
    </Tabs>
  </div>
</template>
