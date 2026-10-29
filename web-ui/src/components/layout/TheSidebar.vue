<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { 
  LayoutDashboard, 
  ListTodo, 
  Users, 
  Layers, 
  Terminal,
  Settings2,
  SlidersHorizontal,
  ChevronRight
} from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

const emit = defineEmits<{
  (event: 'navigate'): void
}>()
const { t } = useI18n()

const navItems = computed(() => [
  { to: '/dashboard', label: t('sidebar.dashboard'), icon: LayoutDashboard },
  { to: '/tasks', label: t('sidebar.tasks'), icon: ListTodo },
  { to: '/accounts', label: t('sidebar.accounts'), icon: Users },
  { to: '/results', label: t('sidebar.results'), icon: Layers },
  { to: '/logs', label: t('sidebar.logs'), icon: Terminal },
  { to: '/ops', label: t('sidebar.ops'), icon: SlidersHorizontal },
  { to: '/settings', label: t('sidebar.settings'), icon: Settings2 },
])
</script>

<template>
  <nav class="space-y-1">
    <RouterLink
      v-for="item in navItems"
      :key="item.to"
      :to="item.to"
      v-slot="{ isActive }"
      class="group relative flex items-center px-3 py-2.5 rounded-xl transition-all duration-200 overflow-hidden"
      @click="emit('navigate')"
    >
      <!-- Active Background Effect -->
      <div 
        v-if="isActive" 
        class="absolute inset-0 bg-gradient-to-r from-primary/10 to-transparent z-0"
      ></div>
      <div 
        v-if="isActive" 
        class="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-primary rounded-r-full"
      ></div>

      <div class="relative z-10 flex items-center w-full">
        <component
          :is="item.icon"
          class="w-5 h-5 mr-2.5 shrink-0 transition-colors"
          :class="isActive ? 'text-primary' : 'text-slate-400 group-hover:text-slate-600'"
        />
        <span
          class="text-sm font-bold leading-snug transition-colors max-w-[112px] break-words"
          :class="isActive ? 'text-slate-900' : 'text-slate-500 group-hover:text-slate-700'"
        >
          {{ item.label }}
        </span>
        <ChevronRight
          class="ml-1.5 w-4 h-4 shrink-0 text-primary transition-opacity"
          :class="isActive ? 'opacity-100' : 'opacity-0'"
        />
      </div>
    </RouterLink>
  </nav>
</template>

<style scoped>
.router-link-active {
  background-color: transparent !important;
}
</style>
