import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/domain/action_engine.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/ui/money_format.dart';

class CapturingStore implements ActionStore {
  final List<AppAction> actions = [];
  @override
  Future<String> apply(AppAction action) async { actions.add(action); return 'record'; }
  @override
  Future<List<Record>> records() async => [];
  @override
  Future<Map<String, String>> settings() async => {};
  @override
  Future<void> setSetting(String key, String value) async {}
  @override
  Future<void> close() async {}
}

void main() {
  test('typed mutations validate before storage and preserve targets', () async {
    final store = CapturingStore();
    final engine = ActionEngine(store);
    await engine.execute(EditMoney('edit', 'original', EntryKind.expense, 3,
      amount: '1,25', currencyCode: 'RUB', date: DateTime(2026, 10, 11)));
    await engine.execute(const EditTask('task-edit', 'task', 2, 'New title'));
    await engine.execute(const EditNote('note-edit', 'note', 1, 'New body'));
    await engine.execute(const DeleteRecord('delete', 'original', EntryKind.expense, 4));
    await engine.execute(const UndoRecordChange('undo', 'original', EntryKind.expense, 5));
    expect(store.actions.length, 5);
    expect(store.actions.first.payload['id'], 'original');
    expect(() => engine.execute(const EditTask('invalid', 'task', 0, 'Title')), throwsA(isA<DomainFailure>()));
    expect(() => engine.execute(const EditNote('empty', 'note', 2, ' ')), throwsA(isA<DomainFailure>()));
    expect(store.actions.length, 5);
  });
  test('localized money preserves cents and exact large integer values', () {
    final rub = Currency.fromCode('RUB');
    expect(formatMoney(rub, 12250000, locale: 'ru'), '122 500 ₽');
    expect(formatMoney(rub, -1, locale: 'ru'), '-0,01 ₽');
    expect(formatMoney(rub, 123450, locale: 'ru'), '1 234,50 ₽');
    expect(formatMoney(rub, 900719925474099301, locale: 'ru'), '9 007 199 254 740 993,01 ₽');
    expect(formatMoney(Currency.fromCode('USD'), 123450, locale: 'en'), r'$1,234.50');
    expect(formatMoney(Currency.fromCode('JPY'), 1234, locale: 'en'), '¥1,234');
    expect(formatMoney(Currency.fromCode('KWD'), 1, locale: 'en'), 'din0.001');
  });
  test('money uses integer minor units, comma input, and explicit precision', () {
    final rub = Currency.fromCode('rub');
    expect(rub.parse('0,01'), 1);
    expect(rub.parse('1 234.50'), 123450);
    expect(rub.parse('0.10') + rub.parse('0.20'), 30);
    expect(rub.format(1), '0.01 RUB');
    expect(rub.format(-1), '-0.01 RUB');
    expect(Currency.fromCode('JPY').parse('100'), 100);
    expect(Currency.fromCode('KWD').parse('0.001'), 1);
    expect(() => rub.parse('1.001'), throwsA(isA<DomainFailure>()));
    expect(() => Currency.fromCode('JPY').parse('1.5'), throwsA(isA<DomainFailure>()));
    for (final input in ['-1', '0', 'NaN', '1e3', '1,2.3', '999999999999999999999999']) {
      expect(() => rub.parse(input), throwsA(isA<DomainFailure>()));
    }
  });
  test('minimal task, note and expense need no registration or source account', () async {
    final store = CapturingStore();
    final engine = ActionEngine(store);
    await engine.execute(const CreateTask('task-op', 'Buy milk'));
    await engine.execute(const CreateNote('note-op', 'Remember this'));
    await engine.execute(CreateMoney('money-op', kind: EntryKind.expense, amount: '50',
      currencyCode: 'USD', date: DateTime(2026, 10, 10)));
    expect(store.actions.length, 3);
    expect((store.actions.last as CreateMoney).label, '');
  });
  test('invalid action never reaches storage', () {
    final store = CapturingStore();
    final engine = ActionEngine(store);
    expect(() => engine.execute(const CreateTask('op', '  ')), throwsA(isA<DomainFailure>()));
    expect(() => engine.execute(const CreateNote('op', '\n')), throwsA(isA<DomainFailure>()));
    expect(() => engine.execute(CreateMoney('op', kind: EntryKind.task, amount: '1',
      currencyCode: 'USD', date: DateTime.now())), throwsA(isA<DomainFailure>()));
    expect(store.actions, isEmpty);
  });
  test('calendar date is preserved without converting to UTC', () {
    expect(dateOnly(DateTime(2026, 10, 10, 23, 59)), '2026-10-10');
  });
}
