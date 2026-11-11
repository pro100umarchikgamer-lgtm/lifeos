"""Shared selectors for the responsive workspace navigation."""


def open_tab(page, label):
    nav = page.locator('.nav')
    if label in ('Профиль', 'Заметки') and nav.locator('.nav-more').is_visible():
        nav.locator('.nav-more > summary').click()
    nav.get_by_role('button', name=label, exact=True).click()


def open_settings(page, section):
    back = page.locator('.settings-back')
    if back.is_visible():
        back.click()
    page.locator(f'.settings-navigation button[data-section="{section}"]').click()
