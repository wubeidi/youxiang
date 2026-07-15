<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMessages, getMessage, getAccounts } from '../api'

const route = useRoute()

// ========== 列表数据与查询 ==========
const loading = ref(false)
const tableData = ref([])
const total = ref(0)

// 查询条件
const query = reactive({
  account_id: '',
  only_code: false,
  q: '',
  page: 1,
  size: 20
})

// 账号下拉选项（用于按账号筛选）
const accountOptions = ref([])

// 加载账号选项
async function loadAccountOptions() {
  try {
    const res = await getAccounts({ page: 1, size: 500 })
    accountOptions.value = res.items || []
  } catch (e) {
    // 忽略
  }
}

// 加载邮件列表
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

// 格式化时间
function formatTime(t) {
  if (!t) return '-'
  const d = new Date(t)
  if (isNaN(d.getTime())) return t
  return d.toLocaleString('zh-CN', { hour12: false })
}

// ========== 复制验证码 ==========
async function copyCode(code) {
  try {
    await navigator.clipboard.writeText(code)
    ElMessage.success('验证码已复制')
  } catch (e) {
    // 降级方案：使用临时输入框
    const input = document.createElement('input')
    input.value = code
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    document.body.removeChild(input)
    ElMessage.success('验证码已复制')
  }
}

// ========== 邮件详情弹窗 ==========
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
    // 详情接口会自动标记已读，同步更新列表中的该行状态
    row.is_read = true
  } catch (e) {
    // 错误已提示
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  // 如果从账号页跳转过来，带上 account_id 筛选
  if (route.query.account_id) {
    query.account_id = Number(route.query.account_id)
  }
  loadAccountOptions()
  loadMessages()
})
</script>

<template>
  <div>
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select
          v-model="query.account_id"
          placeholder="按账号筛选"
          clearable
          filterable
          style="width: 240px"
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
          placeholder="按主题/发件人搜索"
          clearable
          style="width: 220px"
          :prefix-icon="'Search'"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-switch
          v-model="query.only_code"
          active-text="只看验证码"
          @change="handleSearch"
        />
        <el-button type="primary" :icon="'Search'" @click="handleSearch">查询</el-button>
      </div>
      <div class="toolbar-right">
        <el-button :icon="'Refresh'" @click="loadMessages">刷新</el-button>
      </div>
    </div>

    <!-- 邮件表格 -->
    <el-table
      v-loading="loading"
      :data="tableData"
      border
      stripe
      style="width: 100%"
      @row-click="handleViewDetail"
    >
      <el-table-column label="已读" width="70" align="center">
        <template #default="{ row }">
          <el-badge v-if="!row.is_read" is-dot type="danger">
            <el-icon><Message /></el-icon>
          </el-badge>
          <el-icon v-else color="#c0c4cc"><Message /></el-icon>
        </template>
      </el-table-column>
      <el-table-column prop="from_addr" label="发件人" min-width="200" show-overflow-tooltip />
      <el-table-column prop="from_domain" label="发件域名" width="160" show-overflow-tooltip />
      <el-table-column prop="subject" label="主题" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="{ unread: !row.is_read }">{{ row.subject || '(无主题)' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="验证码" width="160" align="center">
        <template #default="{ row }">
          <div v-if="row.verification_code" class="code-cell" @click.stop>
            <el-tag type="danger" effect="dark" size="large" class="code-tag">
              {{ row.verification_code }}
            </el-tag>
            <el-button
              :icon="'CopyDocument'"
              circle
              size="small"
              @click.stop="copyCode(row.verification_code)"
            />
          </div>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="接收时间" width="180" align="center">
        <template #default="{ row }">{{ formatTime(row.received_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click.stop="handleViewDetail(row)">
            查看
          </el-button>
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

    <!-- 邮件详情弹窗 -->
    <el-dialog v-model="detailDialogVisible" title="邮件详情" width="720px" top="6vh">
      <div v-loading="detailLoading">
        <template v-if="detail">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="发件人">{{ detail.from_addr }}</el-descriptions-item>
            <el-descriptions-item label="主题">{{ detail.subject || '(无主题)' }}</el-descriptions-item>
            <el-descriptions-item label="接收时间">
              {{ formatTime(detail.received_at) }}
            </el-descriptions-item>
            <el-descriptions-item v-if="detail.verification_code" label="验证码">
              <el-tag type="danger" effect="dark" size="large">
                {{ detail.verification_code }}
              </el-tag>
              <el-button
                :icon="'CopyDocument'"
                circle
                size="small"
                style="margin-left: 8px"
                @click="copyCode(detail.verification_code)"
              />
            </el-descriptions-item>
          </el-descriptions>
          <div class="body-text">
            <div class="body-label">正文</div>
            <pre class="body-content">{{ detail.body_text || '(无正文内容)' }}</pre>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
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

.toolbar-left {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.code-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.code-tag {
  font-weight: 600;
  letter-spacing: 1px;
  cursor: default;
}

.unread {
  font-weight: 600;
  color: #303133;
}

.text-muted {
  color: #c0c4cc;
}

/* 表格行可点击 */
:deep(.el-table__row) {
  cursor: pointer;
}

.body-text {
  margin-top: 16px;
}

.body-label {
  font-weight: 600;
  margin-bottom: 8px;
  color: #303133;
}

.body-content {
  background-color: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
  max-height: 360px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
}
</style>
