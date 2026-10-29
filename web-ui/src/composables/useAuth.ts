import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { wsService } from '@/services/websocket'

// 登录态以服务端会话 Cookie 为准，localStorage 只保存展示用的用户名
const username = ref<string | null>(localStorage.getItem('auth_username'))
const isLoggedIn = ref(false)
let sessionChecked = false

async function checkSession(force = false): Promise<boolean> {
  if (sessionChecked && !force) return isLoggedIn.value
  sessionChecked = true
  try {
    const response = await fetch('/auth/session')
    const data = await response.json().catch(() => ({}))
    isLoggedIn.value = data?.authenticated === true
    if (isLoggedIn.value && typeof data?.username === 'string') {
      username.value = data.username
      localStorage.setItem('auth_username', data.username)
    }
  } catch {
    isLoggedIn.value = false
  }
  if (isLoggedIn.value) {
    wsService.start()
  }
  return isLoggedIn.value
}

export function useAuth() {
  const router = useRouter()

  const isAuthenticated = computed(() => isLoggedIn.value)

  function setAuthenticated(user: string) {
    username.value = user
    isLoggedIn.value = true
    sessionChecked = true

    localStorage.setItem('auth_username', user)

    // 启动 WebSocket 连接
    wsService.start()
  }

  async function logout() {
    username.value = null
    isLoggedIn.value = false
    sessionChecked = true
    localStorage.removeItem('auth_username')
    localStorage.removeItem('auth_logged_in')

    // 停止 WebSocket 连接
    wsService.stop()

    try {
      await fetch('/auth/logout', { method: 'POST' })
    } catch {
      // 会话已经失效时忽略
    }

    // Redirect to login if using router
    if (router) {
      router.push('/login')
    } else {
      window.location.href = '/login'
    }
  }

  async function login(user: string, pass: string): Promise<boolean> {
    try {
      const response = await fetch('/auth/status', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username: user, password: pass }),
      })

      if (response.ok) {
        setAuthenticated(user)
        return true
      } else {
        return false
      }
    } catch (e) {
      console.error('Login error', e)
      return false
    }
  }

  return {
    username,
    isAuthenticated,
    login,
    logout,
    checkSession,
  }
}
