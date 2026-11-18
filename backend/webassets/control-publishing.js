const TITLES = {
  az: ['Açıq səhifələr', 'Android buraxılışları'], de: ['Öffentliche Seiten', 'Android-Versionen'],
  en: ['Public pages', 'Android releases'], es: ['Páginas públicas', 'Versiones de Android'],
  fr: ['Pages publiques', 'Versions Android'], hy: ['Հանրային էջեր', 'Android-ի թողարկումներ'],
  it: ['Pagine pubbliche', 'Versioni Android'], ka: ['საჯარო გვერდები', 'Android-ის გამოშვებები'],
  kk: ['Жария беттер', 'Android шығарылымдары'], ky: ['Ачык барактар', 'Android чыгарылыштары'],
  pt: ['Páginas públicas', 'Versões Android'], ru: ['Публичные страницы', 'Релизы Android'],
  tg: ['Саҳифаҳои оммавӣ', 'Нашрҳои Android'], uk: ['Публічні сторінки', 'Випуски Android'],
  'uz-Cyrl': ['Очиқ саҳифалар', 'Android релизлари'], 'uz-Latn': ['Ochiq sahifalar', 'Android relizlari'],
};

export function publishingTitle(section, language) {
  return (TITLES[language] || TITLES.en)[section === 'public-pages' ? 0 : 1];
}

const labels = {
  loading: ['literal_db491ef5033f', 'Загрузка…', 'Loading…'],
  refresh: ['loc_6adf2720c88f', 'Обновить', 'Refresh'],
  save: ['literal_6a4e14990b20', 'Сохранить черновик', 'Save draft'],
  draft: ['literal_65fd24f1cb37', 'Черновик', 'Draft'],
  published: ['literal_382ded9c6877', 'Опубликовано', 'Published'],
  cancelled: ['literal_23a2a9bfcf74', 'Отменено', 'Cancelled'],
  review: ['literal_0d54787744b2', 'Проверить публикацию', 'Review publication'],
  publish: ['literal_4d0fa33cdbdd', 'Опубликовать', 'Publish'],
  confirm: ['literal_27bca309f5f8', 'Подтвердить', 'Confirm'],
  reason: ['control_reason', 'Причина для журнала аудита', 'Reason for the audit log'],
  cancel: ['control_cancel', 'Отменить', 'Cancel'],
  next: ['control_next', 'Следующая страница', 'Next page'],
  previous: ['control_previous', 'Предыдущая страница', 'Previous page'],
  title: ['literal_5f77cb92e071', 'Заголовок', 'Title'],
  link: ['literal_f4cb2c0e2410', 'Ссылка', 'Link'],
  version: ['literal_83c21cec4c45', 'Версия', 'Version'],
  history: [null, 'История версий', 'Revision history'],
  text: [null, 'Текст', 'Text'],
  page: [null, 'Страница сайта', 'Website page'],
  language: [null, 'Язык страницы', 'Page language'],
  baseline: [null, 'Исходная версия', 'Shipped version'],
  live: [null, 'На сайте', 'Live on the site'],
  saved: [null, 'Черновик сохранён', 'Draft saved'],
  unsaved: [null, 'Есть несохранённые изменения', 'Unsaved changes'],
  fields: [null, 'Текст страницы', 'Page copy'],
  blocks: [null, 'Блоки страницы', 'Page blocks'],
  block: [null, 'Тип блока', 'Block type'],
  addBlock: [null, 'Добавить блок', 'Add block'],
  up: [null, 'Выше', 'Move up'],
  down: [null, 'Ниже', 'Move down'],
  remove: [null, 'Убрать', 'Remove'],
  source: [null, 'Исходный блок', 'Source block'],
  restoreSource: [null, 'Вернуть исходный блок', 'Add a source block back'],
  guidance: [null, 'Рекомендации', 'Guidance'],
  resources: [null, 'Ссылки по теме', 'Related links'],
  capabilities: [null, 'Возможности', 'Capabilities'],
  highlights: [null, 'Главное', 'Highlights'],
  features: [null, 'Возможности', 'Features'],
  steps: [null, 'Шаги', 'Steps'],
  instructions: [null, 'Инструкции', 'Instructions'],
  image: [null, 'Изображение', 'Image'],
  imageFile: [null, 'Файл изображения', 'Image file'],
  loadImage: [null, 'Загрузить изображение', 'Upload image'],
  imageInvalid: [null, 'Выберите PNG, JPEG или WebP до 1 МиБ.', 'Select a PNG, JPEG, or WebP up to 1 MiB.'],
  imageMissing: [null, 'Загрузите изображение, чтобы сохранить блок.', 'Upload the image before saving the block.'],
  href: [null, 'Адрес ссылки', 'Link destination'],
  alt: [null, 'Описание изображения', 'Alt text'],
  caption: [null, 'Подпись', 'Caption'],
  edit: [null, 'К редактированию', 'Back to editor'],
  preview: [null, 'Предпросмотр материалов', 'Content preview'],
  previewDraft: [null, 'Предпросмотр черновика', 'Preview draft'],
  empty: [null, 'В этом разделе пока ничего нет.', 'This section is empty.'],
  restore: [null, 'Восстановить как черновик', 'Restore as draft'],
  restoredRevision: [null, 'Восстановленный черновик', 'Restored draft'],
  confirmRestore: [null, 'Сохранить восстановленный черновик', 'Save restored draft'],
  restored: [null, 'Версия восстановлена в черновик', 'Revision restored to draft'],
  reset: [null, 'Отменить несохранённые изменения', 'Discard unsaved changes'],
  stale: [null, 'Версия обновилась. Ваши правки сохранены в редакторе. Обновите данные перед повторным действием.', 'The revision changed. Your edits are still in the editor. Refresh before trying again.'],
  revision: [null, 'Редакция', 'Revision'],
  actor: [null, 'Сотрудник', 'Staff member'],
  releaseActive: [null, 'Текущий APK', 'Current APK'],
  releaseNone: [null, 'Текущий APK не получен.', 'No current APK is available.'],
  releases: [null, 'Кандидаты на публикацию', 'Release candidates'],
  create: [null, 'Новый кандидат', 'New candidate'],
  upload: [null, 'Загрузить APK', 'Upload APK'],
  file: [null, 'Файл APK', 'APK file'],
  pickFile: [null, 'Выберите или перетащите подписанный файл .apk до 512 МиБ.', 'Choose or drop one signed .apk file up to 512 MiB.'],
  validating: [null, 'Проверяем подпись и сведения о сборке…', 'Verifying signature and build metadata…'],
  validate: [null, 'Проверить APK', 'Validate APK'],
  uploaded: [null, 'Загружено', 'Uploaded'],
  validated: [null, 'Подпись проверена', 'Signature verified'],
  rejected: [null, 'Проверка не пройдена', 'Validation failed'],
  releasePublish: [null, 'Опубликовать APK', 'Publish APK'],
  releasePublishHelp: [null, 'Эта сборка станет доступна на странице загрузки ULADIM.', 'This build will become available on the ULADIM download page.'],
  releaseCancel: [null, 'Отменить кандидата', 'Cancel candidate'],
  size: [null, 'Размер', 'Size'],
  versionCode: [null, 'Код версии', 'Version code'],
  signer: [null, 'Сертификат SHA-256', 'Signer SHA-256'],
  package: [null, 'Пакет Android', 'Android package'],
  checksum: [null, 'SHA-256 файла', 'File SHA-256'],
  blocksEmpty: [null, 'Добавьте блок в этот раздел страницы.', 'Add a block to this part of the page.'],
  reviewConflict: [null, 'Сравнить с новой версией', 'Review newer version'],
  remoteChanges: [null, 'Изменения другого сотрудника', 'Changes saved by someone else'],
  savedValue: [null, 'Сохранённая версия', 'Saved version'],
  yourValue: [null, 'Ваши правки', 'Your edits'],
  useYourValue: [null, 'Оставить мои правки', 'Keep my edits'],
  useSavedValue: [null, 'Использовать сохранённую версию', 'Use the saved version'],
  applyReconciliation: [null, 'Продолжить с выбранными правками', 'Continue with reviewed changes'],
  reconciled: [null, 'Правки согласованы. Сохраните черновик, чтобы их записать.', 'Changes reconciled. Save the draft to record them.'],
  noRemoteChanges: [null, 'Сохранённый текст не изменился.', 'The saved content is unchanged.'],
};

const fieldLabels = {
  body: ['Текст', 'Text'], lead: ['Введение', 'Introduction'], kicker: ['Надзаголовок', 'Eyebrow'],
  'title-accent': ['Вторая часть заголовка', 'Second part of title'], title: ['Заголовок', 'Title'],
  'guest-note': ['Подпись для гостя', 'Guest note'], footnote: ['Примечание', 'Footnote'],
  note: ['Примечание', 'Note'], label: ['Подпись ссылки', 'Link label'], href: ['Адрес ссылки', 'Link destination'],
};

export function createControlPublishing({app, heading, api, uploadApk, getLanguage, getLanguages, getCopy}) {
  const editor = globalThis.UladimPublicPages;
  const copy = (key, values = {}) => {
    const translated = getCopy()?.labels?.[key];
    if (translated) return translated;
    const [id, russian, english] = labels[key] || [null, key, key];
    const language = getLanguage();
    const fallback = language === 'ru' ? russian : english;
    return id ? globalThis.UladimI18n.text(id, values, fallback).trim() : fallback;
  };
  const permissions = (session, capability) => session.permissions.includes(capability);
  const drafts = new Map();
  const saving = new Map();
  let pageChoice = null;
  let localeChoice = null;

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function view(section) {
    heading(publishingTitle(section, getLanguage()));
    const root = element('div', undefined, 'cw-workbench publishing-workbench');
    app.append(root);
    return root;
  }
  function status(parent, text = '') {
    const node = element('p', text, 'cw-status');
    node.setAttribute('role', 'status');
    parent.append(node);
    return node;
  }
  function report(node, text, error = false) {
    node.textContent = text;
    node.classList.toggle('error', error);
  }
  function failure(node, error) {
    const code = error.code;
    const publishingErrors = {
      apk_package: ['Неверный пакет Android.', 'The APK has the wrong Android package.'],
      apk_signer: ['Подпись не совпадает с сертификатом ULADIM.', 'The signer differs from the ULADIM certificate.'],
      apk_version_not_newer: ['Код версии должен быть выше опубликованного.', 'The version code must exceed the published build.'],
      apk_signature: ['Не удалось проверить подпись APK.', 'APK signature verification failed.'],
      apk_manifest: ['Сведения о сборке отсутствуют или повреждены.', 'The APK build metadata is missing or invalid.'],
      apk_file_changed: ['Файл изменился. Отмените кандидата и загрузите APK заново.', 'The APK changed. Cancel the candidate and upload it again.'],
      apk_storage_unavailable: ['Хранилище APK недоступно.', 'APK storage is unavailable.'],
      apk_busy: ['Другая операция с APK ещё выполняется.', 'Another APK operation is in progress.'],
      apk_draft_limit: ['Отмените лишнего кандидата перед созданием нового.', 'Cancel an unused candidate before creating another.'],
      apk_state_conflict: ['Состояние кандидата изменилось. Обновите список.', 'The candidate changed. Refresh the list.'],
      apk_baseline_unavailable: ['Не удалось проверить текущий APK. Повторите позже.', 'The current APK could not be verified. Try again later.'],
      apk_verifier_timeout: ['Проверка APK заняла слишком много времени. Повторите позже.', 'APK verification timed out. Try again later.'],
      apk_verifier_unavailable: ['Проверка APK временно недоступна.', 'APK verification is temporarily unavailable.'],
      apk_upload_incomplete: ['Файл загружен не полностью. Повторите загрузку.', 'The upload was incomplete. Upload the file again.'],
      invalid_page_content: ['Проверьте текст, ссылки и размеры блоков.', 'Check the text, links, and block sizes.'],
      invalid_page_image: ['Проверьте формат и размер изображения.', 'Check the image format and size.'],
    };
    const localeErrors = getCopy()?.errors;
    report(node, code === 'revision_conflict' ? copy('stale') : localeErrors?.[code] || publishingErrors[code]?.[getLanguage() === 'ru' ? 0 : 1] || error.message || localeErrors?.generic || code, true);
  }
  function action(parent, text, run, {primary = false, disabled = false} = {}) {
    const button = element('button', text, primary ? '' : 'secondary');
    button.type = 'button';
    button.disabled = disabled;
    button.addEventListener('click', run);
    parent.append(button);
    return button;
  }
  function actions(parent) {
    const row = element('div', undefined, 'actions cw-actions');
    parent.append(row);
    return row;
  }
  function field(parent, label, value, {type = 'text', max = 4096, required = true} = {}) {
    const wrap = element('div', undefined, 'cw-field');
    const input = element(type === 'textarea' ? 'textarea' : 'input');
    if (type !== 'textarea') input.type = type;
    input.id = 'publishing-' + crypto.randomUUID();
    input.value = value;
    input.required = required;
    input.maxLength = max;
    const caption = element('label', label);
    caption.htmlFor = input.id;
    wrap.append(caption, input);
    parent.append(wrap);
    return input;
  }
  function select(parent, label, options, value) {
    const wrap = element('div', undefined, 'cw-field');
    const native = element('select');
    native.id = 'publishing-' + crypto.randomUUID();
    for (const [key, text] of options) {
      const option = element('option', text);
      option.value = key;
      native.append(option);
    }
    native.value = value;
    const caption = element('label', label);
    caption.htmlFor = native.id;
    wrap.append(caption, native);
    parent.append(wrap);
    const menu = globalThis.UladimFieldMenu?.enhance(native, label);
    if (menu) {
      const trigger = menu.querySelector('button');
      trigger.id = 'publishing-menu-' + crypto.randomUUID();
      caption.htmlFor = trigger.id;
    }
    return native;
  }
  function card(parent, title, className = '') {
    const node = element('section', undefined, 'card cw-card ' + className);
    node.append(element('h2', title));
    parent.append(node);
    return node;
  }
  function metadata(parent, rows) {
    const list = element('dl', undefined, 'cw-metadata');
    for (const [key, value, code] of rows) {
      if (value === null || value === undefined) continue;
      const info = element('dd');
      info.append(code ? element('code', String(value)) : document.createTextNode(String(value)));
      list.append(element('dt', key), info);
    }
    parent.append(list);
  }
  function running(button, feedback, task, progress = copy('loading')) {
    if (button.disabled) return;
    button.disabled = true;
    report(feedback, progress);
    return Promise.resolve().then(task).catch(error => failure(feedback, error)).finally(() => {button.disabled = false;});
  }
  function shortDate(seconds) {
    return seconds ? new Date(seconds * 1000).toLocaleString(getLanguage()) : '';
  }
  function scope(page, locale, extras = {}) {
    return new URLSearchParams({page, lang: locale, ...extras});
  }
  function localeName(locale) {
    return getLanguages()[locale]?.name || locale;
  }
  function revisionKind(kind) {
    return copy(kind === 'source' ? 'baseline' : kind === 'restored' ? 'restoredRevision' : kind);
  }
  function fieldName(key) {
    return key.split('.').map(part => getCopy()?.fields?.[part] || (labels[part] ? copy(part)
      : fieldLabels[part]?.[getLanguage() === 'ru' ? 0 : 1] || part.replaceAll('-', ' '))).join(' · ');
  }
  function initial(pageState) {
    return structuredClone((pageState.draft || pageState.published || pageState.baseline).content);
  }

  async function pages(session) {
    const root = view('public-pages');
    const feedback = status(root, copy('loading'));
    const result = await api('pages');
    if (!root.isConnected) return;
    const pages = result.pages;
    if (!pages.some(item => item.page === pageChoice)) pageChoice = pages[0]?.page;
    if (!result.locales.includes(localeChoice)) localeChoice = getLanguage();
    if (!result.locales.includes(localeChoice)) localeChoice = result.locales[0];
    const filters = element('div', undefined, 'publishing-filters');
    const route = select(filters, copy('page'), pages.map(item => [item.page, `${item.label} · ${item.page}`]), pageChoice);
    const locale = select(filters, copy('language'), result.locales.map(lang => [lang, localeName(lang)]), localeChoice);
    root.prepend(filters);
    const work = element('div');
    root.append(work);
    let generation = 0;

    async function load() {
      const current = ++generation;
      pageChoice = route.value;
      localeChoice = locale.value;
      const page = route.value, lang = locale.value;
      const key = `${page}\n${lang}`;
      work.replaceChildren();
      report(feedback, copy('loading'));
      try {
        await saving.get(key)?.catch(() => {});
        if (!work.isConnected || current !== generation) return;
        const pageState = await api('pages/page?' + scope(page, lang));
        if (!work.isConnected || current !== generation) return;
        report(feedback, '');
        drawPage(work, pageState, key, session, load);
      } catch (error) {
        if (work.isConnected && current === generation) {
          failure(feedback, error);
          action(work, copy('refresh'), load);
        }
      }
    }
    for (const control of [route, locale]) control.addEventListener('change', load);
    await load();
  }

  function drawPage(host, state, key, session, reload, notice = '') {
    host.replaceChildren();
    const {page, locale, version} = state;
    const base = initial(state);
    const buffer = drafts.get(key) || {base, content: structuredClone(base), version};
    const content = buffer.content;
    let stale = buffer.version !== version;
    const summary = card(host, `${page} · ${localeName(locale)}`);
    metadata(summary, [[copy('live'), state.published ? `${copy('revision')} ${state.published.revision}` : copy('baseline')],
      [copy('draft'), state.draft ? state.draft.revision : '—']]);
    const feedback = status(summary, notice);
    const form = element('form', undefined, 'cw-editor publishing-editor');
    host.append(form);
    const primary = actions(form);
    const save = element('button', copy('save'));
    save.type = 'submit';
    primary.append(save);
    const preview = action(primary, copy('previewDraft'), () => openRevision(state, state.draft.revision, key, host, session, reload));
    action(primary, copy('history'), () => readHistory(state, key, host, session, reload));
    const reconcile = action(primary, copy('reviewConflict'), () => reviewNewVersion(host, state, key, buffer, session, reload));
    const reset = action(primary, copy('reset'), () => {
      drafts.delete(key);
      return reload();
    });
    function syncButtons() {
      const dirty = drafts.has(key);
      preview.disabled = dirty || !state.draft;
      reset.hidden = !dirty;
      reconcile.hidden = !stale;
      save.disabled = stale;
    }
    function changed() {
      drafts.set(key, buffer);
      report(feedback, copy('unsaved'));
      syncButtons();
    }
    syncButtons();
    form.addEventListener('invalid', event => {
      for(let group = event.target.closest('details'); group; group = group.parentElement.closest('details')) group.open = true;
    }, true);
    form.addEventListener('submit', event => {
      event.preventDefault();
      if (Object.values(content.regions).flat().some(block => block.kind === 'image' && !block.media_id)) {
        report(feedback, copy('imageMissing'), true);
        return;
      }
      running(save, feedback, async () => {
        form.inert = true;
        const snapshot = structuredClone(content);
        const attempt = api('pages/save', {page, locale, expected_version: buffer.version, content: snapshot});
        saving.set(key, attempt);
        try {
          const updated = await attempt;
          if (drafts.get(key) === buffer) {
            if (sameValue(snapshot, content)) drafts.delete(key);
            else {buffer.version = updated.version;buffer.base = initial(updated);}
          }
          if (form.isConnected) drawPage(host, updated, key, session, reload, copy('saved'));
        } catch (error) {
          if (error.code === 'revision_conflict') stale = true;
          throw error;
        } finally {
          if (saving.get(key) === attempt) saving.delete(key);
          form.inert = false;
        }
      })?.finally(syncButtons);
    });
    const fieldGroup = element('details', undefined, 'publishing-group');
    fieldGroup.open = true;
    fieldGroup.append(element('summary', copy('fields')));
    form.append(fieldGroup);
    for (const [id, value] of Object.entries(content.fields)) {
      const link = id.endsWith('.href');
      const input = field(fieldGroup, fieldName(id), value, {type: value.length > 100 ? 'textarea' : 'text', required: link, max: link ? 1024 : 4096});
      input.addEventListener('input', () => {content.fields[id] = input.value; changed();});
      if (link) input.addEventListener('input', () => input.setCustomValidity(editor.safeLink(input.value) ? '' : copy('href')));
    }
    form.append(element('h2', copy('blocks')));
    for (const [id, blocks] of Object.entries(content.regions)) {
      const section = id.replace(/\.prose\d*$/, '');
      const name = state.baseline.content.fields[section + '.title'] || fieldName(id);
      blockEditor(form, name, blocks, state.baseline.content.regions[id], changed, feedback);
    }
    if (stale) report(feedback, copy('stale'), true);
    else if (drafts.has(key) && !notice) report(feedback, copy('unsaved'));
  }

  function sameValue(left, right) {
    if (left === right) return true;
    const ordered = (_key, value) => value && typeof value === 'object' && !Array.isArray(value)
      ? Object.fromEntries(Object.keys(value).sort().map(key => [key, value[key]])) : value;
    return JSON.stringify(left, ordered) === JSON.stringify(right, ordered);
  }

  async function reviewNewVersion(host, state, key, buffer, session, reload) {
    host.replaceChildren();
    const tools = actions(host);
    action(tools, copy('edit'), reload);
    const review = card(host, copy('remoteChanges'), 'publishing-reconciliation');
    const feedback = status(review, copy('loading'));
    try {
      const latest = await api('pages/page?' + scope(state.page, state.locale));
      if (!review.isConnected) return;
      const saved = initial(latest);
      const revised = structuredClone(buffer.content);
      let differences = 0;
      for (const group of ['fields', 'regions']) {
        for (const [id, value] of Object.entries(saved[group])) {
          const original = buffer.base[group][id];
          const mine = buffer.content[group][id];
          if (sameValue(original, value)) continue;
          differences++;
          if (sameValue(original, mine)) revised[group][id] = value;
          const item = element('section', undefined, 'publishing-conflict');
          item.append(element('h3', fieldName(id)));
          const versions = element('div', undefined, 'publishing-conflict-values');
          for (const [label, variant] of [['savedValue', value], ['yourValue', mine]]) {
            const version = element('div');
            version.append(element('h4', copy(label)));
            if (group === 'regions') editor.renderRegion(version, variant, previewOptions());
            else version.append(element('p', variant));
            versions.append(version);
          }
          item.append(versions);
          if (!sameValue(original, mine) && !sameValue(mine, value)) {
            const choice = select(item, fieldName(id), [['mine', copy('useYourValue')], ['saved', copy('useSavedValue')]], 'mine');
            choice.addEventListener('change', () => {revised[group][id] = choice.value === 'mine' ? mine : value;});
          }
          review.append(item);
        }
      }
      report(feedback, differences ? '' : copy('noRemoteChanges'));
      action(actions(review), copy('applyReconciliation'), () => {
        drafts.set(key, {base: saved, content: revised, version: latest.version});
        drawPage(host, latest, key, session, reload, copy('reconciled'));
      }, {primary: true});
    } catch (error) {
      if (review.isConnected) failure(feedback, error);
    }
  }

  function blockEditor(parent, region, blocks, baseline, changed, feedback) {
    const section = element('details', undefined, 'publishing-group');
    const summary = element('summary');
    const content = element('div', undefined, 'publishing-blocks');
    section.append(summary, content);
    parent.append(section);
    const type = select(section, copy('block'), ['text', 'link', 'image'].map(key => [key, copy(key)]), 'text');
    const row = actions(section);
    action(row, copy('addBlock'), () => {
      const kind = type.value;
      const values = {text: {title: '', body: ''}, link: {label: '', href: ''}, image: {media_id: '', alt: '', caption: ''}};
      const item = {id: crypto.randomUUID(), kind, ...values[kind]};
      blocks.push(item);
      changed();
      draw(item.id, 'field');
    });
    if (baseline?.length) {
      const missing = () => baseline.filter(block => !blocks.some(item => item.id === block.id));
      action(row, copy('restoreSource'), () => {
        const [source] = missing();
        if (!source) return;
        blocks.push(structuredClone(source));
        changed();
        draw(source.id, 'field');
      });
      row.lastElementChild.dataset.restoreSource = '';
    }

    function draw(focusedId = null, focusPart = null) {
      summary.textContent = `${region} (${blocks.length})`;
      content.replaceChildren();
      const restore = row.querySelector('[data-restore-source]');
      if (restore) restore.hidden = baseline.every(block => blocks.some(item => item.id === block.id));
      if (!blocks.length) content.append(element('p', copy('blocksEmpty')));
      blocks.forEach((item, index) => {
        const node = element('fieldset', undefined, 'publishing-block');
        node.dataset.block = item.id;
        const sample = item.kind === 'source' ? Object.values(item.fields)[0]?.trim().slice(0, 75) : '';
        node.append(element('legend', sample || copy(item.kind)));
        const fields = item.kind === 'source' ? item.fields : item;
        const keys = item.kind === 'source' ? Object.keys(fields) : {text: ['title', 'body'], link: ['label', 'href'], image: ['alt', 'caption']}[item.kind];
        for (const key of keys) {
          const max = item.kind === 'source' ? 4096 : ({title: 200, body: 4096, label: 200, href: 1024, alt: 300, caption: 1000}[key]);
          const required = item.kind === 'source' ? key === 'href' : !['caption', 'title'].includes(key);
          const input = field(node, fieldName(key), fields[key], {type: key === 'body' || key === 'caption' || fields[key].length > 100 ? 'textarea' : 'text', max, required});
          input.addEventListener('input', () => {fields[key] = input.value; changed();});
          if (key === 'href') input.addEventListener('input', () => input.setCustomValidity(editor.safeLink(input.value) ? '' : copy('href')));
        }
        if (item.kind === 'image') imageInput(node, item, changed, feedback);
        const tools = actions(node);
        for (const [operation, offset] of [['up', -1], ['down', 1]]) {
          const moved = index + offset;
          const button = action(tools, copy(operation), () => {
            [blocks[index], blocks[moved]] = [blocks[moved], blocks[index]];
            changed();
            draw(item.id, operation);
          }, {disabled: moved < 0 || moved >= blocks.length});
          button.dataset.part = operation;
        }
        action(tools, copy('remove'), () => {
          blocks.splice(index, 1);
          changed();
          draw(blocks[index]?.id || blocks.at(-1)?.id, 'remove');
          if (!blocks.length) summary.focus();
        }).dataset.part = 'remove';
        content.append(node);
        if (item.id === focusedId) {
          const control = focusPart === 'field' ? node.querySelector('input, textarea') : node.querySelector(`[data-part="${focusPart}"]:not(:disabled)`);
          (control || node.querySelector('button:not(:disabled)'))?.focus();
        }
      });
    }
    draw();
  }

  function imageInput(parent, block, changed, feedback) {
    const details = element('div');
    parent.append(details);
    const input = field(parent, copy('imageFile'), '', {type: 'file', required: false});
    input.accept = 'image/png,image/jpeg,image/webp';
    const local = status(parent);
    const buttons = actions(parent);
    let selection = 0;
    let uploading = false;
    function show() {
      details.replaceChildren();
      if (block.media_id) {
        const image = editor.renderBlock(document, block, {mediaPath: id => '/control/api/pages/media/' + id});
        if (image) details.append(image);
      }
    }
    const upload = action(buttons, copy('loadImage'), () => {
      const task = running(upload, local, async () => {
        const file = input.files[0];
        const current = selection;
        if (!file || file.size > 1024 * 1024 || !['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) throw new Error(copy('imageInvalid'));
        const data = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.addEventListener('load', () => resolve(reader.result.split(',')[1]));
          reader.addEventListener('error', () => reject(new Error(copy('imageInvalid'))));
          reader.readAsDataURL(file);
        });
        const saved = await api('pages/media', {data});
        if (!parent.isConnected || current !== selection) return;
        block.media_id = saved.id;
        input.value = '';
        changed();
        show();
        report(local, '');
      });
      if (!task) return;
      uploading = true;
      task.finally(() => {uploading = false;upload.disabled = !input.files.length;});
    });
    input.addEventListener('change', () => {selection++;upload.disabled = uploading || !input.files.length;report(feedback, copy('unsaved'));});
    show();
    upload.disabled = true;
  }

  function changeForm(parent, label, run, {reason = true, description = ''} = {}) {
    const form = element('form', undefined, 'cw-inline-editor');
    if (description) form.append(element('p', description));
    const audit = reason ? field(form, copy('reason'), '', {max: 500}) : null;
    const feedback = status(form);
    const submit = element('button', label);
    submit.type = 'submit';
    form.append(submit);
    parent.append(form);
    form.addEventListener('submit', event => {
      event.preventDefault();
      running(submit, feedback, () => run(audit?.value.trim()));
    });
  }

  async function openRevision(state, revision, key, host, session, reload) {
    host.replaceChildren();
    const tools = actions(host);
    action(tools, copy('edit'), () => drawPage(host, state, key, session, reload));
    action(tools, copy('history'), () => readHistory(state, key, host, session, reload));
    const feedback = status(host, copy('loading'));
    try {
      const result = await api('pages/preview?' + scope(state.page, state.locale, {revision}));
      if (!feedback.isConnected) return;
      report(feedback, '');
      const preview = card(host, copy('preview'), 'publishing-preview');
      metadata(preview, [[copy('page'), result.page], [copy('language'), localeName(result.locale)], [copy('revision'), result.revision],
        [copy('live'), state.published?.revision === result.revision ? copy('published') : revisionKind(result.kind)]]);
      previewDocument(preview, result.content, result.locale);
      if (state.draft?.revision === revision && !drafts.has(key) && permissions(session, 'pages.publish')) {
        changeForm(host, copy('publish'), async reason => {
          const updated = await api('pages/publish', {page: state.page, locale: state.locale, expected_version: state.version, draft_revision: revision, reason});
          if (feedback.isConnected) drawPage(host, updated, key, session, reload, copy('published'));
        }, {description: `${copy('publish')} · ${state.page} · ${localeName(state.locale)} · ${copy('revision')} ${revision}`});
      }
    } catch (error) {
      if (feedback.isConnected) failure(feedback, error);
    }
  }

  function previewDocument(parent, content, language) {
    const preview = element('article', undefined, 'public-editorial-region publishing-preview-content');
    preview.lang = language;
    for (const [key, value] of Object.entries(content.fields)) appendPreviewField(preview, key, value, 'h2');
    for (const [name, blocks] of Object.entries(content.regions)) {
      if (!blocks.length) continue;
      const section = element('section', undefined, 'publishing-preview-region');
      section.setAttribute('aria-label', fieldName(name));
      editor.renderRegion(section, blocks, previewOptions());
      preview.append(section);
    }
    parent.append(preview);
  }

  function appendPreviewField(parent, key, value, headingTag) {
    if (key === 'href' || key.endsWith('.href')) {
      const destination = editor.previewUrl(document, value);
      if (destination) {
        const line = element('p');
        line.append(destination);
        parent.append(line);
      }
      return;
    }
    const isHeading = key === 'title' || key.endsWith('.title') || key.endsWith('-title');
    parent.append(element(isHeading ? headingTag : 'p', value));
  }

  function previewOptions() {
    return {
      preview: true,
      mediaPath: id => '/control/api/pages/media/' + id,
      source: ({fields}) => {
        const source = element('div', undefined, 'help-prose');
        for (const [key, value] of Object.entries(fields)) appendPreviewField(source, key, value, 'h3');
        return source;
      },
    };
  }

  async function readHistory(state, key, host, session, reload, before = null) {
    host.replaceChildren();
    const tools = actions(host);
    action(tools, copy('edit'), () => drawPage(host, state, key, session, reload));
    const wrapper = card(host, copy('history'));
    const feedback = status(wrapper, copy('loading'));
    try {
      const result = await api('pages/history?' + scope(state.page, state.locale, before === null ? {} : {before}));
      if (!wrapper.isConnected) return;
      report(feedback, '');
      for (const item of result.revisions) {
        const line = element('section', undefined, 'publishing-history-row');
        line.append(element('h3', `${copy('revision')} ${item.revision} · ${revisionKind(item.kind)}`));
        metadata(line, [['', shortDate(item.created_at)], [copy('actor'), item.author_id, true]]);
        const row = actions(line);
        action(row, copy('preview'), () => openRevision(state, item.revision, key, host, session, reload));
        const restore = action(row, copy('restore'), () => {
          restore.hidden = true;
          changeForm(line, copy('confirmRestore'), async reason => {
            const updated = await api('pages/restore', {page: state.page, locale: state.locale, expected_version: state.version, revision: item.revision, reason});
            if (line.isConnected) drawPage(host, updated, key, session, reload, copy('restored'));
          });
          line.querySelector('input').focus();
        }, {disabled: drafts.has(key)});
        wrapper.append(line);
      }
      const paging = actions(wrapper);
      if (before !== null) action(paging, copy('previous'), () => readHistory(state, key, host, session, reload));
      if (result.next_before != null) action(paging, copy('next'), () => readHistory(state, key, host, session, reload, result.next_before));
    } catch (error) {
      if (wrapper.isConnected) failure(feedback, error);
    }
  }

  async function android(session) {
    const root = view('android-releases');
    const feedback = status(root, copy('loading'));
    const content = element('div', undefined, 'publishing-releases');
    root.append(content);
    let request = 0;
    async function load() {
      const current = ++request;
      try {
        const data = await api('android-releases');
        if (!root.isConnected || request !== current) return;
        report(feedback, '');
        drawReleases(content, data, session, load);
      } catch (error) {
        if (root.isConnected && request === current) {
          failure(feedback, error);
          content.replaceChildren();
          action(content, copy('refresh'), load);
        }
      }
    }
    await load();
  }

  function releaseDetails(parent, release) {
    const bytes = release.bytes;
    const [unit, scale] = bytes >= 1000000 ? ['megabyte', 1000000] : bytes >= 1000 ? ['kilobyte', 1000] : ['byte', 1];
    const number = new Intl.NumberFormat(getLanguage(), {style: 'unit', unit, maximumFractionDigits: 1});
    metadata(parent, [[copy('version'), release.version_name], [copy('versionCode'), release.version_code],
      [copy('size'), bytes ? number.format(bytes / scale) : null], [copy('package'), release.package_name, true],
      [copy('signer'), release.certificate_sha256, true], [copy('checksum'), release.apk_sha256, true]]);
  }

  function drawReleases(host, data, session, refresh) {
    host.replaceChildren();
    const current = card(host, copy('releaseActive'));
    if (data.current) releaseDetails(current, data.current);
    else current.append(element('p', copy('releaseNone')));
    const options = actions(host);
    const canUpload = permissions(session, 'android.upload');
    if (canUpload) {
      const feedback = status(options);
      const create = action(options, copy('create'), () => running(create, feedback, async () => {
        await api('android-releases/draft', {});
        if (host.isConnected) await refresh();
      }), {primary: true});
    }
    action(options, copy('refresh'), refresh);
    const candidates = card(host, copy('releases'));
    if (!data.drafts.length) candidates.append(element('p', copy('empty')));
    for (const release of data.drafts) drawCandidate(candidates, release, session, refresh);
    const history = card(host, copy('history'));
    if (!data.history.length) history.append(element('p', copy('empty')));
    for (const release of data.history) {
      const row = element('section', undefined, 'publishing-history-row');
      row.append(element('h3', copy(release.state)));
      if (release.published_at || release.updated_at) row.append(element('p', shortDate(release.published_at || release.updated_at)));
      releaseDetails(row, release);
      history.append(row);
    }
  }

  function drawCandidate(parent, release, session, refresh) {
    const section = element('section', undefined, 'publishing-history-row');
    section.append(element('h3', copy(release.state)));
    if (release.updated_at) section.append(element('p', shortDate(release.updated_at)));
    releaseDetails(section, release);
    parent.append(section);
    const feedback = status(section);
    if (release.error) failure(feedback, {code: release.error});
    const row = actions(section);
    const canUpload = permissions(session, 'android.upload');
    const identity = {id: release.id, revision: release.revision};
    async function transition(path) {
      await api('android-releases/' + path, identity);
      if (parent.isConnected) await refresh();
    }
    if (release.state === 'draft' && canUpload) apkInput(section, release, refresh);
    if (release.state === 'uploaded' && canUpload) {
      const validate = action(row, copy('validate'), () => running(validate, feedback, () => transition('validate'), copy('validating')), {primary: true});
    }
    if (release.state === 'validated' && permissions(session, 'android.publish')) {
      addConfirmation(section, copy('review'), copy('releasePublish'), () => transition('publish'), copy('releasePublishHelp'));
    }
    if (canUpload) addConfirmation(section, copy('releaseCancel'), copy('confirm'), () => transition('cancel'));
  }

  function addConfirmation(parent, label, confirm, run, description = '') {
    const disclosure = element('details', undefined, 'publishing-group');
    disclosure.append(element('summary', label));
    changeForm(disclosure, confirm, run, {reason: false, description});
    parent.append(disclosure);
  }

  function apkInput(parent, release, refresh) {
    const form = element('form', undefined, 'cw-inline-editor publishing-file-form');
    const hint = element('p', copy('pickFile'));
    form.append(hint);
    const input = field(form, copy('file'), '', {type: 'file', required: false});
    input.accept = '.apk,application/vnd.android.package-archive';
    const feedback = status(form);
    const submit = element('button', copy('upload'));
    submit.type = 'submit';
    submit.disabled = true;
    form.append(submit);
    parent.append(form);
    let file = null;
    function choose(files) {
      if (submit.dataset.busy === 'true') return;
      file = files.length === 1 ? files[0] : null;
      const valid = file && /\.apk$/i.test(file.name) && file.size > 0 && file.size <= 512 * 1024 * 1024;
      if (!valid) file = null;
      submit.disabled = !file;
      report(feedback, file ? file.name : copy('pickFile'), !file);
    }
    input.addEventListener('change', () => choose(input.files));
    form.addEventListener('dragover', event => {event.preventDefault();});
    form.addEventListener('drop', event => {event.preventDefault(); choose(event.dataTransfer.files);});
    form.addEventListener('submit', event => {
      event.preventDefault();
      if (!file) return;
      running(submit, feedback, async () => {
        submit.dataset.busy = 'true';
        input.disabled = true;
        try {
          await uploadApk(release, file, fraction => {
            if (form.isConnected) report(feedback, `${copy('upload')} · ${new Intl.NumberFormat(getLanguage(), {style: 'percent'}).format(fraction)}`);
          });
          if (form.isConnected) await refresh();
        } finally {
          input.disabled = false;
          delete submit.dataset.busy;
        }
      });
    });
  }

  function clear() {
    drafts.clear();
    saving.clear();
    pageChoice = null;
    localeChoice = null;
  }
  return {pages, android, clear};
}
