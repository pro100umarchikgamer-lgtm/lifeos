"""Compact normal/reduced-motion check against actual built CSS and disposable WSGI.

Checks observed geometry, native CSS motion and filtering; no device FPS claims.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from tool.check_web_platform import fixture, login
from tool.web_browser_navigation import open_tab, open_finance_section


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('web_evidence/motion'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    results=[]
    with fixture() as (origin,backend,actor,workspace),sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=os.environ.get('ULADIM_CHROMIUM'))
        for preference in ['no-preference','reduce']:
            context=browser.new_context(viewport={'width':390,'height':844},locale='ru-RU',timezone_id='Europe/Moscow',reduced_motion=preference,service_workers='block')
            page=context.new_page();page.set_default_timeout(4000);errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            row={'motion':preference,'checks':{},'observations':{}};checks=row['checks'];observations=row['observations']
            def settle(locator):
                locator.evaluate('e=>Promise.all(e.getAnimations().map(a=>a.finished.catch(()=>{})))')
            def styles(locator):
                return locator.evaluate('''e=>{const s=getComputedStyle(e);return {animation:s.animationName,duration:s.animationDuration,transform:s.transform,transition:s.transitionProperty,transitionDuration:s.transitionDuration,frames:e.getAnimations().filter(a=>a.effect?.target===e).map(a=>({duration:a.effect.getTiming().duration,frames:a.effect.getKeyframes()}))};}''')
            try:
                login(page,origin);settle(page.locator('main'))
                response=context.request.get(origin+'/assets/design.css')
                actual=response.body();built=Path('backend/webassets/design.css').read_bytes()
                assert response.ok and actual==built,'fixture must serve actual built stylesheet'
                observations['built_css_sha256']=hashlib.sha256(actual).hexdigest()
                open_tab(page,'Задачи');settle(page.locator('main'))
                if preference=='no-preference':
                    legacy=page.locator('.task-reset-filters').evaluate('''e=>{const body=document.body,before=body.getAttribute('data-design');body.setAttribute('data-design','');const s=getComputedStyle(e),result={visibility:s.visibility,opacity:s.opacity};if(before===null)body.removeAttribute('data-design');else body.setAttribute('data-design',before);return result;}''')
                    observations['legacy_idle_reset']=legacy
                    checks['legacy_idle_reset_hidden']=legacy['visibility']=='hidden' and legacy['opacity']=='0'
                    settle(page.locator('main'))
                task_list=page.locator('.task-list');before=task_list.bounding_box()['y']
                slots=page.locator('.task-filters').evaluate('''e=>{const status=e.querySelector('[name=task-status]').getBoundingClientRect(),reset=e.querySelector('.task-reset-filters').getBoundingClientRect();return {status:{top:status.top,bottom:status.bottom},reset:{top:reset.top,bottom:reset.bottom}};}''')
                observations['task_reset_slot']=slots
                checks['task_reset_shares_status_row']=slots['reset']['top']<slots['status']['bottom'] and slots['reset']['bottom']>slots['status']['top']
                page.locator('[name=task-search]').fill('Ничего совпадающего123')
                active=task_list.bounding_box()['y'];expect(task_list).to_contain_text('Ничего не найдено')
                page.get_by_role('button',name='Сбросить фильтры',exact=True).click()
                reset=task_list.bounding_box()['y'];expect(page.locator('[name=task-search]')).to_have_value('')
                observations['task_list_top']=[before,active,reset]
                checks['task_reset_footprint_stable']=max(before,active,reset)-min(before,active,reset)<1
                checks['task_results_update_immediately']=page.locator('.task-row').count()==2
                checks['filter_does_not_replay_view_entry']=page.locator('main').evaluate('e=>e.getAnimations().every(a=>a.playState!=="running")')
                open_tab(page,'Финансы');open_finance_section(page,'ledger');settle(page.locator('main'))
                page.locator('.finance-filter-panel>summary').click()
                panel=page.locator('.finance-filter-panel');before=panel.bounding_box()['height']
                page.locator('[name=finance-search]').fill('Ничего совпадающего123')
                active=panel.bounding_box()['height'];expect(page.locator('.ledger')).to_contain_text('Ничего не найдено')
                page.get_by_role('button',name='Сбросить фильтры',exact=True).click()
                reset=panel.bounding_box()['height'];expect(page.locator('.ledger-row')).to_have_count(2)
                observations['finance_panel_height']=[before,active,reset]
                checks['finance_reset_footprint_stable']=max(before,active,reset)-min(before,active,reset)<1
                button=page.get_by_role('button',name='Добавить операцию',exact=True)
                button.scroll_into_view_if_needed();box=button.bounding_box()
                page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2);page.mouse.down();settle(button)
                press=styles(button);observations['press']=press
                if preference=='reduce':
                    checks['press_is_physically_still']=press['transform']=='none'
                    checks['press_transition_is_disabled']=press['transition']=='none' or all(float(v.strip().rstrip('s'))==0 for v in press['transitionDuration'].split(','))
                else:
                    checks['press_uses_short_transform_transition']='transform' in press['transition'] and all(float(v.strip().rstrip('s'))<=.2 for v in press['transitionDuration'].split(','))
                page.mouse.up()
                editor=page.get_by_role('dialog');expect(editor).to_be_visible()
                dialog=styles(editor);backdrop=editor.evaluate('''e=>{const s=getComputedStyle(e,'::backdrop');return {blur:s.backdropFilter,webkitBlur:s.webkitBackdropFilter,animation:s.animationName,duration:s.animationDuration,transform:s.transform};}''')
                observations['dialog']=dialog;observations['backdrop']=backdrop
                checks['backdrop_has_no_blur']=backdrop['blur'] in ['none',''] and backdrop.get('webkitBlur','none') in ['none','',None]
                if preference=='reduce':
                    checks['dialog_and_backdrop_still']=dialog['animation']=='none' and dialog['transform']=='none' and backdrop['animation']=='none'
                else:
                    checks['dialog_has_short_entry']=dialog['animation']!='none' and all(float(v.strip().rstrip('s'))<=.2 for v in dialog['duration'].split(','))
                    checks['backdrop_has_short_opacity_entry']=backdrop['animation']!='none' and all(float(v.strip().rstrip('s'))<=.2 for v in backdrop['duration'].split(','))
                settle(editor)
                editor.locator('[name=label]').fill('Проверка движения')
                editor.get_by_role('button',name='Закрыть',exact=True).click()
                choice=editor.locator('.editor-discard-choice');expect(choice).to_be_visible();choice_styles=styles(choice);observations['inline_choice']=choice_styles
                checks['one_inline_choice_retains_input']=page.get_by_role('dialog').count()==1 and editor.locator('[name=label]').input_value()=='Проверка движения'
                checks['inline_choice_motion']=choice_styles['animation']=='none' if preference=='reduce' else choice_styles['animation']!='none' and all(float(v.strip().rstrip('s'))<=.2 for v in choice_styles['duration'].split(','))
                settle(choice);page.screenshot(path=str(args.output/(preference+'-inline-choice.jpg')),type='jpeg',quality=70)
                editor.get_by_role('button',name='Не сохранять',exact=True).click();expect(editor).to_have_count(0)
                open_tab(page,'Заметки');settle(page.locator('main'));page.locator('.intro>button').click()
                note=page.get_by_role('dialog');expect(note).to_be_visible();note_styles=styles(note);observations['note_dialog']=note_styles
                checks['note_entry_has_no_physical_motion']=note_styles['animation']=='none' if preference=='reduce' else note_styles['animation']!='none' and all('transform' not in frame for animation in note_styles['frames'] for frame in animation['frames'])
                note.get_by_role('button',name='Отмена',exact=True).click();expect(note).to_have_count(0)
                checks['no_page_errors']=not errors
                row['status']='passed' if all(checks.values()) else 'failed'
            except Exception as error:
                row['status']='error';row['error']=str(error);row['page_errors']=errors
            finally:context.close()
            results.append(row)
        browser.close()
    (args.output/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    for row in results:print(json.dumps({'motion':row['motion'],'status':row['status'],'failed':[key for key,value in row['checks'].items() if not value],'error':row.get('error')},ensure_ascii=False))
    if any(row['status']!='passed' for row in results):raise SystemExit(1)

if __name__=='__main__':main()
