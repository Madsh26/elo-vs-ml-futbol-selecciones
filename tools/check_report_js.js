// Check JavaScript syntax without interacting with the browser.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const file = path.join(__dirname, '..', 'reports', 'final_evaluation', 'football_report.html');
const source = fs.readFileSync(file, 'utf8');
const scripts = [...source.matchAll(/<script>([\s\S]*?)<\/script>/g)];
if (!scripts.length) throw new Error('No report script found');
for (const script of scripts) new vm.Script(script[1], {filename: 'football_report.html'});
process.stdout.write('Report JavaScript syntax valid.\n');
