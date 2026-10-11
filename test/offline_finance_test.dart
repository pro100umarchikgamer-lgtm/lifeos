import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/domain/finance_engine.dart';
import 'package:lifeos/domain/offline_validation.dart';

void main(){
  const f=FinanceEngine();
  Record expense(String id,int amount,{String? account,String? category,String date='2026-10-11'})=>Record(id:id,kind:EntryKind.expense,text:'',createdAt:DateTime(2026),amountMinor:amount,currency:const Currency('USD',2),date:date,accountId:account,categoryId:category);
  test('unassigned money never changes account and transfers are not consumption',(){
    final account=<String,Object?>{'id':'a','currency':'USD','opening_minor':-100};
    expect(f.accountBalance(account,[expense('e',500)],[]),BigInt.from(-100));
    expect(f.accountBalance(account,[expense('e',500,account:'a')],[{'from_account_id':'a','to_account_id':'b','sent_minor':200,'received_minor':200}]),BigInt.from(-800));
    expect(f.spending([expense('e',500)],[], 'USD',DateTime(2026,10),DateTime(2026,10,31)),BigInt.from(500));
  });
  test('splits affect category budgets once and total expense once',(){
    final r=[expense('e',1000)];final s=<Map<String,Object?>>[{'transaction_id':'e','category_id':'food','amount_minor':600},{'transaction_id':'e','category_id':'home','amount_minor':400}];
    expect(f.spending(r,s,'USD',DateTime(2026,10),DateTime(2026,10,31)),BigInt.from(1000));
    expect(f.spending(r,s,'USD',DateTime(2026,10),DateTime(2026,10,31),categories:{'food'}),BigInt.from(600));
  });
  test('negative and positive rollover follow explicit policy',(){
    for(final policy in ['none','positive','negative','both']){
      final b=<String,Object?>{'start_on':'2026-10-01','period':'month','rollover':policy,'currency':'USD','limit_minor':1000};
      expect(f.budgetRemaining(b,DateTime(2026,11,2),[expense('e',1500)],[],[]),BigInt.from(['negative','both'].contains(policy)?500:1000));
      expect(f.budgetRemaining(b,DateTime(2026,11,2),[expense('e',500)],[],[]),BigInt.from(['positive','both'].contains(policy)?1500:1000));
    }
  });
  test('invalid transfer and allocation never reach storage validation',(){
    expect(()=>OfflineValidation.validate(SaveTransfer('op','id',0,fromId:'a',toId:'a',sentMinor:1,receivedMinor:1,date:DateTime(2026))),throwsA(isA<DomainFailure>()));
    expect(()=>OfflineValidation.validateSplits([const ExpenseSplit('same',1),const ExpenseSplit('same',1)]),throwsA(isA<DomainFailure>()));
  });
}
