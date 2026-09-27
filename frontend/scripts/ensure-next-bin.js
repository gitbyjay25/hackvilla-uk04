#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

function patchNextBin() {
  const binPath = path.join(__dirname, '..', 'node_modules', '.bin', 'next');
  const targetPath = path.join(__dirname, '..', 'node_modules', 'next', 'dist', 'bin', 'next');

  if (!fs.existsSync(binPath) || !fs.existsSync(targetPath)) {
    console.log('[ensure-next-bin] skipped: next binary path not found');
    return;
  }

  let isSymlink = false;
  try {
    isSymlink = fs.lstatSync(binPath).isSymbolicLink();
  } catch (error) {
    console.warn('[ensure-next-bin] unable to inspect next binary:', error.message);
    return;
  }

  if (!isSymlink) {
    console.log('[ensure-next-bin] ok: next binary is not a symlink');
    return;
  }

  const wrapper = [
    '#!/usr/bin/env node',
    "require(require('path').join(__dirname, '..', 'next', 'dist', 'bin', 'next'));",
    '',
  ].join('\n');

  try {
    fs.unlinkSync(binPath);
    fs.writeFileSync(binPath, wrapper, { encoding: 'utf8' });
    fs.chmodSync(binPath, 0o755);
    console.log('[ensure-next-bin] patched: replaced symlinked .bin/next with stable wrapper');
  } catch (error) {
    console.warn('[ensure-next-bin] patch failed:', error.message);
  }
}

patchNextBin();
