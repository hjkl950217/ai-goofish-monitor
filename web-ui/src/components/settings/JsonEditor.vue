<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatJsonc, stripJsonc, validateJsonc } from '@/lib/jsonc'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const { t } = useI18n()

const editor = ref<HTMLTextAreaElement | null>(null)
const highlight = ref<HTMLElement | null>(null)
const gutter = ref<HTMLElement | null>(null)
const caretLayer = ref<HTMLElement | null>(null)

const lineNumbers = computed(() => props.modelValue.replace(/\n$/, '').split('\n').length)

// 行高与 textarea 的 leading-5、上内边距 py-3 对应
const LINE_HEIGHT = 20
const LINE_PADDING = 12

const caretLine = ref(0)
const focused = ref(false)

function escapeHtml(text: string) {
  return text.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c] as string))
}

// 注释灰、键蓝、字符串值绿、数字琥珀、true/false/null 紫
const TOKEN = /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|("(?:[^"\\]|\\.)*")(\s*:)?|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|\b(true|false|null)\b/g

const highlighted = computed(() => {
  const text = props.modelValue
  let out = ''
  let last = 0
  for (const match of text.matchAll(TOKEN)) {
    const index = match.index ?? 0
    out += escapeHtml(text.slice(last, index))
    const [raw, comment, str, colon, num, literal] = match
    if (comment) out += `<span class="italic text-slate-400">${escapeHtml(comment)}</span>`
    else if (str) {
      out += `<span class="${colon ? 'text-sky-700' : 'text-emerald-700'}">${escapeHtml(str)}</span>`
      if (colon) out += escapeHtml(colon)
    } else if (num) out += `<span class="text-amber-700">${escapeHtml(num)}</span>`
    else if (literal) out += `<span class="text-violet-700">${escapeHtml(literal)}</span>`
    else out += escapeHtml(raw)
    last = index + raw.length
  }
  return out + escapeHtml(text.slice(last))
})

const error = computed(() => {
  const message = validateJsonc(props.modelValue)
  if (!message) return ''
  const position = Number(message.match(/position (\d+)/)?.[1])
  if (!Number.isFinite(position)) return message
  const line = stripJsonc(props.modelValue).slice(0, position).split('\n').length
  return `第 ${line} 行：${message}`
})

function onInput(event: Event) {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
  // 等 props 更新后再按新文本算行号，否则按回车时光标行会差一行
  void nextTick(trackCaret)
}

function onFocus() {
  focused.value = true
  trackCaret()
}

function onBlur() {
  focused.value = false
}

// 行号层与着色层跟随 textarea 滚动
function syncScroll() {
  const el = editor.value
  if (!el) return
  if (highlight.value) highlight.value.style.transform = `translate(${-el.scrollLeft}px, ${-el.scrollTop}px)`
  if (gutter.value) gutter.value.style.transform = `translateY(${-el.scrollTop}px)`
  if (caretLayer.value) caretLayer.value.style.transform = `translateY(${-el.scrollTop}px)`
}

// 光标所在行，用来高亮整行和行号
function trackCaret() {
  const el = editor.value
  if (!el) return
  caretLine.value = props.modelValue.slice(0, el.selectionStart ?? 0).split('\n').length - 1
}

// 格式后滚回顶部，从头看一遍
function format() {
  if (error.value) return
  emit('update:modelValue', formatJsonc(props.modelValue))
  const el = editor.value
  if (!el) return
  el.scrollTop = 0
  el.scrollLeft = 0
  caretLine.value = 0
  syncScroll()
}
</script>

<template>
  <div
    class="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm transition-colors focus-within:border-primary/40 focus-within:ring-2 focus-within:ring-primary/15"
  >
    <div class="flex items-center justify-between border-b border-slate-100 bg-slate-50/60 px-3 py-1.5">
      <span class="text-[11px] tracking-wide text-slate-400">JSONC</span>
      <button
        type="button"
        class="rounded border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600 transition-colors hover:border-primary/40 hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
        :disabled="!!error || !modelValue.trim()"
        @click="format"
      >
        {{ t('settings.configFile.format') }}
      </button>
    </div>
    <div class="relative flex h-[56vh] min-h-[380px] overflow-hidden font-mono text-xs leading-5">
      <div class="w-11 shrink-0 select-none overflow-hidden border-r border-slate-100 bg-slate-50 py-3 text-right text-slate-400">
        <div ref="gutter" class="pr-2">
          <div
            v-for="n in lineNumbers"
            :key="n"
            :class="focused && n - 1 === caretLine ? 'bg-primary/10 font-medium text-primary' : ''"
          >{{ n }}</div>
        </div>
      </div>
      <div class="relative flex-1 overflow-hidden">
        <div ref="caretLayer" class="pointer-events-none absolute inset-0">
          <div
            v-if="focused"
            class="absolute inset-x-0 bg-primary/10"
            :style="{ top: `${LINE_PADDING + caretLine * LINE_HEIGHT}px`, height: `${LINE_HEIGHT}px` }"
          ></div>
        </div>
        <pre
          ref="highlight"
          aria-hidden="true"
          class="pointer-events-none absolute inset-0 whitespace-pre px-3 py-3 text-slate-700"
          v-html="highlighted"
        ></pre>
        <textarea
          ref="editor"
          :value="modelValue"
          class="absolute inset-0 h-full w-full resize-none whitespace-pre bg-transparent px-3 py-3 text-xs leading-5 text-transparent caret-slate-900 outline-none"
          spellcheck="false"
          wrap="off"
          @input="onInput"
          @scroll="syncScroll"
          @keyup="trackCaret"
          @click="trackCaret"
          @select="trackCaret"
          @focus="onFocus"
          @blur="onBlur"
        ></textarea>
      </div>
    </div>
    <div v-if="error" class="border-t border-rose-100 bg-rose-50 px-3 py-1.5 text-xs text-rose-700">
      {{ error }}
    </div>
  </div>
</template>
