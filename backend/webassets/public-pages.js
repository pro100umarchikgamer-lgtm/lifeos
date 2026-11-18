'use strict';
(function (root) {
  const mediaId = /^[a-f0-9]{64}$/;
  const destinations = new Set(['/', '/account', '/app', '/app/', '/delete-account', '/docs', '/download', '/early-access', '/faq', '/plans', '/privacy', '/status', '/support', '/terms']);
  const record = value => !!value && typeof value === 'object' && !Array.isArray(value);
  const textFields = value => record(value) && Object.values(value).every(field => typeof field === 'string');

  function safeLink(value) {
    if (typeof value !== 'string' || /[\s\\\u0000-\u001f\u007f]/u.test(value)) return null;
    if (/^#[a-z][a-z0-9-]*$/.test(value)) return value;
    if (value.startsWith('/') && !value.startsWith('//')) {
      return destinations.has(value.split(/[?#]/, 1)[0]) ? value : null;
    }
    try {
      const url = new URL(value);
      if (value.startsWith('https://') && url.protocol === 'https:' && url.port !== '0' && !url.username && !url.password) return value;
    } catch { /* Invalid destinations have no visible link. */ }
    return null;
  }

  function previewUrl(document, value) {
    const href = safeLink(value);
    if (!href) return null;
    const code = document.createElement('code');
    code.dir = 'ltr';
    code.textContent = href;
    return code;
  }

  function renderBlock(document, block, {source, mediaPath, preview = false} = {}) {
    function element(tag, value, className) {
      const node = document.createElement(tag);
      if (typeof value === 'string') node.textContent = value;
      if (className) node.className = className;
      return node;
    }
    if (!block || typeof block !== 'object') return null;
    if (block.kind === 'source') return textFields(block.fields) ? source?.(block) || null : null;
    if (block.kind === 'text') {
      const section = element('section', undefined, 'help-prose public-editorial-text');
      if (block.title) section.append(element('h2', block.title));
      section.append(element('p', block.body));
      return section;
    }
    if (block.kind === 'link') {
      const href = safeLink(block.href);
      if (!href) return null;
      const link = element(preview ? 'span' : 'a', block.label, 'help-inline-link public-editorial-link');
      if (preview) link.append(' · ', previewUrl(document, href));
      else link.href = href;
      return link;
    }
    if (block.kind === 'image' && mediaId.test(block.media_id || '')) {
      const figure = element('figure', undefined, 'public-editorial-image');
      const image = element('img');
      image.src = (mediaPath || (id => '/public-pages/media/' + id))(block.media_id);
      image.alt = typeof block.alt === 'string' ? block.alt : '';
      image.loading = 'lazy';
      image.decoding = 'async';
      figure.append(image);
      if (block.caption) figure.append(element('figcaption', block.caption));
      return figure;
    }
    return null;
  }

  function renderRegion(host, blocks, options = {}) {
    for (const block of blocks) {
      const node = renderBlock(host.ownerDocument, block, options);
      if (node) host.append(options.wrap && block.kind !== 'source' ? options.wrap(node) : node);
    }
  }

  function field(content, key, fallback) {
    const value = content?.fields?.[key];
    return typeof value === 'string' ? value : fallback;
  }

  function region(content, key, baseline) {
    const value = content?.regions?.[key];
    return Array.isArray(value) ? value : baseline;
  }

  async function load(page, locale, signal) {
    const query = new URLSearchParams({page, lang: locale});
    const response = await root.fetch('/public-pages/document?' + query, {
      credentials: 'omit', cache: 'no-store', redirect: 'error', signal,
    });
    if (!response.ok) return null;
    const result = await response.json();
    if (!record(result) || result.page !== page || result.locale !== locale || !Number.isSafeInteger(result.revision) || result.revision < 0) return null;
    const {content} = result;
    if (!record(content) || !textFields(content.fields) || !record(content.regions)) return null;
    for (const blocks of Object.values(content.regions)) {
      if (!Array.isArray(blocks) || !blocks.every(block => record(block) && typeof block.id === 'string' &&
          (block.kind === 'source' ? textFields(block.fields) : ['text', 'image', 'link'].includes(block.kind)))) return null;
    }
    return content;
  }

  root.UladimPublicPages = {safeLink, previewUrl, renderBlock, renderRegion, field, region, load};
})(globalThis);
