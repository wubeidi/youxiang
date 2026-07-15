import { defineStore } from 'pinia'
import { ref } from 'vue'

// 用于存储登录 token 的 Pinia store
// token 同时持久化到 localStorage，刷新页面后仍可保持登录状态
export const useAuthStore = defineStore('auth', () => {
  // 从 localStorage 初始化 token
  const token = ref(localStorage.getItem('token') || '')

  // 保存 token（登录成功后调用）
  function setToken(newToken) {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  // 清除 token（登出或 401 时调用）
  function clearToken() {
    token.value = ''
    localStorage.removeItem('token')
  }

  // 是否已登录
  function isLoggedIn() {
    return !!token.value
  }

  return { token, setToken, clearToken, isLoggedIn }
})
