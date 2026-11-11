const HEADER = ['Date', 'Amount', 'Description', 'Currency', 'Transaction ID', 'Direction'];
const FIELD = {
  operationDate: /^(?:transaction|operation|purchase) date(?: (?:and |& )?time)?$|^дата (?:и время )?(?:операции|транзакции|покупки)(?: и время)?$/u,
  date: /^(?:date|value date|booking date|posting date|payment date|дата|дата и время|дата платежа|дата обработки|дата проводки)$/u,
  description: /^(?:description|details|transaction details|memo|narrative|merchant|reference details|описание(?: операции)?|назначение(?: платежа)?|(?:информация|детали) (?:об )?операции|получатель|контрагент)$/u,
  accountAmount: /^(?:amount in (?:account|billing) currency|account amount|billing amount|сумма (?:платежа|в валюте сч[её]та|в валюте карты))$/u,
  amount: /^(?:amount|transaction amount|operation amount|сумма|сумма операции|сумма транзакции)$/u,
  debit: /^(?:debit|withdrawal|withdrawals|money out|outflow|расход|списание|дебет)$/u,
  credit: /^(?:credit|deposit|deposits|money in|inflow|приход|поступление|пополнение|кредит)$/u,
  currency: /^(?:currency|(?:transaction|original) currency|валюта(?: операции)?)$/u,
  accountCurrency: /^(?:account currency|billing currency|валюта сч[её]та|валюта платежа)$/u,
  bankId: /^(?:transaction id|operation id|bank reference|fitid|идентификатор операции|номер операции)$/u,
  direction: /^(?:direction|transaction type|debit credit|тип операции|вид операции|направление)$/u,
};
const DATE = /^(?:\d{4}-\d\d-\d\d|\d{1,2}[./-]\d{1,2}(?:[./-]|\s*')\s*(?:\d{4}|\d{2}))(?=$|[T ])/;
const SUMMARY = /^(?:opening balance|closing balance|balance (?:brought|carried) forward|totals?|начальный остаток|конечный остаток|входящий остаток|исходящий остаток|итого|всего)(?:$|[ :])/iu;
const BALANCE = /^(?:opening balance|closing balance|balance (?:brought|carried) forward|начальный остаток|конечный остаток|входящий остаток|исходящий остаток)[: ]*$/iu;
const CURRENCY = '[A-Z]{3}|[€₽₸]';
const AMOUNT = new RegExp(`^(?:(${CURRENCY})\\s*)?([+−-]?\\s*\\d(?:[\\d .,’']*\\d)?[−-]?|\\(\\s*\\d(?:[\\d .,’']*\\d)?\\s*\\))(?:\\s*(${CURRENCY}))?$`, 'u');
const MAX_FILE = 5 * 1024 * 1024;
const MAX_PAGES = 120;
const MAX_SPANS = 150_000;
const MAX_ROWS = 10_000;

function failure(code) {
  return Object.assign(new Error(code), {code});
}

function clean(value) {
  return value.replace(/\s+/gu, ' ').trim();
}

function textLines(items) {
  const spans = items.flatMap(item => {
    if (!item.str?.trim() || !item.transform || !Number.isFinite(item.width)) return [];
    const [a, b, , , x, y] = item.transform;
    if (!Number.isFinite(x) || !Number.isFinite(y) || Math.abs(b) > Math.abs(a) * 0.25) return [];
    return [{x, y, right: x + item.width, text: item.str, size: Math.abs(item.height) || 8}];
  }).sort((a, b) => b.y - a.y || a.x - b.x);
  const lines = [];
  for (const span of spans) {
    let line = lines.at(-1);
    if (!line || Math.abs(line.y - span.y) > 2) {
      line = {y: span.y, size: span.size, spans: []};
      lines.push(line);
    }
    line.spans.push(span);
  }
  for (const line of lines) {
    const cells = [];
    for (const span of line.spans.sort((a, b) => a.x - b.x)) {
      const previous = cells.at(-1);
      if (previous && span.x - previous.right <= Math.max(2, span.size * 0.42)) {
        const space = span.x - previous.right > 1 && !/\s$/u.test(previous.text) && !/^\s/u.test(span.text);
        previous.text += (space ? ' ' : '') + span.text;
        previous.right = Math.max(previous.right, span.right);
      } else cells.push({...span});
    }
    line.cells = cells.map(cell => ({...cell, text: clean(cell.text)}));
  }
  return lines;
}

function tableLayout(cells) {
  const labels = cells.map(cell => clean(cell.text.toLowerCase().replace(/[():]/gu, ' ')));
  const matches = Object.fromEntries(Object.entries(FIELD).map(([key, pattern]) =>
    [key, labels.flatMap((label, index) => pattern.test(label) ? [index] : [])]));
  const transactionDate = matches.operationDate.length ? matches.operationDate : matches.date;
  const amount = matches.accountAmount.length ? matches.accountAmount : matches.amount;
  const signed = amount.length === 1;
  const split = matches.debit.length === 1 && matches.credit.length === 1;
  if (transactionDate.length !== 1 || matches.description.length !== 1 || signed === split) return null;
  if (amount.length > 1 || matches.currency.length > 1 || matches.accountCurrency.length > 1 || matches.bankId.length > 1 || matches.direction.length > 1) return null;
  return {
    columns: cells,
    converted: matches.accountAmount.length > 0,
    fields: {
      date: transactionDate[0], description: matches.description[0], amount: signed ? amount[0] : -1,
      debit: split ? matches.debit[0] : -1, credit: split ? matches.credit[0] : -1,
      currency: (matches.accountAmount.length ? matches.accountCurrency[0] : matches.currency[0] ?? matches.accountCurrency[0]) ?? -1, bankId: matches.bankId[0] ?? -1,
      direction: matches.direction[0] ?? -1,
    },
  };
}

function columnValues(layout, cells) {
  const bounds = layout.columns.slice(1).map((column, i) =>
    (Math.min(column.x, layout.columns[i].right) + column.x) / 2);
  const values = layout.columns.map(() => []);
  for (const cell of cells) {
    // Long amounts may extend to the left of a right-aligned heading.
    const position = AMOUNT.test(cell.text) ? cell.right - 0.25 : cell.x + 0.25;
    const index = bounds.findIndex(bound => position < bound);
    values[index < 0 ? bounds.length : index].push(cell.text);
  }
  return Object.fromEntries(Object.entries(layout.fields).map(([key, index]) =>
    [key, index < 0 ? '' : values[index].join(' ')]));
}

function currencyCode(value) {
  const symbol = {'€': 'EUR', '₽': 'RUB', '₸': 'KZT'}[value];
  if (symbol) return symbol;
  return /^[A-Z]{3}$/.test(value) ? value : '';
}

function amountValue(value) {
  const match = AMOUNT.exec(value);
  if (!match) return {value: '', currency: ''};
  const before = currencyCode(match[1] || '');
  const after = currencyCode(match[3] || '');
  if (before && after && before !== after) return {value: '', currency: ''};
  return {value: match[2], currency: before || after};
}

function fromColumns(fields, accountCurrency, converted) {
  let amount = amountValue(fields.amount);
  let direction = fields.direction;
  if (fields.debit || fields.credit) {
    const debit = amountValue(fields.debit);
    const credit = amountValue(fields.credit);
    const zero = value => /^[+−-]?0+(?:[.,]0+)?$/u.test(value);
    const isDebit = debit.value && !zero(debit.value);
    const isCredit = credit.value && !zero(credit.value);
    const validDebit = !fields.debit || !!debit.value || /^[-—–]$/u.test(fields.debit);
    const validCredit = !fields.credit || !!credit.value || /^[-—–]$/u.test(fields.credit);
    const negativeCredit = /^[−(-]|[−-]$/u.test(credit.value);
    if (validDebit && validCredit && !negativeCredit && Boolean(isDebit) !== Boolean(isCredit)) {
      amount = isDebit ? debit : credit;
      const magnitude = amount.value.replace(/^[+−(-]\s*|[−)-]$/gu, '').trim();
      amount.value = (isDebit ? '-' : '+') + magnitude;
      direction = isDebit ? 'debit' : 'credit';
    }
  }
  const declared = currencyCode(fields.currency.toUpperCase());
  // An invalid or conflicting currency needs a manual correction, even if
  // the amount itself is well formed.
  const currency = declared || amount.currency || accountCurrency;
  if ((fields.currency && !declared) || (declared && amount.currency && declared !== amount.currency) ||
      (converted && (!currency || (accountCurrency && currency!==accountCurrency)))) amount.value = '';
  return [fields.date, amount.value, fields.description, currency, fields.bankId, direction];
}

async function readPdf(document) {
  if (document.numPages > MAX_PAGES) throw failure('import_limit');
  if (await document.getPermissions() !== null) throw failure('import_pdf_encrypted');

  const rows = [HEADER];
  let layout = null;
  let accountCurrency = '';
  let spanCount = 0;
  for (let number = 1; number <= document.numPages; number++) {
    const page = await document.getPage(number);
    const {items} = await page.getTextContent();
    spanCount += items.length;
    if (spanCount > MAX_SPANS) throw failure('import_limit');
    const lines = textLines(items);
    if (!lines.length) throw failure('import_pdf_scanned');
    let preceding = null;
    for (const line of lines) {
      const all = line.cells.map(cell => cell.text).join(' ');
      const currency = /^(?:account currency|валюта сч[её]та)\s*:?\s*([A-Z]{3}|[€₽₸])$/iu.exec(all);
      if (currency) {
        const declared = currencyCode(currency[1].toUpperCase());
        if (accountCurrency && declared !== accountCurrency) throw failure('import_pdf_layout');
        accountCurrency = declared;
        preceding = null;
        continue;
      }
      const heading = tableLayout(line.cells);
      if (heading) {
        layout = heading;
        preceding = null;
        continue;
      }
      if (!layout) continue;
      const fields = columnValues(layout, line.cells);
      if (DATE.test(fields.date)) {
        if (!fields.bankId && !fields.direction && BALANCE.test(fields.description)) {
          preceding = null;
          continue;
        }
        if (!fields.amount && !fields.debit && !fields.credit && !fields.description) {
          preceding = null;
          continue;
        }
        const row = fromColumns(fields, accountCurrency, layout.converted);
        rows.push(row);
        if (rows.length > MAX_ROWS + 1) throw failure('import_limit');
        preceding = {row, y: line.y};
      } else if (preceding && line.cells.length === 1 && fields.description &&
          !SUMMARY.test(fields.description) && preceding.y - line.y <= Math.max(18, line.size * 1.6)) {
        preceding.row[2] = clean(`${preceding.row[2]} ${fields.description}`).slice(0, 4096);
        preceding.y = line.y;
      } else {
        preceding = null;
      }
    }
    page.cleanup();
  }
  if (rows.length < 2) throw failure('import_pdf_layout');
  return {rows, detection: {header: 0, date: 0, amount: 1, description: 2, currency: 3, bankId: 4, directionColumn: 5}, needsReview: true};
}

// Mozilla PDF.js 6.5.438 legacy distribution (Apache-2.0), loaded from the app origin.
// Extraction reads text and its positions only. Rendering, actions and forms
// are not used, and the statement bytes are passed to a local worker.
export async function extractStatementPdf(bytes) {
  const source = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  if (source.byteLength > MAX_FILE) throw failure('import_limit');
  if (!new TextDecoder().decode(source.subarray(0, 1024)).includes('%PDF-')) throw failure('import_format');
  // PDF.js transfers ownership of the buffer to its worker. Keep the
  // original available to callers for hashing or another preview.
  const data = source.slice();
  let task;
  let timer;
  try {
    const {getDocument, GlobalWorkerOptions} = await import('./pdf-lib.mjs');
    GlobalWorkerOptions.workerSrc = new URL('./pdf-worker.mjs', import.meta.url).href;
    task = getDocument({
      data, isEvalSupported: false, useWasm: false, useWorkerFetch: false, enableXfa: false,
      disableFontFace: true, disableAutoFetch: true, maxImageSize: 1_000_000, stopAtErrors: true, verbosity: 0,
    });
    const extract = task.promise.then(readPdf);
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => reject(failure('import_limit')), 15_000);
    });
    return await Promise.race([extract, timeout]);
  } catch (error) {
    if (error?.code && typeof error.code === 'string') throw error;
    if (error?.name === 'PasswordException') throw failure('import_pdf_encrypted');
    if (error?.name === 'InvalidPDFException') throw failure('import_format');
    throw failure('import_pdf_layout');
  } finally {
    clearTimeout(timer);
    if (task) await task.destroy().catch(() => {});
  }
}
