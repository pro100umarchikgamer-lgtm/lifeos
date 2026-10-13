import 'models.dart';
import 'finance_engine.dart';

/// Calculate only the records authorized by the server. Never combine personal data.
class FamilyFinance {
  const FamilyFinance();
  List<Record> transactions(
    List<Map<String, dynamic>> rows, {
    Set<String>? participants,
  }) => [
    for (final r in rows)
      if (r['kind'] == 'transaction' &&
          (participants == null ||
              (r['audience'] as List).any(participants.contains)))
        Record(
          id: r['id'] as String,
          kind: (r['data']['kind'] == 'income'
              ? EntryKind.income
              : EntryKind.expense),
          text: r['data']['label'] as String,
          createdAt: DateTime.parse(r['data']['date'] as String),
          amountMinor: r['data']['amount_minor'] as int,
          currency: Currency.fromCode(r['data']['currency'] as String),
          date: r['data']['date'] as String,
          accountId: r['data']['account_id'] as String?,
        ),
  ];
  BigInt accountBalance(
    Map<String, dynamic> row,
    List<Map<String, dynamic>> rows,
  ) => const FinanceEngine().accountBalance(
    {'id': row['id'], ...Map<String, Object?>.from(row['data'] as Map)},
    transactions(rows),
    [
      for (final r in rows)
        if (r['kind'] == 'transfer')
          {
            'from_account_id': r['data']['from_id'],
            'to_account_id': r['data']['to_id'],
            'sent_minor': r['data']['sent_minor'],
            'received_minor': r['data']['received_minor'],
            'deleted_at': null,
          },
    ],
  );
  BigInt budgetRemaining(
    Map<String, dynamic> row,
    List<Map<String, dynamic>> rows,
    DateTime at,
  ) {
    final data = Map<String, Object?>.from(row['data'] as Map),
        participants = (data['participants'] as List).cast<String>().toSet();
    return const FinanceEngine().budgetRemaining(
      {...data, 'category_id': null},
      at,
      transactions(
        rows,
        participants: participants.isEmpty ? null : participants,
      ),
      [],
      [],
    );
  }
}
