import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/domain/statement_import.dart';
import 'package:lifeos/domain/models.dart';
void main(){
  StatementTable read(String text,String type)=>StatementTable.text(Uint8List.fromList(utf8.encode(text)),type);
  test('quoted separators and multiline descriptions remain intact',(){
    final table=read('date;amount;description\r\n11.10.2026;-1 234,56;"Shop; food\nitems"','csv');
    final row=const ImportMapping(date:0,amount:1,description:2,dateFormat:'dmy',decimal:',').normalize(table.rows[1]);
    expect(row.amountMinor,123456);expect(row.kind,EntryKind.expense);expect(row.label,'Shop; food\nitems');expect(row.date,'2026-10-11');
  });
  test('impossible dates, imprecise money and unclosed quotes are rejected',(){
    expect(()=>const ImportMapping(date:0,amount:1,description:2).normalize(['2026-02-30','12.00','x']),throwsA(isA<DomainFailure>()));
    expect(()=>const ImportMapping(date:0,amount:1,description:2).normalize(['2026-10-11','0.001','x']),throwsA(isA<DomainFailure>()));
    expect(()=>read('a,b\n"x,y','csv'),throwsA(isA<DomainFailure>()));
  });
  test('OFX and QIF use explicit date and decimal interpretation',(){
    final table=read('<OFX><CURDEF>USD<STMTTRN><DTPOSTED>20261011<TRNAMT>-12.50<NAME>Shop</STMTTRN></OFX>','ofx');
    expect(const ImportMapping(date:0,amount:1,description:2,currency:3).normalize(table.rows[1]).amountMinor,1250);
    final qif=read('!Type:Bank\nD10/11/2026\nT-12.50\nPShop\n^','qif');
    expect(const ImportMapping(date:0,amount:1,description:2,dateFormat:'mdy').normalize(qif.rows[1]).date,'2026-10-11');
  });
  test('content hashes are deterministic and do not depend on filenames',() async {
    expect(await importDigest(['row',1]),await importDigest(['row',1]));expect(await importDigest(['row',1]),isNot(await importDigest(['row',2])));
  });
}
