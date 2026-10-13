import 'statement_import.dart';

/// Conservative detection: ambiguous headers or dates require explicit adjustment.
class StatementDetection {
  const StatementDetection(this.header, this.mapping);
  final int header;
  final ImportMapping mapping;
  static StatementDetection? detect(
    StatementTable table,
    String defaultCurrency,
  ) {
    const aliases = {
      'date': {
        'date',
        'дата',
        'дата операции',
        'operation date',
        'дата платежа',
      },
      'amount': {'amount', 'сумма', 'сумма операции', 'transaction amount'},
      'description': {
        'description',
        'описание',
        'назначение',
        'назначение платежа',
        'memo',
      },
      'currency': {'currency', 'валюта', 'код валюты'},
    };
    for (
      var header = 0;
      header < table.rows.length - 1 && header < 20;
      header++
    ) {
      final cells = table.rows[header]
          .map((v) => v.trim().toLowerCase())
          .toList();
      int column(String key) {
        final matches = [
          for (var i = 0; i < cells.length; i++)
            if (aliases[key]!.contains(cells[i])) i,
        ];
        return matches.length == 1 ? matches.single : -1;
      }

      final date = column('date'), amount = column('amount');
      if (date < 0 || amount < 0) continue;
      final samples = table.rows
          .skip(header + 1)
          .take(20)
          .where((r) => r.length > date && r.length > amount)
          .toList();
      if (samples.isEmpty) return null;
      String? format, decimal;
      for (final row in samples) {
        final d = row[date].trim();
        String? candidate;
        if (RegExp(r'^\d{4}-\d{2}-\d{2}$|^\d{8}$').hasMatch(d)) {
          candidate = 'iso';
        } else if (RegExp(r'^\d{1,2}\.\d{1,2}\.\d{4}$').hasMatch(d)) {
          candidate = 'dmy';
        } else {
          return null;
        }
        if (format != null && format != candidate) return null;
        format = candidate;
        final value = row[amount]
            .trim()
            .replaceAll(' ', '')
            .replaceAll('\u00a0', '');
        final comma = value.lastIndexOf(','), dot = value.lastIndexOf('.');
        if (comma >= 0 || dot >= 0) {
          final chosen = comma > dot ? ',' : '.';
          if (decimal != null && decimal != chosen) return null;
          decimal = chosen;
        }
      }
      final mapping = ImportMapping(
        date: date,
        amount: amount,
        description: column('description'),
        currency: column('currency'),
        dateFormat: format!,
        decimal: decimal ?? '.',
        defaultCurrency: defaultCurrency,
      );
      try {
        for (final row in samples) {
          mapping.normalize(row);
        }
      } catch (_) {
        return null;
      }
      return StatementDetection(header, mapping);
    }
    return null;
  }
}
