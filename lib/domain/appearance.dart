import 'dart:convert';

/// One versioned value makes Apply atomic; previews never write preferences.
class Appearance {
  const Appearance(
      {this.palette = 'violet',
      this.shape = 'balanced',
      this.surface = 'soft',
      this.mode = 'system',
      this.dynamic = false,
      this.intensity = 50});
  final String palette, shape, surface, mode;
  final bool dynamic;
  final int intensity;
  static const palettes = [
    'violet',
    'emerald',
    'pistachio',
    'sky',
    'sand',
    'slate',
    'ink',
    'moss'
  ];
  static const shapes = ['subtle', 'balanced', 'rounded'];
  static const surfaces = ['soft', 'tonal', 'outlined'];
  String encode() => jsonEncode({
        'version': 1,
        'palette': palette,
        'shape': shape,
        'surface': surface,
        'mode': mode,
        'dynamic': dynamic,
        'intensity': intensity
      });
  static Appearance decode(String? encoded) {
    if (encoded == null) return const Appearance();
    final value = jsonDecode(encoded);
    if (value is! Map ||
        !{6, 7}.contains(value.length) ||
        value.keys.any((key) => !{
              'version',
              'palette',
              'shape',
              'surface',
              'mode',
              'dynamic',
              'intensity'
            }.contains(key)) ||
        value['version'] != 1 ||
        (value.containsKey('intensity') &&
            (value['intensity'] is! int ||
                value['intensity'] < 0 ||
                value['intensity'] > 100)) ||
        !palettes.contains(value['palette']) ||
        !shapes.contains(value['shape']) ||
        !['system', 'light', 'dark'].contains(value['mode']) ||
        !surfaces.contains(value['surface']) ||
        value['dynamic'] is! bool) {
      throw const FormatException('Invalid appearance preferences');
    }
    return Appearance(
        palette: value['palette'] as String,
        shape: value['shape'] as String,
        surface: value['surface'] as String,
        mode: value['mode'] as String,
        dynamic: value['dynamic'] as bool,
        intensity: value['intensity'] as int? ?? 50);
  }

  Appearance copyWith(
          {String? palette,
          String? shape,
          String? surface,
          String? mode,
          bool? dynamic,
          int? intensity}) =>
      Appearance(
          palette: palette ?? this.palette,
          shape: shape ?? this.shape,
          surface: surface ?? this.surface,
          mode: mode ?? this.mode,
          dynamic: dynamic ?? this.dynamic,
          intensity: intensity ?? this.intensity);
}
