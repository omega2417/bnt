const fs=require('fs');
const D=require('docx');
const {Paragraph,TextRun,HeadingLevel,Table,TableRow,TableCell,WidthType,BorderStyle,
       AlignmentType,ShadingType,ImageRun,PageBreak}=D;

function parseCSV(path){
  const lines=fs.readFileSync(path,'utf8').split(/\r?\n/).filter(l=>l.length);
  return lines.map(l=>{
    const out=[];let cur='',q=false;
    for(const ch of l){ if(ch==='"'){q=!q;} else if(ch===','&&!q){out.push(cur);cur='';} else cur+=ch; }
    out.push(cur); return out;
  });
}
const FONT='Calibri';
function runs(text,opts={}){ return new TextRun({text,font:FONT,size:opts.size||20,bold:opts.bold,italics:opts.it,color:opts.color}); }
function H(text,level){ return new Paragraph({heading:level,spacing:{before:220,after:110},children:[new TextRun({text,font:FONT})]}); }
function P(text,opts={}){
  if(Array.isArray(text)) return new Paragraph({spacing:{after:120,line:264},alignment:opts.align,children:text});
  return new Paragraph({spacing:{after:120,line:264},alignment:opts.align,children:[runs(text,opts)]});
}
function bullet(text,opts={}){ return new Paragraph({bullet:{level:opts.level||0},spacing:{after:60,line:252},children:Array.isArray(text)?text:[runs(text,opts)]}); }
function numbered(text,ref){ return new Paragraph({numbering:{reference:ref,level:0},spacing:{after:60,line:252},children:[runs(text)]}); }
function noteBox(children,color){
  color=color||'FFF3CD';
  return new Table({width:{size:9020,type:WidthType.DXA},columnWidths:[9020],
    borders:{top:{style:BorderStyle.SINGLE,size:6,color:'C0A000'},bottom:{style:BorderStyle.SINGLE,size:6,color:'C0A000'},
             left:{style:BorderStyle.SINGLE,size:18,color:'C0A000'},right:{style:BorderStyle.SINGLE,size:6,color:'C0A000'},
             insideHorizontal:{style:BorderStyle.NONE},insideVertical:{style:BorderStyle.NONE}},
    rows:[new TableRow({children:[new TableCell({width:{size:9020,type:WidthType.DXA},
      shading:{type:ShadingType.CLEAR,fill:color},margins:{top:120,bottom:120,left:160,right:160},
      children:children})]})]});
}
function table(rows,opts={}){
  const total=opts.total||9020;
  const ncol=rows[0].length;
  let widths=opts.widths;
  if(!widths){ widths=Array(ncol).fill(1); }
  while(widths.length<ncol) widths.push(1);
  widths=widths.slice(0,ncol);
  const sum=widths.reduce((a,b)=>a+b,0); widths=widths.map(w=>Math.floor(w*total/sum));
  const trs=rows.map((r,ri)=>new TableRow({tableHeader:ri===0,children:r.map((c,ci)=>new TableCell({
    width:{size:widths[ci],type:WidthType.DXA},
    shading:ri===0?{type:ShadingType.CLEAR,fill:'1F4E8C'}:(ri%2===0?{type:ShadingType.CLEAR,fill:'EEF3FA'}:undefined),
    margins:{top:40,bottom:40,left:70,right:70},
    children:[new Paragraph({alignment:ci===0?AlignmentType.LEFT:AlignmentType.CENTER,spacing:{after:0,line:230},
      children:[new TextRun({text:String(c),font:FONT,size:opts.size||16,bold:ri===0,color:ri===0?'FFFFFF':'000000'})]})]
  }))}));
  return new Table({width:{size:total,type:WidthType.DXA},columnWidths:widths,
    borders:{top:{style:BorderStyle.SINGLE,size:4,color:'8AA0C0'},bottom:{style:BorderStyle.SINGLE,size:4,color:'8AA0C0'},
      left:{style:BorderStyle.SINGLE,size:4,color:'8AA0C0'},right:{style:BorderStyle.SINGLE,size:4,color:'8AA0C0'},
      insideHorizontal:{style:BorderStyle.SINGLE,size:2,color:'C8D4E6'},insideVertical:{style:BorderStyle.SINGLE,size:2,color:'C8D4E6'}},
    rows:trs});
}
function tableFromCSV(path,opts={}){ return table(parseCSV(path),opts); }
function pngDims(path){ const b=fs.readFileSync(path); return {w:b.readUInt32BE(16),h:b.readUInt32BE(20)}; }
function figure(path,maxW){
  maxW=maxW||560; const d=pngDims(path); const scale=Math.min(1,maxW/d.w);
  return new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:80,after:40},
    children:[new ImageRun({type:'png',data:fs.readFileSync(path),transformation:{width:Math.round(d.w*scale),height:Math.round(d.h*scale)}})]});
}
function caption(text){ return new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:160},children:[new TextRun({text,font:FONT,size:16,italics:true,color:'555555'})]}); }
module.exports={D,Paragraph,TextRun,HeadingLevel,AlignmentType,PageBreak,parseCSV,H,P,bullet,numbered,noteBox,table,tableFromCSV,figure,caption,runs,FONT};
