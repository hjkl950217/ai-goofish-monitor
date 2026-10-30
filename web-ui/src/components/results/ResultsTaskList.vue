<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

interface FileOption {
  value: string
  label: string
  taskName?: string
}

const props = defineProps<{
  fileOptions: FileOption[]
  selectedFile: string | null
}>()

const emit = defineEmits<{
  (e: 'select', value: string): void
}>()

const { t } = useI18n()

// 同一任务可能有多次抓取的结果文件，列表按任务合并，点任务进最新那份
const groups = computed(() => {
  const map = new Map<string, { taskName: string; latest: string; files: string[] }>()
  for (const option of props.fileOptions) {
    const taskName = option.taskName || t('common.unnamed')
    const group = map.get(taskName)
    if (group) group.files.push(option.value)
    else map.set(taskName, { taskName, latest: option.value, files: [option.value] })
  }
  return [...map.values()]
})
</script>

<template>
  <nav
    class="app-surface hidden w-52 shrink-0 flex-col p-2 lg:flex"
    :aria-label="t('results.taskList.title')"
  >
    <p class="px-3 pb-1 pt-2 text-xs font-semibold text-slate-500">
      {{ t('results.taskList.title') }}
    </p>
    <ul class="space-y-0.5">
      <li v-for="group in groups" :key="group.taskName">
        <button
          type="button"
          class="w-full truncate rounded-xl px-3 py-2 text-left text-sm transition-colors"
          :class="group.files.includes(selectedFile ?? '')
            ? 'bg-primary/10 font-semibold text-primary'
            : 'text-slate-600 hover:bg-slate-100/80'"
          :title="group.taskName"
          :aria-current="group.files.includes(selectedFile ?? '') ? 'page' : undefined"
          @click="emit('select', group.latest)"
        >
          {{ group.taskName }}
        </button>
      </li>
    </ul>
    <p v-if="groups.length === 0" class="px-3 py-2 text-xs text-slate-400">
      {{ t('results.taskList.empty') }}
    </p>
  </nav>
</template>
