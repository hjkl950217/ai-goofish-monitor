<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import TheHeader from '@/components/layout/TheHeader.vue'
import TheSidebar from '@/components/layout/TheSidebar.vue'
import { useMobileNav } from '@/composables/useMobileNav'

const { isMobileNavOpen, closeMobileNav } = useMobileNav()
const { t } = useI18n()
const route = useRoute()

// 结果页要铺满宽屏，其余页面维持原来的居中宽度，避免表单被拉成整屏长条
const isWide = computed(() => route.meta.wide === true)
</script>

<template>
  <div class="relative min-h-screen w-full flex flex-col bg-background selection:bg-primary/15">
    <a
      href="#main-content"
      class="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[120] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-primary-foreground"
    >
      {{ t('common.skipToContent') }}
    </a>

    <!-- 背景装饰渐变 -->
    <div aria-hidden="true" class="fixed inset-0 pointer-events-none overflow-hidden">
      <div class="absolute -top-[10%] -left-[10%] h-[40%] w-[40%] rounded-full bg-primary/5 blur-[120px] animate-pulse motion-reduce:animate-none"></div>
      <div class="absolute top-[20%] -right-[5%] w-[30%] h-[35%] rounded-full bg-blue-400/5 blur-[100px]"></div>
      <div class="absolute -bottom-[10%] left-[20%] w-[35%] h-[35%] rounded-full bg-emerald-400/5 blur-[100px]"></div>
    </div>

    <!-- Header -->
    <TheHeader class="sticky top-0 z-50 glass" />

    <transition name="mobile-nav">
      <div v-if="isMobileNavOpen" class="fixed inset-0 z-[90] md:hidden">
        <button
          type="button"
          class="absolute inset-0 bg-slate-950/25 backdrop-blur-[2px]"
          :aria-label="t('common.close')"
          @click="closeMobileNav"
        />
        <aside class="relative h-full w-72 border-r border-slate-200/60 bg-white/90 p-4 shadow-2xl backdrop-blur-xl">
          <TheSidebar class="pt-16" @navigate="closeMobileNav" />
        </aside>
      </div>
    </transition>

    <div class="flex flex-grow relative z-10">
      <!-- Sidebar -->
      <aside class="hidden md:block w-fit max-w-[208px] flex-shrink-0 border-r border-slate-200/60 bg-white/40 backdrop-blur-sm">
        <TheSidebar class="sticky top-16 h-[calc(100vh-4rem)] p-3" />
      </aside>

      <!-- Main Content Area -->
      <main id="main-content" tabindex="-1" class="flex-grow overflow-x-clip px-2 py-4 focus:outline-none md:py-6">
        <div class="animate-fade-in" :class="{ 'mx-auto max-w-7xl': !isWide }">
          <RouterView v-slot="{ Component }">
            <transition name="page" mode="out-in">
              <component :is="Component" />
            </transition>
          </RouterView>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.page-enter-active,
.page-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.mobile-nav-enter-active,
.mobile-nav-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.mobile-nav-enter-from,
.mobile-nav-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}

@media (prefers-reduced-motion: reduce) {
  .page-enter-active,
  .page-leave-active,
  .mobile-nav-enter-active,
  .mobile-nav-leave-active {
    transition: none;
  }

  .page-enter-from,
  .page-leave-to,
  .mobile-nav-enter-from,
  .mobile-nav-leave-to {
    opacity: 1;
    transform: none;
  }
}
</style>
