#!/usr/bin/env bash
# Ubuntu 一键部署助手（无域名，IP 访问）
# 用法：
#   chmod +x deploy.sh
#   ./deploy.sh          # 初始化 .env（若不存在）并构建启动
#   ./deploy.sh up       # 同上
#   ./deploy.sh down     # 停止
#   ./deploy.sh logs     # 看后端日志
#   ./deploy.sh status   # 查看容器状态
#   ./deploy.sh gen-env  # 仅生成/刷新 .env 密钥（不覆盖已有非空 MASTER_KEY）

set -euo pipefail
cd "$(dirname "$0")"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "缺少命令: $1"
    exit 1
  }
}

gen_master_key() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
  else
    # 无 python 时用 openssl 生成 32 字节再 base64
    openssl rand -base64 32 | tr -d '\n'
    echo
  fi
}

gen_jwt() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import secrets;print(secrets.token_urlsafe(48))"
  else
    openssl rand -base64 48 | tr -d '\n'
    echo
  fi
}

gen_password() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import secrets;print(secrets.token_urlsafe(16))"
  else
    openssl rand -base64 18 | tr -d '\n=/+' | head -c 20
    echo
  fi
}

ensure_env() {
  if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "已创建 .env"
  fi

  # 若 MASTER_KEY 为空则写入
  if ! grep -qE '^MASTER_KEY=.+' .env; then
    MK=$(gen_master_key)
    if grep -qE '^MASTER_KEY=' .env; then
      sed -i "s|^MASTER_KEY=.*|MASTER_KEY=${MK}|" .env
    else
      echo "MASTER_KEY=${MK}" >> .env
    fi
    echo "已生成 MASTER_KEY（请妥善备份 .env）"
  fi

  if ! grep -qE '^JWT_SECRET=.+' .env || grep -qE '^JWT_SECRET=change-this-to-a-long-random-string' .env || grep -qE '^JWT_SECRET=please-change' .env; then
    JS=$(gen_jwt)
    if grep -qE '^JWT_SECRET=' .env; then
      sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${JS}|" .env
    else
      echo "JWT_SECRET=${JS}" >> .env
    fi
    echo "已生成 JWT_SECRET"
  fi

  if grep -qE '^POSTGRES_PASSWORD=change-this-db-password' .env || grep -qE '^POSTGRES_PASSWORD=$' .env; then
    PW=$(gen_password)
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PW}|" .env
    echo "已生成 POSTGRES_PASSWORD"
  fi

  if grep -qE '^ADMIN_PASSWORD=change-this-admin-password' .env || grep -qE '^ADMIN_PASSWORD=changeme' .env; then
    AP=$(gen_password)
    sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${AP}|" .env
    echo "已生成 ADMIN_PASSWORD: ${AP}"
    echo "  ↑ 请记下此面板密码，登录后可再改"
  fi
}

show_access() {
  PORT=$(grep -E '^WEB_PORT=' .env 2>/dev/null | cut -d= -f2 || true)
  PORT=${PORT:-8080}
  IP=$(hostname -I 2>/dev/null | awk '{print $1}')
  IP=${IP:-你的服务器IP}
  echo ""
  echo "=========================================="
  echo "  部署完成"
  echo "  访问地址: http://${IP}:${PORT}"
  echo "  登录账号见 .env 中 ADMIN_USERNAME / ADMIN_PASSWORD"
  echo "  查看密码: grep ADMIN_ .env"
  echo "=========================================="
}

# 清理宿主机上传的依赖目录，避免 Windows node_modules 污染 Docker 构建
# （典型报错: sh: vite: Permission denied / exit 126）
clean_host_artifacts() {
  echo "清理宿主机依赖目录（防止污染 Docker 构建）..."
  rm -rf frontend/node_modules frontend/dist 2>/dev/null || true
  rm -rf backend/.venv backend/venv backend/__pycache__ 2>/dev/null || true
  find backend -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
  # 确保 dockerignore 存在（旧包可能没同步到）
  if [[ ! -f frontend/.dockerignore ]]; then
    cat > frontend/.dockerignore <<'EOF'
node_modules
dist
.DS_Store
*.log
.git
.gitignore
.env
.env.*
EOF
    echo "已补写 frontend/.dockerignore"
  fi
  if [[ ! -f backend/.dockerignore ]]; then
    cat > backend/.dockerignore <<'EOF'
__pycache__
*.pyc
*.pyo
.venv
venv
.env
.env.*
*.log
.git
.gitignore
EOF
    echo "已补写 backend/.dockerignore"
  fi
}

cmd=${1:-up}

case "$cmd" in
  gen-env)
    ensure_env
    echo ".env 已就绪"
    ;;
  clean)
    clean_host_artifacts
    echo "清理完成"
    ;;
  up|start|"")
    need_cmd docker
    if ! docker compose version >/dev/null 2>&1; then
      echo "需要 Docker Compose 插件: docker compose"
      exit 1
    fi
    ensure_env
    clean_host_artifacts
    # 前端曾失败时强制无缓存重建，避免沿用坏层
    docker compose build --no-cache frontend
    docker compose up -d --build
    docker compose ps
    show_access
    ;;
  down|stop)
    docker compose down
    ;;
  logs)
    docker compose logs -f backend
    ;;
  status)
    docker compose ps
    ;;
  restart)
    docker compose restart
    ;;
  *)
    echo "用法: $0 {up|down|logs|status|restart|gen-env|clean}"
    exit 1
    ;;
esac
