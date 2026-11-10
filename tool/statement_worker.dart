// Compiled from the same domain implementation used by Android. No file upload.
import 'dart:convert';
import 'dart:js_interop';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/domain/statement_import.dart';
import 'package:lifeos/domain/statement_detection.dart';
import 'package:lifeos/domain/finance_engine.dart';

@JS('self.onmessage')
external set onMessage(JSFunction callback);
@JS('self.postMessage')
external void reply(JSString value);
extension type Message(JSObject _) implements JSObject {
  external JSString get data;
}
void main() {
  onMessage = ((Message event) {
    try {
      final request = jsonDecode(event.data.toDart) as Map<String, dynamic>;
      if (request['action'] == 'budgets') {
        final records = <Record>[];
        for (final raw in request['records'] as List) {
          final r = raw as Map, data = r['data'] as Map;
          records.add(Record(id: r['id'] as String, kind: EntryKind.values.byName(data['kind'] as String),
            text: data['label'] as String, createdAt: DateTime.utc(1970),
            amountMinor: data['amount_minor'] as int, currency: Currency.fromCode(data['currency'] as String), date: data['date'] as String));
        }
        final at = DateTime.parse(request['at'] as String);
        final values = <String, String>{};
        for (final raw in request['budgets'] as List) {
          final budget = raw as Map;
          values[budget['id'] as String] = const FinanceEngine().budgetRemaining(
            (budget['data'] as Map).cast<String,Object?>(), at, records, [], []).toString();
        }
        reply(jsonEncode({'remaining': values}).toJS);
      } else if (request['action'] == 'parse') {
        final bytes = base64Decode(request['bytes'] as String);
        try {
          final table = StatementTable.text(bytes, request['extension'] as String,
              encoding: request['encoding'] as String, delimiter: request['delimiter'] as String);
          final detection = StatementDetection.detect(table, request['currency'] as String);
          reply(jsonEncode({'rows': table.rows, 'detection': detection == null ? null : {
            'header': detection.header, 'date': detection.mapping.date,
            'amount': detection.mapping.amount, 'description': detection.mapping.description,
            'currency': detection.mapping.currency, 'dateFormat': detection.mapping.dateFormat,
            'decimal': detection.mapping.decimal,
          }}).toJS);
        } finally { bytes.fillRange(0, bytes.length, 0); }
      } else {
        final table = StatementTable.checked([for (final row in request['rows'] as List) (row as List).cast<String>()]);
        final m = request['mapping'] as Map;
        final mapping = ImportMapping(date: m['date'] as int, amount: m['amount'] as int,
          description: m['description'] as int, currency: m['currency'] as int,
          dateFormat: m['dateFormat'] as String, decimal: m['decimal'] as String,
          defaultCurrency: m['defaultCurrency'] as String, direction: m['direction'] as String);
        final rows = <Object?>[];
        for (final row in table.rows.skip((m['header'] as int) + 1)) {
          try { rows.add({'value': mapping.normalize(row).canonical}); }
          on DomainFailure catch (e) { rows.add({'error': e.key}); }
          catch (_) { rows.add({'error': 'import_format'}); }
        }
        reply(jsonEncode({'preview': rows}).toJS);
      }
    } on DomainFailure catch (e) { reply(jsonEncode({'error': e.key}).toJS); }
    catch (_) { reply(jsonEncode({'error': 'import_format'}).toJS); }
  }).toJS;
}
