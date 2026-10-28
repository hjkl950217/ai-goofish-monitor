<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getOpsConfig, saveOpsConfig, listTraces, type TraceDir } from '@/api/ops'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { toast } from '@/components/ui/toast'
const { t } = useI18n()

const traceEnabled = ref(false)
const traceDir = ref('/tmp/agm-trace')
const debugCapture = ref('')
const isSaving = ref(false)
const isLoading = ref(false)
const traces = ref<TraceDir[]>([])

async function loadConfig() {
  try {
    const cfg = await getOpsConfig()
    const enabled = (cfg.AGM_BROWSER_TRACE || '').toLowerCase()
    traceEnabled.value = ['1', 'true', 'yes', 'on'].includes(enabled)
    traceDir.value = cfg.AGM_TRACE_DIR || '/tmp/agm-trace'
    debugCapture.value = cfg.AGM_DEBUG_CAPTURE || ''
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
  isSaving.value = true
  try {
    await saveOpsConfig({
      AGM_BROWSER_TRACE: traceEnabled.value ? 'true' : 'false',
      AGM_TRACE_DIR: traceDir.value.trim(),
      AGM_DEBUG_CAPTURE: debugCapture.value.trim(),
    })
    toast({ title: t('ops.saved') })
    await Promise.all([loadConfig(), loadTraces()])
  } catch (e) {
    toast({ title: t('ops.saveFailed'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isSaving.value = false
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
