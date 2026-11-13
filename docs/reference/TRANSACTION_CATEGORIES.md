# Optional cloud transaction categories

The existing transaction contract accepts an optional `category` value:
`food`, `transport`, `shopping`, `housing`, `health`, `leisure`, `education`,
`transfers`, `other`, or `null` to clear it. All existing required fields,
permissions, revisions, operation IDs, monetary units and currencies are unchanged.

PostgreSQL migration `012_transaction_categories.sql` adds one nullable checked
column. The SQLite development backend adds the same column to older databases.
Existing records stay uncategorized; no history is classified by guessing from
its description. Null values are omitted from responses to preserve the previous
shape of uncategorized records.

A legacy client can keep sending the original six transaction fields. The SQL
upsert changes only supplied columns, so omitting `category` preserves an existing
selection. A current client must send explicit `null` to clear it. Old Android
clients continue to ignore the additional optional response metadata.

The expense chart groups saved categories within one selected currency and the
current account/date/search filters. Unassigned expenses are shown separately.
Transfers between accounts keep their existing record kind and balance effects;
they are not silently reclassified as expenses. Custom categories and automatic
classification are not implemented by this extension.

Deployment retains the encrypted backup and existing migration-before-switch
sequence. The publication helper accepts only the exact reviewed backend hashes;
it does not allow arbitrary schema or authorization changes.
