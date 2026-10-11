import 'models.dart';

abstract interface class ActionStore {
  Future<String> apply(AppAction action);
  Future<List<Record>> records();
  Future<Map<String, String>> settings();
  Future<void> setSetting(String key, String value);
  Future<void> close();
}

class ActionEngine {
  const ActionEngine(this.store);
  final ActionStore store;

  Future<String> execute(AppAction action) {
    if (action.operationId.trim().isEmpty) throw const DomainFailure('invalid_action');
    switch (action) {
      case CreateMoney():
        if (action.kind != EntryKind.expense && action.kind != EntryKind.income) {
          throw const DomainFailure('invalid_action');
        }
        Currency.fromCode(action.currencyCode).parse(action.amount);
        if (action.date.year < 1900 || action.date.year > 2200) {
          throw const DomainFailure('invalid_date');
        }
      case CreateTask():
        if (action.title.trim().isEmpty) throw const DomainFailure('required_text');
      case CreateNote():
        if (action.body.trim().isEmpty) throw const DomainFailure('required_text');
      case CompleteTask():
        if (action.id.isEmpty) throw const DomainFailure('invalid_action');
        if (action.expectedRevision != null && action.expectedRevision! < 1) {
          throw const DomainFailure('invalid_action');
        }
      case RecordMutation():
        if (action.id.trim().isEmpty || action.expectedRevision < 1) {
          throw const DomainFailure('invalid_action');
        }
        if (action is EditMoney) {
          if (action.kind != EntryKind.expense && action.kind != EntryKind.income) {
            throw const DomainFailure('invalid_action');
          }
          Currency.fromCode(action.currencyCode).parse(action.amount);
          if (action.date.year < 1900 || action.date.year > 2200) {
            throw const DomainFailure('invalid_date');
          }
        }
        if (action is EditTask && action.title.trim().isEmpty ||
            action is EditNote && action.body.trim().isEmpty) {
          throw const DomainFailure('required_text');
        }
    }
    return store.apply(action);
  }
}
