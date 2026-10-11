import 'models.dart';
import 'calendar_engine.dart';

class OfflineValidation {
  static void money(int value,{bool signed=false,bool zero=false}) {
    if(value.abs()>999999999999999 || !signed && (zero?value<0:value<=0)) throw const DomainFailure('invalid_amount');
  }
  static void name(String value) { if(value.trim().isEmpty || value.length>2000) throw const DomainFailure('required_text'); }
  static void date(DateTime value) { if(value.year<1900||value.year>2200) throw const DomainFailure('invalid_date'); }
  static void validate(OfflineAction action) {
    if(action.id.isEmpty || action.expectedRevision<0) throw const DomainFailure('invalid_action');
    switch(action) {
      case SaveGoal(): name(action.name);Currency.fromCode(action.currency);money(action.targetMinor,zero:true);if(action.targetOn!=null)date(action.targetOn!);
      case SaveGoalEntry(): money(action.amountMinor,signed:true);date(action.date);if(action.amountMinor==0||action.transactionId!=null&&action.transferId!=null)throw const DomainFailure('invalid_action');
      case SaveDebt(): name(action.name);Currency.fromCode(action.currency);money(action.principalMinor,zero:true);if(!['owing','owed'].contains(action.direction))throw const DomainFailure('invalid_action');if(action.schedule!=null)CalendarEngine.validate(action.schedule!);
      case SaveDebtEntry(): money(action.principalMinor,zero:true);money(action.interestMinor,zero:true);money(action.feeMinor,zero:true);date(action.date);
        if(!['advance','repay'].contains(action.flow)||BigInt.from(action.principalMinor)+BigInt.from(action.interestMinor)+BigInt.from(action.feeMinor)==BigInt.zero)throw const DomainFailure('invalid_action');
      case SaveAsset(): name(action.name);Currency.fromCode(action.currency);
      case SaveInvestmentEntry(): money(action.cashMinor,zero:true);money(action.feeMinor,zero:true);money(action.quantityMicros,zero:true);date(action.date);
        if(!['buy','sell','dividend','distribution','valuation'].contains(action.kind)||['buy','sell'].contains(action.kind)&&action.quantityMicros==0||!['buy','sell'].contains(action.kind)&&action.quantityMicros!=0)throw const DomainFailure('invalid_action');
      case SaveAccount(): name(action.name); Currency.fromCode(action.currency); money(action.openingMinor,signed:true);
        if(!['cash','card','wallet','deposit','custom'].contains(action.kind)) throw const DomainFailure('invalid_action');
      case SaveCategory(): name(action.name); if(action.parentId==action.id) throw const DomainFailure('invalid_action');
      case SaveTransfer(): money(action.sentMinor); money(action.receivedMinor); date(action.date);
        if(action.fromId.isEmpty||action.toId.isEmpty||action.fromId==action.toId) throw const DomainFailure('invalid_action');
      case SetMoneyDetails(): if(action.expectedRevision<1) throw const DomainFailure('invalid_action'); validateSplits(action.splits);
      case SaveBudget(): name(action.name); Currency.fromCode(action.currency); money(action.limitMinor,zero:true); date(action.start);
        if(!['week','month','year','custom'].contains(action.period)||!['none','positive','negative','both'].contains(action.rollover)||
          action.period=='month'&&action.start.day!=1 || action.period=='year'&&(action.start.day!=1||action.start.month!=1)||
          action.period=='custom'&&(action.end==null||action.end!.isBefore(action.start))) throw const DomainFailure('invalid_date');
        if(action.end!=null) date(action.end!);
      case SavePlannedPayment(): name(action.name); Currency.fromCode(action.currency); money(action.amountMinor); CalendarEngine.validate(action.schedule);
        if(action.kind!=EntryKind.expense&&action.kind!=EntryKind.income) throw const DomainFailure('invalid_action');
      case ConfirmPlannedPayment(): final value=DateTime.tryParse(action.occurrence);
        if(action.expectedRevision<1||value==null||dateOnly(value)!=action.occurrence) throw const DomainFailure('invalid_date'); date(value);
      case DeleteOffline() || UndoOffline(): if(action.expectedRevision<1) throw const DomainFailure('invalid_action');
    }
  }
  static void validateSplits(List<ExpenseSplit> splits) {
    if(splits.length>100 || splits.map((s)=>s.id).toSet().length!=splits.length) throw const DomainFailure('invalid_action');
    for(final s in splits) { if(s.id.isEmpty) throw const DomainFailure('invalid_action'); money(s.amountMinor); }
  }
}
