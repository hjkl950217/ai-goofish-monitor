<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

interface TrendPoint {
  day: string
  avg_price: number | null
  median_price: number | null
  min_price?: number | null
  max_price?: number | null
  sample_count?: number | null
}

const props = defineProps<{
  points: TrendPoint[]
}>()
const { t } = useI18n()

const chartWidth = 720
const chartHeight = 220
const padTop = 24
const padBottom = 30
const padLeft = 56
const padRight = 24
const usableHeight = chartHeight - padTop - padBottom

const hoveredIndex = ref<number | null>(null)

const validPoints = computed(() =>
  props.points.filter((point) => point.avg_price !== null && point.avg_price !== undefined)
)

const valueRange = computed(() => {
  const values = validPoints.value
    .flatMap((point) => [point.avg_price, point.median_price])
    .filter((value): value is number => typeof value === 'number')
  if (values.length === 0) {
    return { min: 0, max: 1 }
  }
  const min = Math.min(...values)
  const max = Math.max(...values)
  if (min === max) {
    return { min: min - 1, max: max + 1 }
  }
  return { min, max }
})

const slotWidth = computed(
  () => (chartWidth - padLeft - padRight) / Math.max(1, validPoints.value.length - 1)
)

function resolveX(index: number) {
  if (validPoints.value.length <= 1) return (padLeft + chartWidth - padRight) / 2
  return padLeft + (chartWidth - padLeft - padRight) / (validPoints.value.length - 1) * index
}

function resolveY(value: number) {
  const ratio = (value - valueRange.value.min) / (valueRange.value.max - valueRange.value.min)
  return chartHeight - padBottom - ratio * usableHeight
}

function buildPath(values: Array<number | null>) {
  const commands = values
    .map((value, index) => {
      if (value === null || value === undefined) return null
      const prefix = index === 0 ? 'M' : 'L'
      return `${prefix} ${resolveX(index)} ${resolveY(value)}`
    })
    .filter(Boolean)
  return commands.join(' ')
}

const avgPath = computed(() => buildPath(validPoints.value.map((point) => point.avg_price)))
const medianPath = computed(() => buildPath(validPoints.value.map((point) => point.median_price)))
const areaPath = computed(() => {
  if (!avgPath.value || validPoints.value.length === 0) return ''
  const firstX = resolveX(0)
  const lastX = resolveX(validPoints.value.length - 1)
  const baseline = chartHeight - padBottom
  return `${avgPath.value} L ${lastX} ${baseline} L ${firstX} ${baseline} Z`
})

const priceTicks = computed(() => {
  const { min, max } = valueRange.value
  return Array.from({ length: 5 }, (_, i) => ({
    y: padTop + (usableHeight / 4) * i,
    label: `¥${Math.round(max - ((max - min) * i) / 4)}`,
  }))
})

const tooltip = computed(() => {
  const index = hoveredIndex.value
  if (index === null) return null
  const point = validPoints.value[index]
  if (!point) return null
  const pointX = resolveX(index)
  let x = pointX + 14
  if (x + 200 > chartWidth) x = pointX - 214
  x = Math.min(Math.max(x, 4), chartWidth - 204)
  const y = Math.min(Math.max(resolveY(point.avg_price as number) - 50, 8), chartHeight - padBottom - 124)
  return { point, x, y }
})

function formatPrice(value: number | null | undefined) {
  return value === null || value === undefined ? '—' : `¥${value}`
}
</script>

<template>
  <div class="app-surface-subtle p-4">
    <div class="mb-3 flex flex-col gap-3 text-xs uppercase tracking-[0.22em] text-slate-500 sm:flex-row sm:items-center sm:justify-between">
      <span>{{ t('results.chart.title') }}</span>
      <div class="flex items-center gap-3">
        <span class="inline-flex items-center gap-1">
          <span class="h-2.5 w-2.5 rounded-full bg-sky-600" />
          {{ t('results.chart.avgPrice') }}
        </span>
        <span class="inline-flex items-center gap-1">
          <span class="h-2.5 w-2.5 rounded-full bg-amber-500" />
          {{ t('results.chart.medianPrice') }}
        </span>
      </div>
    </div>

    <!-- 高度与下面的 SVG 一致，避免数据到达前后整块面板变高变矮 -->
    <div v-if="validPoints.length < 2" class="flex h-[220px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white/70 px-4 text-center text-sm text-slate-500">
      {{ t('results.chart.notEnoughData') }}
    </div>

    <div v-else>
      <svg :viewBox="`0 0 ${chartWidth} ${chartHeight}`" class="h-[220px] w-full" role="img" :aria-label="t('results.chart.noTrend')" @mouseleave="hoveredIndex = null">
        <defs>
          <linearGradient id="avg-area-fill" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#0284c7" stop-opacity="0.24" />
            <stop offset="100%" stop-color="#0284c7" stop-opacity="0" />
          </linearGradient>
        </defs>

        <g>
          <template v-for="(tick, index) in priceTicks" :key="index">
            <line
              :x1="padLeft"
              :x2="chartWidth - padRight"
              :y1="tick.y"
              :y2="tick.y"
              stroke="#cbd5e1"
              stroke-dasharray="4 6"
            />
            <text
              :x="padLeft - 10"
              :y="tick.y"
              text-anchor="end"
              dominant-baseline="middle"
              font-size="11"
              fill="#94a3b8"
            >
              {{ tick.label }}
            </text>
          </template>
        </g>

        <path :d="areaPath" fill="url(#avg-area-fill)" />
        <path :d="avgPath" fill="none" stroke="#0284c7" stroke-width="4" stroke-linecap="round" />
        <path :d="medianPath" fill="none" stroke="#f59e0b" stroke-width="3" stroke-dasharray="8 6" stroke-linecap="round" />

        <line
          v-if="hoveredIndex !== null"
          :x1="resolveX(hoveredIndex)"
          :x2="resolveX(hoveredIndex)"
          :y1="padTop"
          :y2="chartHeight - padBottom"
          stroke="#cbd5e1"
          stroke-width="1"
          stroke-dasharray="4 4"
        />

        <g v-for="(point, index) in validPoints" :key="point.day">
          <circle
            :cx="resolveX(index)"
            :cy="resolveY(point.avg_price as number)"
            :r="hoveredIndex === index ? 7 : 5"
            fill="#0284c7"
            :stroke="hoveredIndex === index ? '#fff' : undefined"
            :stroke-width="hoveredIndex === index ? 2 : undefined"
          />
          <circle
            :cx="resolveX(index)"
            :cy="resolveY(point.median_price as number)"
            :r="hoveredIndex === index ? 6 : 4"
            fill="#f59e0b"
            :stroke="hoveredIndex === index ? '#fff' : undefined"
            :stroke-width="hoveredIndex === index ? 2 : undefined"
          />
          <text
            :x="resolveX(index)"
            :y="chartHeight - 8"
            text-anchor="middle"
            fill="#64748b"
            font-size="12"
          >
            {{ point.day.slice(5) }}
          </text>
        </g>

        <rect
          v-for="(point, index) in validPoints"
          :key="`hover-${point.day}`"
          :x="resolveX(index) - slotWidth / 2"
          :y="0"
          :width="slotWidth"
          :height="chartHeight"
          fill="transparent"
          @mouseenter="hoveredIndex = index"
        />

        <g v-if="tooltip" pointer-events="none" :transform="`translate(${tooltip.x} ${tooltip.y})`">
          <rect width="200" height="124" rx="10" fill="#0f172a" fill-opacity="0.94" />
          <text x="14" y="26" font-size="12" fill="#e2e8f0">{{ tooltip.point.day }}</text>
          <text x="14" y="48" font-size="12" fill="#7dd3fc">{{ t('results.chart.avgPrice') }} {{ formatPrice(tooltip.point.avg_price) }}</text>
          <text x="14" y="70" font-size="12" fill="#fcd34d">{{ t('results.chart.medianPrice') }} {{ formatPrice(tooltip.point.median_price) }}</text>
          <text x="14" y="92" font-size="12" fill="#e2e8f0">{{ t('results.insights.priceRange') }} {{ formatPrice(tooltip.point.min_price) }} – {{ formatPrice(tooltip.point.max_price) }}</text>
          <text x="14" y="114" font-size="12" fill="#cbd5e1">{{ tooltip.point.sample_count !== null && tooltip.point.sample_count !== undefined ? t('results.insights.sampleCount', { count: tooltip.point.sample_count }) : '—' }}</text>
        </g>
      </svg>
    </div>
  </div>
</template>
