const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');
const script = readFileSync(join(__dirname,'../static/leaderboard.js'),'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
function harness(fetch) {
  const nodes = new Map();
  const make = () => ({textContent:'', hidden:false, children:[], listeners:{},
    append(...children) {this.children.push(...children);},
    replaceChildren(...children) {this.children=children;},
    addEventListener(type,listener) {this.listeners[type]=listener;}});
  const get = key => {if(!nodes.has(key))nodes.set(key,make());return nodes.get(key);};
  vm.runInNewContext(script, {document:{querySelector:get,createElement:make,
    createDocumentFragment:make,addEventListener(){}},fetch,AbortSignal,setInterval(){}});
  return get;
}
const empty = {roommates:[],totals:{roommates:0,completed:0,pending:0},updated_at:1000};
test('empty households show a call to action with no invented MVP', async () => {
  const get=harness(async()=>({ok:true,json:async()=>empty}));
  await flush();
  assert.equal(get('#empty').hidden,false);
  assert.equal(get('#scores').hidden,true);
  assert.equal(get('#champion').hidden,true);
  assert.equal(get('#total-roommates').textContent,0);
});
test('standings render earned scores, overdue counts, and missing duration', async () => {
  const member={rank:1,target:'Alice',points:25,completed:2,pending:1,on_time:1,overdue:1,fastest_seconds:0,average_seconds:null};
  const get=harness(async()=>({ok:true,json:async()=>({...empty,roommates:[member],totals:{roommates:1,completed:2,pending:1}})}));
  await flush();
  assert.equal(get('#scores').hidden,false);
  assert.equal(get('#champion').children[0].textContent,'👑 Alice');
  const cells=get('#rows').children[0].children[0].children;
  assert.equal(cells[2].textContent,25);
  assert.equal(cells[4].children[0].textContent,'1 overdue');
  assert.equal(cells[6].textContent,'0s');
  assert.equal(cells[7].textContent,'—');
});
test('refresh failures retain previous rows and let the user retry', async () => {
  let fail=false;
  const get=harness(async()=>{if(fail)throw new Error('offline');return {ok:true,json:async()=>empty};});
  await flush();
  const previous=get('#rows').children;
  fail=true;
  await get('#refresh').listeners.click();
  assert.equal(get('#rows').children,previous);
  assert.match(get('#status').textContent,/Could not refresh/);
  assert.equal(get('#refresh').disabled,false);
});
