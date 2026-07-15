<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMessages, getMessage, getAccounts } from '../api'

const route = useRoute()
const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const accountOptions = ref([])

const query = reactive({
  account_id: '',
  only_code: false,
  q: '',
  page: 1,
  size: 12
})

async function loadAccountOptions() {
  try {
    const res = await getAccounts({ page: 1, size: 500 })
    accountOptions.value = res.items || []
  } catch (e) {
    // 忽略
  }
}

async function loadMessages() {
  loading.value = true
  try {
    const res = await getMessages({
      account_id: query.account_id || undefined,
      only_code: query.only_code ? true : undefined,
      q: query.q || undefined,
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
  loadMessages()
}

function handlePageChange(page) {
  query.page = page
  loadMessages()
}

function handleSizeChange(size) {
  query.size = size
  query.page = 1
  loadMessages()
}

function formatTime(t) {
  if (!t) return '-'
  const d = new Date(t)
  if (isNaN(d.getTime())) return t
  return d.toLocaleString('zh-CN', { hour12: false })
}

function domainColor(domain = '') {
  const palette = ['#4f6ef7', '#22c55e', '#a855f7', '#f59e0b', '#f43f5e', '#14b8a6', '#0078d4', '#ea4335']
  let h = 0
  for (let i = 0; i < domain.length; i++) h = (h + domain.charCodeAt(i) * (i + 1)) % palette.length
  return palette[h]
}

function initialOf(addr = '') {
  return (addr[0] || 'M').toUpperCase()
}

async function copyCode(code) {
  try {
    await navigator.clipboard.writeText(code)
    ElMessage.success('验证码已复制')
  } catch (e) {
    const input = document.createElement('input')
    input.value = code
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    document.body.removeChild(input)
    ElMessage.success('验证码已复制')
  }
}

const detailDialogVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)

async function handleViewDetail(row) {
  detail.value = null
  detailDialogVisible.value = true
  detailLoading.value = true
  try {
    const res = await getMessage(row.id)
    detail.value = res
    row.is_read = true
  } catch (e) {
    // 错误已提示
  } finally {
    detailLoading.value = false
  }
}

function accountEmail(id) {
  const acc = accountOptions.value.find((a) => a.id === id)
  return acc?.email || `账号 #${id}`
}

onMounted(() => {
  if (route.query.account_id) {
    query.account_id = Number(route.query.account_id)
  }
  loadAccountOptions()
  loadMessages()
})
</script>

<template>
  <div class="page-shell">
    <div class="hero">
      <div>
        <h2 class="page-title" style="font-size:24px">邮件聚合</h2>
        <p class="page-subtitle">跨邮箱浏览邮件，验证码一键复制</p>
      </div>
      <el-button :icon="'Refresh'" @click="loadMessages">刷新</el-button>
    </div>

    <div class="toolbar mh-card">
      <div class="toolbar-left">
        <el-select
          v-model="query.account_id"
          placeholder="按账号筛选"
          clearable
          filterable
          style="width: 260px"
          @change="handleSearch"
        >
          <el-option
            v-for="acc in accountOptions"
            :key="acc.id"
            :label="acc.email"
            :value="acc.id"
          />
        </el-select>
        <el-input
          v-model="query.q"
          placeholder="搜索主题 / 发件人"
          clearable
          style="width: 220px"
          :prefix-icon="'Search'"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-switch v-model="query.only_code" active-text="只看验证码" @change="handleSearch" />
        <el-button type="primary" :icon="'Search'" @click="handleSearch">查询</el-button>
      </div>
      <div class="toolbar-right">
        <span class="total-tip">共 {{ total }} 封</span>
      </div>
    </div>

    <div v-loading="loading">
      <div v-if="tableData.length" class="msg-grid">
        <div
          v-for="row in tableData"
          :key="row.id"
          class="msg-card"
          :class="{ unread: !row.is_read, 'has-code': !!row.verification_code }"
          @click="handleViewDetail(row)"
        >
          <div class="msg-top">
            <div class="avatar" :style="{ background: domainColor(row.from_domain) }">
              {{ initialOf(row.from_addr || row.from_domain) }}
            </div>
            <div class="msg-meta">
              <div class="from" :title="row.from_addr">{{ row.from_addr || '(未知发件人)' }}</div>
              <div class="domain">{{ row.from_domain || '-' }} · {{ accountEmail(row.account_id) }}</div>
            </div>
            <span v-if="!row.is_read" class="unread-dot" />
          </div>

          <div class="subject" :title="row.subject">{{ row.subject || '(无主题)' }}</div>
          <div class="snippet">{{ (row.body_text || '').slice(0, 90) || '暂无正文预览' }}</div>

          <div class="msg-bottom">
            <div v-if="row.verification_code" class="code-box" @click.stop>
              <span class="code-text">{{ row.verification_code }}</span>
              <el-button size="small" circle :icon="'CopyDocument'" @click="copyCode(row.verification_code)" />
            </div>
            <span v-else class="no-code">无验证码</span>
            <span class="time">{{ formatTime(row.received_at) }}</span>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无邮件，可先对邮箱执行刷新或监听" />
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

    <el-dialog v-model="detailDialogVisible" title="邮件详情" width="720px" top="6vh">
      <div v-loading="detailLoading">
        <template v-if="detail">
          <div class="detail-head">
            <div class="detail-from">{{ detail.from_addr }}</div>
            <div class="detail-time">{{ formatTime(detail.received_at) }}</div>
          </div>
          <div class="detail-subject">{{ detail.subject || '(无主题)' }}</div>
          <div v-if="detail.verification_code" class="detail-code">
            <span>验证码</span>
            <strong>{{ detail.verification_code }}</strong>
            <el-button size="small" :icon="'CopyDocument'" @click="copyCode(detail.verification_code)">复制</el-button>
          </div>
          <pre class="body-content">{{ detail.body_text || '(无正文内容)' }}</pre>
        </template>
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
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

.msg-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.msg-card {
  background: #fff;
  border-radius: 20px;
  padding: 16px 16px 14px;
  border: 1px solid rgba(232, 237, 245, 0.95);
  box-shadow: var(--mh-shadow);
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
  min-height: 188px;
  display: flex;
  flex-direction: column;
}

.msg-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 36px rgba(31, 42, 68, 0.08);
}

.msg-card.unread {
  border-color: #dbe4ff;
  background: linear-gradient(180deg, #fbfcff 0%, #fff 60%);
}

.msg-card.has-code {
  border-top: 3px solid #f56c6c;
}

.msg-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 800;
  flex-shrink: 0;
}

.msg-meta {
  min-width: 0;
  flex: 1;
}

.from {
  font-size: 13px;
  font-weight: 700;
  color: #1f2a44;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.domain {
  margin-top: 2px;
  font-size: 12px;
  color: #98a2b3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.unread-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f56c6c;
  flex-shrink: 0;
}

.subject {
  font-size: 15px;
  font-weight: 700;
  color: #1f2a44;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 42px;
}

.snippet {
  margin-top: 8px;
  color: #98a2b3;
  font-size: 12px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}

.msg-bottom {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.code-box {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #fff1f2;
  border-radius: 999px;
  padding: 4px 8px 4px 12px;
}

.code-text {
  color: #e11d48;
  font-weight: 800;
  letter-spacing: 1px;
  font-family: Consolas, Monaco, monospace;
  font-size: 14px;
}

.no-code {
  color: #c0c4cc;
  font-size: 12px;
}

.time {
  color: #98a2b3;
  font-size: 12px;
  white-space: nowrap;
}

.pagination {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.detail-from {
  font-weight: 700;
  color: #1f2a44;
}

.detail-time {
  color: #98a2b3;
  font-size: 13px;
}

.detail-subject {
  font-size: 18px;
  font-weight: 800;
  margin-bottom: 12px;
  color: #1f2a44;
}

.detail-code {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff1f2;
  border-radius: 12px;
  padding: 10px 12px;
  margin-bottom: 12px;
  color: #e11d48;
}

.detail-code strong {
  font-size: 22px;
  letter-spacing: 2px;
  font-family: Consolas, Monaco, monospace;
}

.body-content {
  background: #f8faff;
  border: 1px solid #e8edf5;
  border-radius: 14px;
  padding: 14px;
  max-height: 360px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
}

@media (max-width: 1200px) {
  .msg-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .msg-grid { grid-template-columns: 1fr; }
}
</style>
