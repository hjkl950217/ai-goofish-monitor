<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { acquireImageSlot, releaseImageSlot } from '@/composables/imageQueue'

const props = defineProps<{ src: string; alt: string }>()

const el = ref<HTMLImageElement>()
const shown = ref('')
const loaded = ref(false)
let granted = false
let released = false
let cancelled = false
let observer: IntersectionObserver | undefined

function release() {
  if (released) return
  // 还在排队就被卸载：等拿到槽位时再还，不能提前减计数
  if (!granted) {
    cancelled = true
    return
  }
  released = true
  releaseImageSlot()
}

function start() {
  acquireImageSlot().then(() => {
    granted = true
    if (cancelled) {
      released = true
      releaseImageSlot()
      return
    }
    shown.value = props.src
  })
}

onMounted(() => {
  // 进入视口附近才去排队：离屏卡片不占下载名额，快速滚动时新卡片不会被前面那批挤住
  observer = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) {
      observer?.disconnect()
      start()
    }
  }, { rootMargin: '400px' })
  if (el.value) observer.observe(el.value)
})

onUnmounted(() => {
  observer?.disconnect()
  release()
})

function finish() {
  loaded.value = true
  release()
}
</script>

<template>
  <img
    ref="el"
    :src="shown || undefined"
    :alt="alt"
    decoding="async"
    :class="loaded ? 'opacity-100' : 'opacity-0'"
    @load="finish"
    @error="finish"
  />
</template>
