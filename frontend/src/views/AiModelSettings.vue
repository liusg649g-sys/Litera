<script setup lang="ts">
import { computed,onBeforeUnmount,onMounted,reactive,ref,watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import Brand from '../components/Brand.vue'
import { auth } from '../auth'
import { readUserModel,saveUserModel,testUserModel,deleteUserModel,type UserModelProfile } from '../userModels'
const available=ref(false),busy=ref(false),error=ref(''),message=ref(''),profile=ref<UserModelProfile|null>(null)
const form=reactive({provider:'openai_compatible',baseUrl:'',model:'',apiKey:'',clearKey:false})
const dirty=computed(()=>form.baseUrl!==(profile.value?.baseUrl||'') || form.model!==(profile.value?.model||'') || !!form.apiKey || form.clearKey)
let epoch=0
function apply(value:UserModelProfile|null){profile.value=value;form.provider=value?.provider||'openai_compatible';form.baseUrl=value?.baseUrl||'';form.model=value?.model||'';form.apiKey='';form.clearKey=false}
async function action(task:()=>Promise<void>){
 if(busy.value)return
 const token=epoch;busy.value=true;error.value='';message.value=''
 try{await task()}catch(e){if(token===epoch)error.value=e instanceof Error?e.message:'操作失败，请稍后重试'}finally{if(token===epoch)busy.value=false}
}
async function load(){const token=epoch;await action(async()=>{const result=await readUserModel();if(token!==epoch)return;available.value=result.available;apply(result.profile)})}
async function save(){const token=epoch;await action(async()=>{
 const result=await saveUserModel({...form,apiKey:form.apiKey||undefined,expectedRevision:profile.value?.revision||null})
 if(token!==epoch)return;apply(result.profile);message.value='已安全保存。请点击测试连接；保存本身不会调用模型。'
})}
async function test(){const token=epoch;const revision=profile.value?.revision;if(!revision||dirty.value)return
 await action(async()=>{const result=await testUserModel(revision);if(token!==epoch)return;apply(result.profile);message.value='连接测试成功，可在翻译栏选择“我的模型”。'})}
async function remove(){const revision=profile.value?.revision;if(!revision||!window.confirm('删除你的模型配置和已保存密钥？已有译文与笔记会保留。'))return
 const token=epoch;await action(async()=>{await deleteUserModel(revision);if(token!==epoch)return;apply(null);message.value='模型配置已删除，已有笔记与译文保持不变。'})}
function cancel(){apply(profile.value);error.value='';message.value='已放弃未保存修改'}
function beforeUnload(event:BeforeUnloadEvent){if(dirty.value){event.preventDefault();event.returnValue=''}}
onBeforeRouteLeave(()=>!auth.user || !dirty.value || window.confirm('放弃尚未保存的模型设置并离开？'))
watch(()=>auth.user?.id,()=>{epoch++;available.value=false;apply(null);error.value='';message.value='';busy.value=false})
onMounted(()=>{void load();window.addEventListener('beforeunload',beforeUnload)})
onBeforeUnmount(()=>{epoch++;form.apiKey='';window.removeEventListener('beforeunload',beforeUnload)})
</script>
<template>
 <div class="workspace"><header class="workspace-header"><Brand/><router-link to="/library">返回文献库</router-link><router-link to="/profile">个人资料</router-link></header>
 <main class="profile-page ai-settings"><h1>AI 模型设置</h1><p>配置仅属于当前账号。模型请求由 Litera 后端发送；你选择的文献文字会交给此服务处理。</p>
 <section class="profile-card" aria-label="AI 模型设置">
  <p role="status" data-testid="model-status">{{ !available?'此环境未启用用户模型设置':!profile?'模型未配置':profile.verified?'已验证 · '+profile.model:profile.hasApiKey?'已保存，尚未验证':'模型未配置：请添加 API Key' }}</p>
  <p v-if="error" role="alert">{{ error }}</p><p v-if="message" role="status">{{ message }}</p>
  <button type="button" :disabled="busy" @click="load">重新加载配置</button>
  <form v-if="available" @submit.prevent="save"><fieldset :disabled="busy">
   <label>模型服务类型<select v-model="form.provider" aria-label="模型服务类型"><option value="openai_compatible">OpenAI Compatible</option></select></label>
   <label>API Base URL<input v-model="form.baseUrl" aria-label="API Base URL" type="url" required maxlength="2048" placeholder="https://api.example.com/v1" autocomplete="off"/></label>
   <p class="muted">仅支持公网 HTTPS 默认端口443；不允许本机、内网、查询参数或重定向。</p>
   <label>模型名称<input v-model="form.model" aria-label="模型名称" required maxlength="200" autocomplete="off"/></label>
   <label>API Key<input v-model="form.apiKey" aria-label="API Key" type="password" maxlength="4096" autocomplete="new-password" :disabled="form.clearKey" :placeholder="profile?.hasApiKey?'留空保留已保存密钥':'填写你的 API Key'"/></label>
   <p class="muted">{{ profile?.hasApiKey?'已有密钥已加密保存，浏览器不会读取其内容。':'密钥由后端安全存储加密，主密钥与业务数据库分开管理。' }}</p>
   <label v-if="profile?.hasApiKey" class="checkbox"><input v-model="form.clearKey" type="checkbox" aria-label="清除已保存密钥" @change="form.apiKey=''"/>清除已保存密钥</label>
   <div class="actions"><button type="submit">保存设置</button><button type="button" :disabled="dirty || !profile?.hasApiKey" @click="test">测试连接</button><button v-if="profile" type="button" @click="remove">删除设置</button><button type="button" :disabled="!dirty" @click="cancel">放弃修改</button></div>
   <p class="muted">先保存，再主动测试连接（固定短提示、最多32输出Token）。测试成功才启用翻译；每次修改后需要重新测试。不会自动调用，也不会在失败时回退其他人的模型。</p>
  </fieldset></form>
 </section></main></div>
</template>
<style scoped>
.ai-settings{max-width:800px}.ai-settings p{line-height:1.7}.ai-settings fieldset{border:0;padding:0;min-width:0}.ai-settings label{display:flex;flex-direction:column;gap:8px;margin:18px 0}.ai-settings input,.ai-settings select{font:inherit;padding:10px;border:1px solid #ccc;border-radius:6px;min-width:0}.ai-settings .checkbox{flex-direction:row;align-items:center}.actions{display:flex;flex-wrap:wrap;gap:10px}.ai-settings button{padding:9px 14px;border:1px solid #ccc;border-radius:5px;cursor:pointer}.ai-settings button[type=submit]{background:#940b18;color:white}.ai-settings button:disabled{opacity:.5;cursor:default}[role=alert]{color:#9b0000}
</style>
