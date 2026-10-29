<script setup lang="ts">
import { Globe } from 'lucide-vue-next'
import { useLocale } from '@/i18n'
import { useI18n } from 'vue-i18n'

const { locale, toggleLocale, locales } = useLocale()
const { t } = useI18n()
</script>

<template>
  <div
    class="inline-flex items-center gap-1 rounded-full border border-slate-200/80 bg-white/80 p-1 shadow-sm backdrop-blur"
    :aria-label="t('locale.switchLabel')"
    role="group"
  >
    <span class="hidden pl-2 text-slate-400 sm:inline-flex">
      <Globe class="h-4 w-4" />
    </span>
    <button
      v-for="option in locales"
      :key="option.code"
      type="button"
      class="rounded-full px-2.5 py-1 text-[11px] font-bold transition-colors sm:px-3"
      :class="locale === option.code ? 'bg-primary text-white shadow-sm' : 'text-slate-500 hover:bg-slate-100'"
      @click="toggleLocale(option.code)"
    >
      <span class="sm:hidden">{{ option.shortLabel }}</span>
      <span class="hidden sm:inline">{{ option.label }}</span>
    </button>
  </div>
</template>
