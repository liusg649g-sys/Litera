import { createRouter, createWebHistory } from 'vue-router'
import { auth, restoreSession } from './auth'
import AuthPage from './views/AuthPage.vue'
import LibraryPage from './views/LibraryPage.vue'
import ProfilePage from './views/ProfilePage.vue'
export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/library' },
    { path: '/login', component: AuthPage, meta: { title: '登录' } },
    { path: '/register', component: AuthPage, meta: { title: '注册' } },
    { path: '/library', component: LibraryPage, meta: { protected: true, title: '文献库' } },
    { path: '/profile', component: ProfilePage, meta: { protected: true, title: '个人资料' } },
    { path: '/:pathMatch(.*)*', redirect: '/library' },
  ],
})
router.beforeEach(async (to) => {
  await restoreSession()
  if (auth.restoreError) return true
  if (to.meta.protected && !auth.user) return '/login'
  if ((to.path === '/login' || to.path === '/register') && auth.user) return '/library'
})
router.afterEach((to) => { document.title = 'Litera · ' + String(to.meta.title || '科研文献智能管理与协作平台') })
