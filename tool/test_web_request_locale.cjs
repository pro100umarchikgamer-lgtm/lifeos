'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const acorn = require('internal/deps/acorn/acorn/dist/acorn');

function helper(filename, name) {
  const source = fs.readFileSync(path.join(__dirname, '..', filename), 'utf8');
  const node = acorn.parse(source, {ecmaVersion: 'latest'}).body.find(
    item => item.type === 'FunctionDeclaration' && item.id.name === name);
  assert.ok(node, `${name} request helper is missing`);
  return source.slice(node.start, node.end);
}

async function check(filename, name, globals, route, action='recovery') {
  const sent = [];
  const context = vm.createContext({...globals, fetch: async (url, options) => {
    sent.push({url, options});
    return {ok: true, json: async () => ({accepted: true})};
  }});
  vm.runInContext(helper(filename, name), context);
  const result = await vm.runInContext(`${name}('${action}', {email:'synthetic@example.test'})`, context);
  assert.equal(result.accepted, true);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].url, route);
  assert.equal(sent[0].options.method, 'POST');
  assert.equal(sent[0].options.credentials, 'same-origin');
  assert.equal(sent[0].options.headers['Accept-Language'], globals.authLanguage || globals.state.lang);
  assert.equal(sent[0].options.headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(sent[0].options.body), {email:'synthetic@example.test'});
  return sent[0];
}

(async () => {
  const publicGlobals = {viewEpoch:0, authLanguage:'fr', prefix:'/account/api/', csrf:'synthetic-csrf'};
  await check('backend/webassets/web.js', 'api', publicGlobals, '/account/api/recovery');
  await check('backend/webassets/app/app.js', 'call', {
    privateEpoch:0, state:{lang:'pt', csrf:'synthetic-csrf', session:null},
  }, '/account/api/recovery');
  const early = await check('backend/webassets/web.js', 'earlyApi', publicGlobals, '/early-access/api/recover', 'recover');
  assert.equal(early.options.headers['X-CSRF-Token'], undefined,
    'early routes retain their existing Origin-only request policy');
  console.log('WEB_REQUEST_LOCALE_PASS: public/app/early synthetic requests');
})().catch(error => { console.error(error); process.exitCode = 1; });
