'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const filename=path.join(__dirname,'../backend/webassets/app/password-policy.js');
assert.ok(fs.existsSync(filename),'New-password guidance and validator are missing');
require(path.join(__dirname,'../backend/webassets/app/i18n.js'));
require(filename);
const policy=globalThis.UladimPassword;
for(const value of ['river731','Москва42','Rivera٧٣','𐐀bcdefg7','Очень-длинная-фраза','synthetic-web-platform-password','sunlit meadow riverbank']){
 assert.equal(policy.validate(value),null,JSON.stringify(value));
}
for(const value of ['River!7','𐐀bcdef7','x'.repeat(257)])assert.equal(policy.validate(value),'password_length');
for(const value of ['12345678','11111111','22222222','onlyletters','riverwind       ','Password1!','welcome2026!','test12345','abcd1234','4321dcba','Qwer1234','zxcv1234','абвг1234','a1b2c3d4','ab12ab12','leafleaf9','abcabc123','abcdefghijklmnop']){
 assert.equal(policy.validate(value),'password_weak',JSON.stringify(value));
}
console.log('WEB_PASSWORD_POLICY_VECTORS_PASS');
