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
    final customDays=period=='custom'?DateTime.utc(customEnd!.year,customEnd.month,customEnd.day).difference(first).inDays+1:1;
    int index(DateTime d)=>switch(period){'week'=>d.difference(first).inDays~/7,'month'=>(12*(d.year-first.year)+d.month-first.month),'year'=>d.year-first.year,_=>d.difference(first).inDays~/customDays};
    final target=index(current), buckets=<int,BigInt>{},grouped=<String,List<Map<String,Object?>>>{};
    for(final s in splits){grouped.putIfAbsent(s['transaction_id'] as String,()=>[]).add(s);}
    for(final r in records){
      if(r.kind!=EntryKind.expense||r.currency?.code!=budget['currency']||r.date==null)continue;
      final rawDate=DateTime.parse(r.date!),d=DateTime.utc(rawDate.year,rawDate.month,rawDate.day);
      if(d.isBefore(first))continue;final n=index(d);if(n>target)continue;
      var used=BigInt.zero;
      if(tree==null){used=BigInt.from(r.amountMinor!);}else {
        final parts=grouped[r.id];
        if(parts==null||parts.isEmpty){if(tree.contains(r.categoryId))used=BigInt.from(r.amountMinor!);}
        else{for(final s in parts){if(tree.contains(s['category_id']))used+=BigInt.from(s['amount_minor'] as int);}}
      }
      buckets[n]=(buckets[n]??BigInt.zero)+used;
    }
    final allowance=BigInt.from(budget['limit_minor'] as int);
    BigInt carryRule(BigInt amount)=>policy=='both'||policy=='positive'&&!amount.isNegative||policy=='negative'&&amount.isNegative?amount:BigInt.zero;
    BigInt emptyPeriods(BigInt carry,int count){
      if(count<=0)return carry;if(policy=='none')return BigInt.zero;
      final value=carry+allowance*BigInt.from(count);
      return policy=='negative'&&!value.isNegative?BigInt.zero:value;
    }
    var carry=BigInt.zero,position=0;
    final periods=buckets.keys.toList()..sort();
    for(final n in periods){
      carry=emptyPeriods(carry,n-position);
      final remaining=allowance+carry-buckets[n]!;
      if(n==target)return remaining;
      carry=carryRule(remaining);position=n+1;
    }
    return allowance+emptyPeriods(carry,target-position);
  }
}
