const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const html = readFileSync(join(__dirname, '../static/index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function harness(fetch, search = '') {
  const elements = new Map();
  const revoked = [];
  const scheduled = [];
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, {
      value: '', style: {}, hidden: false, disabled: false, innerHTML: '',
      textContent: '', files: [],
      play: () => Promise.resolve(), pause() {}, remove() {},
      removeAttribute(name) { delete this[name]; },
      replaceChildren() { this.innerHTML = ''; },
    });
    return elements.get(selector);
  }
  class PreviewURL extends URL {
    static createObjectURL() { return `blob:test-${Math.random()}`; }
    static revokeObjectURL(url) { revoked.push(url); }
  }
  const context = vm.createContext({
    URL: PreviewURL, URLSearchParams, FormData, fetch,
    location: { search, href: 'http://localhost/' + search, origin: 'http://localhost' },
    history: { replaceState() {} },
    document: { querySelector: element, querySelectorAll: () => [], addEventListener() {},
      body: { classList: { remove() {}, add() {} } } },
    window: { addEventListener() {} }, navigator: {},
    setTimeout(fn) { scheduled.push(fn); return scheduled.length; },
    clearTimeout() {}, cancelAnimationFrame() {},
  });
  vm.runInContext(script, context);
  return { element, context, revoked, scheduled, run: code => vm.runInContext(code, context) };
}

test('new complaints clear previous files, IDs, and preview URLs', () => {
  const h = harness(async () => { throw new Error('unexpected request'); });
  h.run(`Object.assign(S, {id:'old', evFile:{}, plFile:{}, walkerFile:{}, ageFile:{},
    walker:'/uploads/old.png', evidence:'blob:photo', payload:'blob:audio', agePreview:'blob:face'}); setup();`);
  assert.equal(h.run('S.id'), undefined);
  for (const key of ['evFile', 'plFile', 'walkerFile', 'ageFile', 'walker']) {
    assert.equal(h.run(`S.${key}`), undefined);
  }
  assert.deepEqual(h.revoked.sort(), ['blob:audio', 'blob:face', 'blob:photo']);
});

test('clearing a selected photo also clears its stored file', () => {
  const h = harness(async () => ({}));
  h.run(`S.evFile = {}; S.evidence = 'blob:old';`);
  h.element('#ev').onchange({ target: { files: [] } });
  assert.equal(h.run('S.evFile'), null);
  assert.equal(h.run('S.evidence'), null);
  assert.equal(h.element('#evp').hidden, true);
  assert.deepEqual(h.revoked, ['blob:old']);
});

test('failed resolution shows server error and allows retry without completion', async () => {
  const h = harness(async () => ({ ok: false, status: 413,
    json: async () => ({ error: 'File is too large' }) }));
  h.run(`S.id = 'abc'; age();`);
  h.element('#ap').onchange({ target: { files: [new Blob(['photo'])] } });
  await h.element('#sub').onclick();
  assert.match(h.element('#m').textContent, /File is too large/);
  assert.equal(h.element('#sub').disabled, false);
  assert.equal(h.scheduled.length, 0);
});

test('resolution waits for persistence before running completion animation', async () => {
  let respond;
  const response = new Promise(resolve => { respond = resolve; });
  const h = harness(() => response);
  h.run(`S.id = 'abc'; age();`);
  h.element('#ap').onchange({ target: { files: [new Blob(['photo'])] } });
  const submission = h.element('#sub').onclick();
  assert.equal(h.element('#sub').disabled, true);
  assert.equal(h.scheduled.length, 0);
  respond({ ok: true, json: async () => ({ ok: true }) });
  await submission;
  assert.equal(h.scheduled.length, 1);
  assert.match(h.element('#m').textContent, /Scanning/);
});

test('already resolved portal opens completion screen', async () => {
  const h = harness(async () => ({ ok: true, json: async () => ({
    id: 'abc', chore: 'Dishes', target: 'Roommate', status: 'resolved', ptype: '',
  }) }), '?c=abc');
  await new Promise(resolve => setImmediate(resolve));
  assert.match(h.element('#app').innerHTML, /CHORE SUBMITTED/);
});

test('missing portal displays an actionable error', async () => {
  const h = harness(async () => ({ ok: false, status: 404,
    json: async () => ({ error: 'Chore not found' }) }), '?c=missing');
  await new Promise(resolve => setImmediate(resolve));
  assert.match(h.element('#app').innerHTML, /Chore not found/);
  assert.equal(typeof h.element('#retry').onclick, 'function');
  assert.equal(typeof h.element('#new').onclick, 'function');
});
