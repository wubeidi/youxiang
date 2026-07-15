# 邮箱管理服务（Outlook 批量邮箱收信面板）

自托管的多邮箱管理服务：批量导入 Outlook 邮箱配置，按需收信，可视化查看邮件、验证码，以及每个邮箱注册过哪些网站。针对「低频账号」优化——默认不做后台轮询，改用按需刷新 + 临时监听，省资源、更保号。

> ⚠️ 仅用于管理你**本人合法拥有**的邮箱账号。

---

## 功能

- **批量导入**：支持上传配置文件或粘贴文本，格式 `邮箱----密码----ClientID----RefreshToken`
- **三种收信模式**：
  - **按需刷新**：随手拉取单个邮箱最新邮件（默认，最省资源）
  - **临时监听**：等验证码时对单个账号短时快拉，拿到即停、超时自停
  - **监听看板**：同时监听多个账号，各自卡片实时显示验证码（并发有上限）
  - 后台全量轮询：保留但**默认关闭**（`POLL_ENABLED`），仅在需要所有账号准实时时开启
- **邮箱测活**：单账号 / 当前页 / 全部启用账号一键探测；先 OAuth 换票，再 IMAP 轻量登录，不拉邮件正文，结果回写「正常/错误」状态
- **验证码识别**：自动从邮件中提取验证码并高亮展示，一键复制
- **注册网站分析**：从收件箱反推每个邮箱在哪些网站注册过（按发件域名聚合）
- **可视化面板**：账号状态总览、邮件列表、搜索筛选
- **凭证加密**：refresh token 用 AES-256-GCM 加密存储，主密钥仅存于环境变量

---

## 技术架构

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Vue3 前端   │────▶│  FastAPI 后端     │────▶│ PostgreSQL   │
│ Element Plus │ /api│  + APScheduler   │     │              │
└─────────────┘     │  轮询引擎         │     └──────────────┘
     nginx          └────────┬─────────┘
                             │ OAuth2 刷新 + IMAP(XOAUTH2)
                             ▼
                    ┌──────────────────┐
                    │ Microsoft / IMAP  │
                    │ outlook.office365 │
                    └──────────────────┘
```

- **后端**：Python 3.12 + FastAPI + 异步 SQLAlchemy + asyncpg
- **收信**：refresh token → access token（缓存）→ IMAP XOAUTH2 增量拉取（UID 游标）
- **并发**：asyncio 信号量限制同时在线 IMAP 连接数，IMAP 同步调用走线程池
- **前端**：Vue 3 + Vite + Element Plus
- **部署**：Docker Compose 一键起（db + backend + frontend/nginx）

---

## 快速部署（Docker，推荐）

### 1. 准备环境变量

```bash
cp .env.example .env
```

编辑 `.env`，**必须**填写：

```bash
# 生成加密主密钥
python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
```

把输出填到 `MASTER_KEY=`，并改掉 `POSTGRES_PASSWORD`、`ADMIN_PASSWORD`、`JWT_SECRET`。

### 2. 启动

```bash
docker compose up -d --build
```

### 3. 访问

浏览器打开 `http://服务器IP:8080`（端口由 `.env` 的 `WEB_PORT` 决定），用 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 登录。

### 4. 导入邮箱

登录后进入「账号管理」→「导入配置」，上传你的 `.txt` 配置文件或粘贴文本。导入后系统会自动开始轮询收信。

---

## 本地开发

### 后端

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # 填 MASTER_KEY，DATABASE_URL 指向本地 postgres
uvicorn app.main:app --reload --port 8000
```

需要一个本地 PostgreSQL；或临时用 docker 起一个：

```bash
docker run -d --name pg -e POSTGRES_USER=mailadmin -e POSTGRES_PASSWORD=mailadmin -e POSTGRES_DB=maildb -p 5432:5432 postgres:16-alpine
```

### 前端

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173，已代理 /api 到 8000
```

---

## 配置项说明（backend/.env）

| 变量 | 说明 | 默认 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL 异步连接串 | — |
| `MASTER_KEY` | 凭证加密主密钥（32 字节 base64，必填） | — |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 面板登录账号 | admin / changeme |
| `JWT_SECRET` | 登录令牌签名密钥 | — |
| `OAUTH_TOKEN_URL` | 微软 token 端点（消费号用 /consumers） | login.microsoftonline.com/consumers |
| `OAUTH_SCOPE` | OAuth 授权范围 | IMAP.AccessAsUser.All offline_access |
| `IMAP_HOST` / `IMAP_PORT` | IMAP 服务器 | outlook.office365.com / 993 |
| `POLL_INTERVAL_SECONDS` | 轮询间隔 | 300 |
| `POLL_CONCURRENCY` | 并发 IMAP 连接数上限 | 30 |
| `FETCH_MAX_PER_ACCOUNT` | 单账号每轮最多拉取新邮件数 | 30 |

---

## 关键实现说明与注意事项

### OAuth / IMAP
- 配置里的 token（`M.C554...`）是**消费级 outlook.com** 账号的 refresh token，走 `/consumers` 端点。
- 若你的账号是企业版（Microsoft 365），需把 `OAUTH_TOKEN_URL` 改为对应租户端点、scope 相应调整。
- access token 有效期约 1 小时，服务内存缓存复用，减少 token 端点请求。
- 如果某账号一直 `error` 且提示刷新失败，通常是 refresh token 失效（被改密码/长期未用/被风控），需要重新获取。

### 规模与限流
- 几千账号：`POLL_CONCURRENCY` 别设太高（默认 30），微软对高频 IMAP 连接会限流甚至临时封禁。
- 若账号量继续增长（万级），建议把轮询从 APScheduler 单进程改造为 **Celery/RQ + Redis** 多 worker 分片调度。
- 后端容器**必须单进程运行**（当前 Dockerfile 已是单 worker）——多 worker 会导致轮询任务重复执行。

### 安全
- **务必**改掉默认 `ADMIN_PASSWORD` 和 `JWT_SECRET`。
- `MASTER_KEY` 一旦丢失，已加密的 token 无法解密；请妥善备份。
- 生产环境建议在 nginx 前再加一层 HTTPS（Caddy/Let's Encrypt）或只在内网/VPN 内访问。
- 数据库端口默认不对外暴露。

### 「注册网站」的准确性
- 该功能是**启发式推断**：基于发件域名聚合，不是精确的注册记录。
- 通过邮件服务商（如 SendGrid、Mailgun）群发的邮件，域名会被剥离常见发信子域前缀以还原真实站点，但仍可能有偏差。
