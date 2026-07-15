<script setup>
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '../api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loginForm = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const formRef = ref(null)
const loading = ref(false)

async function handleLogin() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const res = await login({
        username: loginForm.username,
        password: loginForm.password
      })
      authStore.setToken(res.access_token)
      ElMessage.success('登录成功')
      const redirect = route.query.redirect || '/'
      router.push(redirect)
    } catch (e) {
      // 拦截器已提示
    } finally {
      loading.value = false
    }
  })
}
</script>

<template>
  <div class="login-page">
    <div class="login-left">
      <div class="brand">
        <div class="brand-mark"><el-icon :size="20"><Message /></el-icon></div>
        <span>MailHub</span>
      </div>
      <h1>统一管理多个邮箱<br />高效处理验证码与邮件</h1>
      <p>按需刷新 · 临时监听 · 测活 · 注册网站分析</p>
      <div class="preview-cards">
        <div class="mini-card">
          <div class="mini-label">邮箱总数</div>
          <div class="mini-value">N+</div>
        </div>
        <div class="mini-card">
          <div class="mini-label">监听收码</div>
          <div class="mini-value">实时</div>
        </div>
        <div class="mini-card">
          <div class="mini-label">自托管</div>
          <div class="mini-value">安全</div>
        </div>
      </div>
    </div>

    <div class="login-right">
      <div class="login-card">
        <h2>欢迎回来</h2>
        <p class="sub">登录以继续使用 MailHub</p>
        <el-form
          ref="formRef"
          :model="loginForm"
          :rules="rules"
          label-position="top"
          size="large"
          @keyup.enter="handleLogin"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              :prefix-icon="'User'"
              clearable
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="'Lock'"
              show-password
            />
          </el-form-item>
          <el-button type="primary" class="login-btn" :loading="loading" @click="handleLogin">
            登 录
          </el-button>
        </el-form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  background:
    radial-gradient(circle at 20% 20%, rgba(79, 110, 247, 0.18), transparent 28%),
    linear-gradient(135deg, #0b1220 0%, #172033 45%, #eef3fb 45%, #f7f9fc 100%);
}

.login-left {
  color: #fff;
  padding: 56px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 22px;
  font-weight: 800;
  margin-bottom: 36px;
}

.brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #5b7cfa, #7a5af8);
}

.login-left h1 {
  margin: 0;
  font-size: 40px;
  line-height: 1.25;
  letter-spacing: -0.03em;
}

.login-left p {
  margin: 16px 0 28px;
  color: #b7c0d1;
  font-size: 15px;
}

.preview-cards {
  display: flex;
  gap: 12px;
}

.mini-card {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 14px 16px;
  min-width: 100px;
}

.mini-label {
  color: #9aa6bc;
  font-size: 12px;
}

.mini-value {
  margin-top: 8px;
  font-size: 22px;
  font-weight: 800;
}

.login-right {
  display: grid;
  place-items: center;
  padding: 32px;
}

.login-card {
  width: min(420px, 100%);
  background: #fff;
  border-radius: 24px;
  padding: 32px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.12);
}

.login-card h2 {
  margin: 0;
  font-size: 28px;
  letter-spacing: -0.03em;
}

.sub {
  margin: 8px 0 24px;
  color: #8b95a7;
}

.login-btn {
  width: 100%;
  height: 44px;
  margin-top: 8px;
}

@media (max-width: 900px) {
  .login-page {
    grid-template-columns: 1fr;
    background: linear-gradient(180deg, #0b1220 0%, #172033 36%, #eef3fb 36%, #f7f9fc 100%);
  }
  .login-left {
    padding: 32px 24px 8px;
  }
  .login-left h1 {
    font-size: 28px;
  }
  .preview-cards {
    display: none;
  }
}
</style>
