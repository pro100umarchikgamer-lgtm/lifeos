'use strict';
const assert = require('node:assert/strict');
require('../backend/webassets/app/money.js');
require('../backend/webassets/app/statement-formats.js');
const {read, preview} = globalThis.ULADIMStatement;
function parse(text, settings = {}) {
  const source = read(new TextEncoder().encode(text), {});
  return preview(source, {...source.detection, defaultCurrency: 'RUB', ...settings});
}
const tbank = 'Дата операции;Дата платежа;Сумма операции;Валюта операции;Сумма платежа;Описание\n' +
  Array.from({length:145}, (_, i) => `11.11.2026 09:41:00;12.11.2026;-1 234,56;RUB;-42,00;Покупка ${i}`).join('\n');
const rows = parse(tbank);
assert.equal(rows.length,145);
assert.deepEqual(rows[0].value,{date:'2026-11-11',kind:'expense',amount:123456,currency:'RUB',label:'Покупка 0',bankID:''});
assert.equal(parse('Date\tAmount\tDescription\n2026-11-10T23:58:00-05:00\t+12.05\tPay')[0].value.date,'2026-11-10');
assert.equal(parse('{"transactions":[{"bookingDate":"2026-11-11","amount":-1.23,"currency":"USD","transactionId":"bank-42","description":"Coffee"}]}')[0].value.bankID,'bank-42');
assert.equal(parse('OFXHEADER:100\nDATA:OFXSGML\n\n<OFX><CURDEF>USD<BANKTRANLIST><STMTTRN><DTPOSTED>20261111090000[-5:EST]<TRNAMT>-1.23<FITID>42<NAME>Store</STMTTRN></BANKTRANLIST></OFX>')[0].value.amount,123);
assert.equal(parse('!Type:Bank\nD11/21\'26\nT-12.05\nPStore\nL[Other account]\n^\n')[0].error,'import_transfer_review');
assert.equal(parse('!Type:Bank\nD11/21\'26\nT-12.05\nPStore\n^\n')[0].value.date,'2026-11-21');
assert.equal(parse('Date;Amount\n04/05/2026;-12.05')[0].error,'import_date_ambiguous');
assert.equal(parse('Date;Amount\n04/05/2026;-12.05\n22/05/2026;-13.00')[0].value.date,'2026-05-04');
assert.equal(parse('Date;Amount;Currency\n2026-11-10;1,234;KWD')[0].error,'import_number_ambiguous');
assert.equal(parse('Date;Amount;Currency\n2026-11-10;1,234;KWD\n2026-11-10;2,34;KWD')[0].value.amount,1234);
assert.equal(parse('Date;Amount\n2026-02-30;10')[0].error,'import_date_invalid');
assert.equal(parse('Date;Amount;Currency\n2026-11-10;0.001;KWD')[0].value.amount,1);
assert.throws(()=>parse('{"balance":234}'),{code:'import_json_structure'});
assert.throws(()=>parse('plain unstructured text'),{code:'import_format'});
const splitAmounts = parse('Date;Debit;Credit;Currency\n2026-11-11;0,00;13,21;RUB\n2026-11-12;16,54;0,00;RUB\n2026-11-13;12,12;4,21;RUB');
assert.deepEqual(splitAmounts.map(row => row.error || [row.value.kind,row.value.amount]),[
  ['income',1321],['expense',1654],'import_amount_invalid'
]);

// An empty leading TSV column is part of the source layout.
assert.equal(parse('\tDate\tAmount\n\t2026-11-10\t-12.05')[0].value.amount,1205);
const combined = parse('Date;Amount;Debit;Credit\n2026-11-10;12.05;12.05;0\n2026-11-10;13.00;12.05;0\n2026-11-10;-12.05;0;12.05');
assert.deepEqual(combined.map(row=>row.error||row.value.kind),['expense','import_amount_invalid','import_amount_invalid']);
assert.equal(parse('Date;Debit\ninvalid;12.05')[0].original.kind,'expense');
assert.equal(parse('Date;Сумма платежа;Валюта операции\n2026-11-10;900;USD')[0].error,'import_currency_invalid');
assert.equal(parse('Date;Сумма платежа;Валюта операции;Валюта платежа\n2026-11-10;900;USD;RUB')[0].value.currency,'RUB');

const formulaCurrency = ULADIMStatement.table([['Date','Amount','Currency'], ['2026-11-10','900','\ufffd']], 'XLSX');
assert.equal(preview(formulaCurrency,{...formulaCurrency.detection,defaultCurrency:'RUB'})[0].error,'import_unreadable_cell');
