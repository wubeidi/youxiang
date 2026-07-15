# ---- 构建阶段 ----
FROM node:20-alpine AS build
WORKDIR /app

# 先拷依赖清单，利用 Docker 层缓存
COPY package.json package-lock.json* ./

# 只用容器内安装依赖，禁止使用宿主机上传的 node_modules
# npm ci 在有 lock 时更稳；没有 lock 时回退 npm install
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# 只拷源码（.dockerignore 会排除 node_modules / dist）
COPY . .

# 用 node 直接跑本地 vite，避免 PATH/权限问题
RUN node node_modules/vite/bin/vite.js build

# ---- 运行阶段：nginx 托管静态资源 + 反代后端 ----
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
