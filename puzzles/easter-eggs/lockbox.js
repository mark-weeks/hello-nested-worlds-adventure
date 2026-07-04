#!/usr/bin/env node
// Minimal lockbox: node puzzles/lockbox.js --key=chess
const arg = process.argv.find(a => a.startsWith('--key='));
const key = arg ? arg.split('=')[1].trim().toLowerCase() : '';

const ok = (msg) => { console.log(msg); process.exit(0); };
const nope = () => {
  console.log('🔒 Incorrect key. Hint: 64… then boards and kings.');
  process.exit(1);
};

if (key !== 'chess') nope();

ok([
  '✅ Unlocked!',
  '',
  'Next step: visit the project site page at',
  'puzzles/easter-eggs/optical-illusion.html (served live at /easter-egg/illusion)',
  '',
  'Psst: if it looks empty, try switching your system to **dark mode**.',
].join('\n'));
