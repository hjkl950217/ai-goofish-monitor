<script setup lang="ts">
import { onMounted } from "vue"
import type { SelectContentEmits, SelectContentProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import {
  SelectContent,
  SelectPortal,
  SelectViewport,
  useForwardPropsEmits,
} from "reka-ui"
import { cn } from "@/lib/utils"
import { SelectScrollDownButton, SelectScrollUpButton } from "."

defineOptions({
  inheritAttrs: false,
})

const props = withDefaults(
  defineProps<SelectContentProps & { class?: HTMLAttributes["class"] }>(),
  {
    position: "popper",
  },
)
const emits = defineEmits<SelectContentEmits>()

const delegatedProps = reactiveOmit(props, "class")

const forwarded = useForwardPropsEmits(delegatedProps, emits)

// reka 默认锁页面滚动：给 body 加 paddingRight 并把 overflow 设为 hidden。
// 有滚动条的页面一开下拉，整页就横移一次（看起来像抖动），滚轮也跟着失效。
// 关掉滚动锁，改成滚轮落在下拉外面时直接收起。
function handleWheel(event: WheelEvent) {
  const listbox = document.querySelector('[role="listbox"][data-state="open"]')
  if (!listbox) return
  const target = event.target
  if (target instanceof Node && listbox.contains(target)) return
  // Escape 要能冒泡到 window，reka 的按键监听挂在 window 上
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))
}

let wheelBound = false
onMounted(() => {
  if (wheelBound) return
  wheelBound = true
  window.addEventListener("wheel", handleWheel, { passive: true })
})
</script>

<template>
  <SelectPortal>
    <SelectContent
      v-bind="{ ...forwarded, ...$attrs }"
      :body-lock="false"
      :side-offset="position === 'popper' ? 4 : 0"
      :class="cn(
        'relative z-50 max-h-96 min-w-32 overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        props.class,
      )
      "
    >
      <SelectScrollUpButton />
      <SelectViewport :class="cn('p-1', position === 'popper' && 'h-[--reka-select-trigger-height] w-full min-w-[--reka-select-trigger-width]')">
        <slot />
      </SelectViewport>
      <SelectScrollDownButton />
    </SelectContent>
  </SelectPortal>
</template>
