<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
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

// ========== 账号选择（远程搜索，支持上千账号）==========
const selectedIds = ref([])
const accountOptions = ref([])
const selectLoading = ref(false)

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

// ========== 看板数据 ==========
const boards = ref([])
const starting = ref(false)
let boardTimer = null

// 拉取所有监听状态
async function refreshBoards() {
  try {
    boards.value = await getActiveWatches()
  } catch (e) {
    // 静默：轮询失败不打扰
  }
}

// 每 2.5 秒轮询一次看板
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

// 批量开始监听选中的账号
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

// 单个操作
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

// 全局操作
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

// ========== 展示辅助 ==========
function cardStatus(b) {
  if (b.latest_code) return { type: 'success', text: '已收到验证码', cls: 'is-code' }
  if (b.active) return { type: 'primary', text: '监听中', cls: 'is-active' }
  if (b.last_error) return { type: 'danger', text: '账号报错', cls: 'is-error' }
  return { type: 'info', text: '已结束', cls: 'is-ended' }
}

function progressPercent(b) {
  if (!b.active || !b.duration) return 0
  return Math.round((b.remaining_seconds / b.duration) * 100)
}

function copyCode(code) {
  if (!code) return
  if (navigator.clipboard && navigator.clipboard.writeText) {
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
    <div style="margin-bottom:8px">
      <h2 class="page-title" style="font-size:24px">监听看板</h2>
      <p class="page-subtitle">同时监听多个邮箱，验证码到账即时展示</p>
    </div>
    <!-- 工具栏 -->
    <div class="toolbar mh-card" style="padding:14px 16px;margin-bottom:16px">
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

    <!-- 说明 -->
    <el-alert
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
      title="使用说明"
    >
      搜索并选中要等验证码的账号，点「开始监听」。系统会同时对这些账号短时快拉，收到验证码即在对应卡片高亮显示、可一键复制。拿到码或超时会自动停止，不影响其他账号。
    </el-alert>

    <!-- 看板卡片 -->
    <el-empty v-if="!boards.length" description="暂无监听中的账号，从上方选择账号开始" />
    <el-row v-else :gutter="16">
      <el-col
        v-for="b in boards"
        :key="b.account_id"
        :xs="24" :sm="12" :md="8" :lg="6"
        style="margin-bottom: 16px"
      >
        <el-card shadow="hover" :class="['watch-card', cardStatus(b).cls]" body-style="padding: 16px">
          <!-- 卡片头：邮箱 + 状态 -->
          <div class="card-head">
            <span class="card-email" :title="b.email">{{ b.email }}</span>
            <el-tag :type="cardStatus(b).type" size="small" effect="dark">{{ cardStatus(b).text }}</el-tag>
          </div>

          <!-- 已收到验证码 -->
          <div v-if="b.latest_code" class="card-body">
            <div class="code-big">{{ b.latest_code }}</div>
            <el-button type="primary" size="small" @click="copyCode(b.latest_code)">复制验证码</el-button>
            <div v-if="b.latest_subject" class="card-sub" :title="b.latest_subject">{{ b.latest_subject }}</div>
          </div>

          <!-- 监听中 -->
          <div v-else-if="b.active" class="card-body">
            <div class="waiting-tip">
              <el-icon class="is-loading"><Loading /></el-icon>
              等待验证码…
            </div>
            <div class="card-meta">剩余 {{ b.remaining_seconds }}s · 已检查 {{ b.poll_count }} 次</div>
            <el-progress :percentage="progressPercent(b)" :show-text="false" :stroke-width="5" />
          </div>

          <!-- 结束/报错 -->
          <div v-else class="card-body">
            <div v-if="b.last_error" class="card-error" :title="b.last_error">报错：{{ b.last_error }}</div>
            <div v-else class="card-meta">本次未收到验证码</div>
          </div>

          <!-- 卡片底操作 -->
          <div class="card-foot">
            <el-button v-if="b.active" size="small" type="warning" plain @click="stopOne(b)">停止</el-button>
            <el-button v-else size="small" type="success" plain @click="restartOne(b)">重新监听</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 10px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.watch-card {
  transition: border-color 0.2s;
  border-top: 3px solid transparent;
}

.watch-card.is-code {
  border-top-color: #67c23a;
}

.watch-card.is-active {
  border-top-color: #409eff;
}

.watch-card.is-error {
  border-top-color: #f56c6c;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}

.card-email {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-body {
  min-height: 92px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-align: center;
}

.code-big {
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 4px;
  color: #67c23a;
  font-family: 'Consolas', 'Monaco', monospace;
}

.waiting-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #409eff;
  font-size: 14px;
}

.card-meta {
  color: #909399;
  font-size: 12px;
}

.card-sub {
  color: #909399;
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
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.card-foot {
  margin-top: 12px;
  display: flex;
  justify-content: center;
}

.card-body .el-progress {
  width: 100%;
}
</style>
