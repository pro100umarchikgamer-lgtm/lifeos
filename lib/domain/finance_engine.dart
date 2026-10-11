import 'models.dart';

/// Pure, exact accounting. A transfer and an earmark are never income/consumption.
class FinanceEngine {
  const FinanceEngine();
  BigInt accountBalance(Map<String,Object?> account,List<Record> records,List<Map<String,Object?>> transfers) {
    var value=BigInt.from(account['opening_minor'] as int);
    for(final r in records.where((r)=>r.accountId==account['id'] && r.currency?.code==account['currency'])) {
      value += BigInt.from(r.amountMinor!)*(r.kind==EntryKind.income?BigInt.one:-BigInt.one);
    }
    for(final t in transfers.where((t)=>t['deleted_at']==null)) {
      if(t['from_account_id']==account['id']) value-=BigInt.from(t['sent_minor'] as int);
      if(t['to_account_id']==account['id']) value+=BigInt.from(t['received_minor'] as int);
    }
    return value;
  }
  BigInt spending(List<Record> records,List<Map<String,Object?>> splits,String currency,DateTime start,DateTime end,{Set<String>? categories}) {
    final grouped=<String,List<Map<String,Object?>>>{};
    for(final s in splits) { grouped.putIfAbsent(s['transaction_id'] as String,()=>[]).add(s); }
    var total=BigInt.zero;
    for(final r in records.where((r)=>r.kind==EntryKind.expense && r.currency?.code==currency &&
      r.date!.compareTo(dateOnly(start))>=0 && r.date!.compareTo(dateOnly(end))<=0)) {
      if(categories==null) { total+=BigInt.from(r.amountMinor!); continue; }
      final allocations=grouped[r.id];
      if(allocations==null || allocations.isEmpty) {
        if(categories.contains(r.categoryId)) total+=BigInt.from(r.amountMinor!);
      } else {
        for(final s in allocations.where((s)=>categories.contains(s['category_id']))) { total+=BigInt.from(s['amount_minor'] as int); }
      }
    }
    return total;
  }
  Set<String> categoryTree(String id,List<Map<String,Object?>> categories) {
    final ids={id}; bool changed=true;
    while(changed) { changed=false; for(final c in categories) { if(ids.contains(c['parent_id'])&&ids.add(c['id'] as String)) changed=true; } }
    return ids;
  }
  /// Positive/negative remainder is carried only under the explicitly chosen policy.
  BigInt budgetRemaining(Map<String,Object?> budget,DateTime at,List<Record> records,List<Map<String,Object?>> splits,List<Map<String,Object?>> categories) {
    final raw=DateTime.parse(budget['start_on'] as String);
    final first=DateTime.utc(raw.year,raw.month,raw.day), current=DateTime.utc(at.year,at.month,at.day);
    if(current.isBefore(first)) return BigInt.from(budget['limit_minor'] as int);
    final period=budget['period'] as String, policy=budget['rollover'] as String;
    final category=budget['category_id'] as String?;
    final tree=category==null?null:categoryTree(category,categories);
    final customEnd=budget['end_on']==null?null:DateTime.parse(budget['end_on'] as String);
    DateTime boundary(int n)=>switch(period) {
      'week'=>first.add(Duration(days:7*n)), 'month'=>DateTime.utc(first.year,first.month+n),
      'year'=>DateTime.utc(first.year+n), _=>first.add(Duration(days:(DateTime.utc(customEnd!.year,customEnd.month,customEnd.day).difference(first).inDays+1)*n)),
    };
    var carry=BigInt.zero;
    for(var n=0;n<16000;n++) {
      final start=boundary(n), next=boundary(n+1);
      final used=spending(records,splits,budget['currency'] as String,start,next.subtract(const Duration(days:1)),categories:tree);
      final remainder=BigInt.from(budget['limit_minor'] as int)+carry-used;
      if(current.isBefore(next)) return remainder;
      carry=policy=='both'||policy=='positive'&&!remainder.isNegative||policy=='negative'&&remainder.isNegative?remainder:BigInt.zero;
    }
    throw const DomainFailure('invalid_date');
  }
}
