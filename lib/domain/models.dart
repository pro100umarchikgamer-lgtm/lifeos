import 'statement_import.dart';
part 'calendar_models.dart';
part 'offline_models.dart';

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
    const zero = {
      'JPY',
      'KRW',
      'VND',
      'CLP',
      'ISK',
      'PYG',
      'UGX',
      'XAF',
      'XOF',
    };
    const three = {'BHD', 'JOD', 'KWD', 'OMR', 'TND', 'IQD', 'LYD'};
    return Currency(
      code,
      zero.contains(code)
          ? 0
          : three.contains(code)
          ? 3
          : 2,
    );
  }

  int parse(String raw) {
    final value = raw
        .trim()
        .replaceAll(' ', '')
        .replaceAll('\u00a0', '')
        .replaceAll(',', '.');
    final match = RegExp(r'^(\d+)(?:\.(\d+))?$').firstMatch(value);
    if (match == null) throw const DomainFailure('invalid_amount');
    final fractional = match.group(2) ?? '';
    if (fractional.length > digits)
      throw const DomainFailure('amount_precision');
    final minor = int.tryParse(
      '${match.group(1)}${fractional.padRight(digits, '0')}',
    );
    if (minor == null || minor <= 0 || minor > 999999999999999) {
      throw const DomainFailure('invalid_amount');
    }
    return minor;
  }

  String format(int minor, {String separator = '.'}) {
    final sign = minor < 0 ? '-' : '';
    final text = minor.abs().toString().padLeft(digits + 1, '0');
    if (digits == 0) return '$sign$text $code';
    return '$sign${text.substring(0, text.length - digits)}$separator${text.substring(text.length - digits)} $code';
  }
}

class Record {
  const Record({
    required this.id,
    required this.kind,
    required this.text,
    required this.createdAt,
    this.amountMinor,
    this.currency,
    this.date,
    this.completed = false,
    this.revision = 1,
    this.updatedAt,
    this.accountId,
    this.categoryId,
  });
  final String id;
  final EntryKind kind;
  final String text;
  final DateTime createdAt;
  final int? amountMinor;
  final Currency? currency;
  final String? date;
  final bool completed;
  final int revision;
  final DateTime? updatedAt;
  final String? accountId, categoryId;
}

sealed class AppAction {
  const AppAction(this.operationId);
  final String operationId;
  Map<String, Object?> get payload;
}

class CreateMoney extends AppAction {
  const CreateMoney(
    super.operationId, {
    required this.kind,
    required this.amount,
    required this.currencyCode,
    required this.date,
    this.label = '',
    this.accountId,
    this.categoryId,
  });
  final EntryKind kind;
  final String amount;
  final String currencyCode;
  final DateTime date;
  final String label;
  final String? accountId, categoryId;
  @override
  Map<String, Object?> get payload => {
    'action': kind.name,
    'amount': amount,
    'currency': currencyCode,
    'date': dateOnly(date),
    'label': label.trim(),
    if (accountId != null) 'accountId': accountId,
    if (categoryId != null) 'categoryId': categoryId,
  };
}

class CreateTask extends AppAction {
  const CreateTask(super.operationId, this.title, {this.schedule});
  final String title;
  final ScheduleSpec? schedule;
  @override
  Map<String, Object?> get payload => {
    'action': 'task.create',
    'title': title.trim(),
    if (schedule != null) 'schedule': schedule!.toJson(),
  };
}

class CreateNote extends AppAction {
  const CreateNote(super.operationId, this.body, {this.schedule});
  final String body;
  final ScheduleSpec? schedule;
  @override
  Map<String, Object?> get payload => {
    'action': 'note.create',
    'body': body.trim(),
    if (schedule != null) 'schedule': schedule!.toJson(),
  };
}

class CompleteTask extends AppAction {
  const CompleteTask(
    super.operationId,
    this.id,
    this.completed, {
    this.expectedRevision,
  });
  final String id;
  final bool completed;
  final int? expectedRevision;
  @override
  Map<String, Object?> get payload => {
    'action': 'task.complete',
    'id': id,
    'completed': completed,
    if (expectedRevision != null) 'expectedRevision': expectedRevision,
  };
}

sealed class RecordMutation extends AppAction {
  const RecordMutation(
    super.operationId,
    this.id,
    this.kind,
    this.expectedRevision,
  );
  final String id;
  final EntryKind kind;
  final int expectedRevision;
  Map<String, Object?> get target => {
    'id': id,
    'kind': kind.name,
    'expectedRevision': expectedRevision,
  };
}

class EditMoney extends RecordMutation {
  const EditMoney(
    super.operationId,
    super.id,
    super.kind,
    super.expectedRevision, {
    required this.amount,
    required this.currencyCode,
    required this.date,
    this.label = '',
    this.accountId,
    this.categoryId,
    this.updateDetails = false,
  });
  final String amount;
  final String currencyCode;
  final DateTime date;
  final String label;
  final String? accountId, categoryId;
  final bool updateDetails;
  @override
  Map<String, Object?> get payload => {
    ...target,
    'action': 'money.edit',
    'amount': amount,
    'currency': currencyCode,
    'date': dateOnly(date),
    'label': label.trim(),
    if (updateDetails) ...{'accountId': accountId, 'categoryId': categoryId},
  };
}

class EditTask extends RecordMutation {
  const EditTask(
    String operationId,
    String id,
    int revision,
    this.title, {
    this.schedule,
    this.updateSchedule = false,
    this.expectedScheduleRevision,
  }) : super(operationId, id, EntryKind.task, revision);
  final String title;
  final ScheduleSpec? schedule;
  final bool updateSchedule;
  final int? expectedScheduleRevision;
  @override
  Map<String, Object?> get payload => {
    ...target,
    'action': 'task.edit',
    'title': title.trim(),
    if (updateSchedule) ...{
      'schedule': schedule?.toJson(),
      'expectedScheduleRevision': expectedScheduleRevision,
    },
  };
}

class EditNote extends RecordMutation {
  const EditNote(
    String operationId,
    String id,
    int revision,
    this.body, {
    this.schedule,
    this.updateSchedule = false,
    this.expectedScheduleRevision,
  }) : super(operationId, id, EntryKind.note, revision);
  final String body;
  final ScheduleSpec? schedule;
  final bool updateSchedule;
  final int? expectedScheduleRevision;
  @override
  Map<String, Object?> get payload => {
    ...target,
    'action': 'note.edit',
    'body': body.trim(),
    if (updateSchedule) ...{
      'schedule': schedule?.toJson(),
      'expectedScheduleRevision': expectedScheduleRevision,
    },
  };
}

class DeleteRecord extends RecordMutation {
  const DeleteRecord(
    super.operationId,
    super.id,
    super.kind,
    super.expectedRevision,
  );
  @override
  Map<String, Object?> get payload => {...target, 'action': 'record.delete'};
}

class UndoRecordChange extends RecordMutation {
  const UndoRecordChange(
    super.operationId,
    super.id,
    super.kind,
    super.expectedRevision,
  );
  @override
  Map<String, Object?> get payload => {...target, 'action': 'record.undo'};
}

String dateOnly(DateTime date) =>
    '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
