part of 'local_store.dart';
extension WealthPersistence on LocalStore {
  Future<void> _linkedCash(sql.Transaction tx,String? id,String currency,BigInt amount,String kind,{String? owner,String? space}) async {
    if(id==null)return;final row=await _scoped(tx,'transactions',id,deleted:true,owner:owner,space:space);
    if(row['deleted_at']!=null||row['currency']!=currency||row['kind']!=kind||BigInt.from(row['amount_minor'] as int)!=amount)throw const DomainFailure('cash_link_mismatch');
  }
  Future<void> _preserveWealthCurrency(sql.Transaction tx,String table,String entries,String foreignId,OfflineAction action,String currency) async {
    if(action.expectedRevision==0)return;final old=await _scoped(tx,table,action.id);
    if(old['currency']!=currency&&(await tx.query(entries,columns:['id'],where:'$foreignId=?',whereArgs:[action.id],limit:1)).isNotEmpty)throw const DomainFailure('currency_mismatch');
  }
  Future<void> _applyWealth(sql.Transaction tx,OfflineAction action,String now) async {
    switch(action) {
      case SaveGoal():
        await _preserveWealthCurrency(tx,'savings_goals','savings_entries','goal_id',action,action.currency);
        if(action.accountId!=null&&(await _scoped(tx,'accounts',action.accountId!))['currency']!=action.currency)throw const DomainFailure('currency_mismatch');
        await _writeEntity(tx,'savings_goals',action,{'name':action.name.trim(),'currency':action.currency,'target_minor':action.targetMinor,'target_on':action.targetOn==null?null:dateOnly(action.targetOn!),'account_id':action.accountId},now);
      case SaveGoalEntry():
        await _scoped(tx,'savings_goals',action.goalId);
        await _writeEntity(tx,'savings_entries',action,{'goal_id':action.goalId,'amount_minor':action.amountMinor,'occurred_on':dateOnly(action.date),'transaction_id':action.transactionId,'transfer_id':action.transferId},now);
      case SaveDebt():
        await _preserveWealthCurrency(tx,'debts','debt_entries','debt_id',action,action.currency);
        final old=action.expectedRevision==0?null:await _scoped(tx,'debts',action.id);
        final calendar=old?['calendar_id'] as String? ?? (action.schedule==null?null:LocalStore._uuid.v4());
        if(action.schedule!=null) {
          final prior=old?['calendar_id']==null?null:await _scoped(tx,'calendar_entries',calendar!);
          await _saveCalendar(tx,calendar!,action.name,action.schedule!,now,expectedRevision:prior?['revision'] as int?);
        } else if(old?['calendar_id']!=null) {
          final prior=await _scoped(tx,'calendar_entries',calendar!);
          await tx.update('calendar_entries',{'deleted_at':now,'updated_at':now,'revision':(prior['revision'] as int)+1},where:'id=?',whereArgs:[calendar]);
        }
        await _writeEntity(tx,'debts',action,{'name':action.name.trim(),'currency':action.currency,'principal_minor':action.principalMinor,'direction':action.direction,'calendar_id':action.schedule==null?null:calendar},now);
      case SaveDebtEntry():
        await _scoped(tx,'debts',action.debtId);
        await _writeEntity(tx,'debt_entries',action,{'debt_id':action.debtId,'flow':action.flow,'principal_minor':action.principalMinor,'interest_minor':action.interestMinor,'fee_minor':action.feeMinor,'occurred_on':dateOnly(action.date),'transaction_id':action.transactionId},now);
      case SaveAsset():await _preserveWealthCurrency(tx,'investment_assets','investment_entries','asset_id',action,action.currency);await _writeEntity(tx,'investment_assets',action,{'name':action.name.trim(),'currency':action.currency},now);
      case SaveInvestmentEntry():
        await _scoped(tx,'investment_assets',action.assetId);
        await _writeEntity(tx,'investment_entries',action,{'asset_id':action.assetId,'kind':action.kind,'quantity_micros':action.quantityMicros,'cash_minor':action.cashMinor,'fee_minor':action.feeMinor,'occurred_on':dateOnly(action.date),'transaction_id':action.transactionId},now);
      default:throw const DomainFailure('invalid_action');
    }
  }
  Future<void> _validateWealth(sql.Transaction tx,{String? owner,String? space}) async {
    for(final row in await tx.query('savings_goals')) {
      if(row['account_id']!=null&&(await _scoped(tx,'accounts',row['account_id'] as String,deleted:true,owner:owner,space:space))['currency']!=row['currency'])throw const DomainFailure('currency_mismatch');
    }
    for(final row in await tx.query('savings_entries',where:'deleted_at IS NULL')) {
      final goal=await _scoped(tx,'savings_goals',row['goal_id'] as String,deleted:true,owner:owner,space:space);
      final value=row['amount_minor'] as int;
      await _linkedCash(tx,row['transaction_id'] as String?,goal['currency'] as String,BigInt.from(value.abs()),value>0?'income':'expense',owner:owner,space:space);
      if(row['transaction_id']!=null&&goal['account_id']!=null&&(await _scoped(tx,'transactions',row['transaction_id'] as String,deleted:true,owner:owner,space:space))['account_id']!=goal['account_id'])throw const DomainFailure('cash_link_mismatch');
      if(row['transfer_id']!=null) {
        final transfer=await _scoped(tx,'transfers',row['transfer_id'] as String,deleted:true,owner:owner,space:space);
        if(transfer['deleted_at']!=null||goal['account_id']==null||(value>0?transfer['to_account_id']:transfer['from_account_id'])!=goal['account_id']||(value>0?transfer['received_minor']:transfer['sent_minor'])!=value.abs())throw const DomainFailure('cash_link_mismatch');
      }
    }
    for(final row in await tx.query('debt_entries',where:'deleted_at IS NULL')) {
      final debt=await _scoped(tx,'debts',row['debt_id'] as String,deleted:true,owner:owner,space:space);
      final amount=BigInt.from(row['principal_minor'] as int)+BigInt.from(row['interest_minor'] as int)+BigInt.from(row['fee_minor'] as int);
      final income=(debt['direction']=='owing')==(row['flow']=='advance');
      await _linkedCash(tx,row['transaction_id'] as String?,debt['currency'] as String,amount,income?'income':'expense',owner:owner,space:space);
    }
    final movements=[for(final r in await tx.query('investment_entries',where:'deleted_at IS NULL'))Map<String,Object?>.from(r)];
    for(final row in movements) {
      final asset=await _scoped(tx,'investment_assets',row['asset_id'] as String,deleted:true,owner:owner,space:space);
      if(row['kind']=='valuation'&&row['transaction_id']!=null)throw const DomainFailure('cash_link_mismatch');
      final gross=BigInt.from(row['cash_minor'] as int),fee=BigInt.from(row['fee_minor'] as int),buy=row['kind']=='buy';
      await _linkedCash(tx,row['transaction_id'] as String?,asset['currency'] as String,buy?gross+fee:gross-fee,buy?'expense':'income',owner:owner,space:space);
    }
    for(final asset in await tx.query('investment_assets')) { const WealthEngine().investment(asset['id'] as String,movements); }
  }
}
