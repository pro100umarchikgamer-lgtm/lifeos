"""Render isolated HTML concepts at real CSS viewport sizes; no production access."""
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'web_evidence/design-20261109'
SCREENS=('home','today','finance','account','tasks','notes','family','plans','apply','login','support','control')
VIEWPORTS={'desktop':(1440,1000),'ipad':(820,1180),'iphone':(390,844)}


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT/'design/20261109')))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    checks=[];errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(args=['--no-sandbox'])
            for direction in ('clarity','signal','bloom'):
                for device, (width,height) in VIEWPORTS.items():
                    page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    for screen in SCREENS:
                        page.goto(f'http://127.0.0.1:{server.server_port}/?direction={direction}&screen={screen}',wait_until='networkidle')
                        assert page.locator('h1').count()==1,(direction,device,screen,'heading')
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(direction,device,screen,'horizontal overflow')
                        if device=='iphone' and screen not in ('home','plans','apply','login'):
                            assert page.locator('.bottom-nav').is_visible()
                        page.screenshot(path=str(OUT/f'{direction}-{device}-{screen}.png'))
                        checks.append({'direction':direction,'screen':screen,'viewport':[width,height],'overflow':False})
                    # Prove actual interactions, rather than drawing a static picture.
                    page.goto(f'http://127.0.0.1:{server.server_port}/?direction={direction}&screen=today')
                    item=page.get_by_role('checkbox',name='Подготовить план на следующую неделю',exact=True)
                    item.check();assert item.is_checked()
                    page.close()
                contact_sheet(direction)
            browser.close()
        assert not errors,errors
    finally:
        server.shutdown();server.server_close();thread.join(5)
    (OUT/'RESULT.json').write_text(json.dumps({'result':'passed','screenshots':len(checks),'checks':checks,'scope':'Synthetic design previews, not authenticated production or physical Safari acceptance'},ensure_ascii=False,indent=2))
    print('DESIGN_CONCEPTS_OK',len(checks))


def contact_sheet(direction):
    canvas=Image.new('RGB',(1600,1930),'#e9e9ed');draw=ImageDraw.Draw(canvas)
    try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19)
    except OSError: font=ImageFont.load_default()
    titles={'clarity':'01 / CLARITY — neutral, precise, quiet','signal':'02 / SIGNAL — dark, technical, focused','bloom':'03 / BLOOM — warm, soft, human'}
    draw.text((30,20),titles[direction],font=font,fill='#222230')
    for device,screen,x,y,w in [('desktop','home',30,95,755),('desktop','today',815,95,755),('desktop','finance',30,680,755),('desktop','account',815,680,755),('iphone','today',30,1270,270),('iphone','finance',335,1270,270),('iphone','account',640,1270,270),('ipad','finance',970,1270,420)]:
        img=Image.open(OUT/f'{direction}-{device}-{screen}.png').convert('RGB')
        img=img.resize((w,round(img.height*w/img.width)),Image.Resampling.LANCZOS)
        draw.text((x,y-30),device.upper()+' / '+screen.upper(),font=font,fill='#454552')
        canvas.paste(img,(x,y))
    canvas.save(OUT/f'{direction}-overview.png')


if __name__=='__main__':main()
