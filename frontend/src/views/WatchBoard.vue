<script setup>
import { computed, reactive, ref, onMounted, onUnmounted } from 'vue'
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

// ========== 已选账号（用 Map 保留 email，方便展示标签）==========
const selectedMap = ref(new Map()) // id -> email
const selectedIds = computed(() => Array.from(selectedMap.value.keys()))
const selectedCount = computed(() => selectedMap.value.size)
const selectedList = computed(() =>
  Array.from(selectedMap.value.entries()).map(([id, email]) => ({ id, email }))
)

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

// ========== 选号面板 ==========
const pickerVisible = ref(false)
const pickerLoading = ref(false)
const pickerRows = ref([])
const pickerTotal = ref(0)
const pickerQuery = reactive({
  q: '',
  status: '',
  page: 1,
  size: 20
})
const pasteText = ref('')
const pasteLoading = ref(false)

const statusOptions = [
  { label: '全部状态', value: '' },
  { label: '正常', value: 'ok' },
  { label: '错误', value: 'error' },
  { label: '待处理', value: 'pending' }
]

function isSelected(id) {
  return selectedMap.value.has(id)
}

function setSelected(id, email, on) {
  const next = new Map(selectedMap.value)
  if (on) next.set(id, email)
  else next.delete(id)
  selectedMap.value = next
}

function toggleRow(row) {
  setSelected(row.id, row.email, !isSelected(row.id))
}

function clearSelected() {
  selectedMap.value = new Map()
}

function removeSelected(id) {
  setSelected(id, '', false)
}

function selectCurrentPage() {
  const next = new Map(selectedMap.value)
  for (const row of pickerRows.value) next.set(row.id, row.email)
  selectedMap.value = next
  ElMessage.success(`已勾选当前页 ${pickerRows.value.length} 个`)
}

function unselectCurrentPage() {
  const next = new Map(selectedMap.value)
  for (const row of pickerRows.value) next.delete(row.id)
  selectedMap.value = next
}

function selectAllLoadedOk() {
  const next = new Map(selectedMap.value)
  let n = 0
  for (const row of pickerRows.value) {
    if (row.status === 'ok') {
      next.set(row.id, row.email)
      n += 1
    }
  }
  selectedMap.value = next
  ElMessage.success(`已勾选当前页正常账号 ${n} 个`)
}

async function loadPicker() {
  pickerLoading.value = true
  try {
    const res = await getAccounts({
      q: pickerQuery.q || undefined,
      status: pickerQuery.status || undefined,
      page: pickerQuery.page,
      size: pickerQuery.size
    })
    pickerRows.value = res.items || []
    pickerTotal.value = res.total || 0
  } catch (e) {
    // 错误已提示
  } finally {
    pickerLoading.value = false
  }
}

function openPicker() {
  pickerVisible.value = true
  pickerQuery.page = 1
  loadPicker()
}

function handlePickerSearch() {
  pickerQuery.page = 1
  loadPicker()
}

function handlePickerPageChange(page) {
  pickerQuery.page = page
  loadPicker()
}

function handlePickerSizeChange(size) {
  pickerQuery.size = size
  pickerQuery.page = 1
  loadPicker()
}

/**
 * 粘贴批量邮箱：支持换行 / 逗号 / 分号 / 空白分隔
 * 自动解析并分页检索匹配账号加入已选
 */
async function handlePasteSelect() {
  const raw = (pasteText.value || '').trim()
  if (!raw) {
    ElMessage.warning('请先粘贴邮箱列表')
    return
  }
  const emails = Array.from(
    new Set(
      raw
        .split(/[\s,;，；|]+/)
        .map((s) => s.trim().toLowerCase())
        .filter((s) => s.includes('@'))
    )
  )
  if (!emails.length) {
    ElMessage.warning('未识别到有效邮箱')
    return
  }

  pasteLoading.value = true
  let matched = 0
  let missing = 0
  const next = new Map(selectedMap.value)
  try {
    // 逐个精确搜索（后端是模糊搜，取 items 里 email 全等）
    // 控制并发，避免一次打爆
    const concurrency = 8
    for (let i = 0; i < emails.length; i += concurrency) {
      const chunk = emails.slice(i, i + concurrency)
      const results = await Promise.all(
        chunk.map(async (email) => {
          try {
            const res = await getAccounts({ q: email, page: 1, size: 20 })
            const hit = (res.items || []).find((x) => (x.email || '').toLowerCase() === email)
            return hit || null
          } catch (e) {
            return null
          }
        })
      )
      for (let j = 0; j < chunk.length; j++) {
        const hit = results[j]
        if (hit) {
          next.set(hit.id, hit.email)
          matched += 1
        } else {
          missing += 1
        }
      }
    }
    selectedMap.value = next
    pasteText.value = ''
    if (missing) {
      ElMessage.warning(`已加入 ${matched} 个，未匹配 ${missing} 个`)
    } else {
      ElMessage.success(`已加入 ${matched} 个邮箱`)
    }
  } finally {
    pasteLoading.value = false
  }
}

// ========== 看板逻辑 ==========
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
    // 成功后清空已选，避免重复点
    clearSelected()
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

function statusMeta(status) {
  if (status === 'ok') return { text: '正常', cls: 'ok' }
  if (status === 'error') return { text: '异常', cls: 'err' }
  return { text: '待测', cls: 'pending' }
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
        <p class="page-subtitle">批量选择邮箱，验证码到账即时展示</p>
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

    <!-- 选号区 -->
    <div class="picker-bar mh-card">
      <div class="picker-left">
        <el-button type="primary" :icon="'Plus'" @click="openPicker">选择邮箱</el-button>
        <el-button :disabled="!selectedCount" @click="clearSelected">清空已选</el-button>
        <span class="picked-count">已选 <b>{{ selectedCount }}</b> 个</span>
      </div>
      <div class="picker-right">
        <el-button
          type="success"
          :loading="starting"
          :disabled="!selectedCount"
          @click="startSelected"
        >
          开始监听（{{ selectedCount }}）
        </el-button>
        <el-button :icon="'Refresh'" @click="refreshBoards">刷新看板</el-button>
        <el-button type="warning" plain @click="handleClearFinished">清除已结束</el-button>
        <el-button type="danger" plain @click="handleStopAll">全部停止</el-button>
      </div>
    </div>

    <!-- 已选标签 -->
    <div v-if="selectedList.length" class="selected-box mh-card">
      <div class="selected-head">
        <span>待监听邮箱</span>
        <el-button text type="primary" @click="openPicker">继续添加</el-button>
      </div>
      <div class="selected-tags">
        <el-tag
          v-for="item in selectedList"
          :key="item.id"
          closable
          effect="plain"
          class="email-tag"
          @close="removeSelected(item.id)"
        >
          {{ item.email }}
        </el-tag>
      </div>
    </div>
    <div v-else class="tip-card">
      点击「选择邮箱」打开选号面板：可搜索、按状态筛选、勾选当前页，或直接粘贴一批邮箱地址。
    </div>

    <!-- 看板卡片 -->
    <el-empty v-if="!boards.length" description="暂无监听中的账号，先选择邮箱开始监听" />
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

    <!-- 选号弹窗 -->
    <el-dialog
      v-model="pickerVisible"
      title="选择要监听的邮箱"
      width="860px"
      top="5vh"
      destroy-on-close
    >
      <div class="picker-toolbar">
        <el-input
          v-model="pickerQuery.q"
          placeholder="搜索邮箱"
          clearable
          style="width: 240px"
          :prefix-icon="'Search'"
          @keyup.enter="handlePickerSearch"
          @clear="handlePickerSearch"
        />
        <el-select
          v-model="pickerQuery.status"
          style="width: 130px"
          @change="handlePickerSearch"
        >
          <el-option
            v-for="opt in statusOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-button type="primary" :icon="'Search'" @click="handlePickerSearch">查询</el-button>
        <el-button @click="selectCurrentPage">全选当前页</el-button>
        <el-button @click="unselectCurrentPage">取消当前页</el-button>
        <el-button @click="selectAllLoadedOk">只选当前页正常</el-button>
      </div>

      <el-table
        v-loading="pickerLoading"
        :data="pickerRows"
        height="360"
        border
        stripe
        row-key="id"
        @row-click="toggleRow"
      >
        <el-table-column width="52" align="center">
          <template #default="{ row }">
            <el-checkbox
              :model-value="isSelected(row.id)"
              @click.stop
              @change="(val) => setSelected(row.id, row.email, val)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="240" show-overflow-tooltip />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <span class="status-pill" :class="statusMeta(row.status).cls">
              {{ statusMeta(row.status).text }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="message_count" label="邮件数" width="90" align="center" />
      </el-table>

      <div class="picker-pagination">
        <el-pagination
          :current-page="pickerQuery.page"
          :page-size="pickerQuery.size"
          :total="pickerTotal"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="handlePickerPageChange"
          @size-change="handlePickerSizeChange"
        />
      </div>

      <div class="paste-box">
        <div class="paste-title">批量粘贴邮箱（可选）</div>
        <el-input
          v-model="pasteText"
          type="textarea"
          :rows="3"
          placeholder="支持换行 / 逗号 / 分号分隔，例如：&#10;a@outlook.com&#10;b@outlook.com, c@outlook.com"
        />
        <div class="paste-actions">
          <el-button type="primary" plain :loading="pasteLoading" @click="handlePasteSelect">
            解析并加入已选
          </el-button>
          <span class="paste-tip">已选 {{ selectedCount }} 个（跨页保留）</span>
        </div>
      </div>

      <template #footer>
        <el-button @click="pickerVisible = false">完成选择</el-button>
        <el-button type="success" :disabled="!selectedCount" :loading="starting" @click="startSelected">
          开始监听（{{ selectedCount }}）
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.hero { margin-bottom: 16px; }

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

.sum-label { color: #98a2b3; font-size: 13px; margin-bottom: 8px; }
.sum-value { font-size: 28px; font-weight: 800; color: #1f2a44; letter-spacing: -0.03em; }
.sum-value.blue { color: #4f6ef7; }
.sum-value.green { color: #16a34a; }
.sum-value.red { color: #e11d48; }

.picker-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 14px 16px;
  margin-bottom: 14px;
}

.picker-left,
.picker-right {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.picked-count {
  color: #667085;
  font-size: 13px;
}

.picked-count b {
  color: #4f6ef7;
  font-size: 16px;
}

.selected-box {
  padding: 14px 16px;
  margin-bottom: 16px;
}

.selected-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-weight: 700;
  color: #1f2a44;
}

.selected-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.email-tag {
  max-width: 100%;
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

.head-meta { min-width: 0; flex: 1; }
.card-email {
  font-size: 13px;
  font-weight: 700;
  color: #1f2a44;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-status { margin-top: 2px; font-size: 12px; color: #98a2b3; }

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

.card-meta { color: #98a2b3; font-size: 12px; }
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

/* 选号弹窗 */
.picker-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}

.picker-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.paste-box {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed #e5eaf2;
}

.paste-title {
  font-weight: 700;
  margin-bottom: 8px;
  color: #1f2a44;
}

.paste-actions {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.paste-tip {
  color: #98a2b3;
  font-size: 12px;
}

.status-pill {
  font-size: 12px;
  font-weight: 700;
  border-radius: 999px;
  padding: 2px 8px;
}
.status-pill.ok { background: #eef2ff; color: #4f6ef7; }
.status-pill.err { background: #fff1f2; color: #e11d48; }
.status-pill.pending { background: #f3f4f6; color: #6b7280; }

:deep(.el-table__row) {
  cursor: pointer;
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
