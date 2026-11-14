"""Shared selectors for the responsive workspace navigation."""


def open_tab(page, label):
    nav = page.locator('.nav')
    if label == 'Профиль':
        page.locator('.header-profile').click()
        return
    tabs = {'Сегодня': 'today', 'Задачи': 'tasks', 'Календарь': 'calendar',
            'Заметки': 'notes', 'Финансы': 'money'}
    if label in tabs:
        # The phone has six direct destinations; the desktop finance overview
        # uses a longer label and tasks may carry a separate count badge.
        nav.locator(f'button[data-tab="{tabs[label]}"][data-section=""]:visible').click()
    else:
        nav.get_by_role('button', name=label, exact=True).click()


def open_settings(page, section):
    back = page.locator('.settings-back')
    if back.is_visible():
        back.click()
    if section == 'profile' and page.locator('.reference-profile-page').is_visible():
        return
    navigation = page.locator(f'.settings-navigation button[data-section="{section}"]')
    if navigation.is_visible():
        navigation.click()
    else:
        page.locator(f'.reference-profile-options button[data-settings-section="{section}"]').click()


def open_finance_section(page, section):
    """Use the sidebar on desktop and the compact finance tabs on a phone."""
    sidebar = page.locator(f'.nav button[data-tab="money"][data-section="{section}"]:visible')
    if sidebar.count():
        sidebar.click()
    else:
        page.locator(f'.finance-navigation button[data-section="{section}"]:visible').click()
