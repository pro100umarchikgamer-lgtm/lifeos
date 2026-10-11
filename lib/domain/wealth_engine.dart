import 'models.dart';
class InvestmentSummary {
  const InvestmentSummary(this.quantityMicros,this.costMinor,this.realizedMinor,this.distributionsMinor,this.valuationMinor);
  final BigInt quantityMicros,costMinor,realizedMinor,distributionsMinor;
  final BigInt? valuationMinor;
  BigInt? get unrealizedMinor=>valuationMinor==null?null:valuationMinor!-costMinor;
}
class WealthEngine {
  const WealthEngine();
  BigInt savings(String id,List<Map<String,Object?>> entries)=>entries.where((e)=>e['goal_id']==id&&e['deleted_at']==null).fold(BigInt.zero,(sum,e)=>sum+BigInt.from(e['amount_minor'] as int));
  BigInt principal(Map<String,Object?> debt,List<Map<String,Object?>> entries)=>entries.where((e)=>e['debt_id']==debt['id']&&e['deleted_at']==null).fold(BigInt.from(debt['principal_minor'] as int),(sum,e)=>sum+BigInt.from(e['principal_minor'] as int)*(e['flow']=='advance'?BigInt.one:-BigInt.one));
  /// FIFO cost basis. Integer division preserves all remaining cost in the lot.
  InvestmentSummary investment(String id,List<Map<String,Object?>> source) {
    final entries=source.where((e)=>e['asset_id']==id&&e['deleted_at']==null).toList()..sort((a,b){
      final date=(a['occurred_on'] as String).compareTo(b['occurred_on'] as String);if(date!=0)return date;
      final at=DateTime.parse(a['created_at'] as String).compareTo(DateTime.parse(b['created_at'] as String));return at!=0?at:(a['id'] as String).compareTo(b['id'] as String);
    });
    final lots=<List<BigInt>>[];var realized=BigInt.zero,distributions=BigInt.zero;var head=0;BigInt? valuation;
    for(final e in entries) {
      final cash=BigInt.from(e['cash_minor'] as int),fee=BigInt.from(e['fee_minor'] as int),qty=BigInt.from(e['quantity_micros'] as int);
      switch(e['kind']) {
        case 'buy': lots.add([qty,cash+fee]);valuation=null;
        case 'sell':
          var left=qty,cost=BigInt.zero;
          while(left>BigInt.zero) {
            if(head>=lots.length)throw const DomainFailure('position_short');
            final lot=lots[head],take=left<lot[0]?left:lot[0],allocated=lot[1]*take~/lot[0];
            cost+=allocated;left-=take;lot[0]-=take;lot[1]-=allocated;if(lot[0]==BigInt.zero)head++;
          }
          realized+=cash-fee-cost;valuation=null;
        case 'dividend'||'distribution':distributions+=cash-fee;
        case 'valuation':valuation=cash;
        default:throw const DomainFailure('invalid_action');
      }
    }
    return InvestmentSummary(lots.fold(BigInt.zero,(s,l)=>s+l[0]),lots.fold(BigInt.zero,(s,l)=>s+l[1]),realized,distributions,valuation);
  }
}
