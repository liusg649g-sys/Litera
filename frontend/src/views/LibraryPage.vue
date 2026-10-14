<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Brand from '../components/Brand.vue'
import { auth, logout } from '../auth'
const router = useRouter(), busy = ref(false), errorMessage = ref('')
async function signOut() {
  if (busy.value) return
  busy.value = true; errorMessage.value = ''
  try { await logout(); await router.replace('/login') }
  catch (error) { errorMessage.value = error instanceof Error ? error.message : '退出失败，请重试' }
  finally { busy.value = false }
}
</script>
<template>
  <div class="workspace">
    <header class="workspace-header"><Brand /><div class="account-actions"><span>{{ auth.user?.displayName }}</span><router-link to="/profile">个人资料</router-link><el-button :loading="busy" @click="signOut">退出登录</el-button></div></header>
    <main class="placeholder-page">
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" role="alert" />
      <span class="eyebrow">个人科研空间</span>
      <h1>欢迎，{{ auth.user?.displayName }}</h1>
      <p>你已成功登录 Litera。</p>
      <section class="placeholder-card"><span class="phase-badge">下一阶段</span><h2>文献库正在准备中</h2><p>本轮已开放账号注册、登录与个人资料。文献导入、分类和检索将在下一轮开发。</p></section>
    </main>
  </div>
</template>
