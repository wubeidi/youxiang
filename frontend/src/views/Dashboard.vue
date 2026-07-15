<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 当前激活的菜单项，跟随路由变化高亮
const activeMenu = computed(() => route.path)

// 菜单点击跳转
function handleSelect(index) {
  router.push(index)
}

// 登出
async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    authStore.clearToken()
    router.push('/login')
  } catch (e) {
    // 用户取消，无需处理
  }
}
</script>

<template>
  <el-container class="layout">
    <!-- 左侧菜单 -->
    <el-aside width="220px" class="aside">
      <div class="logo">
        <el-icon :size="24"><Message /></el-icon>
        <span>邮箱管理面板</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        class="menu"
        router
        @select="handleSelect"
      >
        <el-menu-item index="/">
          <el-icon><DataBoard /></el-icon>
          <span>概览</span>
        </el-menu-item>
        <el-menu-item index="/accounts">
          <el-icon><User /></el-icon>
          <span>账号管理</span>
        </el-menu-item>
        <el-menu-item index="/watch-board">
          <el-icon><Monitor /></el-icon>
          <span>监听看板</span>
        </el-menu-item>
        <el-menu-item index="/messages">
          <el-icon><Message /></el-icon>
          <span>邮件列表</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶部栏 -->
      <el-header class="header">
        <div class="header-title">邮箱管理系统</div>
        <el-dropdown @command="handleLogout">
          <span class="user-info">
            <el-icon><UserFilled /></el-icon>
            <span>管理员</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <!-- 主内容区，子路由在此渲染 -->
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}

.aside {
  background-color: #304156;
  overflow: hidden;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  background-color: #263445;
}

.menu {
  border-right: none;
  background-color: #304156;
}

/* 深色菜单样式覆盖 */
.menu :deep(.el-menu-item) {
  color: #bfcbd9;
}

.menu :deep(.el-menu-item.is-active) {
  color: #fff;
  background-color: #409eff;
}

.menu :deep(.el-menu-item:hover) {
  background-color: #263445;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
}

.header-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: #606266;
  outline: none;
}

.main {
  background-color: #f0f2f5;
  padding: 16px;
}
</style>
