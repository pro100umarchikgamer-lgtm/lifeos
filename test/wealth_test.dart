import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/domain/wealth_engine.dart';
import 'package:lifeos/domain/models.dart';
void main(){
  const w=WealthEngine();
  test('earmarks and principal exclude fees and interest',(){
    expect(w.savings('g',[{'goal_id':'g','amount_minor':1000},{'goal_id':'g','amount_minor':-250}]),BigInt.from(750));
    expect(w.principal({'id':'d','principal_minor':1000},[{'debt_id':'d','flow':'repay','principal_minor':200,'interest_minor':90,'fee_minor':10}]),BigInt.from(800));
  });
  Map<String,Object?> entry(String id,String kind,int qty,int cash,{int fee=0})=>{'id':id,'asset_id':'a','kind':kind,'quantity_micros':qty,'cash_minor':cash,'fee_minor':fee,'occurred_on':'2026-10-11','created_at':id};
  test('FIFO conserves integer cost and separates gains and cash distributions',(){
    final result=w.investment('a',[entry('1','buy',3000000,1000,fee:1),entry('2','sell',1000000,500,fee:10),entry('3','dividend',0,90),entry('4','valuation',0,900)]);
    expect(result.quantityMicros,BigInt.from(2000000));expect(result.costMinor,BigInt.from(668));expect(result.realizedMinor,BigInt.from(157));expect(result.unrealizedMinor,BigInt.from(232));expect(result.distributionsMinor,BigInt.from(90));
    expect(w.investment('a',[entry('1','buy',3000000,1001),entry('2','sell',1000000,500),entry('3','sell',2000000,600)]).costMinor,BigInt.zero);
  });
  test('sale before acquisition is rejected',(){expect(()=>w.investment('a',[entry('1','sell',1,100)]),throwsA(isA<DomainFailure>()));});
}
