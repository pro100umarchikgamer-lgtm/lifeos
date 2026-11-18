import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {JSDOM} from 'jsdom';

const asset = name => new URL(`../backend/webassets/${name}`, import.meta.url);

test('published regions reorder only editorial nodes and render markup as text', () => {
  const dom = new JSDOM('<main><form><input value="preserved"></form><section></section></main>', {runScripts: 'outside-only'});
  const {window} = dom;
  window.eval(readFileSync(asset('public-pages.js'), 'utf8'));
  const target = window.document.querySelector('section');
  window.UladimPublicPages.renderRegion(target, [
    {id: 'two', kind: 'source', fields: {title: 'Second'}},
    {id: 'new', kind: 'text', title: 'New', body: '<img src=x onerror=alert(1)>'},
    {id: 'bad', kind: 'link', label: 'Bad', href: 'javascript:alert(1)'},
  ], {
    source(block) {
      const heading = window.document.createElement('h2');
      heading.textContent = block.fields.title;
      return heading;
    },
  });
  assert.deepEqual([...target.querySelectorAll('h2')].map(node => node.textContent), ['Second', 'New']);
  assert.equal(target.querySelector('img, a'), null);
  assert.match(target.textContent, /<img src=x onerror=alert\(1\)>/);
  assert.equal(window.document.querySelector('input').value, 'preserved');
  window.close();
});

test('source editorial catalog covers the twelve public page routes', () => {
  const catalog = JSON.parse(readFileSync(asset('public-pages-source.json'), 'utf8'));
  assert.deepEqual(Object.keys(catalog.pages).sort(), ['/', '/account', '/delete-account', '/docs', '/download', '/early-access', '/faq', '/plans', '/privacy', '/status', '/support', '/terms'].sort());
  for (const {fields, regions} of Object.values(catalog.pages)) {
    assert.ok(Object.keys(fields).length, 'each page has editable existing fields');
    assert.ok(Object.keys(regions).length, 'each page supplies an ordered block region');
  }
});

test('the frozen revision-zero response supplies renderable content', async () => {
  const dom = new JSDOM('', {runScripts: 'outside-only', url: 'https://uladim.test/status'});
  const {window} = dom;
  window.eval(readFileSync(asset('public-pages.js'), 'utf8'));
  const content = {fields: {title: 'Shipped status'}, regions: {guidance: []}};
  window.fetch = async () => ({ok: true, json: async () => ({page: '/status', locale: 'en', revision: 0, content})});
  assert.equal(await window.UladimPublicPages.load('/status', 'en'), content);
  window.close();
});

test('a preview shows the exact link target as inert text', () => {
  const dom = new JSDOM('', {runScripts: 'outside-only', url: 'https://control.uladim.test/'});
  const {window} = dom;
  window.eval(readFileSync(asset('public-pages.js'), 'utf8'));
  const target = window.UladimPublicPages.renderBlock(window.document, {
    id: 'link', kind: 'link', label: 'Guide', href: 'https://docs.example.test/guide',
  }, {preview: true});
  assert.equal(target.querySelector('code').textContent, 'https://docs.example.test/guide');
  assert.equal(target.querySelector('a'), null);
  window.close();
});

test('publishing copy covers the same sixteen locales and every detail key', () => {
  const {schemaVersion, locales} = JSON.parse(readFileSync(asset('control-publishing-copy.json'), 'utf8'));
  const application = JSON.parse(readFileSync(asset('app/locales.json'), 'utf8'));
  assert.equal(schemaVersion, 1);
  assert.deepEqual(Object.keys(locales).sort(), Object.keys(application).sort());
  let keyCount = 0;
  for (const group of ['labels', 'fields', 'errors', 'roles']) {
    const keys = Object.keys(locales.en[group]).sort();
    keyCount += keys.length;
    for (const [locale, translation] of Object.entries(locales)) {
      assert.deepEqual(Object.keys(translation[group]).sort(), keys, `${locale}: ${group} coverage`);
      assert.ok(Object.values(translation[group]).every(value => typeof value === 'string' && value.trim()), `${locale}: ${group} labels`);
    }
  }
  assert.equal(keyCount, 168);
});
