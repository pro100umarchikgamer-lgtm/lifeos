part of 'local_store.dart';
extension ImportPersistence on LocalStore {
  Future<String> _applyImport(sql.Transaction tx,OfflineAction action,String now) async {
    if(action is ConfirmImport) {
      final prior=await tx.query('import_batches',where:'content_key=? AND owner_id=? AND workspace_id=?',whereArgs:[action.contentKey,ownerId,workspaceId]);
      // Batch identity includes confirmed subset, mapping and account. Reversed batches remain deduplicated.
      if(prior.isNotEmpty)return prior.single['id'] as String;
      final account=action.accountId==null?null:await _scoped(tx,'accounts',action.accountId!);
      await _writeEntity(tx,'import_batches',action,{'content_key':action.contentKey,'row_count':action.rows.length},now);
      for(final row in action.rows) {
        if(account!=null&&account['currency']!=row.currency)throw const DomainFailure('currency_mismatch');
        if((await tx.query('import_rows',columns:['origin_key'],where:'origin_key=?',whereArgs:[row.originKey],limit:1)).isNotEmpty)throw const DomainFailure('import_already_selected');
        final duplicates=await tx.query('transactions',columns:['id'],where:'owner_id=? AND workspace_id=? AND kind=? AND amount_minor=? AND currency=? AND occurred_on=? AND label=? AND deleted_at IS NULL',whereArgs:[ownerId,workspaceId,row.kind.name,row.amountMinor,row.currency,row.date,row.label.trim()],limit:1);
        if(duplicates.isNotEmpty&&!row.allowDuplicate)throw const DomainFailure('import_duplicate');
        final id=LocalStore._uuid.v4();
        await tx.insert('transactions',{'id':id,'owner_id':ownerId,'workspace_id':workspaceId,'kind':row.kind.name,'amount_minor':row.amountMinor,'currency':row.currency,'minor_digits':Currency.fromCode(row.currency).digits,'occurred_on':row.date,'label':row.label.trim(),'account_id':action.accountId,'created_at':now,'updated_at':now});
        await tx.insert('import_rows',{'origin_key':row.originKey,'batch_id':action.id,'fingerprint':await importDigest(row.canonical),'transaction_id':id});
      }
    }else if(action is ReverseImport) {
      final batch=await _scoped(tx,'import_batches',action.id);
      if(batch['revision']!=action.expectedRevision)throw const DomainFailure('revision_conflict');
      for(final row in await tx.query('import_rows',where:'batch_id=?',whereArgs:[action.id])) {
        final money=await _scoped(tx,'transactions',row['transaction_id'] as String);
        if(money['revision']!=row['imported_revision'])throw const DomainFailure('import_edited');
        // One atomic batch journal is authoritative. Edited or otherwise linked money cannot be removed silently.
        await tx.update('transactions',{'deleted_at':now,'updated_at':now,'revision':2},where:'id=? AND revision=1',whereArgs:[money['id']]);
      }
      await _validateWealth(tx);
      await _writeEntity(tx,'import_batches',action,{'deleted_at':now},now);
    }else{throw const DomainFailure('invalid_action');}
    return action.id;
  }
}
