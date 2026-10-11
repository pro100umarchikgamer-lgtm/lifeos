import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/domain/appearance.dart';
import 'package:lifeos/ui/design.dart';

void main() {
  test('versioned appearance round-trips and rejects damaged preferences', () {
    const appearance = Appearance(palette: 'pistachio', shape: 'rounded', surface: 'outlined', mode: 'dark', dynamic: true);
    expect(Appearance.decode(appearance.encode()).encode(), appearance.encode());
    final invalid = jsonDecode(appearance.encode()) as Map<String, dynamic>;
    for (final bad in [ {...invalid, 'version': 2}, {...invalid, 'shape': 'unknown'},
      {...invalid, 'dynamic': 'true'}, {...invalid, 'mode': 'unknown'}, {...invalid, 'extra': 1}]) {
      expect(() => Appearance.decode(jsonEncode(bad)), throwsFormatException);
    }
    expect(Appearance.decode(null).palette, 'emerald');
  });
  test('all palettes use accessible primary and surface text roles', () {
    double contrast(Color a, Color b) {
      final x = a.computeLuminance(), y = b.computeLuminance();
      return (x > y ? x + .05 : y + .05) / (x > y ? y + .05 : x + .05);
    }
    for (final palette in Appearance.palettes) {
      for (final brightness in Brightness.values) {
        final theme = lifeTheme(brightness, appearance: Appearance(palette: palette));
        final colors = theme.colorScheme;
        expect(contrast(colors.onPrimary, colors.primary), greaterThanOrEqualTo(4.5));
        expect(contrast(colors.onSurface, colors.surface), greaterThanOrEqualTo(4.5));
        expect(contrast(colors.onSurface, colors.surfaceContainerLow), greaterThanOrEqualTo(4.5));
      }
    }
  });
  test('wallpaper fallback is deterministic and presets are reused by cards', () {
    final fallback = lifeTheme(Brightness.light, appearance: const Appearance(dynamic: true, palette: 'sky'));
    final fixed = lifeTheme(Brightness.light, appearance: const Appearance(palette: 'sky'));
    expect(fallback.colorScheme, fixed.colorScheme);
    expect(lifeTheme(Brightness.light, appearance: const Appearance(shape: 'rounded')).extension<LifeSurfaces>()!.radius, 28);
  });
}
