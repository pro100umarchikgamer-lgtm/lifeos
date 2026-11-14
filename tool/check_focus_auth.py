"""Both customer sign-in routes retain real login and responsive Focus layout."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from tool.check_web_platform import fixture, PASSWORD


def main():
    out = Path('web_evidence/focus-auth')
    out.mkdir(parents=True, exist_ok=True)
    with fixture() as (origin, *_), sync_playwright() as p:
        browser = p.chromium.launch(**({'executable_path': os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
        for route in ['/app', '/account']:
            context = browser.new_context(locale='ru-RU', viewport={'width': 1440, 'height': 1000})
            page = context.new_page()
            page.goto(origin + route)
            expect(page.get_by_role('button', name='Войти', exact=True)).to_be_visible()
            for name, width, height in [('desktop', 1440, 1000), ('ipad', 820, 1180), ('phone', 375, 812)]:
                for theme in ['light', 'dark']:
                    page.set_viewport_size({'width': width, 'height': height})
                    page.evaluate('theme=>document.body.dataset.theme=theme', theme)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    story = page.locator('.focus-login-story')
                    if width >= 1000:
                        expect(story).to_be_visible()
                        assert story.bounding_box()['width'] >= 350
                        assert story.bounding_box()['x'] < page.locator('input[name=email]').bounding_box()['x']
                    else:
                        expect(story).to_be_hidden()
                    page.screenshot(path=str(out / f'{route.strip("/")}-{name}-{theme}.png'), full_page=True)
            page.get_by_label('Электронная почта', exact=True).fill('web@example.test')
            page.locator('input[name=password]').fill(PASSWORD)
            page.get_by_role('button', name='Войти', exact=True).click()
            expect(page.get_by_role('heading', name='Сегодня', exact=True)).to_be_visible()
            context.close()
        browser.close()
    print('PASS: both sign-in routes, wide two-column layout, one-column phone/tablet, both themes, real login')


if __name__ == '__main__':
    main()
