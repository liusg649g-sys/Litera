import { createApp } from 'vue'
import { ElAlert, ElButton, ElForm, ElFormItem, ElInput } from 'element-plus'
import 'element-plus/dist/index.css'
import './theme.css'
import './style.css'
import App from './App.vue'
import { router } from './router'
import { clearAuth } from './auth'
window.addEventListener('litera:unauthenticated', () => {
  clearAuth()
  if (router.currentRoute.value.meta.protected) void router.replace('/login')
})
const app = createApp(App).use(router)
for (const component of [ElAlert, ElButton, ElForm, ElFormItem, ElInput]) app.component(component.name!, component)
app.mount('#app')

const themeMeta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
if (themeMeta) themeMeta.content = getComputedStyle(document.documentElement).getPropertyValue('--litera-primary').trim()
