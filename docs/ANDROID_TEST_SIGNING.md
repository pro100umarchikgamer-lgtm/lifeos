# Постоянная подпись тестовых APK LifeOS

`applicationId`: `app.lifeos.lifeos`. Единственный постоянный тестовый ключ —
`LIFEOS_TEST_KEYSTORE_BASE64` в **Settings → Secrets and variables → Actions →
Repository secrets**. Alias `androiddebugkey`, пароли стандартного debug-keystore
`android`; приватность обеспечивается закрытым keystore и GitHub Actions Secret.
Публичный SHA-256 закреплён в `docs/ANDROID_TEST_CERT.sha256`.
При отсутствии секрета или несовпадении сертификата APK не публикуется.

## Однократная настройка владельцем репозитория

В существующем Codespace ключ уже создан в
`$HOME/.lifeos-signing/lifeos-debug.keystore` вне Git. Не создавайте его заново.

1. Сохраните защищённую резервную копию этого keystore вне Codespace.
2. В терминале Codespace выполните (значение секрета не выводится в журнал):
   ```bash
   umask 077
   base64 -w0 "$HOME/.lifeos-signing/lifeos-debug.keystore" > "$HOME/.lifeos-signing/github-secret.txt"
   code "$HOME/.lifeos-signing/github-secret.txt"
   ```
3. Скопируйте содержимое открытого файла в новый Repository secret
   `LIFEOS_TEST_KEYSTORE_BASE64`. Не отправляйте его в чат, Git или логи.
4. Закройте файл и удалите временный текст:
   ```bash
   rm "$HOME/.lifeos-signing/github-secret.txt"
   ```
5. Сообщите, что секрет добавлен. Запуск: Actions →
   **Personal Core validation and final debug APK** → Run workflow → main →
   `build_apk=true`. Для этой правки `force_full_validation=false`.

## Проверки и повторные запуски

Версия Flutter закреплена на 3.47.7, использованной успешной проверкой #27.
Полная валидация включает существующие Python/Flutter-тесты, 17 скриншотов,
нативную компиляцию и Android SQLCipher integration tests. Она сохраняется
без изменения тестов. При изменении исходников, assets, платформенных шаблонов,
тестов или зависимостей повторно выполняется весь этот набор.

Для изменений только подписи/CI полная проверка переиспользуется исключительно
из успешного main-запуска с совпадающими Git-входами, pubspec.lock и Flutter SDK.
Первый запуск сверяет все 78 фактически разрешённых зависимостей с журналом #27.
Если доказательство недоступно или входы различаются, выполняется полная проверка.
`force_full_validation=true` принудительно запускает полный набор для релиза.

Запуски одной ветки сериализованы. APK собирается только по ручному запросу на
main, а существующий успешный APK-артефакт того же коммита подавляет повторную
сборку. `versionCode = github.run_number * 1000 + github.run_attempt`; номер
workflow сохраняется, повторная попытка увеличивает versionCode. Не переносите
workflow в новый файл без сохранения монотонности versionCode.

После сборки `apksigner` проверяет подпись и закреплённый SHA-256, `aapt`
проверяет applicationId/versionCode. Артефакт содержит APK, публичный сертификат
и `apk-identity.txt`. Приватный ключ удаляется с runner после шага сборки.

## Старые APK

Предыдущие runner использовали разные временные ключи. Без их исходного keystore
новый APK нельзя установить как обновление старого. Не удаляйте приложение с
важными данными без проверенной резервной копии: удаление очищает локальные данные.
Новый постоянный ключ обеспечивает обновления APK, подписанных им, в будущем.
