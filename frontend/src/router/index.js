import { createRouter, createWebHistory } from 'vue-router'

// 路由配置
// 采用懒加载方式引入视图组件，优化首屏加载
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('../views/Dashboard.vue'),
    meta: { requiresAuth: true },
    // 主面板下的子路由
    children: [
      {
        path: '',
        name: 'Overview',
        component: () => import('../views/Overview.vue')
      },
      {
        path: 'accounts',
        name: 'Accounts',
        component: () => import('../views/Accounts.vue')
      },
      {
        path: 'watch-board',
        name: 'WatchBoard',
        component: () => import('../views/WatchBoard.vue')
      },
      {
        path: 'messages',
        name: 'Messages',
        component: () => import('../views/Messages.vue')
      }
    ]
  },
  // 兜底：未匹配的路由跳转到首页
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 全局前置守卫：需要登录的页面在无 token 时跳转到登录页
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next({ path: '/login', query: { redirect: to.fullPath } })
  } else if (to.path === '/login' && token) {
    // 已登录访问登录页，直接进入主面板
    next({ path: '/' })
  } else {
    next()
  }
})

export default router
