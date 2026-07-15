<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const activeMenu = computed(() => route.path)

const menus = [
  { path: '/', label: '概览', icon: 'DataBoard' },
  { path: '/accounts', label: '邮箱管理', icon: 'MessageBox' },
  { path: '/messages', label: '邮件聚合', icon: 'Message' },
  { path: '/watch-board', label: '监听看板', icon: 'Monitor' },
]

function go(path) {
  router.push(path)
}

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
    // 用户取消
  }
}
</script>

<template>
  <div class="mh-layout">
    <!-- 左侧深色导航 -->
    <aside class="mh-sidebar">
      <div class="brand">
        <div class="brand-mark">
          <el-icon :size="18"><Message /></el-icon>
        </div>
        <span class="brand-name">MailHub</span>
      </div>

      <nav class="nav">
        <button
          v-for="item in menus"
          :key="item.path"
          class="nav-item"
          :class="{ active: activeMenu === item.path }"
          @click="go(item.path)"
        >
          <el-icon :size="18"><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <div class="sidebar-bottom">
        <div class="promo-card">
          <div class="promo-title">
            <el-icon><Opportunity /></el-icon>
            <span>自托管邮箱中枢</span>
          </div>
          <div class="promo-desc">按需刷新 · 临时监听 · 验证码聚合</div>
        </div>

        <div class="user-card" @click="handleLogout">
          <div class="avatar">A</div>
          <div class="user-meta">
            <div class="user-name">管理员</div>
            <div class="user-mail">admin@mailhub.local</div>
          </div>
          <el-icon class="more"><SwitchButton /></el-icon>
        </div>
      </div>
    </aside>

    <!-- 右侧内容区 -->
    <div class="mh-main">
      <header class="mh-topbar">
        <div class="search-box">
          <el-icon class="search-icon"><Search /></el-icon>
          <input
            class="search-input"
            placeholder="搜索邮件、联系人或内容"
            readonly
            @click="go('/messages')"
          />
          <span class="kbd">⌘ K</span>
        </div>
        <div class="top-actions">
          <button class="icon-btn" title="通知" @click="go('/messages')">
            <el-icon :size="18"><Bell /></el-icon>
          </button>
          <button class="icon-btn" title="退出" @click="handleLogout">
            <el-icon :size="18"><SwitchButton /></el-icon>
          </button>
        </div>
      </header>

      <main class="mh-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.mh-layout {
  display: flex;
  min-height: 100vh;
  background:
    radial-gradient(circle at top right, rgba(79, 110, 247, 0.08), transparent 28%),
    linear-gradient(180deg, #f7f9fc 0%, #eef3fb 100%);
}

.mh-sidebar {
  width: 248px;
  flex-shrink: 0;
  background: linear-gradient(180deg, #0b1220 0%, #101827 100%);
  color: #d7deea;
  display: flex;
  flex-direction: column;
  padding: 22px 16px;
  position: sticky;
  top: 0;
  height: 100vh;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 10px 22px;
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  color: #fff;
  background: linear-gradient(135deg, #5b7cfa, #7a5af8);
  box-shadow: 0 8px 20px rgba(91, 124, 250, 0.35);
}

.brand-name {
  font-size: 20px;
  font-weight: 800;
  color: #fff;
  letter-spacing: -0.03em;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.nav-item {
  border: 0;
  background: transparent;
  color: #9aa6bc;
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border-radius: 14px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.18s ease;
  text-align: left;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #fff;
}

.nav-item.active {
  background: linear-gradient(90deg, #4f6ef7, #5b7cfa);
  color: #fff;
  box-shadow: 0 10px 24px rgba(79, 110, 247, 0.35);
}

.sidebar-bottom {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: auto;
}

.promo-card {
  border-radius: 18px;
  padding: 16px;
  background: linear-gradient(180deg, rgba(79, 110, 247, 0.22), rgba(255, 255, 255, 0.03));
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.promo-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #fff;
  font-weight: 700;
  font-size: 13px;
}

.promo-desc {
  margin-top: 8px;
  color: #9aa6bc;
  font-size: 12px;
  line-height: 1.5;
}

.user-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.05);
  cursor: pointer;
}

.user-card:hover {
  background: rgba(255, 255, 255, 0.07);
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(135deg, #7a5af8, #4f6ef7);
}

.user-meta {
  flex: 1;
  min-width: 0;
}

.user-name {
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}

.user-mail {
  color: #8b95a7;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.more {
  color: #8b95a7;
}

.mh-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.mh-topbar {
  height: 76px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 28px;
}

.search-box {
  width: min(460px, 100%);
  height: 44px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid #e7edf7;
  border-radius: 999px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 14px 0 16px;
  box-shadow: 0 8px 24px rgba(31, 42, 68, 0.04);
}

.search-icon {
  color: #98a2b3;
}

.search-input {
  flex: 1;
  border: 0;
  outline: none;
  background: transparent;
  font-size: 14px;
  color: var(--mh-text);
}

.search-input::placeholder {
  color: #98a2b3;
}

.kbd {
  font-size: 12px;
  color: #98a2b3;
  background: #f2f5fb;
  border-radius: 8px;
  padding: 4px 8px;
}

.top-actions {
  display: flex;
  gap: 10px;
}

.icon-btn {
  width: 42px;
  height: 42px;
  border: 1px solid #e7edf7;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
  color: #667085;
  display: grid;
  place-items: center;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(31, 42, 68, 0.04);
}

.icon-btn:hover {
  color: var(--mh-primary);
}

.mh-content {
  flex: 1;
  padding: 8px 28px 28px;
}

@media (max-width: 960px) {
  .mh-sidebar {
    display: none;
  }
  .mh-topbar,
  .mh-content {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
