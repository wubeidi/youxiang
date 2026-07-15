<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getAccounts,
  startWatchBatch,
  getActiveWatches,
  stopAllWatches,
  clearFinishedWatches,
  startWatch,
  stopWatch
} from '../api'

const selectedIds = ref([])
const accountOptions = ref([])
const selectLoading = ref(false)
const boards = ref([])
const starting = ref(false)
let boardTimer = null

const summary = computed(() => {
  const list = boards.value || []
  return {
    total: list.length,
    active: list.filter((b) => b.active).length,
    coded: list.filter((b) => b.latest_code).length,
    error: list.filter((b) => !b.active && b.last_error).length
  }
})

async function remoteSearch(q) {
  if (!q) {
    accountOptions.value = []
    return
  }
  selectLoading.value = true
  try {
    const res = await getAccounts({ q, page: 1, size: 50 })
    accountOptions.value = res.items || []
  } catch (e) {
    // 错误已提示
  } finally {
    selectLoading.value = false
  }
}

async function refreshBoards() {
  try {
    boards.value = await getActiveWatches()
  } catch (e) {
    // 静默
  }
}

function startBoardPolling() {
  stopBoardPolling()
  boardTimer = setInterval(refreshBoards, 2500)
}

function stopBoardPolling() {
  if (boardTimer) {
    clearInterval(boardTimer)
    boardTimer = null
  }
}

async function startSelected() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先选择要监听的账号')
    return
  }
  starting.value = true
  try {
    const res = await startWatchBatch(selectedIds.value)
    boards.value = res.active || []
    const okCount = (res.started || []).length
    const failCount = (res.failed || []).length
    if (failCount) {
      ElMessage.warning(`已开始 ${okCount} 个，${failCount} 个失败（多为超出并发上限）`)
    } else {
      ElMessage.success(`已开始监听 ${okCount} 个账号`)
    }
    selectedIds.value = []
    accountOptions.value = []
  } catch (e) {
    // 错误已提示
  } finally {
    starting.value = false
  }
}

async function stopOne(b) {
  try {
    await stopWatch(b.account_id)
    await refreshBoards()
  } catch (e) { /* 忽略 */ }
}

async function restartOne(b) {
  try {
    await startWatch(b.account_id)
    await refreshBoards()
  } catch (e) { /* 忽略 */ }
}

async function handleStopAll() {
  try {
    const res = await stopAllWatches()
    boards.value = res.active || []
    ElMessage.success(`已停止 ${res.stopped} 个监听`)
  } catch (e) { /* 忽略 */ }
}

async function handleClearFinished() {
  try {
    const res = await clearFinishedWatches()
    boards.value = res.active || []
    ElMessage.success(`已清除 ${res.cleared} 条已结束记录`)
  } catch (e) { /* 忽略 */ }
}

function cardStatus(b) {
  if (b.latest_code) return { text: '已收到验证码', cls: 'is-code' }
  if (b.active) return { text: '监听中', cls: 'is-active' }
  if (b.last_error) return { text: '账号报错', cls: 'is-error' }
  return { text: '已结束', cls: 'is-ended' }
}

function progressPercent(b) {
  if (!b.active || !b.duration) return 0
  return Math.round((b.remaining_seconds / b.duration) * 100)
}

function providerLetter(email = '') {
  return (email[0] || 'M').toUpperCase()
}

function providerColor(email = '') {
  const e = email.toLowerCase()
  if (e.includes('gmail')) return '#ea4335'
  if (e.includes('outlook') || e.includes('hotmail') || e.includes('live.')) return '#0078d4'
  if (e.includes('yahoo')) return '#6001d2'
  if (e.includes('icloud') || e.includes('me.com')) return '#3b82f6'
  return '#4f6ef7'
}

function copyCode(code) {
  if (!code) return
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(code).then(() => ElMessage.success('验证码已复制'))
  } else {
    const ta = document.createElement('textarea')
    ta.value = code
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    ElMessage.success('验证码已复制')
  }
}

onMounted(() => {
  refreshBoards()
  startBoardPolling()
})
onUnmounted(stopBoardPolling)
</script>

<template>
  <div class="page-shell">
    <div class="hero">
      <div>
        <h2 class="page-title" style="font-size:24px">监听看板</h2>
        <p class="page-subtitle">同时监听多个邮箱，验证码到账即时展示</p>
      </div>
    </div>

    <div class="summary-grid">
      <div class="sum-card">
        <div class="sum-label">监听中</div>
        <div class="sum-value blue">{{ summary.active }}</div>
      </div>
      <div class="sum-card">
        <div class="sum-label">已收到验证码</div>
        <div class="sum-value green">{{ summary.coded }}</div>
      </div>
      <div class="sum-card">
        <div class="sum-label">异常结束</div>
        <div class="sum-value red">{{ summary.error }}</div>
      </div>
      <div class="sum-card">
        <div class="sum-label">看板条目</div>
        <div class="sum-value">{{ summary.total }}</div>
      </div>
    </div>

    <div class="toolbar mh-card">
      <div class="toolbar-left">
        <el-select
          v-model="selectedIds"
          multiple
          filterable
          remote
          reserve-keyword
          collapse-tags
          collapse-tags-tooltip
          placeholder="输入邮箱搜索，可多选"
          :remote-method="remoteSearch"
          :loading="selectLoading"
          style="width: 360px"
        >
          <el-option
            v-for="acc in accountOptions"
            :key="acc.id"
            :label="acc.email"
            :value="acc.id"
          />
        </el-select>
        <el-button type="primary" :loading="starting" @click="startSelected">
          开始监听选中（{{ selectedIds.length }}）
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-button :icon="'Refresh'" @click="refreshBoards">刷新</el-button>
        <el-button type="warning" plain @click="handleClearFinished">清除已结束</el-button>
        <el-button type="danger" plain @click="handleStopAll">全部停止</el-button>
      </div>
    </div>

    <div class="tip-card">
      搜索并选中要等验证码的账号，点「开始监听」。系统会短时快拉这些账号，收到验证码后卡片高亮并可一键复制；超时或拿到码会自动停止，不影响其他账号。
    </div>

    <el-empty v-if="!boards.length" description="暂无监听中的账号，从上方选择账号开始" />
    <div v-else class="watch-grid">
      <div
        v-for="b in boards"
        :key="b.account_id"
        class="watch-card"
        :class="cardStatus(b).cls"
      >
        <div class="card-head">
          <div class="provider" :style="{ background: providerColor(b.email) }">
            {{ providerLetter(b.email) }}
          </div>
          <div class="head-meta">
            <div class="card-email" :title="b.email">{{ b.email || `账号 #${b.account_id}` }}</div>
            <div class="card-status">{{ cardStatus(b).text }}</div>
          </div>
        </div>

        <div v-if="b.latest_code" class="card-body">
          <div class="code-big">{{ b.latest_code }}</div>
          <el-button type="primary" size="small" @click="copyCode(b.latest_code)">复制验证码</el-button>
          <div v-if="b.latest_subject" class="card-sub" :title="b.latest_subject">{{ b.latest_subject }}</div>
        </div>

        <div v-else-if="b.active" class="card-body">
          <div class="waiting-tip">
            <el-icon class="is-loading"><Loading /></el-icon>
            等待验证码…
          </div>
          <div class="card-meta">剩余 {{ b.remaining_seconds }}s · 已检查 {{ b.poll_count }} 次</div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: `${progressPercent(b)}%` }" />
          </div>
        </div>

        <div v-else class="card-body">
          <div v-if="b.last_error" class="card-error" :title="b.last_error">报错：{{ b.last_error }}</div>
          <div v-else class="card-meta">本次未收到验证码</div>
        </div>

        <div class="card-foot">
          <el-button v-if="b.active" size="small" type="warning" plain @click="stopOne(b)">停止</el-button>
          <el-button v-else size="small" type="success" plain @click="restartOne(b)">重新监听</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hero {
  margin-bottom: 16px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.sum-card {
  background: #fff;
  border-radius: 18px;
  padding: 16px;
  border: 1px solid rgba(232, 237, 245, 0.95);
  box-shadow: var(--mh-shadow);
}

.sum-label {
  color: #98a2b3;
  font-size: 13px;
  margin-bottom: 8px;
}

.sum-value {
  font-size: 28px;
  font-weight: 800;
  color: #1f2a44;
  letter-spacing: -0.03em;
}

.sum-value.blue { color: #4f6ef7; }
.sum-value.green { color: #16a34a; }
.sum-value.red { color: #e11d48; }

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 14px 16px;
  margin-bottom: 14px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.tip-card {
  background: #eef2ff;
  color: #4f6ef7;
  border-radius: 14px;
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 16px;
}

.watch-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.watch-card {
  background: #fff;
  border-radius: 22px;
  padding: 16px;
  border: 1px solid rgba(232, 237, 245, 0.95);
  box-shadow: var(--mh-shadow);
  border-top: 3px solid transparent;
  min-height: 220px;
  display: flex;
  flex-direction: column;
}

.watch-card.is-code { border-top-color: #22c55e; }
.watch-card.is-active { border-top-color: #4f6ef7; }
.watch-card.is-error { border-top-color: #f56c6c; }
.watch-card.is-ended { border-top-color: #cbd5e1; }

.card-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.provider {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 800;
  flex-shrink: 0;
}

.head-meta {
  min-width: 0;
  flex: 1;
}

.card-email {
  font-size: 13px;
  font-weight: 700;
  color: #1f2a44;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-status {
  margin-top: 2px;
  font-size: 12px;
  color: #98a2b3;
}

.card-body {
  min-height: 110px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-align: center;
  flex: 1;
}

.code-big {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: 4px;
  color: #16a34a;
  font-family: Consolas, Monaco, monospace;
}

.waiting-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #4f6ef7;
  font-size: 14px;
  font-weight: 600;
}

.card-meta {
  color: #98a2b3;
  font-size: 12px;
}

.card-sub {
  color: #98a2b3;
  font-size: 12px;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-error {
  color: #f56c6c;
  font-size: 12px;
  max-width: 100%;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.progress-bar {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: #eef2f7;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #4f6ef7, #7a5af8);
}

.card-foot {
  margin-top: 10px;
  display: flex;
  justify-content: center;
}

@media (max-width: 1200px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .watch-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .summary-grid,
  .watch-grid { grid-template-columns: 1fr; }
}
</style>
