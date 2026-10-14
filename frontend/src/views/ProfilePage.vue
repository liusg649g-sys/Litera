<script setup lang="ts">
import { ref } from 'vue'
import type { FormInstance } from 'element-plus'
import Brand from '../components/Brand.vue'
import { auth, updateProfile } from '../auth'
const displayName = ref(auth.user?.displayName || ''), busy = ref(false), errorMessage = ref(''), saved = ref(false)
const formRef = ref<FormInstance>()
async function save() {
  if (busy.value || !await formRef.value?.validate().catch(() => false)) return
  busy.value = true; errorMessage.value = ''; saved.value = false
  try { await updateProfile(displayName.value.trim()); saved.value = true }
  catch (error) { errorMessage.value = error instanceof Error ? error.message : '保存失败' }
  finally { busy.value = false }
}
</script>
<template>
  <div class="workspace">
    <header class="workspace-header"><Brand /><router-link to="/library">返回文献库</router-link></header>
    <main class="profile-page"><h1>个人资料</h1><p class="muted">管理你的账号显示信息。</p>
      <section class="profile-card">
        <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" role="alert" />
        <el-alert v-if="saved" title="资料已保存" type="success" :closable="false" />
        <el-form ref="formRef" :model="{ displayName }" label-position="top" :disabled="busy" @submit.prevent="save">
          <el-form-item label="邮箱"><span>{{ auth.user?.email }}</span></el-form-item>
          <el-form-item label="显示名称" prop="displayName" for="profile-name" :rules="[{ required: true, whitespace: true, min: 1, max: 80, message: '请输入 1–80 个字符的显示名称', trigger: 'blur' }]">
            <el-input id="profile-name" v-model="displayName" maxlength="80" autocomplete="nickname" />
          </el-form-item>
          <el-button type="primary" native-type="submit" :loading="busy">保存资料</el-button>
        </el-form>
      </section>
    </main>
  </div>
</template>
