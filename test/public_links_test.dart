import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/domain/public_links.dart';

void main() {
  test('public legal pages use the website origin without requiring an account',
      () {
    expect(publicSitePage('/privacy').toString(),
        'https://getuladim.space/privacy');
    expect(
        publicSitePage('/terms').toString(), 'https://getuladim.space/terms');
  });
  test(
      'server app links resolve against the public site with their query intact',
      () {
    expect(notificationMessageLink('/app?tab=calendar')?.toString(),
        'https://getuladim.space/app?tab=calendar');
    expect(
        notificationMessageLink('/app/notes?view=recent',
                origin: 'https://stage.example')
            ?.toString(),
        'https://stage.example/app/notes?view=recent');
    expect(notificationMessageLink('https://getuladim.space/app')?.scheme,
        'https');
  });
  test('app links reject unsafe schemes, authorities and path traversal', () {
    for (final value in [
      '//evil.example/app',
      'javascript:alert(1)',
      'http://evil.example/app',
      '/control',
      '/app/../control',
      '/app/%2e%2e/control',
      '/app%2f../control',
      '/app\\evil',
      '/app\n/evil',
      'https://user:secret@example.test/app'
    ]) {
      expect(notificationMessageLink(value), isNull, reason: value);
    }
  });
}
