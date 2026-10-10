enum EntryKind { expense, income, task, note }

class DomainFailure implements Exception {
  const DomainFailure(this.key);
  final String key;
}

class Currency {
  const Currency(this.code, this.digits);
  final String code;
  final int digits;

  static Currency fromCode(String raw) {
    final code = raw.trim().toUpperCase();
    if (!RegExp(r'^[A-Z]{3}$').hasMatch(code)) {
      throw const DomainFailure('invalid_currency');
    }
    const zero = {'JPY', 'KRW', 'VND', 'CLP', 'ISK', 'PYG', 'UGX', 'XAF', 'XOF'};
    const three = {'BHD', 'JOD', 'KWD', 'OMR', 'TND', 'IQD', 'LYD'};
    return Currency(code, zero.contains(code) ? 0 : three.contains(code) ? 3 : 2);
  }

  int parse(String raw) {
    final value = raw.trim().replaceAll(' ', '').replaceAll('\u00a0', '').replaceAll(',', '.');
    final match = RegExp(r'^(\d+)(?:\.(\d+))?$').firstMatch(value);
    if (match == null) throw const DomainFailure('invalid_amount');
    final fractional = match.group(2) ?? '';
    if (fractional.length > digits) throw const DomainFailure('amount_precision');
    final minor = int.tryParse('${match.group(1)}${fractional.padRight(digits, '0')}');
    if (minor == null || minor <= 0 || minor > 999999999999999) {
      throw const DomainFailure('invalid_amount');
    }
    return minor;
  }

  String format(int minor, {String separator = '.'}) {
    final text = minor.toString().padLeft(digits + 1, '0');
    if (digits == 0) return '$text $code';
    return '${text.substring(0, text.length - digits)}$separator${text.substring(text.length - digits)} $code';
  }
}

class Record {
  const Record({required this.id, required this.kind, required this.text,
    required this.createdAt, this.amountMinor, this.currency, this.date, this.completed = false});
  final String id;
  final EntryKind kind;
  final String text;
  final DateTime createdAt;
  final int? amountMinor;
  final Currency? currency;
  final String? date;
  final bool completed;
}

sealed class AppAction {
  const AppAction(this.operationId);
  final String operationId;
  Map<String, Object?> get payload;
}

class CreateMoney extends AppAction {
  const CreateMoney(super.operationId, {required this.kind, required this.amount,
    required this.currencyCode, required this.date, this.label = ''});
  final EntryKind kind;
  final String amount;
  final String currencyCode;
  final DateTime date;
  final String label;
  @override
  Map<String, Object?> get payload => {'action': kind.name, 'amount': amount,
    'currency': currencyCode, 'date': dateOnly(date), 'label': label.trim()};
}

class CreateTask extends AppAction {
  const CreateTask(super.operationId, this.title);
  final String title;
  @override
  Map<String, Object?> get payload => {'action': 'task.create', 'title': title.trim()};
}

class CreateNote extends AppAction {
  const CreateNote(super.operationId, this.body);
  final String body;
  @override
  Map<String, Object?> get payload => {'action': 'note.create', 'body': body.trim()};
}

class CompleteTask extends AppAction {
  const CompleteTask(super.operationId, this.id, this.completed);
  final String id;
  final bool completed;
  @override
  Map<String, Object?> get payload => {'action': 'task.complete', 'id': id, 'completed': completed};
}

String dateOnly(DateTime date) => '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
