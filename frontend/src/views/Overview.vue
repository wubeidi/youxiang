<script setup>
import { ref, onMounted } from 'vue'
import { getAccountStats } from '../api'

// 统计数据
const stats = ref({
  total_accounts: 0,
  by_status: { ok: 0, error: 0, pending: 0 },
  total_messages: 0
})
const loading = ref(false)

// 卡片配置：用于循环渲染
const cards = ref([])

// 加载统计数据
async function loadStats() {
  loading.value = true
  try {
    const res = await getAccountStats()
    stats.value = res
    // 组装展示卡片
    cards.value = [
      { label: '总账号数', value: res.total_accounts, icon: 'User', color: '#409eff' },
      { label: '正常', value: res.by_status?.ok || 0, icon: 'CircleCheck', color: '#67c23a' },
      { label: '错误', value: res.by_status?.error || 0, icon: 'CircleClose', color: '#f56c6c' },
      { label: '待处理', value: res.by_status?.pending || 0, icon: 'Clock', color: '#909399' },
      { label: '总邮件数', value: res.total_messages, icon: 'Message', color: '#e6a23c' }
    ]
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    loading.value = false
  }
}

onMounted(loadStats)
</script>

<template>
  <div v-loading="loading">
    <div class="page-header">
      <h3>概览</h3>
      <el-button :icon="'Refresh'" @click="loadStats">刷新</el-button>
    </div>

    <el-row :gutter="16">
      <el-col v-for="card in cards" :key="card.label" :xs="12" :sm="8" :md="8" :lg="4" :xl="4">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-body">
            <div class="stat-icon" :style="{ backgroundColor: card.color }">
              <el-icon :size="24"><component :is="card.icon" /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ card.value }}</div>
              <div class="stat-label">{{ card.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-header h3 {
  margin: 0;
}

.stat-card {
  margin-bottom: 16px;
  border-radius: 8px;
}

.stat-body {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}
</style>
