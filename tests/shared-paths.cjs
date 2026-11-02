const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),manifest=path.join(root,'manifest.json');
const entry=fs.existsSync(manifest)?JSON.parse(fs.readFileSync(manifest,'utf8')).entryPoints.overlay:null;
const runtime=entry?path.dirname(path.resolve(root,entry)):path.join(root,'templates');
module.exports={runtime,panel:entry?path.resolve(root,entry):path.join(runtime,'Panel.qml')};
