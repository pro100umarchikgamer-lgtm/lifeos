"""Shared selectors for the responsive workspace navigation."""


def choose_field(field, value=None, *, label=None):
    """Choose through the visible app menu, or an unchanged native select.

    The shared menu keeps its native form carrier. Its visible trigger and
    hidden listbox can share an accessible label, so resolve the trigger
    explicitly rather than treating the labeled node as a native select.
    """
    if (value is None) == (label is None):
        raise ValueError('Choose exactly one option value or label')
    field.first.wait_for(state='attached')
    nodes = field.all()
    triggers = [node for node in nodes if node.evaluate(
        "node => node.matches('button.field-menu-trigger')")]
    if triggers:
        assert len(triggers) == 1, 'Choice label must identify one visible field'
        trigger = triggers[0]
        wrapper = trigger.locator('..')
        carrier = wrapper.locator(':scope > select')
    else:
        carriers = [node for node in nodes if node.evaluate(
            "node => node.tagName === 'SELECT'")]
        assert len(carriers) == 1, 'Choice must identify one native value carrier'
        carrier = carriers[0]
        if not carrier.evaluate('node => Boolean(node.choiceField)'):
            return carrier.select_option(**({'value': value} if value is not None else {'label': label}))
        wrapper = carrier.locator('..')
        trigger = wrapper.locator(':scope > button.field-menu-trigger')
    caption = carrier.evaluate("""(select, requested) => {
        const option = Array.from(select.options).find(option =>
            requested.value !== null ? option.value === requested.value : option.label === requested.label);
        return option && !option.disabled && !option.parentElement.disabled ? option.textContent : null;
    }""", {'value': value, 'label': label})
    assert caption is not None, 'Requested choice must be available'
    trigger.click()
    wrapper.get_by_role('option', name=caption, exact=True).click()


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
