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
        if(typeof r.favorite==='boolean') out.favorite=r.favorite;
        if(typeof r.installed==='boolean') out.installed=r.installed;
        ['category','provider','collection'].forEach(function(k){if(stringValue(r[k],256)) out[k]=r[k];});
        if(Array.isArray(r.swatches)&&r.swatches.length<=32) out.swatches=r.swatches.filter(function(c){return typeof c==='string'&&/^#[0-9a-fA-F]{6}$/.test(c);});
        rows.push(out);
    }
    var allowed=actionVerbs();
    var actions=Array.isArray(data.actions)?data.actions.filter(function(a){return allowed.indexOf(a)!==-1;}):[];
    var result={rows:rows,actions:actions,message:stringValue(data.message,1024)?data.message:''};
    var prefs=preferences(data.preferences), schema=settingsSchema(data.settingsSchema);
    if(prefs) result.preferences=prefs;
    if(schema) result.settingsSchema=schema;
    return result;
}
function actionVerbs() {
    return ['copy','launch','apply','export','favorite','restore','confirm','capture','import','export-preset','preview','compare','copy-codepoint','open-folder','shuffle','copy-color'];
}
function primaryVerb(actions) {
    return actions.filter(function(a){return ['copy','launch','apply','export'].indexOf(a)!==-1;})[0]||'';
}
function plainObject(v) { return v!==null&&typeof v==='object'&&!Array.isArray(v); }
function preferenceText(v,max) {
    if(typeof v!=='string'||!isFinite(max)||v.length>max*2||/[\x00-\x1f\x7f-\x9f]/.test(v)||utf8Bytes(v)>4096) return false;
    // QV4 Array.from counts UTF-16 units; count valid pairs explicitly.
    var count=0;
    for(var i=0;i<v.length;i++) {
        var c=v.charCodeAt(i);
        if(c>=0xD800&&c<=0xDBFF) {
            if(i+1>=v.length||v.charCodeAt(i+1)<0xDC00||v.charCodeAt(i+1)>0xDFFF) return false;
            i++;
        } else if(c>=0xDC00&&c<=0xDFFF) return false;
        if(++count>max) return false;
    }
    return true;
}
function preferenceIds(v,max) { return Array.isArray(v)&&v.length<=max&&v.every(function(id,i){return preferenceText(id,256)&&id.length>0&&v.indexOf(id)===i;}); }
function preferences(v) {
    if(!plainObject(v)||v.version!==1||!preferenceIds(v.favorites,512)||!preferenceIds(v.recent,32)||!plainObject(v.collections)||!plainObject(v.options)) return null;
    var names=Object.keys(v.collections);
    if(names.length>64||!names.every(function(n){return preferenceText(n,256)&&n.length>0&&preferenceIds(v.collections[n],512);})) return null;
    if(Object.keys(v.options).length>64) return null;
    return v;
}
function validOption(value,spec) {
    if(spec.type==='enum') return typeof value==='string'&&spec.choices.indexOf(value)>=0;
    if(spec.type==='boolean') return typeof value==='boolean';
    if(spec.type==='integer') return typeof value==='number'&&isFinite(value)&&Math.floor(value)===value&&value>=spec.minimum&&value<=spec.maximum;
    if(spec.type==='string') return preferenceText(value,spec.maxLength===undefined?4096:spec.maxLength);
    if(spec.type==='string-list') return Array.isArray(value)&&value.length<=32&&value.every(function(s){return preferenceText(s,spec.maxLength===undefined?4096:spec.maxLength);});
    return false;
}
function settingsSchema(v) {
    if(!plainObject(v)||Object.keys(v).length>64) return null;
    var out=Object.create(null), keys=Object.keys(v);
    for(var i=0;i<keys.length;i++) {
        var key=keys[i],s=v[key];
        if(!preferenceText(key,128)||!plainObject(s)||!preferenceText(s.label,256)) return null;
        if(s.type==='enum'&&(!Array.isArray(s.choices)||!s.choices.length||s.choices.length>128||!s.choices.every(function(c){return preferenceText(c,256);}))) return null;
        if(s.type==='integer'&&(typeof s.minimum!=='number'||typeof s.maximum!=='number'||!isFinite(s.minimum)||!isFinite(s.maximum)||s.minimum>s.maximum)) return null;
        if(s.maxLength!==undefined&&(typeof s.maxLength!=='number'||s.maxLength<0||s.maxLength>4096)) return null;
        if(!validOption(s.default,s)) return null;
        out[key]=s;
    }
    return out;
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
function preferenceCommand(backend,patch) {
    if(!plainObject(patch)) return null;
    var keys=Object.keys(patch);
    if(keys.indexOf('reset')>=0 ? keys.length!==1||patch.reset!==true : keys.some(function(k){return ['options','favorites','collections'].indexOf(k)<0;})) return null;
    var raw;
    try { raw=JSON.stringify(patch); } catch(e) { return null; }
    if(utf8Bytes(raw)>16384) return null;
    return ['/usr/bin/python3',backend,'preferences','--payload',raw,'--apply'];
}
function viewRows(rows,query,prefs,view,category,provider,installed) {
    if(!prefs) prefs={favorites:[],recent:[],collections:{}};
    var ids=null;
    if(view==='favorites') ids=prefs.favorites;
    else if(view==='recent') ids=prefs.recent;
    else if(typeof view==='string'&&view.indexOf('collection:')===0) ids=prefs.collections[view.slice(11)]||[];
    if(ids && ids.length===0) return [];
    var selected=rows;
    if(ids||category||provider||installed) {
        var members=ids ? Object.create(null) : null;
        if(ids) ids.forEach(function(id){members[id]=true;});
        selected=rows.filter(function(r){
            return (!ids||members[r.id]===true)&&(!category||r.category===category)&&(!provider||r.provider===provider)&&(!installed||(installed==='installed'?r.installed===true:r.installed===false));
        });
    }
    if(view==='recent') selected.sort(function(a,b){return ids.indexOf(a.id)-ids.indexOf(b.id);});
    return filter(selected,query);
}
function imageUrl(path) {
    if(typeof path!=='string'||path[0]!=='/'||/[\x00-\x1f]/.test(path)||path.length>4096) return '';
    return 'file://'+path.split('/').map(function(s){return encodeURIComponent(s);}).join('/');
}
function actionResult(raw,code,status,error) {
    var result={ok:false,message:'Action failed; you can retry'};
    if(typeof raw!=='string'||raw.length>1048576||utf8Bytes(raw)>1048576||error||status!==0) return result;
    try {
        var d=JSON.parse(raw);
        if(d && d.ok===true && code===0) result.ok=true;
        var allowed=actionVerbs();
        if(result.ok && Array.isArray(d.actions) && d.actions.length<=allowed.length && d.actions.every(function(a,i){return allowed.indexOf(a)!==-1 && d.actions.indexOf(a)===i;})) result.actions=d.actions;
        if(d && stringValue(d.message,1024)) result.message=(result.ok?'':'Action failed: ')+d.message;
        else if(result.ok) result.message='Done';
        if(d&&stringValue(d.detail,16384)) result.detail=d.detail;
        if(result.ok) {
            if(preferenceText(d.selectedId,256)&&d.selectedId) result.selectedId=d.selectedId;
            if(imageUrl(d.preview)) result.preview=d.preview;
            var prefs=preferences(d.preferences), schema=settingsSchema(d.settingsSchema);
            if(prefs) result.preferences=prefs;
            if(schema) result.settingsSchema=schema;
        }
    } catch(e) {}
    return result;
}
