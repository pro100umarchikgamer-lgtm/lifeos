import 'dart:convert';
import 'dart:typed_data';
import 'package:cryptography/cryptography.dart';
import 'models.dart';

/// Ephemeral source table. Never serialize this into preferences, files or logs.
class StatementTable {
  const StatementTable(this.rows);
  final List<List<String>> rows;
  static const maxBytes=5*1024*1024, maxRows=10000, maxColumns=100;
  static StatementTable text(Uint8List bytes,String extension,{String encoding='utf8'}) {
    if(bytes.length>maxBytes)throw const DomainFailure('import_limit');
    String decode() {
      if(encoding=='utf16') {
        if(bytes.length<2||bytes.length.isOdd)throw const DomainFailure('import_format');
        final big=bytes[0]==0xfe&&bytes[1]==0xff,little=bytes[0]==0xff&&bytes[1]==0xfe;
        if(!big&&!little)throw const DomainFailure('import_format');
        return String.fromCharCodes([for(var i=2;i<bytes.length;i+=2)big?(bytes[i]<<8)|bytes[i+1]:(bytes[i+1]<<8)|bytes[i]]);
      }
      if(encoding=='cp1251') {
        const high='ЂЃ‚ѓ„…†‡€‰Љ‹ЊЌЋЏђ‘’“”•–—\u0000™љ›њќћџ ЎўЈ¤Ґ¦§Ё©Є«¬­®Ї°±Ііґµ¶·ё№є»јЅѕї';
        if(bytes.contains(0x98))throw const DomainFailure('import_format');
        return String.fromCharCodes([for(final b in bytes)b<128?b:b>=192?0x410+b-192:high.codeUnitAt(b-128)]);
      }
      return utf8.decode(bytes);
    }
    var text=decode(); if(text.startsWith('\ufeff'))text=text.substring(1);
    if(text.length>maxBytes||RegExp(r'<!DOCTYPE|<!ENTITY',caseSensitive:false).hasMatch(text))throw const DomainFailure('import_unsafe');
    final List<List<String>> rows;
    switch(extension.toLowerCase()) {
      case 'json':
        final source=jsonDecode(text);
        if(source is! List||source.any((r)=>r is! Map))throw const DomainFailure('import_format');
        final keys=source.isEmpty?<String>[]:(source.first as Map).keys.cast<String>().toList();
        rows=[keys,for(final raw in source)[for(final k in keys)(raw as Map)[k]?.toString()??'']];
      case 'ofx':
        String tag(String value,String name)=>RegExp('<$name>([^<\\r\\n]+)',caseSensitive:false).firstMatch(value)?.group(1)?.trim()??'';
        final currency=tag(text,'CURDEF');
        rows=[['date','amount','description','currency'],for(final block in RegExp(r'<STMTTRN>(.*?)</STMTTRN>',caseSensitive:false,dotAll:true).allMatches(text))
          [tag(block.group(1)!,'DTPOSTED').substring(0,8),tag(block.group(1)!,'TRNAMT'),tag(block.group(1)!,'MEMO').isEmpty?tag(block.group(1)!,'NAME'):tag(block.group(1)!,'MEMO'),currency]];
      case 'qif':
        rows=[['date','amount','description']];
        for(final block in text.split('^')) {
          final values=<String,String>{};for(final line in const LineSplitter().convert(block)){if(line.isNotEmpty)values[line[0]]=line.substring(1).trim();}
          if(values.containsKey('D')&&values.containsKey('T'))rows.add([values['D']!,values['T']!,values['M']??values['P']??'']);
        }
      case 'csv'||'tsv'||'txt':
        final first=text.split('\n').first;
        final separator=extension=='tsv'?'\t':first.split(';').length>first.split(',').length?';':first.contains('\t')?'\t':',';
        rows=_delimited(text,separator);
      default:throw const DomainFailure('import_format');
    }
    return checked(rows);
  }
  static StatementTable checked(List<List<String>> rows) {
    if(rows.length<2||rows.length>maxRows+1||rows.any((r)=>r.length>maxColumns||r.any((c)=>c.length>4000)))throw const DomainFailure('import_limit');
    return StatementTable(rows);
  }
  static List<List<String>> _delimited(String text,String separator) {
    final rows=<List<String>>[], row=<String>[];var buffer=StringBuffer(),quoted=false,closed=false;
    for(var i=0;i<text.length;i++) {
      final char=text[i];
      if(char=='"') {if(quoted&&i+1<text.length&&text[i+1]=='"'){buffer.write('"');i++;}else if(quoted||buffer.isEmpty){if(quoted)closed=true;quoted=!quoted;}else{throw const DomainFailure('import_format');}}
      else if(!quoted&&(char==separator||char=='\n'||char=='\r')) {
        row.add(buffer.toString());buffer=StringBuffer();closed=false;
        if(char!=separator){if(char=='\r'&&i+1<text.length&&text[i+1]=='\n')i++;if(row.any((v)=>v.isNotEmpty))rows.add(List.of(row));row.clear();}
        if(rows.length>maxRows+1||row.length>maxColumns)throw const DomainFailure('import_limit');
      }else{if(closed)throw const DomainFailure('import_format');buffer.write(char);if(buffer.length>4000)throw const DomainFailure('import_limit');}
    }
    if(quoted)throw const DomainFailure('import_format');
    if(buffer.isNotEmpty||row.isNotEmpty){row.add(buffer.toString());rows.add(row);}
    return rows;
  }
}
class ImportMapping {
  const ImportMapping({required this.date,required this.amount,required this.description,this.currency=-1,this.dateFormat='iso',this.decimal='.',this.defaultCurrency='RUB'});
  final int date,amount,description,currency;
  final String dateFormat,decimal,defaultCurrency;
  ImportedMoney normalize(List<String> row) {
    String cell(int index){if(index<0||index>=row.length)throw const DomainFailure('import_columns');return row[index].trim();}
    final code=Currency.fromCode(currency<0?defaultCurrency:cell(currency));
    var number=cell(amount).replaceAll(' ','').replaceAll('\u00a0','');
    final negative=number.startsWith('-')||number.startsWith('(')&&number.endsWith(')');
    number=number.replaceAll(RegExp(r'^[+-]|^\(|\)$'),'');
    if(decimal==','){number=number.replaceAll('.','').replaceAll(',','.');}else{number=number.replaceAll(',','');}
    final minor=code.parse(number),raw=cell(date);DateTime parsed;
    if(dateFormat=='iso') {
      final match=RegExp(r'^(\d{4})-?(\d{2})-?(\d{2})(?:T.*)?$').firstMatch(raw);
      if(match==null)throw const DomainFailure('invalid_date');parsed=_date(int.parse(match[1]!),int.parse(match[2]!),int.parse(match[3]!));
    }else if(dateFormat=='excel') {
      final serial=int.tryParse(raw);if(serial==null||serial<1||serial>109575||serial==60)throw const DomainFailure('invalid_date');
      parsed=DateTime.utc(1899,12,31).add(Duration(days:serial>60?serial-1:serial));
    }else{
      final parts=raw.split(RegExp(r'[./-]'));if(parts.length!=3||parts[2].length!=4)throw const DomainFailure('invalid_date');
      parsed=_date(int.parse(parts[2]),int.parse(parts[dateFormat=='dmy'?1:0]),int.parse(parts[dateFormat=='dmy'?0:1]));
    }
    if(parsed.year<1900||parsed.year>2200)throw const DomainFailure('invalid_date');
    final label=cell(description);if(label.length>2000)throw const DomainFailure('required_text');
    return ImportedMoney(kind:negative?EntryKind.expense:EntryKind.income,amountMinor:minor,currency:code.code,date:dateOnly(parsed),label:label);
  }
  static DateTime _date(int year,int month,int day){final d=DateTime.utc(year,month,day);if(d.year!=year||d.month!=month||d.day!=day)throw const DomainFailure('invalid_date');return d;}
}
class ImportedMoney {
  const ImportedMoney({required this.kind,required this.amountMinor,required this.currency,required this.date,required this.label,this.originKey='',this.allowDuplicate=false});
  final EntryKind kind;final int amountMinor;final String currency,date,label,originKey;final bool allowDuplicate;
  Map<String,Object?> get canonical=>{'kind':kind.name,'amount':amountMinor,'currency':currency,'date':date,'label':label.trim()};
  Map<String,Object?> toJson()=>{...canonical,'origin':originKey,'allowDuplicate':allowDuplicate};
  bool matches(Record r)=>r.kind==kind&&r.amountMinor==amountMinor&&r.currency?.code==currency&&r.date==date&&r.text.trim()==label.trim();
  ImportedMoney identified(String key,{bool duplicate=false})=>ImportedMoney(kind:kind,amountMinor:amountMinor,currency:currency,date:date,label:label,originKey:key,allowDuplicate:duplicate);
}
Future<String> importDigest(Object value) async => (await Sha256().hash(utf8.encode(jsonEncode(value)))).bytes.map((b)=>b.toRadixString(16).padLeft(2,'0')).join();

List<List<String>> parseStatementWorker(Map<String,Object?> args)=>StatementTable.text(args['bytes'] as Uint8List,args['extension'] as String,encoding:args['encoding'] as String).rows;
