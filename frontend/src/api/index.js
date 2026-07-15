import request from './request'

// ========== 认证相关 ==========

// 登录：返回 { access_token, token_type }
export function login(data) {
  return request.post('/auth/login', data)
}

// ========== 账号相关 ==========

// 上传 .txt 配置文件导入账号（multipart，字段名 file）
export function importAccountsFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/accounts/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 粘贴文本导入账号
export function importAccountsText(content) {
  return request.post('/accounts/import-text', { content })
}

// 账号列表：支持搜索、状态筛选、分页
export function getAccounts(params) {
  return request.get('/accounts', { params })
}

// 账号统计概览
export function getAccountStats() {
  return request.get('/accounts/stats')
}

// 某账号注册过的网站列表
export function getAccountSites(id) {
  return request.get(`/accounts/${id}/sites`)
}

// 立即刷新（拉取最新邮件）
export function refreshAccount(id) {
  return request.post(`/accounts/${id}/refresh`)
}

// 单账号测活：OAuth + IMAP 轻量探测，不拉邮件
export function checkAccount(id) {
  return request.post(`/accounts/${id}/check`)
}

// 批量测活（异步任务）：立即返回 job_id，需轮询 getCheckJob
// 传 ids 测指定账号；不传 / 传空数组则测全部启用账号
export function checkAccountsBatch(accountIds) {
  return request.post('/accounts/check-batch', {
    account_ids: accountIds && accountIds.length ? accountIds : null
  }, {
    // 启动任务本身很快；真正测活在后台跑
    timeout: 60000
  })
}

// 查询批量测活任务进度
export function getCheckJob(jobId) {
  return request.get(`/accounts/check-jobs/${jobId}`, {
    // 轮询接口应快速返回
    timeout: 15000
  })
}

// 取消批量测活任务
export function cancelCheckJob(jobId) {
  return request.post(`/accounts/check-jobs/${jobId}/cancel`, null, {
    timeout: 15000
  })
}

// 开始临时监听：只对该账号短时快拉，拿到验证码或超时自动停止
export function startWatch(id) {
  return request.post(`/accounts/${id}/watch/start`)
}

// 停止监听
export function stopWatch(id) {
  return request.post(`/accounts/${id}/watch/stop`)
}

// 查询监听状态（前端轮询此接口更新倒计时/展示已捕获的验证码）
export function getWatchStatus(id) {
  return request.get(`/accounts/${id}/watch/status`)
}

// 批量开始监听（看板）：body { account_ids: [...] }
export function startWatchBatch(accountIds) {
  return request.post('/accounts/watch/start-batch', { account_ids: accountIds })
}

// 所有监听中/被跟踪的账号状态（看板每隔几秒轮询）
export function getActiveWatches() {
  return request.get('/accounts/watch/active')
}

// 停止全部监听
export function stopAllWatches() {
  return request.post('/accounts/watch/stop-all')
}

// 清除已结束的监听记录（从看板移除）
export function clearFinishedWatches() {
  return request.post('/accounts/watch/clear-finished')
}

// 删除账号
export function deleteAccount(id) {
  return request.delete(`/accounts/${id}`)
}

// ========== 邮件相关 ==========

// 邮件列表：支持按账号筛选、只看验证码、搜索、分页
export function getMessages(params) {
  return request.get('/messages', { params })
}

// 邮件详情（后端会自动标记已读）
export function getMessage(id) {
  return request.get(`/messages/${id}`)
}
