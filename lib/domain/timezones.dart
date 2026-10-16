import 'package:timezone/timezone.dart' as tz;

// Android may return an equivalent UTC alias absent from the loaded database.
// Resolve only known zero-offset aliases; retain IANA/DST behavior for all others.
tz.Location calendarLocation(String name) {
  const utcAliases = {
    'UTC', 'Etc/UTC', 'GMT', 'Etc/GMT', 'GMT0', 'Etc/GMT0',
    'UCT', 'Etc/UCT', 'Universal', 'Etc/Universal',
    'Zulu', 'Etc/Zulu', 'Greenwich', 'Etc/Greenwich',
  };
  return utcAliases.contains(name) ? tz.UTC : tz.getLocation(name);
}
