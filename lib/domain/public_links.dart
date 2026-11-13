/// Public pages are served on SITE_ORIGIN, separately from the authenticated API.
/// The default is the canonical site already used by backend/config.py.
const publicSiteOrigin = String.fromEnvironment('LIFEOS_SITE_ORIGIN',
    defaultValue: 'https://getuladim.space');

Uri _site(String origin) {
  final uri = Uri.parse(origin);
  if (uri.scheme != 'https' ||
      uri.host.isEmpty ||
      uri.userInfo.isNotEmpty ||
      !['', '/'].contains(uri.path) ||
      uri.hasQuery ||
      uri.hasFragment) {
    throw const FormatException('Invalid public site origin');
  }
  return uri;
}

Uri publicSitePage(String path, {String origin = publicSiteOrigin}) =>
    _site(origin).resolve(path);

/// Match the backend's relative /app link boundary before resolving a URL.
Uri? notificationMessageLink(Object? value,
    {String origin = publicSiteOrigin}) {
  if (value is! String ||
      value.isEmpty ||
      value.length > 1000 ||
      value.runes.any((v) => v <= 32 || v == 127) ||
      value.contains('\\')) {
    return null;
  }
  try {
    final uri = Uri.parse(value);
    if (uri.isAbsolute) {
      return uri.scheme == 'https' &&
              uri.host.isNotEmpty &&
              uri.userInfo.isEmpty
          ? uri
          : null;
    }
    final decoded = Uri.decodeFull(value);
    final path = Uri.parse(decoded).path;
    if (uri.hasAuthority ||
        !(path == '/app' || path.startsWith('/app/')) ||
        path
            .split('/')
            .skip(2)
            .any((part) => part.isEmpty || part == '.' || part == '..') ||
        RegExp(r'%2f|%5c|%2e', caseSensitive: false).hasMatch(value)) {
      return null;
    }
    return _site(origin).resolveUri(uri);
  } on FormatException {
    return null;
  }
}
