# Безопасная публикация кандидата

Репозиторий PRIVATE: `pro100umarchikgamer-lgtm/lifeos`. Удалённый main повторно проверен: `23e537d7256bbedf37d24a2d4219ef3f6019f996`. Локальная сохранённая основа — `62e730a`, поверх неё последовательные контрольные точки. Локальная история не является историей GitHub; **не отправлять её force-push**.

В поставке:

- `LifeOS_Offline_Core.patch` — изменения относительно сохранённого main;
- `LifeOS_Offline_Core_Candidate.zip` — полный набор tracked исходников/тестов/локалей/документации/workflow, без caches/build/секретов;
- `LifeOS_Offline_Core.bundle` — сохранение локальной истории для восстановления/ревью, не замена GitHub main.

## Рабочая среда с GitHub write и Flutter

1. Сделать свежий checkout GitHub main. Проверить SHA; если main продвинулся, сначала согласовать изменения и проверить patch, сохраняя чужую работу.
2. `git apply --check /path/LifeOS_Offline_Core.patch`; только при успехе `git apply /path/LifeOS_Offline_Core.patch`. Если проверка не проходит, разобрать конкретные изменения; не заменять каталог вслепую.
3. При наличии SDK: `flutter pub get`, `dart format lib test integration_test`, `flutter analyze`, новые/существующие tests. Исправления форматирования не заменяют анализ или проверки.
4. Commit в настоящей истории main и обычный push. Нужны Contents и Workflows write; токены не публиковать. В этой среде известный отказ записи уже документирован, установки/сетевые повторы не нужны.
5. Один полный Actions gate выполняет analyze, domain/widget/visual tests, Python gates, Kotlin compilation и SQLCipher emulator tests. Просмотреть 73 PNG и исправить реальные несоответствия; генерация goldens не равна визуальной приёмке.
6. После успешной проверки последнего source SHA запустить `stage1.yml` с `build_apk=true`. Workflow использует только проверенное доказательство для идентичных source/SDK/lock/gate inputs; если доказательства нет, выполняет полный gate. Так один полный validation run и один подписанный APK не требуют повторных полных прогонов без причины.
7. Нужен защищённый `LIFEOS_TEST_KEYSTORE_BASE64` от прежней установки. Не создавать новую подпись. `ci_signing.sh` проверяет pinned SHA-256, applicationId и увеличивает versionCode; иначе сборка останавливается. Артефакт: `lifeos-release-test-apk-<source SHA>`; PNG: `lifeos-ui-screenshots-<run number>`.
8. APK — только тестовый кандидат до физической приёмки по `OFFLINE_CORE_ANDROID_CHECKLIST.md`. XLS ещё не реализован; milestone не называть завершённым.
