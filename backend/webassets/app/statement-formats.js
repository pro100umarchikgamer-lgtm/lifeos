'use strict';
/* Browser-only statement decoding. Financial amounts are converted by ULADIMMoney. */
(() => {
  const LIMIT = 10000;
  const fail = code => { throw {code}; };
  const aliases = {
    date: [['operation date','дата операции','booking date','bookingdate','date','дата','дата и время'], ['дата платежа','value date','posted date','dtposted']],
    amount: [['сумма операции','transaction amount','amount','сумма','trnamt'], ['сумма платежа','payment amount','billing amount','amount in account currency']],
    currency: [['валюта операции','transaction currency','currency','валюта','код валюты','curdef'], ['валюта платежа','payment currency','billing currency','account currency']],
    description: [['description','описание','назначение','назначение платежа','memo','payee','name','remittance information']],
    bankID: [['transaction id','transactionid','operation id','operationid','идентификатор операции','fitid','reference','id']],
    directionColumn: [['direction','transaction type','тип операции','тип','credit debit indicator','creditdebitindicator','trntype']],
    credit: [['credit','income','приход','зачисление']],
    debit: [['debit','expense','расход','списание']]
  };
  const fieldNames = Object.keys(aliases);
  const headerText = value => value.normalize('NFKC').trim().toLowerCase().replace(/[_-]+/g,' ').replace(/\s+/g,' ');
  const textValue = value => ['string','number'].includes(typeof value) ? String(value) : '';

  function decode(bytes, encoding = 'auto') {
    if (!bytes.length) fail('import_format');
    if (bytes.length > 5 * 1024 * 1024) fail('import_limit');
    const decodeAs = name => new TextDecoder(name,{fatal:true}).decode(bytes);
    let text;
    try {
      if (encoding !== 'auto') text = decodeAs(({utf8:'utf-8',utf16:'utf-16le',cp1251:'windows-1251'})[encoding] || encoding);
      else if (bytes[0] === 255 && bytes[1] === 254) text = decodeAs('utf-16le');
      else if (bytes[0] === 254 && bytes[1] === 255) text = decodeAs('utf-16be');
      else {
        try { text = decodeAs('utf-8'); }
        catch {
          const declared = new TextDecoder().decode(bytes.subarray(0, 1024)).match(/(?:CHARSET\s*:\s*|encoding\s*=\s*["'])(1251|windows-1251|1252|windows-1252|ISO-8859-1)\b/i)?.[1].toLowerCase();
          if (declared) text = decodeAs(({1251:'windows-1251',1252:'windows-1252'})[declared] || declared);
          else {
            const candidate = decodeAs('windows-1251');
            if (!/дата|сумма|валюта|операци/i.test(candidate.slice(0,12000))) fail('import_encoding_required');
            text = candidate;
          }
        }
      }
    } catch (error) { fail(error.code || 'import_encoding_required'); }
    if (/[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]/.test(text)) fail('import_format');
    return text;
  }

  function csv(text, separator) {
    const rows = [];
    let row = [], field = '', quoted = false, closed = false;
    const cell = () => { if (row.length === 100) fail('import_limit'); row.push(field); field = ''; closed = false; };
    const record = () => {
      cell();
      if (row.some(value => value.trim())) rows.push(row);
      if (rows.length > LIMIT + 20) fail('import_limit');
      row = [];
    };
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"' && text[i+1] === '"') { field += '"'; i++; }
        else if (ch === '"') { quoted = false; closed = true; }
        else field += ch;
      } else if (ch === separator) cell();
      else if (ch === '\r' || ch === '\n') { if (ch === '\r' && text[i+1] === '\n') i++; record(); }
      else if (ch === '"' && !field.trim() && !closed) { quoted = true; field = ''; }
      else if (!closed) field += ch;
      else if (!/\s/.test(ch)) fail('import_format');
    }
    if (quoted) fail('import_format');
    if (row.length || field || closed) record();
    return rows;
  }

  function detect(rows) {
    let best = null;
    for (let header = 0; header < Math.min(rows.length - 1, 20); header++) {
      const cells = rows[header].map(headerText);
      const mapping = {header};
      for (const [field, priorities] of Object.entries(aliases)) {
        mapping[field] = -1;
        for (const names of priorities) {
          const matches = cells.flatMap((cell,i) => names.includes(cell) ? [i] : []);
          if (matches.length) {
            mapping[field] = matches.length === 1 ? matches[0] : -1;
            if (field==='currency'&&matches.length>1) mapping.ambiguousCurrency=true;
            break;
          }
        }
      }
      const amountLabel = cells[mapping.amount];
      if (aliases.amount[1].includes(amountLabel)) {
        const billingCurrencies = cells.flatMap((cell,i)=>aliases.currency[1].includes(cell)?[i]:[]);
        mapping.currency = billingCurrencies.length===1?billingCurrencies[0]:-1;
      }
      const sample = rows.slice(header + 1, header + 21);
      const recognized = mapping.date >= 0 && (mapping.amount >= 0 || mapping.credit >= 0 || mapping.debit >= 0);
      const score = (recognized ? 100 : 0) + fieldNames.filter(k => mapping[k] >= 0).length * 5 +
        sample.filter(row => row.length === cells.length).length / 100;
      if (!best || score > best.score) best = {mapping,score};
    }
    return best;
  }

  function table(rows, format, formatSettings = {}) {
    if (rows.length < 2 || !rows.some(row => row.length > 1)) fail('import_format');
    if (rows.length > LIMIT + 20 || rows.some(row => row.length > 100)) fail('import_limit');
    const detection = detect(rows)?.mapping;
    return {rows,format,detection:{...detection,dateFormat:'auto',decimal:'auto',direction:'signed',...formatSettings}};
  }

  function fromJson(text) {
    let payload;
    // Preserve number tokens exactly, including decimal digits, before JSON.parse can round them.
    try { payload = JSON.parse(text.replace(/"(?:\\[\s\S]|[^"\\])*"|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/g,
      token => token.startsWith('"') ? token : JSON.stringify(token))); }
    catch { fail('import_json_structure'); }
    const entries = Array.isArray(payload) ? payload : [
      payload?.transactions, payload?.operations, payload?.entries, payload?.data?.transactions,
      payload?.transactions?.booked, payload?.data?.transactions?.booked
    ].find(Array.isArray);
    if (!entries?.length || !entries.every(row => row && typeof row === 'object' && !Array.isArray(row))) fail('import_json_structure');
    if (entries.length > LIMIT) fail('import_limit');
    const currencyConflicts = new Set();
    const expanded = entries.map((entry,index) => {
      const fields = Object.assign(Object.create(null),entry);
      const declared = [];
      for(const key of ['currency','transactionCurrency','currencyCode']){
        if(key in fields){declared.push(fields[key]);delete fields[key];}
      }
      for (const key of ['transactionAmount','amount']) {
        const money = fields[key];
        if (money && typeof money === 'object' && !Array.isArray(money) && 'amount' in money) {
          fields[key] = money.amount;
          if ('currency' in money) declared.push(money.currency);
        }
      }
      const currencies=declared.filter(value=>value!=null&&value!=='').map(value=>currencyCode(textValue(value)));
      if(currencies.some(code=>!/^[A-Z]{3}$/.test(code))||new Set(currencies).size>1)currencyConflicts.add(index+2);
      else if(currencies.length)fields.currency=currencies[0];
      return fields;
    });
    const keys = [...new Set(expanded.flatMap(Object.keys))];
    if (keys.length < 2) fail('import_json_structure');
    const labels = keys.map(key => key.replace(/([a-z])([A-Z])/g,'$1 $2'));
    return {...table([labels,...expanded.map(row => keys.map(key => textValue(row[key])))],'JSON'),currencyConflicts:[...currencyConflicts]};
  }

  const canonical = ['Date','Amount','Description','Currency','Transaction ID','Direction'];
  function fromOfx(text) {
    if (/<!DOCTYPE|<!ENTITY/i.test(text)) fail('import_unsafe');
    const get = (source,tag) => source.match(new RegExp('<(?:[\\w.-]+:)?'+tag+'\\b[^>]*>\\s*([^<]*)','i'))?.[1].trim() || '';
    const rows = [canonical];
    const lists = text.matchAll(/<(?:[\w.-]+:)?(?:STMTRS|CCSTMTRS)\b[^>]*>([\s\S]*?)<\/(?:[\w.-]+:)?(?:STMTRS|CCSTMTRS)>/gi);
    let statements = Array.from(lists, match => match[1]);
    if (!statements.length) statements = [text];
    for (const statement of statements) {
      const currency = get(statement,'CURDEF');
      for (const match of statement.matchAll(/<(?:[\w.-]+:)?STMTTRN\b[^>]*>([\s\S]*?)(?=<\/?(?:[\w.-]+:)?(?:STMTTRN|BANKTRANLIST)\b)/gi)) {
        const row = match[1];
        const desc = [get(row,'NAME'),get(row,'MEMO')].filter(Boolean);
        rows.push([get(row,'DTPOSTED'),get(row,'TRNAMT'),[...new Set(desc)].join(' — '),currency,get(row,'FITID'),get(row,'TRNTYPE')]);
        if (rows.length > LIMIT + 1) fail('import_limit');
      }
    }
    return table(rows,'OFX',{decimal:'.'});
  }

  function fromQif(text) {
    const rows = [canonical];
    let section = '', entry = Object.create(null);
    for (const raw of text.split(/\r\n|\n|\r/)) {
      const line = raw.trim();
      if (line.startsWith('!')) { section = line.toLowerCase(); entry = Object.create(null); continue; }
      if (!/^!type:(bank|cash|ccard|oth a|oth l)$/.test(section)) continue;
      if (line === '^') {
        if (entry.D || entry.T || entry.U) rows.push([entry.D || '',entry.T || entry.U || '',entry.P || entry.M || '', '', '', /^\[.+\]$/.test(entry.L || '') ? 'transfer' : '']);
        if (rows.length > LIMIT + 1) fail('import_limit');
        entry = Object.create(null);
      } else if (line) entry[line[0]] ??= line.slice(1).trim();
    }
    return table(rows,'QIF');
  }

  function read(bytes,{encoding = 'auto',delimiter = 'auto'} = {}) {
    const text = decode(bytes,encoding);
    const structured = text.trimStart();
    if (/^[{[]/.test(structured)) return fromJson(structured);
    if (/^(?:OFXHEADER\s*:|<\?OFX\b|<OFX\b|<\?xml[\s\S]{0,512}<OFX\b)/i.test(structured)) return fromOfx(structured);
    if (/^!(Type|Account|Option|Clear):/i.test(structured)) return fromQif(structured);
    if (/<!DOCTYPE|<!ENTITY/i.test(text)) fail('import_unsafe');
    let best = null, tied = false, limit = false;
    for (const separator of delimiter === 'auto' ? [';','\t',',','|'] : [delimiter]) {
      let rows;
      try { rows = csv(text,separator); }
      catch (error) { if (error.code === 'import_limit') limit = true; continue; }
      if (rows.length < 2 || !rows.some(row => row.length > 1)) continue;
      const score = detect(rows)?.score || 0;
      if (!best || score > best.score) { best = {rows,score,separator}; tied = false; }
      else if (score === best.score) tied = true;
    }
    if (!best) fail(limit ? 'import_limit' : 'import_format');
    if (tied) fail('import_delimiter_ambiguous');
    return table(best.rows,best.separator === '\t' ? 'TSV' : 'CSV');
  }

  function dateCandidates(value, format) {
    const iso = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:[.,]\d+)?)?(?:\s*(?:Z|[+-](?:[01]\d|2[0-3]):?[0-5]\d))?)?$/i.exec(value);
    const ofx = /^(\d{4})(\d{2})(\d{2})(?:(?:[01]\d|2[0-3])[0-5]\d[0-5]\d(?:\.\d+)?(?:\[[^\]\r\n]{1,32}\])?)?$/.exec(value);
    const local = /^(\d{1,2})([./-])(\d{1,2})(?:\2|\s*')\s*(\d{2}|\d{4})(?:\s+(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?)?$/.exec(value);
    const yearFirst = iso || ofx;
    const valid = (year,month,day) => {
      const stamp = new Date(Date.UTC(+year,+month-1,+day));
      return +year >= 1900 && +year <= 2200 && stamp.getUTCFullYear() === +year &&
        stamp.getUTCMonth() + 1 === +month && stamp.getUTCDate() === +day ? stamp.toISOString().slice(0,10) : null;
    };
    if (format === 'excel' && /^\d{1,6}$/.test(value)) {
      const serial = Number(value);
      if (serial < 1 || serial === 60) return {};
      const day = new Date(Date.UTC(1899,11,31) + (serial - (serial > 60 ? 1 : 0))*86400000);
      return {both:valid(day.getUTCFullYear(),day.getUTCMonth()+1,day.getUTCDate())};
    }
    if (yearFirst && ['auto','iso'].includes(format)) return {both:valid(...yearFirst.slice(1,4))};
    if (!local || format === 'iso' || format === 'excel') return {};
    const [,first,sep,second,rawYear] = local;
    const year = rawYear.length === 2 ? (+rawYear >= 70 ? 1900 : 2000) + +rawYear : +rawYear;
    return {
      dmy:format !== 'mdy' ? valid(year,second,first) : null,
      mdy:format !== 'dmy' && (sep !== '.' || format === 'mdy') ? valid(year,first,second) : null
    };
  }

  function currencyCode(value) {
    const code = value.trim().toUpperCase();
    return ({643:'RUB',810:'RUB',RUR:'RUB','₽':'RUB',840:'USD',978:'EUR',398:'KZT',860:'UZS',826:'GBP',392:'JPY','€':'EUR'})[code] || code;
  }

  function amountCandidates(value,currency,decimal) {
    const plain = value.trim().replace(/[−–]/g,'-');
    const negative = /^-/.test(plain) || /-$/.test(plain) || /^\(.*\)$/.test(plain);
    const digits = plain.replace(/^[+-]|-$|^\(|\)$/g,'').trim();
    const results = Object.create(null);
    for (const mark of decimal === 'auto' ? ['.',','] : [decimal]) {
      const parts = digits.split(mark);
      if (parts.length > 2 || (parts.length === 2 && !/^\d+$/.test(parts[1]))) continue;
      const grouping = mark === '.' ? ',' : '.';
      const integer = parts[0];
      const groups = integer.split(/[.,' \u00a0\u202f]/);
      const valid = /^\d+$/.test(integer) || (groups.length > 1 && /^[1-9]\d{0,2}$/.test(groups[0]) &&
        groups.slice(1).every(group=>/^\d{3}$/.test(group)) && [...integer].every(ch=>/\d|[' \u00a0\u202f]/.test(ch)||ch===grouping));
      if (!valid) continue;
      const exact = (negative ? '-' : '') + groups.join('') + (parts.length === 2 ? '.' + parts[1] : '');
      try { results[mark] = ULADIMMoney.parse(exact,currency,true); }
      catch {}
    }
    return results;
  }

  function choose(candidates, preferred, ambiguity, invalid) {
    const choices = Object.values(candidates).filter(value=>value != null);
    if (!choices.length) fail(invalid);
    if (new Set(choices).size === 1) return choices[0];
    if (preferred && candidates[preferred] != null) return candidates[preferred];
    fail(ambiguity);
  }

  function preference(samples) {
    const options = new Set();
    for (const values of samples) {
      const keys = Object.keys(values).filter(key=>values[key] != null);
      if (keys.length === 1 && keys[0] !== 'both') options.add(keys[0]);
    }
    return options.size === 1 ? [...options][0] : null;
  }

  function columnCompatible(source, column, role, header = source.detection.header) {
    if (column < 0) return true;
    const samples = source.rows.slice(header + 1, header + 51).map(row => (row[column] || '').trim()).filter(Boolean);
    if (!samples.length) return true;
    if (role === 'date') return samples.some(value =>
      Object.values(dateCandidates(value,'auto')).some(Boolean) || Object.values(dateCandidates(value,'excel')).some(Boolean));
    if (['amount','debit','credit'].includes(role)) return samples.some(value => Object.keys(amountCandidates(value,'KWD','auto')).length);
    return true;
  }

  function preview(source, mapping) {
    // Exported balances and alternative amount columns are not interchangeable.
    // An explicit user choice owns both the magnitude and direction for every row.
    if (mapping.amountMode === 'split') mapping = {...mapping,amount:-1,direction:'signed'};
    else if (mapping.amountMode === 'signed') mapping = {...mapping,debit:-1,credit:-1,direction:['income','expense'].includes(mapping.direction)?mapping.direction:'signed'};
    else if (mapping.amountMode === 'typed') {
      mapping = {...mapping,debit:-1,credit:-1,direction:'signed'};
      if (!(mapping.directionColumn >= 0)) fail('import_mapping_required');
    }
    if (mapping.date < 0 || Math.max(mapping.amount,mapping.debit ?? -1,mapping.credit ?? -1) < 0) fail('import_mapping_required');
    const get = (row,key) => (row[mapping[key]] || '').trim();
    const nonzero = value => Boolean(value && !/^[+−-]?0+(?:[.,]0+)?$/.test(value));
    const currencyConflicts=new Set(source.currencyConflicts);
    const rows = source.rows.slice(mapping.header+1).flatMap((row,index) => {
      const line=mapping.header+index+2;
      const date = get(row,'date');
      const label = get(row,'description');
      const raw = get(row,'amount'), debit = get(row,'debit'), credit = get(row,'credit');
      const hasDebit = nonzero(debit), hasCredit = nonzero(credit);
      const amountText = raw || (hasDebit ? debit : credit);
      if (/^(?:итого|total|balance|остаток)(?:\s|$|:)/i.test(date) || (!date && /^(?:итого|total|balance|остаток)(?:\s|$|:)/i.test(label)) ||
          row.every((cell,i)=>headerText(cell)===headerText(source.rows[mapping.header][i] || ''))) return [];
      const header = source.rows[mapping.header];
      const billingAmount = aliases.amount[1].includes(headerText(header[mapping.amount] || ''));
      const billingCurrency = aliases.currency[1].includes(headerText(header[mapping.currency] || ''));
      const currencyText = get(row,'currency');
      const currency = currencyCode(currencyText || (billingAmount ? '' : mapping.defaultCurrency || ''));
      const currencyConflict = currencyConflicts.has(line)||(mapping.currency<0&&source.detection?.ambiguousCurrency);
      const invalidPair = billingAmount!==billingCurrency;
      const direction = get(row,'directionColumn').toLowerCase();
      const unreadable = source.format === 'XLSX' &&
        ['date','amount','debit','credit','currency','bankID','directionColumn'].some(key=>get(row,key)==='�');
      const amounts = /^[A-Z]{3}$/.test(currency) ? amountCandidates(amountText,currency,mapping.decimal) : {};
      return [{line,row,date,label,currency,direction,raw,debit,credit,hasDebit,hasCredit,amountText,amounts,unreadable,invalidPair,currencyConflict,dates:dateCandidates(date,mapping.dateFormat),bankID:get(row,'bankID')}];
    });
    if (rows.length > LIMIT) fail('import_limit');
    const dateOrder = preference(rows.map(item=>item.dates));
    const decimal = preference(rows.map(item=>item.amounts));
    return rows.map(item => {
      const {line,row,date,label,currency,direction,raw,debit,credit,hasDebit,hasCredit,amountText,bankID} = item;
      const editable = value => value==='�'?'':value;
      const original = {date:editable(date),amount:editable(amountText),label,
        currency:item.invalidPair||item.currencyConflict?'':editable(currency),direction,bankID:editable(bankID),kind:''};
      try {
        if(item.unreadable) fail('import_unreadable_cell');
        if(item.currencyConflict) fail('import_currency_conflict');
        if(item.invalidPair || !/^[A-Z]{3}$/.test(currency)) fail('import_currency_invalid');
        if (/\bxfer\b|transfer|перевод|internal movement/.test(direction)) fail('import_transfer_review');
        const amount = choose(item.amounts,decimal,'import_number_ambiguous','import_amount_invalid');
        if (!amount || (hasDebit && hasCredit)) fail('import_amount_invalid');
        const explicit = ['signed','split'].includes(mapping.amountMode) ? '' : /^(income|credit|crdt|deposit|dep|зачисление|доход|приход)$/.test(direction) ? 'income' :
          /^(expense|debit|dbit|payment|pos|расход|списание)$/.test(direction) ? 'expense' : '';
        if (mapping.amountMode==='typed' && !explicit) fail('import_direction_invalid');
        const splitKind = hasDebit ? 'expense' : hasCredit ? 'income' : '';
        if (!splitKind && mapping.direction==='signed' &&
            ((explicit==='income' && amount<0) || (explicit==='expense' && /^\+/.test(raw)))) fail('import_direction_conflict');
        if(splitKind){
          const splitAmount = choose(amountCandidates(hasDebit?debit:credit,currency,mapping.decimal),
            decimal,'import_number_ambiguous','import_amount_invalid');
          if (Math.abs(splitAmount)!==Math.abs(amount) || (hasCredit && (splitAmount<0 || (raw && amount<0))) ||
              (explicit && explicit!==splitKind) || (mapping.direction!=='signed' && mapping.direction!==splitKind)) fail('import_amount_invalid');
        }
        const kind = splitKind || (mapping.direction==='signed' ? explicit || (amount<0?'expense':'income') : mapping.direction);
        original.kind = kind;
        const date = choose(item.dates,dateOrder,'import_date_ambiguous','import_date_invalid');
        if (label.length > 500 || bankID.length > 256) fail('import_row_length');
        return {line,row,original,value:{date,kind,amount:Math.abs(amount),currency,label,bankID}};
      } catch (error) { return {line,row,original,error:error.code || 'import_format'}; }
    });
  }
  globalThis.ULADIMStatement = Object.freeze({read,table,preview,columnCompatible});
})();
