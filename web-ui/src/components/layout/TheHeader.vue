<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Button } from '@/components/ui/button'
import DashboardTaskSearch from '@/components/layout/DashboardTaskSearch.vue'
import LocaleToggle from '@/components/layout/LocaleToggle.vue'
import { 
  Zap, 
  Bell, 
  UserCircle,
  HelpCircle,
  Menu
} from 'lucide-vue-next'
import Badge from '@/components/ui/badge/Badge.vue'
import { useMobileNav } from '@/composables/useMobileNav'
import { useWebSocket } from '@/composables/useWebSocket'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const { toggleMobileNav } = useMobileNav()
const { t } = useI18n()

const { isConnected } = useWebSocket()
const connectionLabel = computed(() => (
  isConnected.value ? t('sidebar.backendConnected') : t('sidebar.backendConnecting')
))
const connectionTone = computed(() =>
  isConnected.value
    ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]'
    : 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.45)]'
)

function goAccounts() {
  router.push('/accounts')
}

function goNotifications() {
  router.push({ name: 'Settings', query: { tab: 'notifications' } })
}

function goPrompts() {
  router.push({ name: 'Settings', query: { tab: 'prompts' } })
}
</script>

<template>
  <header class="flex items-center justify-between px-6 h-16 bg-white/60 backdrop-blur-md border-b border-slate-200/60 sticky top-0 z-[100]">
    <!-- Brand Logo -->
    <div class="flex items-center gap-3">
    <RouterLink
      to="/dashboard"
      class="flex items-center gap-2 group rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      :aria-label="t('header.goHome')"
    >
      <div class="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shadow-lg shadow-primary/20 transition-transform group-hover:rotate-12">
        <Zap class="w-5 h-5 text-white fill-white" />
      </div>
      <h1 class="text-base sm:text-lg font-black text-slate-800 tracking-tighter whitespace-nowrap">
        AI <span class="text-primary">Xianyu</span> Hunter
      </h1>
      <Badge variant="outline" class="ml-2 text-[10px] font-bold border-primary/20 text-primary bg-primary/5 uppercase tracking-widest hidden sm:flex">
        PRO
      </Badge>
    </RouterLink>
    <div class="hidden items-center gap-1.5 sm:flex" :title="connectionLabel">
      <span class="h-2 w-2 rounded-full" :class="connectionTone"></span>
      <span class="text-xs font-medium text-slate-500">{{ connectionLabel }}</span>
    </div>
    </div>

    <!-- Search -->
    <div class="hidden md:flex flex-grow max-w-md mx-8">
      <DashboardTaskSearch />
    </div>

    <!-- Actions -->
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-2">
        <LocaleToggle />
      </div>

      <div class="flex items-center gap-1 sm:gap-2">
         <Button
           variant="ghost"
           size="icon"
           class="rounded-full text-slate-500 hover:text-primary hover:bg-primary/10"
           :aria-label="t('header.openNotifications')"
           @click="goNotifications"
         >
            <Bell class="w-5 h-5" />
         </Button>
         <Button
           variant="ghost"
           size="icon"
           class="rounded-full text-slate-500 hover:text-primary hover:bg-primary/10"
           :aria-label="t('header.openPrompts')"
           @click="goPrompts"
         >
            <HelpCircle class="w-5 h-5" />
         </Button>
      </div>
      
      <div class="h-6 w-px bg-slate-200 mx-1 hidden sm:block"></div>

      <Button 
        variant="ghost" 
        class="hidden sm:flex items-center gap-2 pl-2 pr-4 rounded-full hover:bg-slate-100 transition-all active:scale-95"
        :aria-label="t('header.openAccounts')"
        @click="goAccounts"
      >
        <div class="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center overflow-hidden border border-slate-300 shadow-sm">
           <UserCircle class="w-6 h-6 text-slate-500" />
        </div>
        <div class="text-left hidden lg:block">
           <p class="text-xs font-black text-slate-700 leading-none mb-0.5">Xianyu Admin</p>
           <p class="text-[10px] text-slate-400 font-medium">{{ t('header.accountManagement') }}</p>
        </div>
      </Button>

      <Button
        variant="ghost"
        size="icon"
        class="md:hidden"
        :aria-label="t('header.openNavigation')"
        @click="toggleMobileNav"
      >
         <Menu class="w-6 h-6 text-slate-700" />
      </Button>
    </div>
  </header>
</template>
