"""A late workspace response must never populate the newly selected workspace."""
import os

from playwright.sync_api import sync_playwright

from tool.check_web_platform import fixture, login


def main():
    with fixture() as (origin, _backend, _actor, _workspace), sync_playwright() as p:
        options = {'executable_path': os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}
        browser = p.chromium.launch(**options)
        try:
            page = browser.new_page()
            login(page, origin)
            # Control sync response order while exercising the real workspace
            # picker, refresh queue, readSpace and renderer.
            page.evaluate("""() => {
                window.focusOriginalCall = call;
                window.focusSyncResolvers = {};
                state.space = 'A';
                state.spaces = [{id:'A', name:'Space A'}, {id:'B', name:'Space B'}];
                state.syncSpace = null;
                state.records = [];
                call = async path => {
                    if (path === 'spaces') return {spaces:state.spaces};
                    if (path.startsWith('roster')) return {};
                    if (path.startsWith('sync?')) return new Promise(resolve => {
                        focusSyncResolvers[path.includes('workspace=A') ? 'A' : 'B'] = resolve;
                    });
                    return focusOriginalCall(path);
                };
                refresh().then(render);
            }""")
            page.wait_for_function('!!window.focusSyncResolvers.A')
            page.evaluate('render()')
            page.locator('select.workspace').select_option('B')
            page.evaluate("""() => focusSyncResolvers.A({
                records:[{id:'a-task', kind:'task', data:{title:'ONLY SPACE A SECRET',
                    completed:0, assignment:'any', assignees:[], review:0}}],
                cursor:1, epoch:'test', more:false
            })""")
            page.wait_for_function('!!window.focusSyncResolvers.B')
            pending = page.evaluate("""() => ({
                space:state.space, syncSpace:state.syncSpace,
                records:state.records.map(record => record.id),
                leaked:document.body.innerText.includes('ONLY SPACE A SECRET')
            })""")
            assert pending['space'] == 'B', pending
            assert pending['syncSpace'] != 'A' and not pending['records'] and not pending['leaked'], pending
            page.evaluate("""() => focusSyncResolvers.B({
                records:[{id:'b-task', kind:'task', data:{title:'ONLY SPACE B TASK',
                    completed:0, assignment:'any', assignees:[], review:0}}],
                cursor:1, epoch:'test', more:false
            })""")
            page.wait_for_function("state.syncSpace === 'B' && state.syncState === 'read'")
            assert page.get_by_text('ONLY SPACE B TASK', exact=True).count() > 0
            assert page.get_by_text('ONLY SPACE A SECRET', exact=True).count() == 0
        finally:
            browser.close()
    print('PASS: delayed old workspace sync cannot render after workspace selection')


if __name__ == '__main__':
    main()
