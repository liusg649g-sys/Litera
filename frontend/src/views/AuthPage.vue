<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import Brand from '../components/Brand.vue'
import { login } from '../auth'
import { api } from '../api'
import { validEmail, validPassword } from '../validation'

const route = useRoute(), router = useRouter()
const registerMode = computed(() => route.path === '/register')
const formRef = ref<FormInstance>(), busy = ref(false), errorMessage = ref('')
const hasSubmitted = ref(false)
type AuthField = 'email' | 'password' | 'displayName' | 'confirm'
const form = reactive({ email: String(route.query.email || ''), password: '', displayName: '', confirm: '' })
const rules = computed<FormRules>(() => ({
  email: [{ required: true, message: '请输入邮箱', trigger: 'blur' },
    { validator: (_r, value, cb) => cb(validEmail(value.trim()) ? undefined : new Error('请输入有效的邮箱地址')), trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' },
    ...(registerMode.value ? [{ validator: (_r: unknown, value: string, cb: (error?: Error) => void) =>
      cb(validPassword(value) ? undefined : new Error('密码长度为 8–128 个字符')), trigger: 'blur' }] : [])],
  displayName: [{ required: true, validator: (_r, value, cb) => cb(value.trim().length >= 1 && Array.from(value.trim()).length <= 80
    ? undefined : new Error('显示名称为 1–80 个字符')), trigger: 'blur' }],
  confirm: [{ required: true, validator: (_r, value, cb) => cb(value === form.password && value ? undefined : new Error('两次密码输入不一致')), trigger: 'blur' }],
}))
watch(registerMode, async () => {
  hasSubmitted.value = false
  form.password = ''; form.confirm = ''; errorMessage.value = ''
  await nextTick()
  formRef.value?.clearValidate()
})
function clearFieldError(field: AuthField) {
  formRef.value?.clearValidate(field)
  if (field === 'password') formRef.value?.clearValidate('confirm')
  errorMessage.value = ''
}
function validateOnBlur(field: AuthField) {
  if (!hasSubmitted.value && form[field] === '') return
  void formRef.value?.validateField(field).catch(() => {})
}
async function submit() {
  if (busy.value) return
  hasSubmitted.value = true
  if (!await formRef.value?.validate().catch(() => false)) return
  busy.value = true; errorMessage.value = ''
  try {
    if (registerMode.value) {
      await api('/auth/register', { method: 'POST', body: JSON.stringify({
        email: form.email.trim(), password: form.password, displayName: form.displayName.trim(),
      }) })
      form.password = ''; form.confirm = ''
      await router.push({ path: '/login', query: { registered: '1', email: form.email.trim() } })
    } else {
      await login(form.email.trim(), form.password)
      form.password = ''
      await router.push('/library')
    }
  } catch (error) { errorMessage.value = error instanceof Error ? error.message : '操作失败，请重试' }
  finally { busy.value = false }
}
</script>
<template>
  <div class="auth-layout">
    <header class="auth-header"><Brand /><span class="header-caption">科研文献智能管理与协作平台</span></header>
    <main class="auth-main">
      <section class="auth-intro" aria-label="Litera 简介">
        <span class="eyebrow">YOUR RESEARCH, IN FOCUS</span>
        <h1>让阅读更专注，<br>让研究更有序。</h1>
        <p>从一篇文献开始，建立属于你的科研空间。</p>
        <div class="intro-rule"></div>
        <div class="intro-notes"><span>文献管理</span><span>深度阅读</span><span>知识积累</span></div>
      </section>
      <section class="auth-card" :class="{ 'auth-card--login': !registerMode }">
        <nav class="auth-tabs" aria-label="账号入口">
          <router-link to="/login" :class="{ active: !registerMode }" :tabindex="busy ? -1 : 0">登录</router-link>
          <router-link to="/register" :class="{ active: registerMode }" :tabindex="busy ? -1 : 0">注册</router-link>
        </nav>
        <h2>{{ registerMode ? '创建你的账号' : '欢迎回到 Litera' }}</h2>
        <p class="card-subtitle">{{ registerMode ? '开启你的科研文献阅读之旅' : '登录后，进入你的个人科研空间' }}</p>
        <el-alert v-if="route.query.registered && !registerMode" title="注册成功，请使用你的邮箱和密码登录" type="success" :closable="false" show-icon />
        <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon role="alert" />
        <el-form ref="formRef" :model="form" :rules="rules" :validate-on-rule-change="false" label-position="top" :disabled="busy" @submit.prevent="submit">
          <el-form-item v-if="registerMode" label="显示名称" prop="displayName" for="display-name">
            <el-input id="display-name" v-model="form.displayName" :validate-event="false" @blur="validateOnBlur('displayName')" @update:model-value="clearFieldError('displayName')" placeholder="你的名字" autocomplete="nickname" maxlength="80" />
          </el-form-item>
          <el-form-item label="邮箱" prop="email" for="email">
            <el-input id="email" v-model="form.email" :validate-event="false" @blur="validateOnBlur('email')" @update:model-value="clearFieldError('email')" placeholder="you@example.com" autocomplete="email" maxlength="254" />
          </el-form-item>
          <el-form-item label="密码" prop="password" for="password">
            <el-input id="password" v-model="form.password" :validate-event="false" @blur="validateOnBlur('password')" @update:model-value="clearFieldError('password')" type="password" show-password :autocomplete="registerMode ? 'new-password' : 'current-password'" :placeholder="registerMode ? '8–128 个字符' : '请输入密码'" />
          </el-form-item>
          <el-form-item v-if="registerMode" label="确认密码" prop="confirm" for="confirm-password">
            <el-input id="confirm-password" v-model="form.confirm" :validate-event="false" @blur="validateOnBlur('confirm')" @update:model-value="clearFieldError('confirm')" type="password" show-password autocomplete="new-password" placeholder="再次输入密码" />
          </el-form-item>
          <el-button class="submit-button" type="primary" native-type="submit" :loading="busy">{{ registerMode ? '创建账号' : '登录' }}</el-button>
        </el-form>
        <p class="form-footnote">{{ registerMode ? '注册后可使用邮箱和密码登录。' : '还没有账号？' }} <router-link v-if="!registerMode" to="/register">立即注册</router-link></p>
      </section>
    </main>
    <footer class="auth-footer">Litera · 科研文献智能管理与协作平台</footer>
  </div>
</template>
