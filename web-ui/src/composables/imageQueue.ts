/**
 * 图片下载队列：同时只放 3 张，其余排队。
 * 一次挂 15 张图时浏览器会同时发出全部请求，「啪」地一下全出来；
 * 排队后一张张出现，观感更线性，解码也不会挤在同一帧。
 *
 * 状态必须放在模块级：写在 <script setup> 里会变成每个组件实例各一份，队列就不起作用了。
 */
const MAX_CONCURRENT = 3

let active = 0
const waiters: Array<() => void> = []

export function acquireImageSlot(): Promise<void> {
  if (active < MAX_CONCURRENT) {
    active += 1
    return Promise.resolve()
  }
  return new Promise((resolve) => waiters.push(resolve))
}

export function releaseImageSlot(): void {
  const next = waiters.shift()
  if (next) next()
  else active = Math.max(0, active - 1)
}
