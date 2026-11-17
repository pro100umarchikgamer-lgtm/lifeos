import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../domain/models.dart';
import '../domain/financial_period.dart';
import '../domain/financial_insights.dart';
import 'design.dart';
import 'money_format.dart';
import 'selection.dart';

class FinancialOverview extends StatefulWidget {
  const FinancialOverview({
    super.key,
    required this.controller,
    required this.period,
    required this.currency,
    required this.onCurrency,
    required this.onPeriod,
    required this.onRecord,
    required this.onAdd,
    this.compact = false,
  });
  final AppController controller;
  final FinancialPeriod period;
  final String currency;
  final ValueChanged<String> onCurrency;
  final VoidCallback onPeriod;
  final ValueChanged<Record> onRecord;
  final ValueChanged<EntryKind> onAdd;
  final bool compact;
  @override
  State<FinancialOverview> createState() => _FinancialOverviewState();
}

class _FinancialOverviewState extends State<FinancialOverview> {
  ChartGrain grain = ChartGrain.day;
  int? selected;
  String? category;
  AppController get c => widget.controller;
  String t(String key) => c.pack.t(key);
  String money(BigInt value) =>
      formatMoney(Currency.fromCode(widget.currency), value, locale: c.region);
  String date(DateTime d) =>
      MaterialLocalizations.of(context).formatShortDate(d);
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final data = FinancialInsights(
      c.records,
      widget.period,
      widget.currency,
      c.offline[OfflineTable.accounts] ?? [],
      c.offline[OfflineTable.transfers] ?? [],
      c.allocations,
    );
    final buckets = data.buckets(grain);
    final index = buckets.isEmpty
        ? null
        : selected?.clamp(0, buckets.length - 1);
    final currencies = {
      widget.currency,
      c.currency,
      ...c.records
          .where((r) => r.currency != null)
          .map((r) => r.currency!.code),
      ...(c.offline[OfflineTable.accounts] ?? []).map(
        (a) => a['currency'] as String,
      ),
    }.toList()..sort();
    final parts =
        data.categories.entries.where((e) => e.value > BigInt.zero).toList()
          ..sort((a, b) => b.value.compareTo(a.value));
    final names = {
      for (final a
          in c.offline[OfflineTable.categories] ?? <Map<String, Object?>>[])
        a['id'] as String: a['name'] as String,
    };
    String name(String id) =>
        names[id] ?? t(id.isEmpty ? 'insight_uncategorized' : 'category');
    Widget amountText(BigInt value, TextStyle? style, {Key? key}) => FittedBox(
      fit: BoxFit.scaleDown,
      alignment: AlignmentDirectional.centerStart,
      child: Text(money(value), key: key, maxLines: 1, style: style),
    );
    Widget metric(String title, BigInt value, Color color) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          t(title),
          style: Theme.of(context).textTheme.labelMedium
              ?.copyWith(color: scheme.onSurfaceVariant),
        ),
        const SizedBox(height: 4),
        amountText(
          value,
          Theme.of(context).textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: lifeAccent(context, color),
          ),
        ),
      ],
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        LifeCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              LayoutBuilder(
                builder: (context, bounds) => Wrap(
                  alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 12,
                  runSpacing: 8,
                  children: [
                    Text(
                      t(data.hasAccounts ? 'insight_balance' : 'difference'),
                      style: Theme.of(context).textTheme.labelLarge
                          ?.copyWith(color: scheme.onSurfaceVariant),
                    ),
                    SizedBox(
                      key: const Key('insight_currency'),
                      width: (112 * MediaQuery.textScalerOf(context).scale(1))
                          .clamp(112.0, bounds.maxWidth),
                      child: LifeSelect<String>(
                        label: t('currency'),
                        showLabel: false,
                        value: widget.currency,
                        choices: {for (final code in currencies) code: code},
                        dialog: true,
                        onChanged: widget.onCurrency,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              amountText(
                data.hasAccounts ? data.balance : data.income - data.expense,
                Theme.of(context).textTheme.headlineMedium
                    ?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -.6),
                key: const Key('insight_balance'),
              ),
              if (!data.hasAccounts && !widget.compact) ...[
                const SizedBox(height: 4),
                Text(
                  t('insight_no_accounts'),
                  style: Theme.of(context).textTheme.bodySmall
                      ?.copyWith(color: scheme.onSurfaceVariant),
                ),
              ],
              Align(
                alignment: AlignmentDirectional.centerStart,
                child: TextButton.icon(
                  key: const Key('financial_period'),
                  style: TextButton.styleFrom(padding: EdgeInsets.zero),
                  onPressed: widget.onPeriod,
                  icon: const Icon(Icons.date_range_outlined, size: 18),
                  label: Text(
                    '${date(widget.period.start)} — ${date(widget.period.end)}',
                  ),
                ),
              ),
              const SizedBox(height: 4),
              LayoutBuilder(
                builder: (context, bounds) {
                  final metrics = [
                    metric('income', data.income, LifePalette.green),
                    metric('expense', data.expense, LifePalette.red),
                  ];
                  return MediaQuery.textScalerOf(context).scale(1) > 1.4 ||
                          bounds.maxWidth < 300 &&
                              (money(data.income).length > 15 ||
                                  money(data.expense).length > 15)
                      ? Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            metrics[0],
                            const SizedBox(height: 12),
                            metrics[1],
                          ],
                        )
                      : Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(child: metrics[0]),
                            const SizedBox(width: 16),
                            Expanded(child: metrics[1]),
                          ],
                        );
                },
              ),
              if (!widget.compact) ...[
                const SizedBox(height: 20),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    FilledButton.icon(
                      onPressed: () => widget.onAdd(EntryKind.expense),
                      icon: const Icon(Icons.remove, size: 18),
                      label: Text(t('expense')),
                    ),
                    OutlinedButton.icon(
                      onPressed: () => widget.onAdd(EntryKind.income),
                      icon: const Icon(Icons.add, size: 18),
                      label: Text(t('income')),
                    ),
                  ],
                ),
              ],
              if (data.records.isEmpty) ...[
                const SizedBox(height: 16),
                Text(
                  t('empty_money'),
                  style: Theme.of(context).textTheme.bodyMedium
                      ?.copyWith(color: scheme.onSurfaceVariant),
                ),
              ] else if (widget.compact) ...[
                const SizedBox(height: 16),
                _chart(buckets, index, scheme),
              ],
            ],
          ),
        ),
        if (!widget.compact && data.records.isNotEmpty) ...[
          const SizedBox(height: 16),
          LifeCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  t('insight_dynamics'),
                  style: Theme.of(context).textTheme.titleMedium
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: [
                    for (final g in ChartGrain.values)
                      ChoiceChip(
                        label: Text(t('insight_${g.name}')),
                        selected: grain == g,
                        onSelected: (_) => setState(() {
                          grain = g;
                          selected = null;
                        }),
                      ),
                  ],
                ),
                const SizedBox(height: 16),
                _chart(buckets, index, scheme),
                if (index != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    '${date(buckets[index].date)} · ${t('income')}: ${money(buckets[index].income)} · ${t('expense')}: ${money(buckets[index].expense)}',
                  ),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      IconButton(
                        tooltip: MaterialLocalizations.of(context)
                            .previousPageTooltip,
                        onPressed: index > 0
                            ? () => setState(() => selected = index - 1)
                            : null,
                        icon: const Icon(Icons.chevron_left),
                      ),
                      IconButton(
                        tooltip: MaterialLocalizations.of(context)
                            .nextPageTooltip,
                        onPressed: index < buckets.length - 1
                            ? () => setState(() => selected = index + 1)
                            : null,
                        icon: const Icon(Icons.chevron_right),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
          if (parts.isNotEmpty) ...[
            const SizedBox(height: 16),
            LifeCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    t('insight_categories'),
                    style: Theme.of(context).textTheme.titleMedium
                        ?.copyWith(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 20),
                  Center(
                    child: SizedBox(
                      key: const Key('expense_categories_chart'),
                      width: 144,
                      height: 144,
                      child: Semantics(
                        label: t('insight_categories'),
                        value: money(data.expense),
                        child: CustomPaint(
                          painter: CategoryRing(
                            parts.map((e) => e.value).toList(),
                            scheme.surfaceContainerHighest,
                          ),
                          child: Center(
                            child: Icon(
                              Icons.pie_chart_outline_rounded,
                              size: 28,
                              color: scheme.onSurfaceVariant,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  for (var i = 0; i < parts.length; i++)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      minLeadingWidth: 12,
                      leading: Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: chartColor(i),
                          shape: BoxShape.circle,
                        ),
                      ),
                      title: Text(name(parts[i].key)),
                      subtitle: Text(
                        '${money(parts[i].value)} · ${formatShare(parts[i].value, data.expense, locale: c.region)}',
                      ),
                      trailing: Icon(
                        category == parts[i].key
                            ? Icons.expand_less
                            : Icons.expand_more,
                        size: 20,
                      ),
                      selected: category == parts[i].key,
                      onTap: () => setState(
                        () => category = category == parts[i].key
                            ? null
                            : parts[i].key,
                      ),
                    ),
                  if (category != null) ...[
                    const Divider(),
                    Text(
                      name(category!),
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                    for (final r in data.categoryRecords(category!))
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(r.text.isEmpty ? t('expense') : r.text),
                        subtitle: Text(
                          '${date(DateTime.parse(r.date!))} · ${money(BigInt.from(r.amountMinor!))}',
                        ),
                        trailing: const Icon(Icons.chevron_right, size: 20),
                        onTap: () => widget.onRecord(r),
                      ),
                  ],
                ],
              ),
            ),
          ],
        ],
      ],
    );
  }

  Widget _chart(
    List<CashBucket> buckets,
    int? index,
    ColorScheme scheme,
  ) => Semantics(
    label: t('insight_dynamics'),
    value: index == null
        ? t('insight_select')
        : '${date(buckets[index].date)} ${t('income')} ${money(buckets[index].income)} ${t('expense')} ${money(buckets[index].expense)}',
    child: LayoutBuilder(
      builder: (context, bounds) => GestureDetector(
        key: const Key('cashflow_chart'),
        behavior: HitTestBehavior.opaque,
        onTapDown: (d) => setState(
          () => selected =
              (d.localPosition.dx / bounds.maxWidth * (buckets.length - 1))
                  .round()
                  .clamp(0, buckets.length - 1),
        ),
        onHorizontalDragUpdate: (d) => setState(
          () => selected =
              (d.localPosition.dx / bounds.maxWidth * (buckets.length - 1))
                  .round()
                  .clamp(0, buckets.length - 1),
        ),
        child: SizedBox(
          height: widget.compact ? 48 : 128,
          width: double.infinity,
          child: CustomPaint(
            painter: CashflowPainter(
              buckets,
              lifeAccent(context, LifePalette.green),
              lifeAccent(context, LifePalette.red),
              scheme.outlineVariant,
              index,
            ),
          ),
        ),
      ),
    ),
  );
}

Color chartColor(int i) => const [
  Color(0xff4d9b87),
  Color(0xffdd9766),
  Color(0xff7f8ad0),
  Color(0xffbd7c9a),
  Color(0xff75a0c5),
  Color(0xffacaa67),
][i % 6];
double chartRatio(BigInt amount, BigInt max) => max == BigInt.zero
    ? 0
    : (amount * BigInt.from(1000000) ~/ max).toDouble() / 1000000;

class CashflowPainter extends CustomPainter {
  CashflowPainter(
    this.buckets,
    this.income,
    this.expense,
    this.grid,
    this.selected,
  );
  final List<CashBucket> buckets;
  final Color income, expense, grid;
  final int? selected;
  @override
  void paint(Canvas canvas, Size size) {
    if (buckets.isEmpty) return;
    var max = BigInt.one;
    for (final b in buckets) {
      if (b.income > max) max = b.income;
      if (b.expense > max) max = b.expense;
    }
    for (var row = 1; row < 4; row++) {
      final y = size.height * row / 4;
      canvas.drawLine(
        Offset(0, y),
        Offset(size.width, y),
        Paint()
          ..color = grid.withValues(alpha: .35)
          ..strokeWidth = 1,
      );
    }
    for (final isIncome in [true, false]) {
      final color = isIncome ? income : expense;
      final line = Path();
      for (var i = 0; i < buckets.length; i++) {
        final x = buckets.length == 1
            ? size.width / 2
            : i * size.width / (buckets.length - 1);
        final y =
            size.height -
            6 -
            chartRatio(isIncome ? buckets[i].income : buckets[i].expense, max) *
                (size.height - 16);
        if (i == 0) {
          line.moveTo(x, y);
        } else {
          line.lineTo(x, y);
        }
        if (i == selected || buckets.length == 1) {
          canvas.drawCircle(Offset(x, y), 4, Paint()..color = color);
        }
      }
      final fill = Path.from(line)
        ..lineTo(size.width, size.height)
        ..lineTo(0, size.height)
        ..close();
      canvas.drawPath(
        fill,
        Paint()
          ..shader = LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [color.withValues(alpha: .18), color.withValues(alpha: 0)],
          ).createShader(Offset.zero & size),
      );
      canvas.drawPath(
        line,
        Paint()
          ..color = color
          ..strokeWidth = 2.5
          ..strokeJoin = StrokeJoin.round
          ..style = PaintingStyle.stroke,
      );
    }
  }

  @override
  bool shouldRepaint(covariant CashflowPainter old) => true;
}

class CategoryRing extends CustomPainter {
  CategoryRing(this.values, this.empty);
  final List<BigInt> values;
  final Color empty;
  @override
  void paint(Canvas canvas, Size size) {
    final rect = (Offset.zero & size).deflate(13);
    final total = values.fold(BigInt.zero, (a, b) => a + b);
    var start = -math.pi / 2;
    canvas.drawOval(
      rect,
      Paint()
        ..color = empty
        ..style = PaintingStyle.stroke
        ..strokeWidth = 18,
    );
    if (total == BigInt.zero) return;
    for (var i = 0; i < values.length; i++) {
      final angle = chartRatio(values[i], total) * math.pi * 2;
      canvas.drawArc(
        rect,
        start,
        angle,
        false,
        Paint()
          ..color = chartColor(i)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 18,
      );
      start += angle;
    }
  }

  @override
  bool shouldRepaint(covariant CategoryRing old) => true;
}
