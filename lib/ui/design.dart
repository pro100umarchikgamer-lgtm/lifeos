import 'dart:math' as math;
import 'package:flutter/material.dart';

class LifePalette {
  static const green = Color(0xff08745a);
  static const darkGreen = Color(0xff075b49);
  static const mint = Color(0xffe1f3ee);
  static const red = Color(0xffe9505d);
  static const rose = Color(0xfffeeff0);
  static const blue = Color(0xff367edd);
  static const ice = Color(0xffeaf3ff);
  static const orange = Color(0xffea921c);
  static const cream = Color(0xfffff4e5);
  static const ink = Color(0xff18232b);
  static const muted = Color(0xff77838d);
  static const background = Color(0xfff5f8f8);
  static const darkBackground = Color(0xff101a1c);
  static const darkSurface = Color(0xff1c2a2d);
}

ThemeData lifeTheme(Brightness brightness) {
  final dark = brightness == Brightness.dark;
  final scheme = ColorScheme.fromSeed(
    seedColor: LifePalette.green,
    brightness: brightness,
    primary: dark ? const Color(0xff69d0ae) : LifePalette.green,
    surface: dark ? LifePalette.darkSurface : Colors.white,
  );
  return ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: scheme,
    scaffoldBackgroundColor: dark ? LifePalette.darkBackground : LifePalette.background,
    textTheme: ThemeData(brightness: brightness).textTheme.apply(
      bodyColor: dark ? const Color(0xffebf3f0) : LifePalette.ink,
      displayColor: dark ? const Color(0xffebf3f0) : LifePalette.ink,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: dark ? const Color(0xff25363a) : const Color(0xfff8fbfa),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide(color: scheme.primary)),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
    ),
    filledButtonTheme: FilledButtonThemeData(style: FilledButton.styleFrom(
      minimumSize: const Size(48, 52), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)))),
  );
}

class LifeCard extends StatelessWidget {
  const LifeCard({super.key, required this.child, this.padding = const EdgeInsets.all(16)});
  final Widget child;
  final EdgeInsets padding;
  @override
  Widget build(BuildContext context) => Container(
    padding: padding,
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surface,
      borderRadius: BorderRadius.circular(20),
      boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: Theme.of(context).brightness == Brightness.dark ? .14 : .045), blurRadius: 20, offset: const Offset(0, 6))],
    ),
    child: child,
  );
}

class KindColors {
  const KindColors(this.foreground, this.background);
  final Color foreground;
  final Color background;
}

class WelcomeLandscape extends StatelessWidget {
  const WelcomeLandscape({super.key});
  @override
  Widget build(BuildContext context) => ClipRRect(
    borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
    child: SizedBox(height: 104, width: double.infinity,
      child: CustomPaint(painter: _LandscapePainter(Theme.of(context).brightness == Brightness.dark))),
  );
}

class _LandscapePainter extends CustomPainter {
  const _LandscapePainter(this.dark);
  final bool dark;
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    canvas.drawRect(Offset.zero & size, Paint()..shader = LinearGradient(
      colors: dark ? [const Color(0xff294f56), const Color(0xff385952)] : [const Color(0xffd9f3f1), const Color(0xfffff3d9)],
      begin: Alignment.topLeft, end: Alignment.bottomRight).createShader(Offset.zero & size));
    canvas.drawCircle(Offset(w * .64, h * .44), 19, Paint()..color = dark ? const Color(0xffffd290) : const Color(0xffffe49a));
    void hill(Color color, List<Offset> points) {
      final path = Path()..moveTo(0, h);
      for (final point in points) { path.lineTo(point.dx, point.dy); }
      path..lineTo(w, h)..close();
      canvas.drawPath(path, Paint()..color = color);
    }
    hill(dark ? const Color(0xff417c75) : const Color(0xffb9e3d9), [Offset(0, h * .61), Offset(w * .12, h * .72), Offset(w * .25, h * .47), Offset(w * .46, h * .8), Offset(w * .7, h * .53), Offset(w, h * .68)]);
    hill(dark ? const Color(0xff27695c) : const Color(0xff80c8ae), [Offset(0, h * .91), Offset(w * .23, h * .79), Offset(w * .42, h * .88), Offset(w * .68, h * .43), Offset(w * .83, h * .83), Offset(w, h * .58)]);
    hill(dark ? const Color(0xff155145) : const Color(0xff3eab85), [Offset(0, h * .93), Offset(w * .39, h * .87), Offset(w * .61, h * .97), Offset(w * .84, h * .48), Offset(w, h * .82)]);
    final tree = Paint()..color = dark ? const Color(0xff113f38) : const Color(0xff26886e);
    for (final x in [.72, .79, .91, .97]) {
      final px = w * x, y = h * (.65 + (x % .09));
      canvas.drawPath(Path()..moveTo(px, y - 22)..lineTo(px - 11, y + 10)..lineTo(px + 11, y + 10)..close(), tree);
    }
    final houseX = w * .85, houseY = h * .74;
    canvas.drawRect(Rect.fromLTWH(houseX, houseY, 23, 17), Paint()..color = const Color(0xffffeccd));
    canvas.drawPath(Path()..moveTo(houseX - 4, houseY)..lineTo(houseX + 11, houseY - 12)..lineTo(houseX + 27, houseY)..close(), Paint()..color = const Color(0xff76695a));
    canvas.drawRect(Rect.fromLTWH(houseX + 9, houseY + 7, 5, 10), Paint()..color = const Color(0xff846b5c));
    canvas.drawRect(Rect.fromLTWH(0, h - 6, w, 6), Paint()..color = dark ? const Color(0xff246e58) : const Color(0xff6cc499));
  }
  @override
  bool shouldRepaint(covariant _LandscapePainter oldDelegate) => oldDelegate.dark != dark;
}

class DailyBarChart extends StatelessWidget {
  const DailyBarChart({super.key, required this.income, required this.expense});
  final List<BigInt> income;
  final List<BigInt> expense;
  @override
  Widget build(BuildContext context) {
    final maxValue = [...income, ...expense].fold<BigInt>(BigInt.one, (a,b) => a > b ? a : b);
    final dark = Theme.of(context).brightness == Brightness.dark;
    return SizedBox(height: 72, child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
      for (var i = 0; i < income.length; i++) Expanded(child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 1),
        child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Expanded(child: _bar(income[i], maxValue, dark ? const Color(0xff68cdaa) : const Color(0xff53c3a4))),
          const SizedBox(width: 1),
          Expanded(child: _bar(expense[i], maxValue, dark ? const Color(0xfff18791) : LifePalette.red)),
        ]),
      )),
    ]));
  }
  Widget _bar(BigInt value, BigInt maxValue, Color color) => value == BigInt.zero ? const SizedBox.shrink() :
    Container(height: math.max(2, value.toDouble() / maxValue.toDouble() * 64), decoration: BoxDecoration(color: color, borderRadius: const BorderRadius.vertical(top: Radius.circular(3))));
}
