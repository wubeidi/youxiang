import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Vite 配置：https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    // 允许局域网访问
    host: true,
    port: 5173,
    proxy: {
      // 开发环境把 /api 代理到后端服务
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    // 构建产物输出到默认 dist 目录
    outDir: 'dist'
  }
})
