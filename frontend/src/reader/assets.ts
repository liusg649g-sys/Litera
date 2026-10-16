import { api } from '../api'
import { auth } from '../auth'
export interface ReaderAsset { assetId:string; width:number; height:number; mimeType:string; sizeBytes:number; status:string; attempts:number; errorCode:string|null }
export const assetPath=(documentId:string)=>`/documents/${encodeURIComponent(documentId)}/reader-assets`
export const assetUrl=(documentId:string,assetId:string)=>`/api/v1${assetPath(documentId)}/${encodeURIComponent(assetId)}/content`
export async function uploadAsset(documentId:string,file:Blob,signal?:AbortSignal):Promise<ReaderAsset> {
  if(file.size>5*1024*1024) throw new Error('单张图片不能超过5MiB')
  const form=new FormData();form.append('file',file,'image.png')
  return api<ReaderAsset>(assetPath(documentId),{method:'POST',body:form,signal},auth.csrfToken)
}
export async function discardAsset(documentId:string,assetId:string) {
  return api<ReaderAsset|undefined>(`${assetPath(documentId)}/${encodeURIComponent(assetId)}`,{method:'DELETE'},auth.csrfToken)
}
