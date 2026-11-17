# Native privacy and accepted-release upgrade plan

Use root integration91e7cb7 as the base. Preserve SubscriptionAccess and help-center work when integrating their separate commits. No local APK build or server action.

1. Add a dedicated lifecycle authorizer and privacy panel. Fresh Google proof must use reauth/start then the existing native Google SDK and finish, never replace the login session. Password or Google proof is refreshed for each sensitive mutation; MFA remains mandatory. Deletion and family closure require impact disclosure and typed confirmation; transfers name the recipient and require their separate acceptance. Staff blockers lead to existing support rather than silent role removal.
2. Project privacy-erased records into minimal raw tombstones. Keep deleted-account currency-only references outside active lists, balances, pickers and editors. Show surviving transfers read-only with their own unchanged amounts/date and correct live/tombstone currencies. Purge explicit privacy-erased queued payloads and block replay/restore; preserve normal revocation recovery semantics.
3. Extend the signed emulator chain134001→303001→accepted312001→candidate without uninstall/data clear. Pin the accepted APK's exact digest, verify task+finance at312, create a new312 task, then require both tasks after candidate restarts. Coordinate proof fields with operator native_evidence.py and retain the existing signed CI step label.

Checks: targeted authorizer/widget/controller/sync/finance tests;16locale key completeness; Flutter analyzer; release-proof parser tests. Real direct upgrade evidence must come from the signed CI emulator run, not generated screenshots or a local APK build.
