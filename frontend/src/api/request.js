import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

// 创建 axios 实例
// baseURL 使用 /api，开发环境由 Vite 代理到后端
const request = axios.create({
  baseURL: '/api',
  timeout: 30000
})

// 请求拦截器：自动为每个请求添加 Bearer 认证头
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：统一处理错误，401 时跳回登录页
request.interceptors.response.use(
  // 直接返回响应体数据，简化调用
  (response) => response.data,
  (error) => {
    const { response } = error
    if (response) {
      if (response.status === 401) {
        // token 失效或未认证，清除本地 token 并跳转登录页
        localStorage.removeItem('token')
        ElMessage.error('登录已过期，请重新登录')
        // 避免在登录页重复跳转
        if (router.currentRoute.value.path !== '/login') {
          router.push({
            path: '/login',
            query: { redirect: router.currentRoute.value.fullPath }
          })
        }
      } else {
        // 其他错误，尝试展示后端返回的错误信息
        const msg =
          response.data?.detail || response.data?.message || `请求失败（${response.status}）`
        ElMessage.error(typeof msg === 'string' ? msg : '请求失败')
      }
    } else {
      // 网络异常或超时
      ElMessage.error('网络异常，请检查后端服务是否启动')
    }
    return Promise.reject(error)
  }
)

export default request
