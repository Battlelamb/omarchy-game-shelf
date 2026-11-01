const path=require('node:path');const m=require('../manifest.json');module.exports=name=>path.join(__dirname,'../runtime',m.version,name);
