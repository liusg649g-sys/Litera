import type {ReaderContext} from './context'
import {textHasUnmappedCharacters,unreliableTextMessage} from './textQuality'
import type {NoteCaptureDraft,CaptureSource} from '../notes/captures'

/** Freeze only a reliable PDF-layer snapshot; body/input selections have no positions. */
export function pdfNoteCapture(context:Readonly<ReaderContext>|null,title:string,activeDocumentId:string):{draft:NoteCaptureDraft<CaptureSource>|null;error:string}{
  if(!context || context.documentId!==activeDocumentId || !context.selectedText.trim() || !context.selectionPosition?.length)
    return {draft:null,error:'请先在当前 PDF 正文文字层选中文字；扫描页没有可靠文字层时不能保存原文摘录。'}
  if(context.textExtractionIssue || textHasUnmappedCharacters(context.selectedText))
    return {draft:null,error:context.textExtractionIssue || unreliableTextMessage}
  if(context.selectedText.length>6000)return {draft:null,error:'单次摘录最多 6000 个字符，请缩小选区。'}
  return {error:'',draft:{title,source:{kind:'pdf_excerpt',documentId:context.documentId,pageNumber:context.selectionPosition[0]!.pageNumber,
    originalText:context.selectedText,positions:JSON.parse(JSON.stringify(context.selectionPosition)),
    contextRevision:context.contextRevision,historical:false,confirmHistorical:false}}}
}
