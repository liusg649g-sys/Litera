import { api } from './api'
import { auth } from './auth'
export interface UserModelProfile { provider:'openai_compatible'; baseUrl:string; model:string; hasApiKey:boolean; revision:string; verified:boolean }
export interface UserModelStatus { available:boolean; profile:UserModelProfile|null }
export const modelSettingsEvent='litera:user-model-changed'
export function readUserModel(){ return api<UserModelStatus>('/user-model') }
export async function saveUserModel(payload:{provider:string;baseUrl:string;model:string;apiKey?:string;clearKey:boolean;expectedRevision:string|null}) {
 const result=await api<UserModelStatus>('/user-model',{method:'PUT',body:JSON.stringify(payload)},auth.csrfToken)
 window.dispatchEvent(new Event(modelSettingsEvent));return result
}
export async function testUserModel(revision:string){
 const result=await api<{status:string;profile:UserModelProfile}>('/user-model/test',{method:'POST',body:JSON.stringify({expectedRevision:revision})},auth.csrfToken)
 window.dispatchEvent(new Event(modelSettingsEvent));return result
}
export async function deleteUserModel(revision:string){
 await api<void>('/user-model',{method:'DELETE',body:JSON.stringify({expectedRevision:revision})},auth.csrfToken)
 window.dispatchEvent(new Event(modelSettingsEvent))
}
