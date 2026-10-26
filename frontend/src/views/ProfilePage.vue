<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import type { FormInstance, FormRules, InputInstance } from 'element-plus'
import Brand from '../components/Brand.vue'
import { auth, changePassword, updateProfile } from '../auth'
import { ApiError } from '../api'
import { validPassword } from '../validation'
const router = useRouter()
const displayName = ref(auth.user?.displayName || ''), busy = ref(false), errorMessage = ref(''), saved = ref(false)
const formRef = ref<FormInstance>()
const passwordOpen = ref(false), passwordBusy = ref(false), passwordError = ref(''), passwordSubmitted = ref(false)
const passwordForm = reactive({ currentPassword: '', newPassword: '', confirm: '' })
const passwordFormRef = ref<FormInstance>(), currentInput = ref<InputInstance>()
let passwordCompleted = false
const passwordRules: FormRules = {
  currentPassword: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  newPassword: [{ required: true, validator: (_rule, value, cb) => cb(!validPassword(value) ? new Error('密码长度为 8–128 个字符') : value === passwordForm.currentPassword ? new Error('新密码不能与当前密码相同') : undefined), trigger: 'blur' }],
  confirm: [{ required: true, validator: (_rule, value, cb) => cb(value && value === passwordForm.newPassword ? undefined : new Error('两次密码输入不一致')), trigger: 'blur' }],
}
type PasswordField = keyof typeof passwordForm
function clearPasswordError(field: PasswordField) {
  passwordFormRef.value?.clearValidate(field)
  if (field === 'newPassword') passwordFormRef.value?.clearValidate('confirm')
  if (field === 'currentPassword') passwordFormRef.value?.clearValidate('newPassword')
  passwordError.value = ''
}
function blurPassword(field: PasswordField) {
  if (passwordSubmitted.value || passwordForm[field]) void passwordFormRef.value?.validateField(field).catch(() => {})
}
async function openPassword() { passwordOpen.value = true; await nextTick(); currentInput.value?.focus() }
function clearPasswords() { passwordForm.currentPassword = ''; passwordForm.newPassword = ''; passwordForm.confirm = '' }
function cancelPassword() {
  if (passwordBusy.value || busy.value) return
  clearPasswords(); passwordError.value = ''; passwordSubmitted.value = false; passwordOpen.value = false
  void nextTick(() => document.getElementById('change-password-trigger')?.focus())
}
async function savePassword() {
  if (passwordBusy.value || busy.value) return
  passwordSubmitted.value = true
  passwordBusy.value = true; passwordError.value = ''
  try {
    if (!await passwordFormRef.value?.validate().catch(() => false)) return
    const email = auth.user?.email || ''
    await changePassword(passwordForm.currentPassword, passwordForm.newPassword)
    passwordCompleted = true; clearPasswords()
    await router.replace({ path: '/login', query: { passwordChanged: '1', email } })
  } catch (error) {
    passwordError.value = error instanceof ApiError && error.status === 0
      ? '请求结果尚未确认，请检查网络后重试；如果登录已失效，请使用新密码重新登录核对。'
      : error instanceof Error ? error.message : '修改密码失败，请重试'
  } finally { passwordBusy.value = false }
}
function passwordDirty() { return Object.values(passwordForm).some(Boolean) }
onBeforeRouteLeave(() => {
  if (!auth.user) return true
  if (!passwordCompleted && (passwordBusy.value || passwordDirty())) {
    passwordError.value = '请先保存新密码或取消修改，再离开此页。'; return false
  }
  return true
})
function beforeUnload(event: BeforeUnloadEvent) { if (passwordDirty()) { event.preventDefault(); event.returnValue = '' } }
onMounted(() => window.addEventListener('beforeunload', beforeUnload))
onBeforeUnmount(() => { clearPasswords(); window.removeEventListener('beforeunload', beforeUnload) })
async function save() {
  if (busy.value || passwordBusy.value || !await formRef.value?.validate().catch(() => false)) return
  busy.value = true; errorMessage.value = ''; saved.value = false
  try { await updateProfile(displayName.value.trim()); saved.value = true }
  catch (error) { errorMessage.value = error instanceof Error ? error.message : '保存失败' }
  finally { busy.value = false }
}
</script>
<template>
  <div class="workspace">
    <header class="workspace-header"><Brand /><router-link to="/library">返回文献库</router-link></header>
    <main class="profile-page"><h1>个人资料</h1><p><router-link to="/settings/ai">AI 模型设置</router-link></p><p class="muted">管理你的账号显示信息。</p>
      <section class="profile-card">
        <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" role="alert" />
        <el-alert v-if="saved" title="资料已保存" type="success" :closable="false" />
        <el-form ref="formRef" :model="{ displayName }" label-position="top" :disabled="busy || passwordBusy" @submit.prevent="save">
          <el-form-item label="邮箱"><span>{{ auth.user?.email }}</span></el-form-item>
          <el-form-item label="显示名称" prop="displayName" for="profile-name" :rules="[{ required: true, whitespace: true, min: 1, max: 80, message: '请输入 1–80 个字符的显示名称', trigger: 'blur' }]">
            <el-input id="profile-name" v-model="displayName" maxlength="80" autocomplete="nickname" />
          </el-form-item>
          <el-button type="primary" native-type="submit" :loading="busy">保存资料</el-button>
        </el-form>
      </section>
      <section class="profile-card security-card" aria-labelledby="account-security-title">
        <h2 id="account-security-title">账号安全</h2>
        <div class="password-summary"><div><strong>登录密码</strong><p class="muted">修改成功后，所有设备需重新登录。</p></div><el-button v-if="!passwordOpen" id="change-password-trigger" :disabled="busy" aria-controls="change-password-form" :aria-expanded="passwordOpen" @click="openPassword">修改密码</el-button></div>
        <el-form v-if="passwordOpen" id="change-password-form" ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" :validate-on-rule-change="false" label-position="top" :disabled="passwordBusy" @submit.prevent="savePassword">
          <el-alert v-if="passwordError" :title="passwordError" type="error" :closable="false" role="alert" />
          <el-form-item label="当前密码" prop="currentPassword" for="current-password"><el-input id="current-password" ref="currentInput" v-model="passwordForm.currentPassword" type="password" show-password autocomplete="current-password" :validate-event="false" @blur="blurPassword('currentPassword')" @update:model-value="clearPasswordError('currentPassword')" /></el-form-item>
          <el-form-item label="新密码" prop="newPassword" for="new-password"><el-input id="new-password" v-model="passwordForm.newPassword" type="password" show-password autocomplete="new-password" placeholder="8–128 个字符" :validate-event="false" @blur="blurPassword('newPassword')" @update:model-value="clearPasswordError('newPassword')" /></el-form-item>
          <el-form-item label="确认新密码" prop="confirm" for="confirm-new-password"><el-input id="confirm-new-password" v-model="passwordForm.confirm" type="password" show-password autocomplete="new-password" :validate-event="false" @blur="blurPassword('confirm')" @update:model-value="clearPasswordError('confirm')" /></el-form-item>
          <div class="password-actions"><el-button type="primary" native-type="submit" :loading="passwordBusy">保存新密码</el-button><el-button @click="cancelPassword">取消</el-button></div>
        </el-form>
      </section>
    </main>
  </div>
</template>
<style scoped>
.security-card h2 { margin:0 0 20px; font-size:20px; font-weight:600 }
.password-summary { display:flex; align-items:center; justify-content:space-between; gap:16px }
.password-summary strong { font-size:14px; font-weight:500 }
.password-summary p { margin:8px 0 0; font-size:13px; line-height:1.6 }
.security-card form { margin-top:24px }
.password-actions { display:flex; gap:12px; flex-wrap:wrap }
.password-actions :deep(.el-button + .el-button) { margin-left:0 }
@media (max-width:600px) { .profile-card { padding:24px } .password-summary { align-items:flex-start } }
</style>
