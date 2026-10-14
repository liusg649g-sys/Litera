<script setup lang="ts">
import { auth } from './auth'
function retry() { window.location.reload() }
</script>
<template>
  <main v-if="auth.restoreError" class="connection-error">
    <img src="/litera.svg" width="48" height="48" alt="Litera">
    <h1>暂时无法连接 Litera</h1>
    <p role="alert">{{ auth.restoreError }}</p>
    <el-button type="primary" @click="retry">重新连接</el-button>
  </main>
  <router-view v-else />
</template>
