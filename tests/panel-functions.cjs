const assert=require('node:assert/strict');
module.exports=function(src,name){
 const start=src.indexOf('function '+name+'(');assert.ok(start>=0,'Missing '+name);
 const body=src.indexOf('{',start);let depth=1,i=body+1,quote='',escape=false;
 for(;i<src.length;i++){
  const c=src[i];
  if(quote){if(escape)escape=false;else if(c==='\\')escape=true;else if(c===quote)quote='';continue;}
  if(c==='"'||c==="'"){quote=c;continue;}
  if(c==='{')depth++;if(c==='}'&&!--depth)break;
 }
 return src.slice(start,i+1);
};
