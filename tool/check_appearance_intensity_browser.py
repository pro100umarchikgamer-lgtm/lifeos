"""Focused keyboard and palette/contrast checks for decorative intensity."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from tool.check_web_platform import fixture, login
from tool.web_browser_navigation import open_tab, open_settings
from tool.check_finance_filter_fit import source_styles


def main():
    out=Path('web_evidence/appearance-intensity');out.mkdir(parents=True,exist_ok=True)
    checks=[]
    with fixture() as (origin,_backend,_actor,_wid),sync_playwright() as p:
        browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
        context=browser.new_context(viewport={'width':1280,'height':1100},locale='ru-RU',service_workers='block',reduced_motion='reduce')
        styles=source_styles()
        context.route('**/assets/design.css',lambda route:route.fulfill(status=200,content_type='text/css',body=styles))
        # Parent integrates this source into the explicit production asset allowlist.
        helper=Path('backend/webassets/app/appearance-intensity.js').read_text()
        context.route('**/app/assets/appearance-intensity.js',lambda route:route.fulfill(status=200,content_type='text/javascript',body=helper))
        page=context.new_page();login(page,origin)
        if not page.evaluate('!!window.UladimAppearance'):
            page.add_script_tag(url=origin+'/app/assets/appearance-intensity.js')
        open_tab(page,'Профиль');open_settings(page,'appearance')
        page.evaluate('UladimAppearance.attachIntensity({container:document.querySelector(".appearance-settings"),state,save:preferences,E,append,input})')
        slider=page.locator('.appearance-intensity input[type=range]')
        expect(slider).to_have_attribute('min','0');expect(slider).to_have_attribute('max','100')
        slider.focus();slider.press('Home');expect(slider).to_have_value('0')
        slider.press('End');expect(slider).to_have_value('100')
        slider.press('ArrowLeft');expect(slider).to_have_value('99')
        assert page.evaluate('state.appearanceIntensity')==99
        for palette in ('violet','forest','ocean','pistachio','rose','sand'):
            for theme,system in (('light','light'),('dark','dark'),('system','light'),('system','dark')):
                page.emulate_media(color_scheme=system)
                samples=[]
                for value in (0,50,100):
                    data=page.evaluate('''({palette,theme,value})=>{
                        Object.assign(state,{palette,theme,appearanceIntensity:value});applyTheme();UladimAppearance.applyIntensity({state});
                        document.getAnimations().forEach(animation=>{try{animation.finish()}catch{}});
                        const style=el=>{const c=getComputedStyle(el);return {color:c.color,background:c.backgroundColor,filter:c.filter}};
                        const color=css=>{const c=document.createElement('canvas').getContext('2d');c.fillStyle=css;c.fillRect(0,0,1,1);return [...c.getImageData(0,0,1,1).data].slice(0,3)};
                        const lum=css=>color(css).map(n=>n/255).map(n=>n<=.04045?n/12.92:Math.pow((n+.055)/1.055,2.4)).reduce((s,n,i)=>s+n*[.2126,.7152,.0722][i],0);
                        const contrast=(a,b)=>{const v=[lum(a),lum(b)].sort((x,y)=>x-y);return(v[1]+.05)/(v[0]+.05)};
                        const body=style(document.body),title=style(document.querySelector('main h1')),button=style(document.querySelector('.header-profile'));
                        const surface=style(document.querySelector('.appearance-settings'));
                        const primary=document.querySelector('.appearance-settings input[type=range]');
                        const tokens=getComputedStyle(document.body),primaryBackground=tokens.getPropertyValue('--ux-button').trim(),primaryInk=tokens.getPropertyValue('--ux-button-ink').trim()||'#fff';
                        return {body,title,button,surface,primaryBackground,primaryInk,primaryContrast:contrast(primaryBackground,primaryInk),accent:getComputedStyle(primary).accentColor,
                            textContrast:contrast(title.color,body.background),value:state.appearanceIntensity,
                            overflow:document.documentElement.scrollWidth>innerWidth};
                    }''',{'palette':palette,'theme':theme,'value':value})
                    assert data['textContrast']>=4.5 and data['primaryContrast']>=4.5,(palette,theme,value,data)
                    assert not data['overflow'] and data['body']['filter']=='none',data
                    samples.append(data)
                    checks.append({'palette':palette,'theme':theme,'system':system,**data})
                assert samples[0]['body']['background']!=samples[-1]['body']['background'],(palette,theme,samples)
                for key in ('title','button','surface','accent','primaryBackground','primaryInk'):
                    assert samples[0][key]==samples[1][key]==samples[2][key],(palette,theme,key,samples)
        page.emulate_media(color_scheme='light')
        page.evaluate('Object.assign(state,{theme:"light",palette:"rose",appearanceIntensity:50});applyTheme();UladimAppearance.applyIntensity({state})')
        page.locator('select[name=theme]').select_option('light')
        page.locator('.palette-choice[data-palette-choice=rose]').click()
        slider.fill('50')
        page.locator('main h1').click()
        page.screenshot(path=str(out/'appearance-slider.png'),full_page=True)
        assert page.locator('.palette-choices .palette-choice').count()==6
        browser.close()
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
    print('APPEARANCE_INTENSITY_BROWSER_OK',len(checks),'palette/theme/intensity states; native keyboard range')


if __name__=='__main__':main()
