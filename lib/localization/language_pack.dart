import 'dart:convert';

import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart';

class LanguagePack {
  LanguagePack._(this.tag, this.name, this.strings, this.plurals);
  final String tag;
  final String name;
  final Map<String, String> strings;
  final Map<String, Map<String, String>> plurals;
  Locale get locale {
    final parts = tag.split('-');
    return Locale.fromSubtags(languageCode: parts.first,
      scriptCode: parts.length > 1 && parts[1].length == 4 ? parts[1] : null);
  }

  factory LanguagePack.decode(String source) {
    final data = jsonDecode(source) as Map<String, dynamic>;
    if (data['schemaVersion'] != 1 || data['packVersion'] is! int || data['packVersion'] < 1) {
      throw const FormatException('Incompatible language pack');
    }
    return LanguagePack._(data['locale'] as String, data['nativeName'] as String,
      Map<String, String>.from(data['strings'] as Map),
      {for (final entry in (data['plurals'] as Map<String, dynamic>).entries)
        entry.key: Map<String, String>.from(entry.value as Map)});
  }

  String t(String key) => strings[key] ?? key;
  String count(String key, int value) {
    final forms = plurals[key]!;
    final result = Intl.plural(value, zero: forms['zero'], one: forms['one'],
      two: forms['two'], few: forms['few'], many: forms['many'], other: forms['other']!,
      locale: locale.languageCode);
    return result.replaceAll('{count}', value.toString());
  }
}

class PackCatalog {
  PackCatalog(this.packs);
  final Map<String, LanguagePack> packs;
  static Future<PackCatalog> load() async {
    final manifest = await AssetManifest.loadFromAssetBundle(rootBundle);
    final paths = manifest.listAssets().where((p) => p.startsWith('assets/locales/') && p.endsWith('.json')).toList()..sort();
    final packs = <String, LanguagePack>{};
    for (final path in paths) {
      final pack = LanguagePack.decode(await rootBundle.loadString(path));
      if (packs.containsKey(pack.tag)) throw const FormatException('Duplicate locale');
      packs[pack.tag] = pack;
    }
    final base = packs['en'];
    if (base == null) throw const FormatException('Missing fallback language');
    // Runtime fallback is explicit; CI requires complete packs.
    for (final pack in packs.values) {
      for (final entry in base.strings.entries) { pack.strings.putIfAbsent(entry.key, () => entry.value); }
      for (final entry in base.plurals.entries) { pack.plurals.putIfAbsent(entry.key, () => entry.value); }
    }
    return PackCatalog(packs);
  }

  LanguagePack resolve(String? tag) {
    if (tag != null && packs.containsKey(tag)) return packs[tag]!;
    final language = tag?.split(RegExp('[-_]')).first;
    return packs[language] ?? packs.values.where((p) => p.locale.languageCode == language).firstOrNull ?? packs['en']!;
  }
}

// Some launch languages do not yet have Flutter's built-in Material translations.
// App text always uses the selected pack; built-in picker text falls back to English.
class MaterialFallbackDelegate extends LocalizationsDelegate<MaterialLocalizations> {
  const MaterialFallbackDelegate();
  @override
  bool isSupported(Locale locale) => true;
  @override
  Future<MaterialLocalizations> load(Locale locale) => GlobalMaterialLocalizations.delegate.load(
    GlobalMaterialLocalizations.delegate.isSupported(locale) ? locale : const Locale('en'));
  @override
  bool shouldReload(MaterialFallbackDelegate old) => false;
}

class WidgetsFallbackDelegate extends LocalizationsDelegate<WidgetsLocalizations> {
  const WidgetsFallbackDelegate();
  @override
  bool isSupported(Locale locale) => true;
  @override
  Future<WidgetsLocalizations> load(Locale locale) => GlobalWidgetsLocalizations.delegate.load(
    GlobalWidgetsLocalizations.delegate.isSupported(locale) ? locale : const Locale('en'));
  @override
  bool shouldReload(WidgetsFallbackDelegate old) => false;
}

class CupertinoFallbackDelegate extends LocalizationsDelegate<CupertinoLocalizations> {
  const CupertinoFallbackDelegate();
  @override
  bool isSupported(Locale locale) => true;
  @override
  Future<CupertinoLocalizations> load(Locale locale) => GlobalCupertinoLocalizations.delegate.load(
    GlobalCupertinoLocalizations.delegate.isSupported(locale) ? locale : const Locale('en'));
  @override
  bool shouldReload(CupertinoFallbackDelegate old) => false;
}
