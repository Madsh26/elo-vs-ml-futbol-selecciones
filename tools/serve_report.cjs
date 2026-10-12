// Optional local preview, only the generated report directory is served.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../reports/probabilistic');
const types = {'.html':'text/html; charset=utf-8','.png':'image/png',
  '.csv':'text/csv; charset=utf-8','.json':'application/json; charset=utf-8'};
http.createServer((req,res) => {
  let requested;
  try { requested=decodeURIComponent(new URL(req.url,'http://localhost').pathname); }
  catch { res.writeHead(400); return res.end(); }
  const file=path.resolve(root, '.'+(requested==='/'?'/report.html':requested));
  if(!file.startsWith(root+path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404); return res.end('Not found');
  }
  res.writeHead(200, {'Content-Type':types[path.extname(file)]||'application/octet-stream'});
  fs.createReadStream(file).pipe(res);
}).listen(8767,'127.0.0.1',()=>console.log('Report: http://127.0.0.1:8767/report.html'));
