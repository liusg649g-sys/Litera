// Real standards-compliant PDF bytes, parsed by the server and PDF.js, never a renderer mock.
export function readerPdf(label: string, count = 7, chinese = false, options: { outline?: boolean; userUnit?: number; scan?: boolean; split?: boolean; mixed?: boolean; detail?: boolean; annotation?: boolean; scripts?: boolean } = {}) {
  const objects: string[] = []
  objects.push('<< /Type /Catalog /Pages 2 0 R >>')
  objects.push(`<< /Type /Pages /Kids [${Array.from({length:count},(_,i)=>`${3+i*2} 0 R`).join(' ')}] /Count ${count} >>`)
  const fontId=3+count*2
  for(let i=0;i<count;i++) {
    const mixed=i%2===1, contentId=4+i*2
    const image = 'q 200 0 0 200 40 400 cm BI /W 1 /H 1 /CS /RGB /BPC 8 /F /ASCIIHexDecode ID cccccc> EI Q'
    const text=options.scan || (options.mixed && i % 2) ? image : `BT /F1 18 Tf 40 700 Td (${label} - Page ${i+1}) Tj ET` + (chinese?'\nBT /F2 18 Tf 40 650 Td <79D178146587732E96058BFB6D4B8BD5> Tj ET':'') + (options.split ? '\nBT /F1 18 Tf 40 600 Td (inter) Tj /F1 19 Tf (national) Tj ET\nBT /F1 18 Tf 40 550 Td (Word word words) Tj ET' : '')
    const detail = options.detail ? '\nBT /F1 32 Tf 40 740 Td (Research title) Tj ET\nBT /F1 12 Tf 40 660 Td (Body text: sharp letters and image edges.) Tj ET\nq 180 0 0 160 40 440 cm BI /W 4 /H 4 /CS /RGB /BPC 8 /F /ASCIIHexDecode ID ' + Array.from({length:16},(_,n)=>(n+Math.floor(n/4))%2?'224488':'eeeeee').join('') + '> EI Q' : ''
    const annotation = options.annotation ? '\nBT /F1 12 Tf 40 600 Td (Precision ) Tj /F3 12 Tf (selection ) Tj /F1 12 Tf [(across) -420 ( split) -400 ( items and spaces.)] TJ ET\nBT /F3 12 Tf 40 586 Td (Compact italic line, punctuation and words.) Tj ET\nBT /F1 12 Tf 40 572 Td (Third line for reverse selection.) Tj ET\nBT /F1 12 Tf 350 600 Td (Separate column remains separate.) Tj ET' : ''
    const scripts = options.scripts ? '\nBT /F1 12 Tf 40 614 Td (Previous compact line, keep separate.) Tj ET\nBT /F1 12 Tf 40 600 Td (Body network) Tj /F1 7 Tf 5 Ts ([6]) Tj /F1 12 Tf 0 Ts ( continuation text.) Tj ET\nBT /F1 12 Tf 40 586 Td (Next compact line, keep separate.) Tj ET' : ''
    objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${mixed?700:612} 792] ${options.userUnit?`/UserUnit ${options.userUnit}`:''} ${i===2?'/CropBox [20 30 600 770] /Rotate 90':''} /Resources << /Font << /F1 ${fontId} 0 R ${options.annotation?`/F3 ${fontId+(chinese?3:1)} 0 R`: ''} ${chinese?`/F2 ${fontId+1} 0 R`:''} >> >> /Contents ${contentId} 0 R >>`)
    objects.push(`<< /Length ${Buffer.byteLength(text+detail+annotation+scripts)} >>\nstream\n${text+detail+annotation+scripts}\nendstream`)
  }
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
  if(chinese) {
    objects.push(`<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H /DescendantFonts [${fontId+2} 0 R] >>`)
    objects.push('<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 4 >> /DW 1000 >>')
  }
  if (options.annotation) objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>')
  if (options.outline) {
    const id = objects.length + 1, target = 3 + Math.min(3, count - 1) * 2
    objects[0] = `<< /Type /Catalog /Pages 2 0 R /Outlines ${id} 0 R /Names << /Dests << /Names [(chapter) [${target} 0 R /XYZ 40 550 null]] >> >> >>`
    objects.push(`<< /Type /Outlines /First ${id+1} 0 R /Last ${id+3} 0 R /Count 3 >>`)
    objects.push(`<< /Title (Chapter) /Parent ${id} 0 R /First ${id+2} 0 R /Last ${id+2} 0 R /Next ${id+3} 0 R /Count 1 /Dest (chapter) >>`)
    objects.push(`<< /Title (Child section) /Parent ${id+1} 0 R /Dest [3 0 R /Fit] >>`)
    objects.push(`<< /Title (Broken target) /Parent ${id} 0 R /Prev ${id+1} 0 R /Dest (missing-target) >>`)
  }
  let source='%PDF-1.7\n', offsets=[0]
  for(const [i,object] of objects.entries()) { offsets.push(Buffer.byteLength(source)); source+=`${i+1} 0 obj\n${object}\nendobj\n` }
  const xref=Buffer.byteLength(source)
  source+=`xref\n0 ${objects.length+1}\n0000000000 65535 f \n`+offsets.slice(1).map(n=>`${String(n).padStart(10,'0')} 00000 n \n`).join('')
  return Buffer.from(source+`trailer\n<< /Size ${objects.length+1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`)
}
