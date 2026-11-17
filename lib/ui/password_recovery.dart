import 'package:flutter/material.dart';
import '../localization/language_pack.dart';
import '../sync/controller.dart';
import 'settings_surfaces.dart';

/// Uses the existing recovery protocol; a Google account does not need an old password.
class PasswordRecoveryPage extends StatefulWidget {
  const PasswordRecoveryPage(
      {super.key, required this.controller, required this.pack});
  final FamilyController controller;
  final LanguagePack pack;
  @override
  State<PasswordRecoveryPage> createState() => _PasswordRecoveryPageState();
}

class _PasswordRecoveryPageState extends State<PasswordRecoveryPage> {
  FamilyController get c => widget.controller;
  late final AccountPrincipal principal;
  late final String origin;
  late final TextEditingController email;
  final code = TextEditingController(), password = TextEditingController();
  bool sent = false;
  String t(String key) => widget.pack.t(key);
  @override
  void initState() {
    super.initState();
    principal = c.capturePrincipal();
    origin = c.accountOrigin;
    email = TextEditingController(text: c.account?['email'] as String? ?? '');
    c.addListener(clearUnavailable);
  }

  void clearUnavailable() {
    if (!c.isCurrentPrincipal(principal)) {
      email.clear();
      code.clear();
      password.clear();
    }
  }

  @override
  void dispose() {
    c.removeListener(clearUnavailable);
    email.dispose();
    code.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> send() async {
    if (!c.isCurrentPrincipal(principal) || c.busy) return;
    await c.recover(origin, email.text.trim());
    if (mounted && c.isCurrentPrincipal(principal) && c.error == null) {
      setState(() => sent = true);
    }
  }

  Future<void> reset() async {
    if (!c.isCurrentPrincipal(principal) || c.busy) return;
    await c.resetPassword(
        origin, email.text.trim(), code.text.trim(), password.text);
    if (!mounted || !c.isCurrentPrincipal(principal) || c.error != null) return;
    password.clear();
    code.clear();
    // Reset revokes sessions server-side; reuse the existing local sign-out path.
    await c.signOut();
    if (mounted) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
      listenable: c,
      builder: (context, _) {
        final available = c.isCurrentPrincipal(principal);
        return Scaffold(
            appBar: settingsAppBar(context, t('family_recovery')),
            body: SafeArea(
                child: !available
                    ? Center(child: Text(t('privacy_record_unavailable')))
                    : ListView(
                        padding: settingsPagePadding(context),
                        children: [
                            Text(t('account_google_password_first')),
                            const SizedBox(height: 16),
                            Text(t('family_recovery_hint')),
                            const SizedBox(height: 24),
                            TextField(
                                controller: email,
                                keyboardType: TextInputType.emailAddress,
                                decoration: InputDecoration(
                                    labelText: t('family_email'))),
                            const SizedBox(height: 16),
                            OutlinedButton(
                                onPressed: c.busy ? null : send,
                                child: Text(t('family_recovery_send'))),
                            if (sent)
                              Padding(
                                  padding:
                                      const EdgeInsets.symmetric(vertical: 12),
                                  child: Text(t('account_done'))),
                            const SizedBox(height: 16),
                            TextField(
                                controller: code,
                                autofillHints: const [
                                  AutofillHints.oneTimeCode
                                ],
                                decoration: InputDecoration(
                                    labelText: t('family_code'))),
                            const SizedBox(height: 16),
                            TextField(
                                controller: password,
                                obscureText: true,
                                autofillHints: const [
                                  AutofillHints.newPassword
                                ],
                                decoration: InputDecoration(
                                    labelText: t('family_new_password'))),
                            const SizedBox(height: 24),
                            FilledButton(
                                onPressed: c.busy ? null : reset,
                                child: Text(t('family_recovery_reset'))),
                            if (c.error != null)
                              Padding(
                                  padding: const EdgeInsets.only(top: 16),
                                  child: Text(t('family_error_${c.error}'))),
                          ])));
      });
}
