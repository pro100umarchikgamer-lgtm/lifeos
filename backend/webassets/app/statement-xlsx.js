const MAX_FILE = 5 * 1024 * 1024;
const MAX_UNCOMPRESSED = 32 * 1024 * 1024;
const MAX_ENTRY = 12 * 1024 * 1024;
const MAX_ROWS = 10_001;
const MAX_COLUMNS = 64;
const MAX_SHEETS = 12;
const SHEET_NAMESPACES = new Set([
  'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
  'http://purl.oclc.org/ooxml/spreadsheetml/main',
]);
const RELATIONSHIP_NAMESPACE = 'http://schemas.openxmlformats.org/package/2006/relationships';
const WORKBOOK_PATH = 'xl/workbook.xml';
const RELATIONSHIPS_PATH = 'xl/_rels/workbook.xml.rels';
const ZIP_SIGNATURE = {end: 0x06054b50, central: 0x02014b50, local: 0x04034b50};
const UTF8 = new TextDecoder('utf-8', {fatal: true});

function failure(code = 'import_xlsx_layout') {
  return Object.assign(new Error(code), {code});
}

function checked(condition) {
  if (!condition) throw failure();
}

function centralDirectory(bytes) {
  const file = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const u16 = offset => file.getUint16(offset, true);
  const u32 = offset => file.getUint32(offset, true);
  let end = file.byteLength - 22;
  const firstEndOffset = Math.max(0, file.byteLength - 65_557);
  while (end >= firstEndOffset) {
    if (u32(end) === ZIP_SIGNATURE.end && end + 22 + u16(end + 20) === file.byteLength) break;
    end--;
  }
  checked(end >= firstEndOffset);
  const count = u16(end + 10);
  checked(u16(end + 4) === 0 && u16(end + 6) === 0 && u16(end + 8) === count && count < 0xffff);
  if (count > 2048) throw failure('import_limit');

  const startDirectory = u32(end + 16);
  let offset = startDirectory;
  checked(startDirectory + u32(end + 12) === end);
  const entries = new Map();
  let total = 0;
  for (let index = 0; index < count; index++) {
    checked(offset + 46 <= end && u32(offset) === ZIP_SIGNATURE.central);
    const nameLength = u16(offset + 28);
    const next = offset + 46 + nameLength + u16(offset + 30) + u16(offset + 32);
    checked(next <= end);
    const name = UTF8.decode(bytes.subarray(offset + 46, offset + 46 + nameLength));
    const flags = u16(offset + 8);
    const method = u16(offset + 10);
    const length = u32(offset + 24);
    const compressed = u32(offset + 20);
    const crc = u32(offset + 16);
    const local = u32(offset + 42);
    checked(!(flags & 0x41) && u16(offset + 34) === 0 && !entries.has(name));
    checked(!name.includes('\\') && !name.startsWith('/') && !name.split('/').includes('..'));
    checked(local + 30 <= offset && u32(local) === ZIP_SIGNATURE.local);
    const start = local + 30 + u16(local + 26) + u16(local + 28);
    checked(start + compressed <= startDirectory);
    checked(u16(local + 8) === method && u16(local + 6) === flags);
    checked(UTF8.decode(bytes.subarray(local + 30, local + 30 + u16(local + 26))) === name);

    total += length;
    if (total > MAX_UNCOMPRESSED || length > MAX_ENTRY) throw failure('import_limit');
    entries.set(name, {method, length, crc, content: bytes.subarray(start, start + compressed)});
    offset = next;
  }
  checked(offset === end && entries.has('[Content_Types].xml'));
  return entries;
}

const CRC32_TABLE = Uint32Array.from({length: 256}, (_, index) => {
  for (let bit = 0; bit < 8; bit++) index = (index >>> 1) ^ (index & 1 ? 0xedb88320 : 0);
  return index;
});

function crc32(bytes) {
  let value = 0xffffffff;
  for (const byte of bytes) value = (value >>> 8) ^ CRC32_TABLE[(value ^ byte) & 0xff];
  return (value ^ 0xffffffff) >>> 0;
}

async function decompress(entry) {
  let bytes = entry.content;
  if (entry.method === 8) {
    let decoder;
    try {
      decoder = new DecompressionStream('deflate-raw');
    } catch {
      throw failure('import_xlsx_browser');
    }
    const reader = new Blob([entry.content]).stream().pipeThrough(decoder).getReader();
    bytes = new Uint8Array(entry.length);
    let offset = 0;
    try {
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        checked(offset + value.byteLength <= bytes.byteLength);
        bytes.set(value, offset);
        offset += value.byteLength;
      }
      checked(offset === bytes.byteLength);
    } finally {
      await reader.cancel().catch(() => {});
    }
  } else {
    checked(entry.method === 0 && bytes.byteLength === entry.length);
  }
  checked(crc32(bytes) === entry.crc);
  return bytes;
}

async function readXml(entries, path, name) {
  checked(entries.has(path));
  const text = UTF8.decode(await decompress(entries.get(path)));
  checked(!/<!DOCTYPE|<!ENTITY/iu.test(text));
  const doc = new DOMParser().parseFromString(text, 'application/xml');
  const root = doc.documentElement;
  checked(!doc.getElementsByTagName('parsererror').length && root.localName === name);
  const namespace = name === 'Relationships' ? new Set([RELATIONSHIP_NAMESPACE]) : SHEET_NAMESPACES;
  checked(namespace.has(root.namespaceURI));
  return root;
}

function children(element, name) {
  return Array.from(element?.children || []).filter(child => child.localName === name && child.namespaceURI === element.namespaceURI);
}

function child(element, name) {
  return children(element, name)[0];
}

function text(element) {
  return element?.textContent || '';
}

function stringContent(element) {
  return text(child(element, 't')) + children(element, 'r').map(run => text(child(run, 't'))).join('');
}

function relationshipPath(relation) {
  checked(relation && relation.getAttribute('TargetMode') !== 'External');
  const target = relation.getAttribute('Target');
  checked(target && !/[?#%\\]/u.test(target) && !target.startsWith('//'));
  const origin = 'https://workbook.invalid';
  const path = new URL(target, origin + '/' + WORKBOOK_PATH);
  checked(path.origin === origin && path.pathname.startsWith('/xl/') && path.pathname.endsWith('.xml'));
  return path.pathname.slice(1);
}

function dateStyles(root) {
  const custom = new Map(children(child(root, 'numFmts'), 'numFmt').map(format =>
    [Number(format.getAttribute('numFmtId')), format.getAttribute('formatCode') || '']));
  return children(child(root, 'cellXfs'), 'xf').map(style => {
    const id = Number(style.getAttribute('numFmtId'));
    const format = (custom.get(id) || '').replace(/"[^"]*"|\\.|\[[^\]]*\]/gu, '').toLowerCase();
    return (id >= 14 && id <= 17) || id === 22 || (id >= 27 && id <= 36) || (id >= 50 && id <= 58) || /[dy]/u.test(format);
  });
}

function excelDate(value, date1904) {
  if (!/^\d+(?:\.\d+)?$/u.test(value)) return '';
  const days = Math.floor(Number(value));
  if (!Number.isSafeInteger(days) || days > 110_000 || (!date1904 && days === 60)) return '';
  const epoch = date1904 ? Date.UTC(1904, 0, 1) : Date.UTC(1899, 11, days < 60 ? 31 : 30);
  return new Date(epoch + days * 86_400_000).toISOString().slice(0, 10);
}

function columnNumber(reference) {
  const column = /^([A-Z]{1,3})[1-9]\d{0,6}$/u.exec(reference)?.[1];
  checked(column);
  let result = 0;
  for (const letter of column) result = result * 26 + letter.charCodeAt(0) - 64;
  if (result > MAX_COLUMNS) throw failure('import_limit');
  return result - 1;
}

function cellValue(cell, strings, dates, date1904) {
  if (child(cell, 'f')) return '';
  const value = text(child(cell, 'v'));
  const type = cell.getAttribute('t') || 'n';
  if (type === 's') {
    checked(/^\d+$/u.test(value) && Number(value) < strings.length);
    return strings[Number(value)];
  }
  if (type === 'inlineStr') return stringContent(child(cell, 'is'));
  if (type === 'n' && dates[Number(cell.getAttribute('s'))] && value) return excelDate(value, date1904);
  return ['n', 'str', 'd'].includes(type) ? value : '';
}

function sheetRows(root, strings, dates, date1904) {
  const rows = [];
  for (const row of children(child(root, 'sheetData'), 'row')) {
    const values = [];
    let next = 0;
    for (const cell of children(row, 'c')) {
      const reference = cell.getAttribute('r');
      const index = reference ? columnNumber(reference) : next;
      checked(index >= next && index < MAX_COLUMNS);
      const value = cellValue(cell, strings, dates, date1904);
      if (value.length > 4096) throw failure('import_limit');
      while (values.length < index) values.push('');
      values.push(value);
      next = index + 1;
    }
    if (values.some(Boolean)) rows.push(values);
    if (rows.length > MAX_ROWS) throw failure('import_limit');
  }
  return rows;
}

// Decode ordinary XLSX workbook parts as data only. No formulas, hyperlinks,
// macros or external relationships are evaluated or followed.
export async function extractStatementXlsx(source) {
  const bytes = new Uint8Array(source);
  if (bytes.byteLength > MAX_FILE) throw failure('import_limit');
  try {
    const entries = centralDirectory(bytes);
    const book = await readXml(entries, WORKBOOK_PATH, 'workbook');
    const relations = children(await readXml(entries, RELATIONSHIPS_PATH, 'Relationships'), 'Relationship');
    const part = (type, name) => {
      const relation = relations.find(item => item.getAttribute('Type')?.endsWith('/' + type));
      return relation ? readXml(entries, relationshipPath(relation), name) : Promise.resolve(null);
    };
    const [strings, styles] = await Promise.all([part('sharedStrings', 'sst'), part('styles', 'styleSheet')]);
    const sharedStrings = children(strings, 'si').map(stringContent);
    const dates = dateStyles(styles);
    const date1904 = ['1', 'true'].includes(child(book, 'workbookPr')?.getAttribute('date1904'));
    const entriesById = new Map(relations.map(item => [item.getAttribute('Id'), item]));
    const sheetElements = children(child(book, 'sheets'), 'sheet').filter(sheet =>
      !['hidden', 'veryHidden'].includes(sheet.getAttribute('state')));
    if (sheetElements.length > MAX_SHEETS) throw failure('import_limit');
    const sheets = [];
    let count = 0;
    for (const sheet of sheetElements) {
      const id = Array.from(sheet.attributes).find(attribute =>
        attribute.localName === 'id' && attribute.namespaceURI?.endsWith('/relationships'))?.value;
      const relation = entriesById.get(id);
      if (!relation?.getAttribute('Type')?.endsWith('/worksheet')) continue;
      const root = await readXml(entries, relationshipPath(relation), 'worksheet');
      const rows = sheetRows(root, sharedStrings, dates, date1904);
      count += rows.length;
      if (count > MAX_ROWS + MAX_SHEETS - 1) throw failure('import_limit');
      if (rows.length > 1) sheets.push({name: sheet.getAttribute('name') || '', rows});
    }
    if (!sheets.length) throw failure();
    return {rows: sheets[0].rows, sheets, needsReview: sheets.length > 1};
  } catch (error) {
    if (error?.code && typeof error.code === 'string') throw error;
    throw failure();
  }
}
