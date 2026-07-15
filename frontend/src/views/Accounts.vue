<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAccounts,
  importAccountsFile,
  importAccountsText,
  refreshAccount,
  deleteAccount,
  getAccountSites,
  startWatch,
  stopWatch,
  getWatchStatus,
  checkAccount,
  checkAccountsBatch,
  getCheckJob,
  cancelCheckJob
} from '../api'

const router = useRouter()
const loading = ref(false)
const tableData = ref([])
const total = ref(0)

const query = reactive({
  q: '',
  status: '',
  page: 1,
  size: 12
})

const statusOptions = [
  { label: '全部', value: '' },
  { label: '正常', value: 'ok' },
  { label: '错误', value: 'error' },
  { label: '待处理', value: 'pending' }
]

function statusMeta(status) {
  if (status === 'ok') return { text: '正常', cls: 'ok' }
  if (status === 'error') return { text: '异常', cls: 'err' }
  return { text: '待测', cls: 'pending' }
}

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

async function loadAccounts() {
  loading.value = true
  try {
    const res = await getAccounts({
      q: query.q || undefined,
      status: query.status || undefined,
      page: query.page,
      size: query.size
    })
    tableData.value = res.items || []
    total.value = res.total || 0
  } catch (e) {
    // 错误已提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  loadAccounts()
}

function handlePageChange(page) {
  query.page = page
  loadAccounts()
}

function handleSizeChange(size) {
  query.size = size
  query.page = 1
  loadAccounts()
}

function formatTime(t) {
  if (!t) return '尚未拉取'
  const d = new Date(t)
  if (isNaN(d.getTime())) return t
  return d.toLocaleString('zh-CN', { hour12: false })
}

// ========== 导入 ==========
const importDialogVisible = ref(false)
const importTab = ref('file')
const importText = ref('')
const importLoading = ref(false)
const selectedFile = ref(null)
const importResult = ref(null)
const resultDialogVisible = ref(false)

function openImportDialog() {
  importTab.value = 'file'
  importText.value = ''
  selectedFile.value = null
  importDialogVisible.value = true
}

function handleFileChange(file) {
  selectedFile.value = file.raw
}

async function handleImport() {
  importLoading.value = true
  try {
    let res
    if (importTab.value === 'file') {
      if (!selectedFile.value) {
        ElMessage.warning('请先选择要上传的 .txt 文件')
        importLoading.value = false
        return
      }
      res = await importAccountsFile(selectedFile.value)
    } else {
      if (!importText.value.trim()) {
        ElMessage.warning('请粘贴要导入的内容')
        importLoading.value = false
        return
      }
      res = await importAccountsText(importText.value)
    }
    importResult.value = res
    importDialogVisible.value = false
    resultDialogVisible.value = true
    loadAccounts()
  } catch (e) {
    // 错误已提示
  } finally {
    importLoading.value = false
  }
}

// ========== 行操作 ==========
const refreshingIds = ref(new Set())
const checkingIds = ref(new Set())
const batchChecking = ref(false)
const checkResultVisible = ref(false)
const checkResult = ref(null)
const checkJobVisible = ref(false)
const checkJob = ref(null)
let checkJobTimer = null
let checkJobId = null

function stopCheckJobPolling() {
  if (checkJobTimer) {
    clearInterval(checkJobTimer)
    checkJobTimer = null
  }
}

async function pollCheckJobOnce() {
  if (!checkJobId) return
  try {
    const job = await getCheckJob(checkJobId)
    checkJob.value = job
    // 终态：展示结果
    if (['done', 'error', 'cancelled'].includes(job.status)) {
      stopCheckJobPolling()
      batchChecking.value = false
      checkResult.value = {
        total: job.total,
        alive: job.alive,
        dead: job.dead,
        items: job.items || []
      }
      // 稍等一下让用户看到 100%，再切结果
      setTimeout(async () => {
        checkJobVisible.value = false
        checkResultVisible.value = true
        await loadAccounts()
      }, 400)
    }
  } catch (e) {
    // 轮询失败不立刻结束任务（后端可能还在跑）；连续失败由用户手动关闭
  }
}

function startCheckJobPolling(jobId) {
  stopCheckJobPolling()
  checkJobId = jobId
  // 立即拉一次，再定时轮询
  pollCheckJobOnce()
  checkJobTimer = setInterval(pollCheckJobOnce, 1500)
}

async function handleCancelCheckJob() {
  if (!checkJobId) {
    checkJobVisible.value = false
    batchChecking.value = false
    return
  }
  try {
    await cancelCheckJob(checkJobId)
  } catch (e) {
    // 忽略
  } finally {
    stopCheckJobPolling()
    batchChecking.value = false
    checkJobVisible.value = false
    // 取消后也刷新列表，展示已测完的那部分状态
    loadAccounts()
  }
}

function isRefreshing(id) {
  return refreshingIds.value.has(id)
}
function isChecking(id) {
  return checkingIds.value.has(id)
}

async function handleRefresh(row) {
  refreshingIds.value.add(row.id)
  refreshingIds.value = new Set(refreshingIds.value)
  try {
    const res = await refreshAccount(row.id)
    row.status = res.status
    row.last_error = res.last_error
    row.message_count = res.message_count
    row.last_polled_at = new Date().toISOString()
    ElMessage.success('刷新完成')
  } catch (e) {
    // 错误已提示
  } finally {
    refreshingIds.value.delete(row.id)
    refreshingIds.value = new Set(refreshingIds.value)
  }
}

async function handleCheck(row) {
  checkingIds.value.add(row.id)
  checkingIds.value = new Set(checkingIds.value)
  try {
    const res = await checkAccount(row.id)
    row.status = res.status
    row.last_error = res.error
    row.last_polled_at = new Date().toISOString()
    if (res.alive) ElMessage.success(`${row.email} 存活`)
    else ElMessage.error(`${row.email} 失效：${res.error || '未知错误'}`)
  } catch (e) {
    // 错误已提示
  } finally {
    checkingIds.value.delete(row.id)
    checkingIds.value = new Set(checkingIds.value)
  }
}

async function handleBatchCheck(scope) {
  let ids = null
  let tip = '全部启用账号'
  if (scope === 'page') {
    ids = tableData.value.map((r) => r.id)
    if (!ids.length) {
      ElMessage.warning('当前页没有账号')
      return
    }
    tip = `当前页 ${ids.length} 个账号`
  }
  try {
    await ElMessageBox.confirm(
      `确定对「${tip}」执行测活？\n只会验证 OAuth/IMAP 是否可登录，不拉取邮件正文。`,
      '批量测活',
      { confirmButtonText: '开始', cancelButtonText: '取消', type: 'info' }
    )
  } catch (e) {
    return
  }
  batchChecking.value = true
  checkJob.value = {
    status: 'running',
    total: ids ? ids.length : 0,
    done: 0,
    alive: 0,
    dead: 0,
    percent: 0,
    elapsed_seconds: 0
  }
  checkJobVisible.value = true
  try {
    // 异步任务：秒回 job_id，再轮询进度（解决「前端超时、后端还在测」）
    const job = await checkAccountsBatch(ids)
    checkJob.value = job
    if (['done', 'error', 'cancelled'].includes(job.status)) {
      batchChecking.value = false
      checkResult.value = {
        total: job.total,
        alive: job.alive,
        dead: job.dead,
        items: job.items || []
      }
      checkJobVisible.value = false
      checkResultVisible.value = true
      await loadAccounts()
    } else {
      startCheckJobPolling(job.job_id)
    }
  } catch (e) {
    batchChecking.value = false
    checkJobVisible.value = false
    // 错误已提示
  }
}

function handleViewMessages(row) {
  router.push({ path: '/messages', query: { account_id: row.id } })
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除账号 ${row.email} 吗？此操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteAccount(row.id)
    ElMessage.success('删除成功')
    loadAccounts()
  } catch (e) {
    // 用户取消或错误
  }
}

// ========== 注册网站 ==========
const sitesDialogVisible = ref(false)
const sitesLoading = ref(false)
const sitesData = ref([])
const currentEmail = ref('')

async function handleViewSites(row) {
  currentEmail.value = row.email
  sitesData.value = []
  sitesDialogVisible.value = true
  sitesLoading.value = true
  try {
    sitesData.value = (await getAccountSites(row.id)) || []
  } catch (e) {
    // 错误已提示
  } finally {
    sitesLoading.value = false
  }
}

// ========== 临时监听 ==========
const watchDialogVisible = ref(false)
const watchEmail = ref('')
const watchAccountId = ref(null)
const watchState = reactive({
  active: false,
  remaining: 0,
  maxRemaining: 0,
  pollCount: 0,
  code: null,
  subject: null,
  from: null,
  lastError: null
})
let watchTimer = null

function applyWatchStatus(s) {
  watchState.active = !!s.active
  watchState.remaining = s.remaining_seconds || 0
  watchState.maxRemaining = Math.max(watchState.maxRemaining, watchState.remaining)
  watchState.pollCount = s.poll_count || 0
  watchState.code = s.latest_code || null
  watchState.subject = s.latest_subject || null
  watchState.from = s.latest_from || null
  watchState.lastError = s.last_error || null
}

function resetWatchState() {
  Object.assign(watchState, {
    active: false, remaining: 0, maxRemaining: 0, pollCount: 0,
    code: null, subject: null, from: null, lastError: null
  })
}

async function openWatchDialog(row) {
  watchEmail.value = row.email
  watchAccountId.value = row.id
  resetWatchState()
  watchDialogVisible.value = true
  await beginWatch()
}

async function beginWatch() {
  try {
    const res = await startWatch(watchAccountId.value)
    applyWatchStatus(res)
    startWatchPolling()
  } catch (e) {
    // 错误已提示
  }
}

function startWatchPolling() {
  stopWatchPolling()
  watchTimer = setInterval(async () => {
    if (!watchAccountId.value) return
    try {
      const s = await getWatchStatus(watchAccountId.value)
      applyWatchStatus(s)
      if (s.latest_code || !s.active) {
        stopWatchPolling()
        if (s.latest_code) ElMessage.success('已收到验证码')
      }
    } catch (e) {
      stopWatchPolling()
    }
  }, 2000)
}

function stopWatchPolling() {
  if (watchTimer) {
    clearInterval(watchTimer)
    watchTimer = null
  }
}

async function handleStopWatch() {
  stopWatchPolling()
  try {
    applyWatchStatus(await stopWatch(watchAccountId.value))
  } catch (e) { /* 忽略 */ }
}

async function restartWatch() {
  resetWatchState()
  await beginWatch()
}

async function onWatchClosed() {
  stopWatchPolling()
  const id = watchAccountId.value
  if (id && watchState.active) {
    try { await stopWatch(id) } catch (e) { /* 忽略 */ }
  }
  watchState.active = false
  loadAccounts()
}

function copyCode() {
  const code = watchState.code
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

onMounted(loadAccounts)
onUnmounted(() => {
  stopWatchPolling()
  stopCheckJobPolling()
})
</script>

<template>
  <div class="page-shell">
    <div class="hero">
      <div>
        <h2 class="page-title" style="font-size:24px">邮箱管理</h2>
        <p class="page-subtitle">卡片式管理全部邮箱 · 导入 / 测活 / 刷新 / 收码</p>
      </div>
      <div class="hero-actions">
        <el-button type="primary" :icon="'Upload'" @click="openImportDialog">导入配置</el-button>
        <el-dropdown split-button type="warning" :loading="batchChecking" @click="handleBatchCheck('page')">
          测活当前页
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="handleBatchCheck('page')">测活当前页</el-dropdown-item>
              <el-dropdown-item @click="handleBatchCheck('all')">测活全部启用账号</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <div class="toolbar mh-card">
      <div class="toolbar-left">
        <el-input
          v-model="query.q"
          placeholder="搜索邮箱地址"
          clearable
          style="width: 260px"
          :prefix-icon="'Search'"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-select v-model="query.status" placeholder="状态" style="width: 130px" @change="handleSearch">
          <el-option v-for="opt in statusOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-button type="primary" :icon="'Search'" @click="handleSearch">查询</el-button>
      </div>
      <div class="toolbar-right">
        <span class="total-tip">共 {{ total }} 个邮箱</span>
        <el-button :icon="'Refresh'" @click="loadAccounts">刷新</el-button>
      </div>
    </div>

    <div v-loading="loading">
      <div v-if="tableData.length" class="card-grid">
        <div v-for="row in tableData" :key="row.id" class="mail-card">
          <div class="mail-top">
            <div class="provider" :style="{ background: providerOf(row.email).color }">
              {{ providerOf(row.email).letter }}
            </div>
            <div class="mail-meta">
              <div class="mail-email" :title="row.email">{{ row.email }}</div>
              <div class="mail-provider">{{ providerOf(row.email).name }}</div>
            </div>
            <span class="status-pill" :class="statusMeta(row.status).cls">
              {{ statusMeta(row.status).text }}
            </span>
          </div>

          <div class="metrics">
            <div>
              <div class="m-label">邮件数</div>
              <div class="m-value">{{ row.message_count || 0 }}</div>
            </div>
            <div>
              <div class="m-label">启用</div>
              <div class="m-value small">{{ row.enabled ? '是' : '否' }}</div>
            </div>
          </div>

          <div class="time-line">
            <el-icon><Clock /></el-icon>
            <span>{{ formatTime(row.last_polled_at) }}</span>
          </div>

          <div v-if="row.status === 'error' && row.last_error" class="err-line" :title="row.last_error">
            {{ row.last_error }}
          </div>

          <div class="actions">
            <el-button size="small" type="primary" :loading="isRefreshing(row.id)" @click="handleRefresh(row)">
              刷新
            </el-button>
            <el-button size="small" :loading="isChecking(row.id)" @click="handleCheck(row)">测活</el-button>
            <el-button size="small" type="success" @click="openWatchDialog(row)">收码</el-button>
            <el-dropdown trigger="click">
              <el-button size="small">
                更多
                <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleViewMessages(row)">查看邮件</el-dropdown-item>
                  <el-dropdown-item @click="handleViewSites(row)">注册网站</el-dropdown-item>
                  <el-dropdown-item divided @click="handleDelete(row)">
                    <span style="color:#f56c6c">删除账号</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无邮箱，先导入配置吧" />
    </div>

    <div class="pagination">
      <el-pagination
        :current-page="query.page"
        :page-size="query.size"
        :total="total"
        :page-sizes="[12, 24, 48, 96]"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

    <!-- 导入弹窗 -->
    <el-dialog v-model="importDialogVisible" title="导入账号配置" width="560px">
      <el-tabs v-model="importTab">
        <el-tab-pane label="上传文件" name="file">
          <el-upload drag accept=".txt" :auto-upload="false" :limit="1" :on-change="handleFileChange">
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">将 .txt 文件拖到此处，或<em>点击选择</em></div>
            <template #tip>
              <div class="el-upload__tip">每行：邮箱----密码----ClientID----RefreshToken</div>
            </template>
          </el-upload>
        </el-tab-pane>
        <el-tab-pane label="粘贴文本" name="text">
          <el-input
            v-model="importText"
            type="textarea"
            :rows="10"
            placeholder="每行一个账号，格式：邮箱----密码----ClientID----RefreshToken"
          />
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importLoading" @click="handleImport">开始导入</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resultDialogVisible" title="导入结果" width="560px">
      <template v-if="importResult">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="总计">{{ importResult.total }}</el-descriptions-item>
          <el-descriptions-item label="新建">{{ importResult.created }}</el-descriptions-item>
          <el-descriptions-item label="更新">{{ importResult.updated }}</el-descriptions-item>
          <el-descriptions-item label="跳过">{{ importResult.skipped }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="importResult.errors?.length" class="error-list">
          <el-alert :title="`存在 ${importResult.errors.length} 条错误`" type="error" :closable="false" show-icon />
          <ul>
            <li v-for="(err, idx) in importResult.errors" :key="idx">{{ err }}</li>
          </ul>
        </div>
        <el-alert v-else title="全部处理完成，无错误" type="success" :closable="false" show-icon style="margin-top:12px" />
      </template>
      <template #footer>
        <el-button type="primary" @click="resultDialogVisible = false">知道了</el-button>
      </template>
    </el-dialog>

    <!-- 批量测活进度 -->
    <el-dialog
      v-model="checkJobVisible"
      title="批量测活进行中"
      width="480px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <div v-if="checkJob" class="job-box">
        <div class="job-title">
          {{ checkJob.status === 'running' ? '正在测活，请稍候…' : '处理中…' }}
        </div>
        <el-progress
          :percentage="checkJob.percent || 0"
          :stroke-width="14"
          striped
          striped-flow
        />
        <div class="job-meta">
          <span>进度 {{ checkJob.done || 0 }} / {{ checkJob.total || 0 }}</span>
          <span>存活 {{ checkJob.alive || 0 }} · 失效 {{ checkJob.dead || 0 }}</span>
          <span>已用时 {{ checkJob.elapsed_seconds || 0 }}s</span>
        </div>
        <div class="job-tip">
          大批量账号会在后台持续测活。即使页面等待较久，也请勿重复点击；可随时取消。
        </div>
      </div>
      <template #footer>
        <el-button type="warning" @click="handleCancelCheckJob">取消测活</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="checkResultVisible" title="批量测活结果" width="720px">
      <template v-if="checkResult">
        <el-descriptions :column="3" border style="margin-bottom:12px">
          <el-descriptions-item label="总计">{{ checkResult.total }}</el-descriptions-item>
          <el-descriptions-item label="存活">
            <span style="color:#67c23a;font-weight:700">{{ checkResult.alive }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="失效">
            <span style="color:#f56c6c;font-weight:700">{{ checkResult.dead }}</span>
          </el-descriptions-item>
        </el-descriptions>
        <el-table :data="checkResult.items || []" border stripe max-height="360" size="small">
          <el-table-column prop="email" label="邮箱" min-width="200" show-overflow-tooltip />
          <el-table-column label="结果" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.alive ? 'success' : 'danger'" size="small">
                {{ row.alive ? '存活' : '失效' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="stage" label="阶段" width="90" align="center" />
          <el-table-column prop="error" label="错误信息" min-width="220" show-overflow-tooltip />
        </el-table>
      </template>
      <template #footer>
        <el-button type="primary" @click="checkResultVisible = false">知道了</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="watchDialogVisible" :title="`监听收码 - ${watchEmail}`" width="460px" @close="onWatchClosed">
      <div class="watch-box">
        <div v-if="watchState.code" class="watch-code-area">
          <div class="watch-label">已捕获验证码</div>
          <div class="watch-code">{{ watchState.code }}</div>
          <el-button type="primary" @click="copyCode">复制验证码</el-button>
          <div v-if="watchState.subject" class="watch-sub">邮件主题：{{ watchState.subject }}</div>
          <div v-if="watchState.from" class="watch-sub">发件人：{{ watchState.from }}</div>
        </div>
        <div v-else-if="watchState.active" class="watch-waiting">
          <el-icon class="is-loading watch-spin" :size="30"><Loading /></el-icon>
          <div class="watch-tip">正在监听新邮件，请到对应网站触发发送验证码…</div>
          <div class="watch-meta">剩余 {{ watchState.remaining }} 秒 · 已检查 {{ watchState.pollCount }} 次</div>
          <el-progress
            :percentage="watchState.maxRemaining ? Math.round(watchState.remaining / watchState.maxRemaining * 100) : 0"
            :show-text="false"
            :stroke-width="6"
            style="width:100%;margin-top:12px"
          />
        </div>
        <div v-else class="watch-ended">
          <div v-if="watchState.lastError" class="error-text">监听中账号报错：{{ watchState.lastError }}</div>
          <div v-else class="watch-tip">本次监听结束，未收到新验证码</div>
          <el-button type="success" style="margin-top:12px" @click="restartWatch">重新监听</el-button>
        </div>
      </div>
      <template #footer>
        <el-button v-if="watchState.active" type="warning" @click="handleStopWatch">停止监听</el-button>
        <el-button @click="watchDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="sitesDialogVisible" :title="`注册网站 - ${currentEmail}`" width="680px">
      <el-table v-loading="sitesLoading" :data="sitesData" border stripe empty-text="暂无注册记录">
        <el-table-column prop="site_name" label="站点名" min-width="140" show-overflow-tooltip />
        <el-table-column prop="site_domain" label="域名" min-width="180" show-overflow-tooltip />
        <el-table-column prop="email_count" label="邮件数" width="90" align="center" />
        <el-table-column label="首次出现" width="170" align="center">
          <template #default="{ row }">{{ formatTime(row.first_seen_at) }}</template>
        </el-table-column>
        <el-table-column label="最近出现" width="170" align="center">
          <template #default="{ row }">{{ formatTime(row.last_seen_at) }}</template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="sitesDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.hero-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 14px 16px;
  margin-bottom: 16px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.total-tip {
  color: #98a2b3;
  font-size: 13px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.mail-card {
  background: #fff;
  border-radius: 22px;
  padding: 18px;
  border: 1px solid rgba(232, 237, 245, 0.95);
  box-shadow: var(--mh-shadow);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.mail-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 36px rgba(31, 42, 68, 0.08);
}

.mail-top {
  display: flex;
  align-items: center;
  gap: 12px;
}

.provider {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 800;
  flex-shrink: 0;
}

.mail-meta {
  min-width: 0;
  flex: 1;
}

.mail-email {
  font-size: 14px;
  font-weight: 700;
  color: #1f2a44;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mail-provider {
  margin-top: 2px;
  font-size: 12px;
  color: #98a2b3;
}

.status-pill {
  font-size: 12px;
  font-weight: 700;
  border-radius: 999px;
  padding: 4px 10px;
  flex-shrink: 0;
}

.status-pill.ok { background: #eef2ff; color: #4f6ef7; }
.status-pill.err { background: #fff1f2; color: #e11d48; }
.status-pill.pending { background: #f3f4f6; color: #6b7280; }

.metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 16px 0 12px;
}

.m-label {
  font-size: 12px;
  color: #98a2b3;
  margin-bottom: 6px;
}

.m-value {
  font-size: 28px;
  font-weight: 800;
  color: #1f2a44;
  letter-spacing: -0.03em;
}

.m-value.small {
  font-size: 18px;
  padding-top: 8px;
}

.time-line {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #98a2b3;
  font-size: 12px;
  margin-bottom: 8px;
}

.err-line {
  color: #f56c6c;
  font-size: 12px;
  margin-bottom: 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}

.pagination {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
}

.error-text { color: #f56c6c; }
.error-list { margin-top: 12px; }
.error-list ul {
  max-height: 200px;
  overflow-y: auto;
  padding-left: 20px;
  color: #f56c6c;
  font-size: 13px;
}

.watch-box {
  min-height: 150px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 8px 4px;
}

.watch-code-area,
.watch-waiting,
.watch-ended {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.watch-label { color: #909399; font-size: 13px; }
.watch-code {
  font-size: 40px;
  font-weight: 700;
  letter-spacing: 6px;
  color: #f56c6c;
  font-family: Consolas, Monaco, monospace;
}
.watch-sub { color: #909399; font-size: 12px; max-width: 400px; word-break: break-all; }
.watch-tip { color: #606266; font-size: 14px; }
.watch-meta { color: #909399; font-size: 13px; }
.watch-spin { color: #409eff; }

.job-box {
  padding: 8px 4px 4px;
}

.job-title {
  font-size: 15px;
  font-weight: 700;
  color: #1f2a44;
  margin-bottom: 14px;
}

.job-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 14px;
  color: #667085;
  font-size: 13px;
}

.job-tip {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #eef2ff;
  color: #4f6ef7;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 1200px) {
  .card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .card-grid { grid-template-columns: 1fr; }
  .hero { flex-direction: column; }
}
</style>
