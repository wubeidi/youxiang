<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAccountStats } from '../api'

const router = useRouter()
const loading = ref(false)
const rangeKey = ref('7') // 7 / 30 / 90
const pulse = ref(0)      // 用于轻微动画刷新
let pulseTimer = null
let autoTimer = null

const stats = ref({
  total_accounts: 0,
  by_status: {},
  total_messages: 0,
  unread_messages: 0,
  today_messages: 0,
  today_codes: 0,
  code_messages: 0,
  daily_series: [],
  series_7: [],
  series_30: [],
  series_90: [],
  hourly_series: [],
  distribution: [],
  domain_ranking: [],
  site_ranking: [],
  health: { ok: 0, error: 0, pending: 0, disabled: 0 }
})

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
    tip: `正常 ${stats.value.health?.ok || stats.value.by_status?.ok || 0}`,
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
    tip: `今日验证码 ${stats.value.today_codes || 0}`,
    icon: 'Download',
    tone: 'violet'
  },
  {
    label: '总邮件数',
    value: stats.value.total_messages || 0,
    tip: '已同步入库',
    icon: 'Promotion',
    tone: 'coral'
  },
  {
    label: '验证码邮件',
    value: stats.value.code_messages || 0,
    tip: '历史累计',
    icon: 'AlarmClock',
    tone: 'mint'
  }
])

const palette = ['#4f6ef7', '#22c55e', '#38bdf8', '#a855f7', '#f59e0b', '#f43f5e', '#14b8a6', '#8b5cf6']

const activeSeries = computed(() => {
  if (rangeKey.value === '30') return stats.value.series_30 || []
  if (rangeKey.value === '90') return stats.value.series_90 || []
  return stats.value.series_7 || stats.value.daily_series || []
})

// 双折线面积图：入库 + 验证码
const trendChart = computed(() => {
  void pulse.value
  const series = activeSeries.value
  const w = 640
  const h = 260
  const padX = 28
  const padY = 28
  const counts = series.map((x) => x.count || 0)
  const codes = series.map((x) => x.code_count || 0)
  const max = Math.max(5, ...counts, ...codes)
  const n = Math.max(series.length, 1)
  const stepX = n > 1 ? (w - padX * 2) / (n - 1) : 0

  const toPoints = (values) =>
    series.map((item, i) => {
      const x = padX + i * stepX
      const y = h - padY - ((values[i] || 0) / max) * (h - padY * 2)
      return { x, y, date: item.date, value: values[i] || 0 }
    })

  const countPts = toPoints(counts)
  const codePts = toPoints(codes)
  const pathOf = (pts) => pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
  const areaOf = (pts) =>
    pts.length
      ? `${pathOf(pts)} L ${pts[pts.length - 1].x.toFixed(1)} ${h - padY} L ${pts[0].x.toFixed(1)} ${h - padY} Z`
      : ''

  // x 轴抽样标签，避免 90 天挤爆
  const labelEvery = n > 40 ? 10 : n > 20 ? 5 : n > 10 ? 2 : 1
  const labels = countPts
    .map((p, i) => ({ ...p, show: i % labelEvery === 0 || i === n - 1 }))
    .filter((p) => p.show)

  return {
    w, h, max,
    countPath: pathOf(countPts),
    codePath: pathOf(codePts),
    countArea: areaOf(countPts),
    codeArea: areaOf(codePts),
    countPts,
    codePts,
    labels
  }
})

// 24 小时柱状图
const hourChart = computed(() => {
  void pulse.value
  const series = stats.value.hourly_series || []
  const w = 640
  const h = 220
  const padX = 20
  const padY = 24
  const values = series.map((x) => x.count || 0)
  const max = Math.max(3, ...values)
  const n = Math.max(series.length, 1)
  const gap = 4
  const barW = Math.max(6, (w - padX * 2 - gap * (n - 1)) / n)
  const bars = series.map((item, i) => {
    const bh = ((item.count || 0) / max) * (h - padY * 2)
    const x = padX + i * (barW + gap)
    const y = h - padY - bh
    return {
      ...item,
      x,
      y,
      w: barW,
      h: Math.max(bh, item.count ? 3 : 0),
      active: (item.count || 0) > 0
    }
  })
  return { w, h, bars, max }
})

// 环形图：邮箱邮件分布
const donut = computed(() => {
  void pulse.value
  const items = (stats.value.distribution || []).filter((x) => (x.message_count || 0) > 0)
  const total = items.reduce((s, x) => s + (x.message_count || 0), 0) || 1
  const r = 72
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
  return { total, arcs, r }
})

// 健康度条
const healthBars = computed(() => {
  const h = stats.value.health || {}
  const rows = [
    { key: 'ok', label: '正常', value: h.ok || 0, color: '#22c55e' },
    { key: 'error', label: '异常', value: h.error || 0, color: '#f43f5e' },
    { key: 'pending', label: '待测', value: h.pending || 0, color: '#94a3b8' },
    { key: 'disabled', label: '停用', value: h.disabled || 0, color: '#f59e0b' }
  ]
  const max = Math.max(1, ...rows.map((r) => r.value))
  return rows.map((r) => ({ ...r, pct: Math.round((r.value / max) * 100) }))
})

// 横向条形：热门域名
const domainBars = computed(() => {
  const rows = stats.value.domain_ranking || []
  const max = Math.max(1, ...rows.map((r) => r.count || 0))
  return rows.map((r, i) => ({
    ...r,
    color: palette[i % palette.length],
    pct: Math.round(((r.count || 0) / max) * 100)
  }))
})

const siteBars = computed(() => {
  const rows = stats.value.site_ranking || []
  const max = Math.max(1, ...rows.map((r) => r.count || 0))
  return rows.map((r, i) => ({
    ...r,
    color: palette[(i + 2) % palette.length],
    pct: Math.round(((r.count || 0) / max) * 100)
  }))
})

async function loadData(silent = false) {
  if (!silent) loading.value = true
  try {
    const s = await getAccountStats()
    stats.value = { ...stats.value, ...(s || {}) }
  } catch (e) {
    // 拦截器已提示
  } finally {
    if (!silent) loading.value = false
  }
}

function openAccounts() {
  router.push('/accounts')
}
function openMessages() {
  router.push('/messages')
}
function openWatch() {
  router.push('/watch-board')
}

onMounted(() => {
  loadData()
  // 轻微动画脉冲 + 定时刷新数据
  pulseTimer = setInterval(() => {
    pulse.value = (pulse.value + 1) % 1000
  }, 2000)
  autoTimer = setInterval(() => loadData(true), 30000)
})

onUnmounted(() => {
  if (pulseTimer) clearInterval(pulseTimer)
  if (autoTimer) clearInterval(autoTimer)
})
</script>

<template>
  <div v-loading="loading" class="overview">
    <div class="hero">
      <div>
        <h1 class="page-title">{{ greeting }}，管理员 👋</h1>
        <p class="page-subtitle">数据看板实时刷新 · 掌握收信与验证码趋势</p>
      </div>
      <div class="hero-actions">
        <el-button @click="loadData()" :icon="'Refresh'">刷新</el-button>
        <el-button @click="openMessages">邮件聚合</el-button>
        <el-button type="primary" @click="openWatch" :icon="'Monitor'">监听看板</el-button>
      </div>
    </div>

    <!-- KPI -->
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

    <!-- 主趋势 + 24h -->
    <div class="charts-top">
      <div class="chart-card main-trend">
        <div class="chart-head">
          <div>
            <h3>邮件入库趋势</h3>
            <p class="chart-sub">总邮件 vs 验证码邮件</p>
          </div>
          <div class="chip-group">
            <button class="chip" :class="{ active: rangeKey === '7' }" @click="rangeKey = '7'">7天</button>
            <button class="chip" :class="{ active: rangeKey === '30' }" @click="rangeKey = '30'">30天</button>
            <button class="chip" :class="{ active: rangeKey === '90' }" @click="rangeKey = '90'">90天</button>
          </div>
        </div>
        <div class="legend">
          <span><i class="dot blue" />入库邮件</span>
          <span><i class="dot green" />验证码邮件</span>
        </div>
        <svg class="line-svg" :viewBox="`0 0 ${trendChart.w} ${trendChart.h}`" preserveAspectRatio="none">
          <defs>
            <linearGradient id="areaBlue" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#4f6ef7" stop-opacity="0.28" />
              <stop offset="100%" stop-color="#4f6ef7" stop-opacity="0.02" />
            </linearGradient>
            <linearGradient id="areaGreen" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#22c55e" stop-opacity="0.22" />
              <stop offset="100%" stop-color="#22c55e" stop-opacity="0.02" />
            </linearGradient>
          </defs>
          <path v-if="trendChart.countArea" :d="trendChart.countArea" fill="url(#areaBlue)" class="area-anim" />
          <path v-if="trendChart.codeArea" :d="trendChart.codeArea" fill="url(#areaGreen)" class="area-anim" />
          <path
            v-if="trendChart.countPath"
            :d="trendChart.countPath"
            fill="none"
            stroke="#4f6ef7"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="line-anim"
          />
          <path
            v-if="trendChart.codePath"
            :d="trendChart.codePath"
            fill="none"
            stroke="#22c55e"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="line-anim"
          />
          <circle
            v-for="(p, idx) in trendChart.countPts"
            :key="'c' + idx"
            :cx="p.x"
            :cy="p.y"
            r="3.5"
            fill="#fff"
            stroke="#4f6ef7"
            stroke-width="2"
          />
        </svg>
        <div class="x-axis">
          <span v-for="p in trendChart.labels" :key="p.date">{{ (p.date || '').slice(5) }}</span>
        </div>
      </div>

      <div class="chart-card">
        <div class="chart-head">
          <div>
            <h3>近 24 小时活跃</h3>
            <p class="chart-sub">按小时入库量</p>
          </div>
        </div>
        <svg class="bar-svg" :viewBox="`0 0 ${hourChart.w} ${hourChart.h}`" preserveAspectRatio="none">
          <rect
            v-for="(b, idx) in hourChart.bars"
            :key="idx"
            :x="b.x"
            :y="b.y"
            :width="b.w"
            :height="b.h"
            rx="4"
            :fill="b.active ? 'url(#barGrad)' : '#e8eef8'"
            class="bar-anim"
          >
            <title>{{ b.hour }} · {{ b.count }}</title>
          </rect>
          <defs>
            <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#7a5af8" />
              <stop offset="100%" stop-color="#4f6ef7" />
            </linearGradient>
          </defs>
        </svg>
        <div class="x-axis hour-axis">
          <span v-for="(b, idx) in hourChart.bars" :key="idx">
            {{ idx % 3 === 0 ? b.hour : '' }}
          </span>
        </div>
      </div>
    </div>

    <!-- 第二行：分布 / 健康 / 域名 -->
    <div class="charts-mid">
      <div class="chart-card">
        <div class="chart-head">
          <h3>邮箱邮件分布</h3>
          <el-button text type="primary" @click="openAccounts">管理邮箱</el-button>
        </div>
        <div class="donut-wrap">
          <svg viewBox="0 0 190 190" class="donut-svg">
            <circle cx="95" cy="95" r="72" fill="none" stroke="#eef2ff" stroke-width="18" />
            <circle
              v-for="(arc, idx) in donut.arcs"
              :key="idx"
              cx="95"
              cy="95"
              :r="donut.r"
              fill="none"
              :stroke="arc.color"
              stroke-width="18"
              :stroke-dasharray="arc.dash"
              :stroke-dashoffset="arc.offset"
              transform="rotate(-90 95 95)"
              class="arc-anim"
            />
            <text x="95" y="90" text-anchor="middle" class="donut-total-label">总邮件</text>
            <text x="95" y="114" text-anchor="middle" class="donut-total-value">{{ stats.total_messages || 0 }}</text>
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

      <div class="chart-card">
        <div class="chart-head">
          <h3>账号健康度</h3>
        </div>
        <div class="health-list">
          <div v-for="row in healthBars" :key="row.key" class="health-row">
            <div class="health-meta">
              <span>{{ row.label }}</span>
              <b>{{ row.value }}</b>
            </div>
            <div class="h-bar">
              <div class="h-fill" :style="{ width: row.pct + '%', background: row.color }" />
            </div>
          </div>
        </div>
      </div>

      <div class="chart-card">
        <div class="chart-head">
          <h3>热门发件域名</h3>
        </div>
        <div v-if="domainBars.length" class="rank-list">
          <div v-for="row in domainBars" :key="row.domain" class="rank-row">
            <div class="rank-meta">
              <span class="rank-name" :title="row.domain">{{ row.domain }}</span>
              <b>{{ row.count }}</b>
            </div>
            <div class="h-bar">
              <div class="h-fill" :style="{ width: row.pct + '%', background: row.color }" />
            </div>
          </div>
        </div>
        <div v-else class="muted center">暂无域名数据，刷新邮箱后会生成</div>
      </div>
    </div>

    <!-- 注册站点排行 -->
    <div class="chart-card sites-card">
      <div class="chart-head">
        <div>
          <h3>注册网站排行</h3>
          <p class="chart-sub">按邮箱聚合到的站点邮件量</p>
        </div>
        <el-button text type="primary" @click="openAccounts">去查看</el-button>
      </div>
      <div v-if="siteBars.length" class="site-grid">
        <div v-for="(row, idx) in siteBars" :key="row.domain" class="site-item">
          <div class="site-top">
            <span class="site-idx">#{{ idx + 1 }}</span>
            <div class="site-meta">
              <div class="site-name" :title="row.name">{{ row.name }}</div>
              <div class="site-domain" :title="row.domain">{{ row.domain }}</div>
            </div>
            <b class="site-count">{{ row.count }}</b>
          </div>
          <div class="h-bar">
            <div class="h-fill" :style="{ width: row.pct + '%', background: row.color }" />
          </div>
        </div>
      </div>
      <div v-else class="muted center">暂无注册网站推断数据</div>
    </div>
  </div>
</template>

<style scoped>
.overview { max-width: 1440px; }

.hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}
.hero-actions { display: flex; gap: 10px; flex-wrap: wrap; }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.stat-card {
  background: #fff;
  border-radius: 20px;
  padding: 16px;
  box-shadow: var(--mh-shadow);
  border: 1px solid rgba(232, 237, 245, 0.9);
  min-height: 120px;
}
.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  margin-bottom: 12px;
  color: #4f6ef7;
  background: #eef2ff;
}
.stat-card.amber .stat-icon { color: #d97706; background: #fff7ed; }
.stat-card.violet .stat-icon { color: #7c3aed; background: #f5f3ff; }
.stat-card.coral .stat-icon { color: #f43f5e; background: #fff1f2; }
.stat-card.mint .stat-icon { color: #059669; background: #ecfdf5; }
.stat-label { color: #8b95a7; font-size: 13px; margin-bottom: 8px; }
.stat-value {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #1f2a44;
  line-height: 1;
}
.stat-tip { margin-top: 8px; font-size: 12px; color: #98a2b3; }

.charts-top {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.charts-mid {
  display: grid;
  grid-template-columns: 1.2fr 0.9fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.chart-card {
  background: #fff;
  border-radius: 22px;
  padding: 16px 16px 12px;
  border: 1px solid rgba(232, 237, 245, 0.95);
  box-shadow: var(--mh-shadow);
}
.chart-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}
.chart-head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #1f2a44;
}
.chart-sub {
  margin: 4px 0 0;
  color: #98a2b3;
  font-size: 12px;
}

.chip-group { display: flex; gap: 8px; }
.chip {
  border: 0;
  font-size: 12px;
  color: #98a2b3;
  background: #f3f6fb;
  border-radius: 999px;
  padding: 5px 12px;
  cursor: pointer;
  font-weight: 600;
}
.chip.active {
  background: #eef2ff;
  color: #4f6ef7;
}

.legend {
  display: flex;
  gap: 14px;
  color: #98a2b3;
  font-size: 12px;
  margin-bottom: 6px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 6px;
}
.dot.blue { background: #4f6ef7; }
.dot.green { background: #22c55e; }

.line-svg, .bar-svg {
  width: 100%;
  height: 240px;
  display: block;
}
.bar-svg { height: 200px; }

.x-axis {
  display: flex;
  justify-content: space-between;
  color: #98a2b3;
  font-size: 11px;
  padding: 0 6px;
  min-height: 18px;
}
.hour-axis span {
  flex: 1;
  text-align: center;
  overflow: hidden;
}

.donut-wrap {
  display: grid;
  grid-template-columns: 190px 1fr;
  gap: 10px;
  align-items: center;
  min-height: 220px;
}
.donut-svg { width: 190px; height: 190px; }
.donut-total-label { fill: #98a2b3; font-size: 12px; }
.donut-total-value { fill: #1f2a44; font-size: 22px; font-weight: 800; }
.donut-legend { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.legend-row {
  display: grid;
  grid-template-columns: 10px 1fr auto;
  gap: 8px;
  align-items: center;
  font-size: 12px;
}
.legend-dot { width: 8px; height: 8px; border-radius: 50%; }
.legend-email {
  color: #667085;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.legend-pct { color: #1f2a44; font-weight: 700; }

.health-list, .rank-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 8px 2px 6px;
}
.health-meta, .rank-meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 13px;
  color: #667085;
}
.health-meta b, .rank-meta b { color: #1f2a44; }
.rank-name {
  max-width: 70%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.h-bar {
  height: 10px;
  border-radius: 999px;
  background: #eef2f7;
  overflow: hidden;
}
.h-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.6s ease;
}

.sites-card { margin-bottom: 8px; }
.site-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 18px;
}
.site-item {
  background: #f8faff;
  border-radius: 14px;
  padding: 12px;
}
.site-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.site-idx {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: #eef2ff;
  color: #4f6ef7;
  font-size: 12px;
  font-weight: 800;
  flex-shrink: 0;
}
.site-meta { min-width: 0; flex: 1; }
.site-name {
  font-weight: 700;
  color: #1f2a44;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.site-domain {
  font-size: 12px;
  color: #98a2b3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.site-count { color: #1f2a44; font-size: 16px; }

.muted { color: #98a2b3; font-size: 13px; }
.center { text-align: center; padding: 28px 0; }

/* 轻量动效 */
.line-anim {
  stroke-dasharray: 1200;
  stroke-dashoffset: 0;
  animation: dashIn 1.1s ease;
}
.area-anim { animation: fadeIn 0.9s ease; }
.bar-anim { transition: height 0.5s ease, y 0.5s ease; }
.arc-anim { transition: stroke-dasharray 0.6s ease; }

@keyframes dashIn {
  from { stroke-dashoffset: 1200; opacity: 0.2; }
  to { stroke-dashoffset: 0; opacity: 1; }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@media (max-width: 1200px) {
  .stat-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .charts-top, .charts-mid { grid-template-columns: 1fr; }
  .site-grid { grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
  .stat-grid { grid-template-columns: 1fr; }
  .hero { flex-direction: column; }
  .donut-wrap { grid-template-columns: 1fr; justify-items: center; }
}
</style>
