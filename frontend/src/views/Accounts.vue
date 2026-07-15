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
  checkAccountsBatch
} from '../api'

const router = useRouter()

// ========== 列表数据与查询 ==========
const loading = ref(false)
const tableData = ref([])
const total = ref(0)

// 查询条件
const query = reactive({
  q: '',
  status: '',
  page: 1,
  size: 20
})

// 状态选项
const statusOptions = [
  { label: '全部', value: '' },
  { label: '正常', value: 'ok' },
  { label: '错误', value: 'error' },
  { label: '待处理', value: 'pending' }
]

// 状态对应的标签类型与文案
const statusMeta = {
  ok: { type: 'success', text: '正常' },
  error: { type: 'danger', text: '错误' },
  pending: { type: 'info', text: '待处理' }
}

// 加载账号列表
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

// 搜索（回到第一页）
function handleSearch() {
  query.page = 1
  loadAccounts()
}

// 分页变化
function handlePageChange(page) {
  query.page = page
  loadAccounts()
}

function handleSizeChange(size) {
  query.size = size
  query.page = 1
  loadAccounts()
}

// 格式化时间显示
function formatTime(t) {
  if (!t) return '-'
  const d = new Date(t)
  if (isNaN(d.getTime())) return t
  return d.toLocaleString('zh-CN', { hour12: false })
}

// ========== 导入功能 ==========
const importDialogVisible = ref(false)
const importTab = ref('file') // file 或 text
const importText = ref('')
const importLoading = ref(false)
const uploadRef = ref(null)
const selectedFile = ref(null)

// 导入结果
const importResult = ref(null)
const resultDialogVisible = ref(false)

// 打开导入弹窗
function openImportDialog() {
  importTab.value = 'file'
  importText.value = ''
  selectedFile.value = null
  importDialogVisible.value = true
}

// el-upload 选择文件后（手动上传模式）
function handleFileChange(file) {
  selectedFile.value = file.raw
}

// 执行导入
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
    // 重新加载列表
    loadAccounts()
  } catch (e) {
    // 错误已提示
  } finally {
    importLoading.value = false
  }
}

// ========== 行操作 ==========
// 单行刷新的 loading 状态记录（按 id）
const refreshingIds = ref(new Set())

function isRefreshing(id) {
  return refreshingIds.value.has(id)
}

// 立即刷新某账号
async function handleRefresh(row) {
  refreshingIds.value.add(row.id)
  // 触发响应式更新
  refreshingIds.value = new Set(refreshingIds.value)
  try {
    const res = await refreshAccount(row.id)
    // 局部更新该行数据
    row.status = res.status
    row.last_error = res.last_error
    row.message_count = res.message_count
    ElMessage.success('刷新完成')
  } catch (e) {
    // 错误已提示
  } finally {
    refreshingIds.value.delete(row.id)
    refreshingIds.value = new Set(refreshingIds.value)
  }
}

// 单行测活
const checkingIds = ref(new Set())
const batchChecking = ref(false)
const checkResultVisible = ref(false)
const checkResult = ref(null)

function isChecking(id) {
  return checkingIds.value.has(id)
}

async function handleCheck(row) {
  checkingIds.value.add(row.id)
  checkingIds.value = new Set(checkingIds.value)
  try {
    const res = await checkAccount(row.id)
    row.status = res.status
    row.last_error = res.error
    if (res.alive) {
      ElMessage.success(`${row.email} 存活`)
    } else {
      ElMessage.error(`${row.email} 失效：${res.error || '未知错误'}`)
    }
  } catch (e) {
    // 错误已提示
  } finally {
    checkingIds.value.delete(row.id)
    checkingIds.value = new Set(checkingIds.value)
  }
}

// 批量测活：当前页 / 全部启用
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
  try {
    const res = await checkAccountsBatch(ids)
    checkResult.value = res
    checkResultVisible.value = true
    // 刷新列表状态
    await loadAccounts()
  } catch (e) {
    // 错误已提示
  } finally {
    batchChecking.value = false
  }
}

// 查看邮件：跳转到邮件列表并携带 account_id
function handleViewMessages(row) {
  router.push({ path: '/messages', query: { account_id: row.id } })
}

// 删除账号
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

// ========== 注册网站弹窗 ==========
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
    const res = await getAccountSites(row.id)
    sitesData.value = res || []
  } catch (e) {
    // 错误已提示
  } finally {
    sitesLoading.value = false
  }
}

// ========== 临时监听收码 ==========
// 只对单个账号短时快拉：点开即开始监听，拿到验证码或超时自动停止。
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

// 把后端返回的监听状态同步到本地
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

// 打开弹窗并开始监听
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
    // 错误已提示（如并发上限 429）
  }
}

// 前端每 2 秒轮询一次监听状态，更新倒计时并捕获验证码
function startWatchPolling() {
  stopWatchPolling()
  watchTimer = setInterval(async () => {
    if (!watchAccountId.value) return
    try {
      const s = await getWatchStatus(watchAccountId.value)
      applyWatchStatus(s)
      // 拿到码或监听已结束 → 停止前端轮询
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

// 手动停止监听（保留弹窗展示结果）
async function handleStopWatch() {
  stopWatchPolling()
  try {
    const s = await stopWatch(watchAccountId.value)
    applyWatchStatus(s)
  } catch (e) {
    // 忽略
  }
}

// 重新监听（结束后再等一次）
async function restartWatch() {
  resetWatchState()
  await beginWatch()
}

// 弹窗关闭：停止前端轮询 + 通知后端停止监听 + 刷新列表
async function onWatchClosed() {
  stopWatchPolling()
  const id = watchAccountId.value
  if (id && watchState.active) {
    try { await stopWatch(id) } catch (e) { /* 忽略 */ }
  }
  watchState.active = false
  loadAccounts()
}

// 复制验证码（带降级方案）
function copyCode() {
  const code = watchState.code
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

onMounted(loadAccounts)
onUnmounted(stopWatchPolling)
</script>

<template>
  <div>
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="query.q"
          placeholder="按邮箱搜索"
          clearable
          style="width: 220px"
          :prefix-icon="'Search'"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-select
          v-model="query.status"
          placeholder="状态筛选"
          style="width: 130px"
          @change="handleSearch"
        >
          <el-option
            v-for="opt in statusOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-button type="primary" :icon="'Search'" @click="handleSearch">查询</el-button>
      </div>
      <div class="toolbar-right">
        <el-button type="success" :icon="'Upload'" @click="openImportDialog">导入配置</el-button>
        <el-dropdown split-button type="warning" :loading="batchChecking" @click="handleBatchCheck('page')">
          测活当前页
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="handleBatchCheck('page')">测活当前页</el-dropdown-item>
              <el-dropdown-item @click="handleBatchCheck('all')">测活全部启用账号</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button :icon="'Refresh'" @click="loadAccounts">刷新列表</el-button>
      </div>
    </div>

    <!-- 账号表格 -->
    <el-table v-loading="loading" :data="tableData" border stripe style="width: 100%">
      <el-table-column type="index" label="#" width="55" align="center" />
      <el-table-column prop="email" label="邮箱" min-width="220" show-overflow-tooltip />
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <!-- error 状态悬停显示 last_error -->
          <el-tooltip
            v-if="row.status === 'error' && row.last_error"
            :content="row.last_error"
            placement="top"
          >
            <el-tag :type="statusMeta[row.status]?.type || 'info'">
              {{ statusMeta[row.status]?.text || row.status }}
            </el-tag>
          </el-tooltip>
          <el-tag v-else :type="statusMeta[row.status]?.type || 'info'">
            {{ statusMeta[row.status]?.text || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="message_count" label="邮件数" width="90" align="center" />
      <el-table-column label="启用" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
            {{ row.enabled ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最后轮询时间" width="180" align="center">
        <template #default="{ row }">{{ formatTime(row.last_polled_at) }}</template>
      </el-table-column>
      <el-table-column label="错误信息" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.status === 'error'" class="error-text">{{ row.last_error || '-' }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="500" fixed="right" align="center">
        <template #default="{ row }">
          <el-button
            size="small"
            type="primary"
            :loading="isRefreshing(row.id)"
            @click="handleRefresh(row)"
          >
            立即刷新
          </el-button>
          <el-button
            size="small"
            type="info"
            :loading="isChecking(row.id)"
            @click="handleCheck(row)"
          >
            测活
          </el-button>
          <el-button size="small" type="success" @click="openWatchDialog(row)">监听收码</el-button>
          <el-button size="small" @click="handleViewMessages(row)">查看邮件</el-button>
          <el-button size="small" type="warning" @click="handleViewSites(row)">注册网站</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        :current-page="query.page"
        :page-size="query.size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

    <!-- 导入弹窗 -->
    <el-dialog v-model="importDialogVisible" title="导入账号配置" width="560px">
      <el-tabs v-model="importTab">
        <el-tab-pane label="上传文件" name="file">
          <el-upload
            ref="uploadRef"
            drag
            accept=".txt"
            :auto-upload="false"
            :limit="1"
            :on-change="handleFileChange"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">将 .txt 文件拖到此处，或<em>点击选择</em></div>
            <template #tip>
              <div class="el-upload__tip">
                仅支持 .txt 文件，每行格式：邮箱----密码----ClientID----RefreshToken
              </div>
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

    <!-- 导入结果弹窗 -->
    <el-dialog v-model="resultDialogVisible" title="导入结果" width="560px">
      <template v-if="importResult">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="总计">{{ importResult.total }}</el-descriptions-item>
          <el-descriptions-item label="新建">{{ importResult.created }}</el-descriptions-item>
          <el-descriptions-item label="更新">{{ importResult.updated }}</el-descriptions-item>
          <el-descriptions-item label="跳过">{{ importResult.skipped }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="importResult.errors && importResult.errors.length" class="error-list">
          <el-alert
            :title="`存在 ${importResult.errors.length} 条错误`"
            type="error"
            :closable="false"
            show-icon
          />
          <ul>
            <li v-for="(err, idx) in importResult.errors" :key="idx">{{ err }}</li>
          </ul>
        </div>
        <el-alert
          v-else
          title="全部处理完成，无错误"
          type="success"
          :closable="false"
          show-icon
          style="margin-top: 12px"
        />
      </template>
      <template #footer>
        <el-button type="primary" @click="resultDialogVisible = false">知道了</el-button>
      </template>
    </el-dialog>

    <!-- 批量测活结果弹窗 -->
    <el-dialog v-model="checkResultVisible" title="批量测活结果" width="720px">
      <template v-if="checkResult">
        <el-descriptions :column="3" border style="margin-bottom: 12px">
          <el-descriptions-item label="总计">{{ checkResult.total }}</el-descriptions-item>
          <el-descriptions-item label="存活">
            <span style="color: #67c23a; font-weight: 600">{{ checkResult.alive }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="失效">
            <span style="color: #f56c6c; font-weight: 600">{{ checkResult.dead }}</span>
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
          <el-table-column label="阶段" width="90" align="center">
            <template #default="{ row }">{{ row.stage || '-' }}</template>
          </el-table-column>
          <el-table-column prop="error" label="错误信息" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.error" class="error-text">{{ row.error }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <template #footer>
        <el-button type="primary" @click="checkResultVisible = false">知道了</el-button>
      </template>
    </el-dialog>

    <!-- 临时监听收码弹窗 -->
    <el-dialog
      v-model="watchDialogVisible"
      :title="`监听收码 - ${watchEmail}`"
      width="460px"
      @close="onWatchClosed"
    >
      <div class="watch-box">
        <!-- 已捕获验证码 -->
        <div v-if="watchState.code" class="watch-code-area">
          <div class="watch-label">已捕获验证码</div>
          <div class="watch-code">{{ watchState.code }}</div>
          <el-button type="primary" @click="copyCode">复制验证码</el-button>
          <div v-if="watchState.subject" class="watch-sub">邮件主题：{{ watchState.subject }}</div>
          <div v-if="watchState.from" class="watch-sub">发件人：{{ watchState.from }}</div>
        </div>

        <!-- 监听中 -->
        <div v-else-if="watchState.active" class="watch-waiting">
          <el-icon class="is-loading watch-spin" :size="30"><Loading /></el-icon>
          <div class="watch-tip">正在监听新邮件，请到对应网站触发发送验证码…</div>
          <div class="watch-meta">剩余 {{ watchState.remaining }} 秒 · 已检查 {{ watchState.pollCount }} 次</div>
          <el-progress
            :percentage="watchState.maxRemaining ? Math.round(watchState.remaining / watchState.maxRemaining * 100) : 0"
            :show-text="false"
            :stroke-width="6"
            style="width: 100%; margin-top: 12px"
          />
        </div>

        <!-- 结束且无码 -->
        <div v-else class="watch-ended">
          <div v-if="watchState.lastError" class="error-text">监听中账号报错：{{ watchState.lastError }}</div>
          <div v-else class="watch-tip">本次监听结束，未收到新验证码</div>
          <el-button type="success" style="margin-top: 12px" @click="restartWatch">重新监听</el-button>
        </div>
      </div>
      <template #footer>
        <el-button v-if="watchState.active" type="warning" @click="handleStopWatch">停止监听</el-button>
        <el-button @click="watchDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 注册网站弹窗 -->
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

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.error-text {
  color: #f56c6c;
}

.error-list {
  margin-top: 12px;
}

.error-list ul {
  max-height: 200px;
  overflow-y: auto;
  padding-left: 20px;
  color: #f56c6c;
  font-size: 13px;
}

/* 临时监听弹窗 */
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

.watch-label {
  color: #909399;
  font-size: 13px;
}

.watch-code {
  font-size: 40px;
  font-weight: 700;
  letter-spacing: 6px;
  color: #f56c6c;
  font-family: 'Consolas', 'Monaco', monospace;
  margin-bottom: 4px;
}

.watch-sub {
  color: #909399;
  font-size: 12px;
  max-width: 400px;
  word-break: break-all;
}

.watch-tip {
  color: #606266;
  font-size: 14px;
}

.watch-meta {
  color: #909399;
  font-size: 13px;
}

.watch-spin {
  color: #409eff;
}
</style>
