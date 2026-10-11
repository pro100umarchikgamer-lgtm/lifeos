import 'dart:convert';

/// One versioned value makes Apply atomic; previews never write preferences.
class Appearance {
  const Appearance({this.palette = 'emerald', this.shape = 'balanced',
    this.surface = 'soft', this.mode = 'system', this.dynamic = false});
  final String palette, shape, surface, mode;
  final bool dynamic;
  static const palettes = ['emerald', 'pistachio', 'sky', 'sand'];
  static const shapes = ['subtle', 'balanced', 'rounded'];
  static const surfaces = ['soft', 'tonal', 'outlined'];
  String encode() => jsonEncode({'version': 1, 'palette': palette, 'shape': shape,
    'surface': surface, 'mode': mode, 'dynamic': dynamic});
  static Appearance decode(String? encoded) {
    if (encoded == null) return const Appearance();
    final value = jsonDecode(encoded);
    if (value is! Map || value.length != 6 || value['version'] != 1 ||
        !palettes.contains(value['palette']) || !shapes.contains(value['shape']) ||
        !['system','light','dark'].contains(value['mode']) || !surfaces.contains(value['surface']) || value['dynamic'] is! bool) {
      throw const FormatException('Invalid appearance preferences');
    }
    return Appearance(palette: value['palette'] as String, shape: value['shape'] as String,
      surface: value['surface'] as String, mode: value['mode'] as String, dynamic: value['dynamic'] as bool);
  }
  Appearance copyWith({String? palette, String? shape, String? surface, String? mode, bool? dynamic}) =>
    Appearance(palette: palette ?? this.palette, shape: shape ?? this.shape,
      surface: surface ?? this.surface, mode: mode ?? this.mode, dynamic: dynamic ?? this.dynamic);
}
