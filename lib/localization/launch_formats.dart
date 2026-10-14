import 'package:intl/date_symbol_data_custom.dart';
import 'package:intl/date_symbols.dart';
import 'package:intl/intl.dart';
import 'package:intl/number_symbols.dart';
import 'package:intl/number_symbols_data.dart';

// intl does not ship Tajik or Uzbek Cyrillic data. Register these explicitly;
// neither language should silently acquire English dates or number separators.
void initializeLaunchFormats() {
  numberFormatSymbols['tg'] = const NumberSymbols(
    NAME: 'tg',
    DECIMAL_SEP: ',',
    GROUP_SEP: '\u00a0',
    PERCENT: '%',
    ZERO_DIGIT: '0',
    PLUS_SIGN: '+',
    MINUS_SIGN: '-',
    EXP_SYMBOL: 'E',
    PERMILL: '\u2030',
    INFINITY: '\u221e',
    NAN: 'NaN',
    DECIMAL_PATTERN: '#,##0.###',
    SCIENTIFIC_PATTERN: '#E0',
    PERCENT_PATTERN: '#,##0\u00a0%',
    CURRENCY_PATTERN: '#,##0.00\u00a0\u00a4',
    DEF_CURRENCY_CODE: 'TJS',
  );
  numberFormatSymbols['uz_Cyrl'] = numberFormatSymbols['uz']!;
  _register(
    'tg',
    months:
        'январ феврал март апрел май июн июл август сентябр октябр ноябр декабр'
            .split(' '),
    weekdays: 'якшанбе душанбе сешанбе чоршанбе панҷшанбе ҷумъа шанбе'.split(
      ' ',
    ),
    shortDays: 'яшб дшб сшб чшб пшб ҷмъ шб'.split(' '),
    eras: ['то милод', 'милодӣ'],
    quarters: ['семоҳаи 1', 'семоҳаи 2', 'семоҳаи 3', 'семоҳаи 4'],
    ampm: ['пеш аз зуҳр', 'пас аз зуҳр'],
  );
  _register(
    'uz_Cyrl',
    months:
        'январ феврал март апрел май июн июл август сентябр октябр ноябр декабр'
            .split(' '),
    weekdays: 'якшанба душанба сешанба чоршанба пайшанба жума шанба'.split(' '),
    shortDays: 'Якш Душ Сеш Чор Пай Жум Шан'.split(' '),
    eras: ['милоддан аввал', 'милодий'],
    quarters: ['1-чорак', '2-чорак', '3-чорак', '4-чорак'],
    ampm: ['тушдан олдин', 'тушдан кейин'],
  );
}

void _register(
  String tag, {
  required List<String> months,
  required List<String> weekdays,
  required List<String> shortDays,
  required List<String> eras,
  required List<String> quarters,
  required List<String> ampm,
}) {
  final data = DateFormat.yMd('ru').dateSymbols.serializeToMap();
  data['NAME'] = tag;
  for (final key in ['MONTHS', 'STANDALONEMONTHS']) {
    data[key] = months;
  }
  for (final key in ['SHORTMONTHS', 'STANDALONESHORTMONTHS']) {
    data[key] = months.map((m) => m.substring(0, 3)).toList();
  }
  for (final key in ['NARROWMONTHS', 'STANDALONENARROWMONTHS']) {
    data[key] = months.map((m) => m[0]).toList();
  }
  for (final key in ['WEEKDAYS', 'STANDALONEWEEKDAYS']) {
    data[key] = weekdays;
  }
  for (final key in ['SHORTWEEKDAYS', 'STANDALONESHORTWEEKDAYS']) {
    data[key] = shortDays;
  }
  for (final key in ['NARROWWEEKDAYS', 'STANDALONENARROWWEEKDAYS']) {
    data[key] = weekdays.map((d) => d[0]).toList();
  }
  data['ERAS'] = eras;
  data['ERANAMES'] = eras;
  data['AMPMS'] = ampm;
  data['QUARTERS'] = quarters;
  data['SHORTQUARTERS'] = quarters;
  data['DATEFORMATS'] = ['EEEE, d MMMM y', 'd MMMM y', 'd MMM y', 'dd.MM.yy'];
  initializeDateFormattingCustom(
    locale: tag,
    symbols: DateSymbols.deserializeFromMap(data),
    patterns: {
      'd': 'd',
      'E': 'ccc',
      'EEEE': 'cccc',
      'LLL': 'LLL',
      'LLLL': 'LLLL',
      'M': 'L',
      'Md': 'dd.MM',
      'MEd': 'EEE, dd.MM',
      'MMM': 'LLL',
      'MMMd': 'd MMM',
      'MMMEd': 'EEE, d MMM',
      'MMMM': 'LLLL',
      'MMMMd': 'd MMMM',
      'MMMMEEEEd': 'EEEE, d MMMM',
      'QQQ': 'QQQ',
      'QQQQ': 'QQQQ',
      'y': 'y',
      'yM': 'MM.y',
      'yMd': 'dd.MM.y',
      'yMEd': 'EEE, dd.MM.y',
      'yMMM': 'MMM y',
      'yMMMd': 'd MMM y',
      'yMMMEd': 'EEE, d MMM y',
      'yMMMM': 'MMMM y',
      'yMMMMd': 'd MMMM y',
      'yMMMMEEEEd': 'EEEE, d MMMM y',
      'yQQQ': 'QQQ y',
      'yQQQQ': 'QQQQ y',
      'H': 'HH',
      'Hm': 'HH:mm',
      'Hms': 'HH:mm:ss',
      'j': 'HH',
      'jm': 'HH:mm',
      'jms': 'HH:mm:ss',
      'jmv': 'HH:mm v',
      'jmz': 'HH:mm z',
      'jv': 'HH v',
      'jz': 'HH z',
      'm': 'm',
      'ms': 'mm:ss',
      's': 's',
    },
  );
}
