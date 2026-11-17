import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/domain/appearance.dart';
import 'package:lifeos/ui/design.dart';

void main() {
  test('versioned appearance round-trips and rejects damaged preferences', () {
    const appearance = Appearance(
        palette: 'pistachio',
        shape: 'rounded',
        surface: 'outlined',
        mode: 'dark',
        dynamic: true);
    expect(
        Appearance.decode(appearance.encode()).encode(), appearance.encode());
    final invalid = jsonDecode(appearance.encode()) as Map<String, dynamic>;
    for (final bad in [
      {...invalid, 'version': 2},
      {...invalid, 'shape': 'unknown'},
      {...invalid, 'dynamic': 'true'},
      {...invalid, 'mode': 'unknown'},
      {...invalid, 'extra': 1}
    ]) {
      expect(() => Appearance.decode(jsonEncode(bad)), throwsFormatException);
    }
    expect(Appearance.decode(null).palette, 'violet');
    for (final palette in ['emerald', 'pistachio', 'sky', 'sand']) {
      final saved =
          Appearance(palette: palette, shape: 'rounded', surface: 'outlined');
      expect(Appearance.decode(saved.encode()).encode(), saved.encode());
    }
  });
  test('old preferences default to50 and intensity rejects damaged values', () {
    final old = {
      'version': 1,
      'palette': 'violet',
      'shape': 'balanced',
      'surface': 'soft',
      'mode': 'system',
      'dynamic': false
    };
    expect(Appearance.decode(jsonEncode(old)).intensity, 50);
    for (final invalid in [-1, 101, 1.5, '50', null]) {
      expect(
          () => Appearance.decode(jsonEncode({...old, 'intensity': invalid})),
          throwsFormatException);
    }
    for (final palette in Appearance.palettes) {
      for (final brightness in Brightness.values) {
        final low = lifeTheme(brightness,
            appearance: Appearance(palette: palette, intensity: 0));
        final high = lifeTheme(brightness,
            appearance: Appearance(palette: palette, intensity: 100));
        expect(low.colorScheme.primary, high.colorScheme.primary);
        expect(low.colorScheme.onPrimary, high.colorScheme.onPrimary);
        expect(
            low.scaffoldBackgroundColor, isNot(high.scaffoldBackgroundColor));
        expect(low.colorScheme.surface, isNot(high.colorScheme.surface));
        expect(low.inputDecorationTheme.fillColor,
            isNot(high.inputDecorationTheme.fillColor));
        for (final surface in [
          high.colorScheme.surface,
          high.colorScheme.surfaceContainerLow,
          high.colorScheme.surfaceContainerHigh,
          high.colorScheme.surfaceContainerHighest,
          high.inputDecorationTheme.fillColor!
        ]) {
          final text = high.colorScheme.onSurfaceVariant.computeLuminance();
          final fill = surface.computeLuminance();
          expect(
              (text > fill ? text + .05 : fill + .05) /
                  (text > fill ? fill + .05 : text + .05),
              greaterThanOrEqualTo(4.5),
              reason: '$palette $brightness secondary text at full intensity');
        }
        final a = high.colorScheme.onSurface.computeLuminance(),
            b = high.scaffoldBackgroundColor.computeLuminance();
        expect((a > b ? a + .05 : b + .05) / (a > b ? b + .05 : a + .05),
            greaterThanOrEqualTo(4.5));
      }
    }
  });
  test('all palettes use accessible primary and surface text roles', () {
    double contrast(Color a, Color b) {
      final x = a.computeLuminance(), y = b.computeLuminance();
      return (x > y ? x + .05 : y + .05) / (x > y ? y + .05 : x + .05);
    }

    for (final palette in Appearance.palettes) {
      for (final brightness in Brightness.values) {
        final theme =
            lifeTheme(brightness, appearance: Appearance(palette: palette));
        final colors = theme.colorScheme;
        expect(contrast(colors.onPrimary, colors.primary),
            greaterThanOrEqualTo(4.5));
        expect(contrast(colors.onSurface, colors.surface),
            greaterThanOrEqualTo(4.5));
        expect(contrast(colors.onSurface, colors.surfaceContainerLow),
            greaterThanOrEqualTo(4.5));
      }
    }
  });
  test('wallpaper fallback is deterministic and presets are reused by cards',
      () {
    final fallback = lifeTheme(Brightness.light,
        appearance: const Appearance(dynamic: true, palette: 'sky'));
    final fixed = lifeTheme(Brightness.light,
        appearance: const Appearance(palette: 'sky'));
    expect(fallback.colorScheme, fixed.colorScheme);
    expect(
        lifeTheme(Brightness.light,
                appearance: const Appearance(shape: 'rounded'))
            .extension<LifeSurfaces>()!
            .radius,
        28);
  });
}
