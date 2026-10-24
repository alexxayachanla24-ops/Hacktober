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
      value: '', style: {}, dataset: {}, hidden: false, disabled: false, innerHTML: '',
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

test('mog battle responds to pushing, ends at full power, and continues once requested', () => {
  const h = harness(async () => ({}));
  h.run('mogBattle();');
  assert.equal(h.element('#mog-meter').value, 50);
  for (let i = 0; i < 7; i++) h.element('#mog-push').onclick();
  assert.equal(h.element('#mog-meter').value, 100);
  assert.match(h.element('#mog-result').textContent, /CLEANING SPRAY WINS/);
  assert.equal(h.element('#mog-push').disabled, true);
  assert.equal(h.element('#mog-continue').hidden, false);
  h.element('#mog-push').onclick();
  assert.equal(h.element('#mog-meter').value, 100);
  h.run('jumpscare = () => { S.verdictReached = true; };');
  h.element('#mog-continue').onclick();
  assert.equal(h.run('S.verdictReached'), true);
});

test('mold pulls back, offers a rematch on defeat, and resets the battle', () => {
  const h = harness(async () => ({}));
  h.run('mogBattle();');
  h.scheduled.shift()();
  assert.equal(h.element('#mog-meter').value, 47);
  while (!h.element('#mog-push').disabled) h.scheduled.shift()();
  assert.equal(h.element('#mog-meter').value, 0);
  assert.match(h.element('#mog-result').textContent, /MOLD MOGGED YOU/);
  assert.equal(h.element('#mog-retry').hidden, false);
  h.element('#mog-retry').onclick();
  assert.equal(h.element('#mog-meter').value, 50);
});

test('successful photo submission reaches the battle after the scanning sequence', async () => {
  const h = harness(async () => ({ok: true, json: async () => ({ok:true})}));
  h.run("S.id = 'abc'; age();");
  h.element('#ap').onchange({target:{files:[new Blob(['photo'])]}});
  await h.element('#sub').onclick();
  for (let i = 0; i < 4; i++) h.scheduled.shift()();
  assert.match(h.element('#app').innerHTML, /MOG BATTLE/);
  assert.equal(h.element('#mog-meter').value, 50);
});

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

test('roulette chooses a matching challenge and avoids immediate repeats', () => {
  const h = harness(async () => ({}));
  h.element('#difficulty').value = 'boss';
  h.element('#spin').onclick();
  const first = h.element('#cu').value;
  assert.equal(h.run('S.challenge'), 'boss');
  assert.equal(h.element('#cu').hidden, false);
  assert.match(h.element('#roulette-result').textContent, /15 minutes/);
  assert.equal(h.run('CHALLENGES.boss.chores.includes(S.challengeChore)'), true);
  h.element('#spin').onclick();
  assert.notEqual(h.element('#cu').value, first);
  h.element('#cu').oninput();
  assert.equal(h.run('S.challenge'), null);
  assert.equal(h.element('#roulette-result').hidden, true);
});

test('countdown handles rounding, minutes, and expired challenges', () => {
  const h = harness(async () => ({}));
  assert.match(h.run('challengeText(1600, 1000000)'), /10:00/);
  assert.match(h.run('challengeText(1001, 1000001)'), /0:01/);
  assert.match(h.run('challengeText(1000, 1000000)'), /TIME'S UP/);
  assert.match(h.run('challengeText(900, 1000000)'), /You can still submit/);
});

test('roulette sends its difficulty and uses the saved server deadline', async () => {
  let sent;
  const h = harness(async (path, options) => {
    sent = options.body;
    return {ok:true, json:async()=>({id:'roulette', challenge:'easy', deadline:1300})};
  });
  h.run('prepareChime = () => Promise.resolve(null); barrage = () => {};');
  h.element('#difficulty').value = 'easy';
  h.element('#spin').onclick();
  h.element('#tg').value = 'roommate@example.com';
  await h.element('#go').onclick();
  assert.equal(sent.get('challenge'), 'easy');
  assert.equal(sent.get('chore'), h.element('#cu').value);
  assert.equal(h.run('S.deadline'), 1300);
});
