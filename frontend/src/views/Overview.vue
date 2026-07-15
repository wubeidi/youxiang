<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAccountStats, getAccounts } from '../api'

const router = useRouter()
const loading = ref(false)
const stats = ref({
  total_accounts: 0,
  by_status: {},
  total_messages: 0,
  unread_messages: 0,
  today_messages: 0,
  code_messages: 0,
  daily_series: [],
  distribution: []
})
const accounts = ref([])

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '早上好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const summaryCards = computed(() => [
  {
    label: '邮箱总数',
    value: stats.value.total_accounts || 0,
    tip: `正常 ${stats.value.by_status?.ok || 0}`,
    icon: 'MessageBox',
    tone: 'indigo'
  },
  {
    label: '未读邮件',
    value: stats.value.unread_messages || 0,
    tip: '待查看',
    icon: 'Message',
    tone: 'amber'
  },
  {
    label: '今日收件',
    value: stats.value.today_messages || 0,
    tip: '今天入库',
    icon: 'Download',
    tone: 'violet'
  },
  {
    label: '总邮件数',
    value: stats.value.total_messages || 0,
    tip: '已同步',
    icon: 'Promotion',
    tone: 'coral'
  },
  {
    label: '验证码邮件',
    value: stats.value.code_messages || 0,
    tip: '含验证码',
    icon: 'AlarmClock',
    tone: 'mint'
  }
])

const palette = ['#4f6ef7', '#22c55e', '#38bdf8', '#a855f7', '#f59e0b', '#f43f5e', '#14b8a6', '#8b5cf6']

function providerOf(email = '') {
  const e = email.toLowerCase()
  if (e.includes('gmail')) return { name: 'Gmail', color: '#ea4335', letter: 'G' }
  if (e.includes('outlook') || e.includes('hotmail') || e.includes('live.')) {
    return { name: 'Outlook', color: '#0078d4', letter: 'O' }
  }
  if (e.includes('yahoo')) return { name: 'Yahoo', color: '#6001d2', letter: 'Y' }
  if (e.includes('icloud') || e.includes('me.com')) return { name: 'iCloud', color: '#3b82f6', letter: 'i' }
  if (e.includes('zoho')) return { name: 'Zoho', color: '#f97316', letter: 'Z' }
  return { name: '邮箱', color: '#4f6ef7', letter: (email[0] || 'M').toUpperCase() }
}

function statusMeta(status) {
  if (status === 'ok') return { text: '正常', cls: 'ok' }
  if (status === 'error') return { text: '异常', cls: 'err' }
  return { text: '待测', cls: 'pending' }
}

// 简易 SVG 折线
const lineChart = computed(() => {
  const series = stats.value.daily_series || []
  const w = 520
  const h = 220
  const pad = 24
  const values = series.map((x) => x.count || 0)
  const max = Math.max(10, ...values)
  const stepX = series.length > 1 ? (w - pad * 2) / (series.length - 1) : 0
  const points = series.map((item, i) => {
    const x = pad + i * stepX
    const y = h - pad - ((item.count || 0) / max) * (h - pad * 2)
    return { x, y, ...item }
  })
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
  const area = points.length
    ? `${path} L ${points[points.length - 1].x} ${h - pad} L ${points[0].x} ${h - pad} Z`
    : ''
  return { w, h, pad, max, points, path, area }
})

// 简易环形图
const donut = computed(() => {
  const items = (stats.value.distribution || []).filter((x) => (x.message_count || 0) > 0)
  const total = items.reduce((s, x) => s + (x.message_count || 0), 0) || 1
  const r = 68
  const c = 2 * Math.PI * r
  let offset = 0
  const arcs = items.map((item, idx) => {
    const value = item.message_count || 0
    const len = (value / total) * c
    const arc = {
      ...item,
      color: palette[idx % palette.length],
      dash: `${len} ${c - len}`,
      offset: -offset,
      percent: ((value / total) * 100).toFixed(1)
    }
    offset += len
    return arc
  })
  return { total, arcs, r, c }
})

async function loadData() {
  loading.value = true
  try {
    const [s, a] = await Promise.all([
      getAccountStats(),
      getAccounts({ page: 1, size: 12 })
    ])
    stats.value = s || stats.value
    accounts.value = a?.items || []
  } catch (e) {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function openAccounts() {
  router.push('/accounts')
}

function openMessages(accountId) {
  router.push({ path: '/messages', query: accountId ? { account_id: accountId } : {} })
}

function openWatch() {
  router.push('/watch-board')
}

onMounted(loadData)
</script>

<template>
  <div v-loading="loading" class="overview">
    <div class="hero">
      <div>
        <h1 class="page-title">{{ greeting }}，管理员 👋</h1>
        <p class="page-subtitle">统一管理，高效处理，尽在 MailHub</p>
      </div>
      <div class="hero-actions">
        <el-button @click="loadData" :icon="'Refresh'">刷新</el-button>
        <el-button type="primary" @click="openAccounts" :icon="'Plus'">添加邮箱</el-button>
      </div>
    </div>

    <!-- 顶部统计 -->
    <div class="stat-grid">
      <div v-for="card in summaryCards" :key="card.label" class="stat-card" :class="card.tone">
        <div class="stat-icon">
          <el-icon :size="20"><component :is="card.icon" /></el-icon>
        </div>
        <div class="stat-label">{{ card.label }}</div>
        <div class="stat-value">{{ card.value }}</div>
        <div class="stat-tip">{{ card.tip }}</div>
      </div>
    </div>

    <!-- 邮箱卡片 -->
    <div class="section-head">
      <h3>我的邮箱</h3>
      <el-button round @click="openAccounts">+ 添加邮箱</el-button>
    </div>

    <div v-if="accounts.length" class="mailbox-grid">
      <div
        v-for="acc in accounts"
        :key="acc.id"
        class="mailbox-card"
        @click="openMessages(acc.id)"
      >
        <div class="mailbox-top">
          <div class="provider" :style="{ background: providerOf(acc.email).color }">
            {{ providerOf(acc.email).letter }}
          </div>
          <div class="mailbox-meta">
            <div class="mailbox-email">{{ acc.email }}</div>
            <div class="mailbox-provider">{{ providerOf(acc.email).name }}</div>
          </div>
          <span class="status-pill" :class="statusMeta(acc.status).cls">
            {{ statusMeta(acc.status).text }}
          </span>
        </div>

        <div class="mailbox-metrics">
          <div>
            <div class="metric-label">邮件总数</div>
            <div class="metric-value">{{ acc.message_count || 0 }}</div>
          </div>
          <div>
            <div class="metric-label">状态</div>
            <div class="metric-value small">{{ statusMeta(acc.status).text }}</div>
          </div>
        </div>

        <div class="progress-wrap">
          <div class="progress-label">
            <span>活跃度</span>
            <span>{{ Math.min(100, (acc.message_count || 0) % 100) }}%</span>
          </div>
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{
                width: `${Math.min(100, Math.max(8, (acc.message_count || 0) % 100))}%`,
                background: providerOf(acc.email).color
              }"
            />
          </div>
        </div>
      </div>
    </div>
    <el-empty v-else description="还没有邮箱，先去导入配置吧" />

    <!-- 底部图表 -->
    <div class="charts">
      <div class="chart-card">
        <div class="chart-head">
          <h3>邮件收发统计</h3>
          <div class="chip-group">
            <span class="chip active">7天</span>
            <span class="chip">30天</span>
            <span class="chip">90天</span>
          </div>
        </div>
        <div class="legend">
          <span><i class="dot blue" />入库邮件</span>
        </div>
        <svg class="line-svg" :viewBox="`0 0 ${lineChart.w} ${lineChart.h}`" preserveAspectRatio="none">
          <defs>
            <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#4f6ef7" stop-opacity="0.25" />
              <stop offset="100%" stop-color="#4f6ef7" stop-opacity="0.02" />
            </linearGradient>
          </defs>
          <path v-if="lineChart.area" :d="lineChart.area" fill="url(#areaFill)" />
          <path
            v-if="lineChart.path"
            :d="lineChart.path"
            fill="none"
            stroke="#4f6ef7"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <circle
            v-for="(p, idx) in lineChart.points"
            :key="idx"
            :cx="p.x"
            :cy="p.y"
            r="4"
            fill="#fff"
            stroke="#4f6ef7"
            stroke-width="2"
          />
        </svg>
        <div class="x-axis">
          <span v-for="p in lineChart.points" :key="p.date">{{ (p.date || '').slice(5) }}</span>
        </div>
      </div>

      <div class="chart-card">
        <div class="chart-head">
          <h3>邮箱使用分布</h3>
          <el-button text type="primary" @click="openWatch">去监听</el-button>
        </div>
        <div class="donut-wrap">
          <svg viewBox="0 0 180 180" class="donut-svg">
            <circle cx="90" cy="90" r="68" fill="none" stroke="#eef2ff" stroke-width="18" />
            <circle
              v-for="(arc, idx) in donut.arcs"
              :key="idx"
              cx="90"
              cy="90"
              :r="donut.r"
              fill="none"
              :stroke="arc.color"
              stroke-width="18"
              :stroke-dasharray="arc.dash"
              :stroke-dashoffset="arc.offset"
              stroke-linecap="butt"
              transform="rotate(-90 90 90)"
            />
            <text x="90" y="86" text-anchor="middle" class="donut-total-label">总邮件</text>
            <text x="90" y="110" text-anchor="middle" class="donut-total-value">{{ stats.total_messages || 0 }}</text>
          </svg>
          <div class="donut-legend">
            <div v-for="arc in donut.arcs" :key="arc.email" class="legend-row">
              <span class="legend-dot" :style="{ background: arc.color }" />
              <span class="legend-email" :title="arc.email">{{ arc.email }}</span>
              <span class="legend-pct">{{ arc.percent }}%</span>
            </div>
            <div v-if="!donut.arcs.length" class="muted">暂无分布数据</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overview {
  max-width: 1400px;
}

.hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 22px;
}

.hero-actions {
  display: flex;
  gap: 10px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  background: #fff;
  border-radius: 20px;
  padding: 18px 18px 16px;
  box-shadow: var(--mh-shadow);
  border: 1px solid rgba(232, 237, 245, 0.9);
  min-height: 128px;
}

.stat-icon {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  margin-bottom: 14px;
  color: #4f6ef7;
  background: #eef2ff;
}

.stat-card.amber .stat-icon { color: #d97706; background: #fff7ed; }
.stat-card.violet .stat-icon { color: #7c3aed; background: #f5f3ff; }
.stat-card.coral .stat-icon { color: #f43f5e; background: #fff1f2; }
.stat-card.mint .stat-icon { color: #059669; background: #ecfdf5; }

.stat-label {
  color: #8b95a7;
  font-size: 13px;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #1f2a44;
  line-height: 1;
}

.stat-tip {
  margin-top: 10px;
  font-size: 12px;
  color: #98a2b3;
}

.mailbox-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.mailbox-card {
  background: #fff;
  border-radius: 22px;
  padding: 18px;
  border: 1px solid rgba(232, 237, 245, 0.95);
  box-shadow: var(--mh-shadow);
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.mailbox-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 36px rgba(31, 42, 68, 0.08);
}

.mailbox-top {
  display: flex;
  align-items: center;
  gap: 12px;
}

.provider {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 800;
  flex-shrink: 0;
}

.mailbox-meta {
  min-width: 0;
  flex: 1;
}

.mailbox-email {
  font-size: 14px;
  font-weight: 700;
  color: #1f2a44;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mailbox-provider {
  margin-top: 2px;
  font-size: 12px;
  color: #98a2b3;
}

.status-pill {
  font-size: 12px;
  font-weight: 700;
  border-radius: 999px;
  padding: 4px 10px;
}

.status-pill.ok { background: #eef2ff; color: #4f6ef7; }
.status-pill.err { background: #fff1f2; color: #e11d48; }
.status-pill.pending { background: #f3f4f6; color: #6b7280; }

.mailbox-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 18px 0 14px;
}

.metric-label {
  font-size: 12px;
  color: #98a2b3;
  margin-bottom: 6px;
}

.metric-value {
  font-size: 28px;
  font-weight: 800;
  color: #1f2a44;
  letter-spacing: -0.03em;
}

.metric-value.small {
  font-size: 18px;
  padding-top: 8px;
}

.progress-wrap {
  margin-top: 4px;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #98a2b3;
  margin-bottom: 8px;
}

.progress-bar {
  height: 8px;
  border-radius: 999px;
  background: #eef2f7;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 999px;
}

.charts {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 16px;
  margin-top: 24px;
}

.chart-card {
  background: #fff;
  border-radius: 22px;
  padding: 18px 18px 14px;
  border: 1px solid rgba(232, 237, 245, 0.95);
  box-shadow: var(--mh-shadow);
}

.chart-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.chart-head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
}

.chip-group {
  display: flex;
  gap: 8px;
}

.chip {
  font-size: 12px;
  color: #98a2b3;
  background: #f3f6fb;
  border-radius: 999px;
  padding: 4px 10px;
}

.chip.active {
  background: #eef2ff;
  color: #4f6ef7;
  font-weight: 700;
}

.legend {
  display: flex;
  gap: 14px;
  color: #98a2b3;
  font-size: 12px;
  margin-bottom: 8px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 6px;
}

.dot.blue { background: #4f6ef7; }

.line-svg {
  width: 100%;
  height: 220px;
  display: block;
}

.x-axis {
  display: flex;
  justify-content: space-between;
  color: #98a2b3;
  font-size: 12px;
  padding: 0 8px;
}

.donut-wrap {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 12px;
  align-items: center;
  min-height: 240px;
}

.donut-svg {
  width: 180px;
  height: 180px;
}

.donut-total-label {
  fill: #98a2b3;
  font-size: 12px;
}

.donut-total-value {
  fill: #1f2a44;
  font-size: 22px;
  font-weight: 800;
}

.donut-legend {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.legend-row {
  display: grid;
  grid-template-columns: 10px 1fr auto;
  gap: 8px;
  align-items: center;
  font-size: 12px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-email {
  color: #667085;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.legend-pct {
  color: #1f2a44;
  font-weight: 700;
}

.muted {
  color: #98a2b3;
  font-size: 13px;
}

@media (max-width: 1200px) {
  .stat-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .mailbox-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .charts { grid-template-columns: 1fr; }
}

@media (max-width: 760px) {
  .stat-grid,
  .mailbox-grid { grid-template-columns: 1fr; }
  .hero { flex-direction: column; }
  .donut-wrap { grid-template-columns: 1fr; justify-items: center; }
}
</style>
