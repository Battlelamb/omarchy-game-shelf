// SPDX-License-Identifier: GPL-3.0-only
function utf8Bytes(s) {
    var n=0;
    for(var i=0;i<s.length;i++) {
        var c=s.charCodeAt(i);
        if(c<128) n++; else if(c<2048) n+=2;
        else if(c>=0xD800 && c<=0xDBFF && i+1<s.length && s.charCodeAt(i+1)>=0xDC00 && s.charCodeAt(i+1)<=0xDFFF) { n+=4; i++; }
        else n+=3;
    }
    return n;
}
function stringValue(v,max) { return typeof v==='string' && v.length<=max && !/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(v); }
function catalog(raw) {
    var empty={rows:[],actions:[],message:'Unable to load catalogue'};
    if(typeof raw!=='string'||raw.length>1048576||utf8Bytes(raw)>1048576) return empty;
    var data;
    try { data=JSON.parse(raw); } catch(e) { return empty; }
    if(!data || typeof data!=='object' || !Array.isArray(data.rows) || data.rows.length>16384) return empty;
    var rows=[],seen=Object.create(null);
    for(var i=0;i<data.rows.length;i++) {
        var r=data.rows[i];
        if(!r||!stringValue(r.id,256)||!r.id||seen[r.id]||!stringValue(r.label,320)||!r.label) continue;
        // Native QV4's Array.from does not combine surrogate pairs.
        if(r.label.length>160&&r.label.replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]/g,'x').length>160) continue;
        seen[r.id]=true;
        var out={id:r.id,label:r.label,detail:stringValue(r.detail,1024)?r.detail:'',preview:'',glyph:'',color:''};
        if(stringValue(r.preview,4096) && r.preview[0]==='/' && !/[\r\n]/.test(r.preview)) out.preview=r.preview;
        if(stringValue(r.glyph,4)) out.glyph=r.glyph;
        if(typeof r.color==='string' && /^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$/.test(r.color)) out.color=r.color;
        rows.push(out);
    }
    var allowed=['copy','launch','apply','export','restore','confirm'];
    var actions=Array.isArray(data.actions)?data.actions.filter(function(a){return allowed.indexOf(a)!==-1;}):[];
    return {rows:rows,actions:actions,message:stringValue(data.message,1024)?data.message:''};
}
function step(index, delta, count) {
    return Math.max(0, Math.min(Math.max(0, count - 1), index + delta));
}
function filter(rows,query) {
    if(!Array.isArray(rows)||typeof query!=='string'||query.length>128) return [];
    var words=query.toLowerCase().trim().split(/\s+/).filter(function(w){return w.length>0;});
    if(!words.length) return rows.slice(0,256);
    var matches=[];
    for(var i=0;i<rows.length;i++) {
        var r=rows[i],text=(r.label+' '+r.detail).toLowerCase();
        if(words.every(function(w){return text.indexOf(w)!==-1;})) {
            matches.push(r);
            if(matches.length===256) break;
        }
    }
    return matches;
}
function imageUrl(path) {
    if(typeof path!=='string'||path[0]!=='/'||/[\x00-\x1f]/.test(path)||path.length>4096) return '';
    return 'file://'+path.split('/').map(function(s){return encodeURIComponent(s);}).join('/');
}
function actionResult(raw,code,status,error) {
    var result={ok:false,message:'Action failed; you can retry'};
    if(typeof raw!=='string'||raw.length>65536||error||status!==0) return result;
    try {
        var d=JSON.parse(raw);
        if(d && d.ok===true && code===0) result.ok=true;
        var allowed=['copy','launch','apply','export','restore','confirm'];
        if(result.ok && Array.isArray(d.actions) && d.actions.length<=allowed.length && d.actions.every(function(a,i){return allowed.indexOf(a)!==-1 && d.actions.indexOf(a)===i;})) result.actions=d.actions;
        if(d && stringValue(d.message,1024)) result.message=(result.ok?'':'Action failed: ')+d.message;
        else if(result.ok) result.message='Done';
    } catch(e) {}
    return result;
}
