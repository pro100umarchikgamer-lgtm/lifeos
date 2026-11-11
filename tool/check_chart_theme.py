"""Actual canvas pixels must follow system-theme changes without navigation."""
from playwright.sync_api import sync_playwright
from tool.check_web_platform import fixture, login

def main():
    with fixture() as (origin,*_),sync_playwright() as p:
        browser=p.chromium.launch();context=browser.new_context(color_scheme='light');page=context.new_page()
        try:
            login(page,origin);page.locator('.nav').get_by_role('button',name='Финансы',exact=True).click()
            page.locator('canvas').wait_for();page.wait_for_timeout(100)
            page.evaluate("state.theme='system';preferences()")
            page.get_by_role('button',name='Добавить операцию',exact=True).click()
            page.get_by_role('dialog').locator('[name=amount]').fill('125,50')
            page.emulate_media(color_scheme='dark')
            page.wait_for_function('''()=>{const c=document.querySelector('canvas'),pixel=c.getContext('2d').getImageData(30,70,1,1).data,color=getComputedStyle(document.body).getPropertyValue('--income').trim();return [1,3,5].every((at,i)=>parseInt(color.slice(at,at+2),16)===pixel[i])}''',timeout=2500)
            assert page.get_by_role('dialog').locator('[name=amount]').input_value()=='125,50','theme change destroyed the draft'
            print('SYSTEM_CHART_THEME_PASSED: actual canvas colors follow OS theme')
        finally:context.close();browser.close()
if __name__=='__main__':main()
