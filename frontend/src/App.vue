<script setup lang="ts">
import { auth } from './auth'
const unifiedAcceptance=import.meta.env.VITE_LITERA_UNIFIED_ACCEPTANCE==='true'
const userModelPreview=import.meta.env.VITE_LITERA_USER_MODEL_PREVIEW==='true'
function retry() { window.location.reload() }
</script>
<template>
  <div v-if="unifiedAcceptance" role="status" style="padding:6px 12px;background:#fff1d6;color:#65420a;font-size:12px">Litera 翻译与笔记统一验收 · 默认 Mock · 选择个人模型后才调用外部服务 · AI 问答仅固定模拟适配</div>
  <div v-else-if="userModelPreview" role="status" style="padding:6px 12px;background:#fff1d6;color:#65420a;font-size:12px">用户模型独立预览 · 数据与5177/5180隔离 · 仅主动测试/翻译时调用你配置的外部服务</div>
  <main v-if="auth.restoreError" class="connection-error">
    <img src="/litera.svg" width="48" height="48" alt="Litera">
    <h1>暂时无法连接 Litera</h1>
    <p role="alert">{{ auth.restoreError }}</p>
    <el-button type="primary" @click="retry">重新连接</el-button>
  </main>
  <router-view v-else />
</template>
