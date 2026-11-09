"""Build web catalogs from Android's authoritative locales and native-code app icons."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'backend/webassets/app'
# All user-facing text comes from complete existing packs, plus these web-specific facts.
EXTRA = {
 'ru': ['Для работы нужен интернет. Личные данные не сохраняются в браузере.', 'Safari → Поделиться → На экран «Домой».'],
 'en': ['An internet connection is required. Personal records are not stored in the browser.', 'Safari → Share → Add to Home Screen.'],
 'de': ['Eine Internetverbindung ist erforderlich. Persönliche Daten werden nicht im Browser gespeichert.', 'Safari → Teilen → Zum Home-Bildschirm.'],
 'fr': ['Une connexion Internet est nécessaire. Les données personnelles ne sont pas stockées dans le navigateur.', 'Safari → Partager → Sur l’écran d’accueil.'],
 'es': ['Se necesita conexión a Internet. Los datos personales no se guardan en el navegador.', 'Safari → Compartir → Añadir a pantalla de inicio.'],
 'it': ['È necessaria una connessione Internet. I dati personali non vengono salvati nel browser.', 'Safari → Condividi → Aggiungi alla schermata Home.'],
 'pt': ['É necessária uma ligação à Internet. Os dados pessoais não são guardados no navegador.', 'Safari → Partilhar → Adicionar ao ecrã principal.'],
 'uk': ['Для роботи потрібен інтернет. Особисті дані не зберігаються в браузері.', 'Safari → Поділитися → На початковий екран.'],
 'kk': ['Жұмыс істеу үшін интернет қажет. Жеке деректер браузерде сақталмайды.', 'Safari → Бөлісу → Басты экранға қосу.'],
 'ky': ['Иштөө үчүн интернет керек. Жеке маалыматтар браузерде сакталбайт.', 'Safari → Бөлүшүү → Башкы экранга кошуу.'],
 'tg': ['Барои кор интернет лозим аст. Маълумоти шахсӣ дар браузер нигоҳ дошта намешавад.', 'Safari → Мубодила → Илова ба экрани асосӣ.'],
 'az': ['İşləmək üçün internet lazımdır. Şəxsi məlumatlar brauzerdə saxlanılmır.', 'Safari → Paylaş → Əsas ekrana əlavə et.'],
 'uz-Latn': ['Ishlash uchun internet kerak. Shaxsiy ma’lumotlar brauzerda saqlanmaydi.', 'Safari → Ulashish → Bosh ekranga qo‘shish.'],
 'uz-Cyrl': ['Ишлаш учун интернет керак. Шахсий маълумотлар браузерда сақланмайди.', 'Safari → Улашиш → Бош экранга қўшиш.'],
 'ka': ['მუშაობისთვის საჭიროა ინტერნეტი. პირადი მონაცემები ბრაუზერში არ ინახება.', 'Safari → გაზიარება → მთავარ ეკრანზე დამატება.'],
 'hy': ['Աշխատելու համար անհրաժեշտ է համացանց։ Անձնական տվյալները զննարկիչում չեն պահվում։', 'Safari → Կիսվել → Ավելացնել գլխավոր էկրանին։'],
}


MFA_HINT = {
 'ru':'Введите новый код из приложения-аутентификатора или неиспользованный резервный код.',
 'en':'Enter a fresh authenticator code or an unused recovery code.',
 'de':'Gib einen aktuellen Authenticator-Code oder einen unbenutzten Wiederherstellungscode ein.',
 'fr':'Saisissez un code actuel de votre application ou un code de secours inutilisé.',
 'es':'Introduce un código actual del autenticador o un código de recuperación sin usar.',
 'it':'Inserisci un codice aggiornato dell’autenticatore o un codice di recupero inutilizzato.',
 'pt':'Introduza um código atual do autenticador ou um código de recuperação não utilizado.',
 'uk':'Введіть новий код із застосунку-автентифікатора або невикористаний резервний код.',
 'kk':'Аутентификатордағы жаңа кодты немесе пайдаланылмаған қалпына келтіру кодын енгізіңіз.',
 'ky':'Аутентификатордон жаңы кодду же колдонула элек калыбына келтирүү кодун киргизиңиз.',
 'tg':'Рамзи нави барномаи тасдиқкунанда ё рамзи эҳтиётии истифоданашударо ворид кунед.',
 'az':'Autentifikatorun cari kodunu və ya istifadə olunmamış bərpa kodunu daxil edin.',
 'uz-Latn':'Autentifikatorning yangi kodini yoki ishlatilmagan tiklash kodini kiriting.',
 'uz-Cyrl':'Аутентификаторнинг янги кодини ёки ишлатилмаган тиклаш кодини киритинг.',
 'ka':'შეიყვანეთ ავთენტიფიკატორის ახალი კოდი ან გამოუყენებელი აღდგენის კოდი.',
 'hy':'Մուտքագրեք նույնականացման հավելվածի նոր կոդը կամ չօգտագործված վերականգնման կոդը։',
}

WEB_SESSION_EXPIRED = {
 'ru':'Сессия истекла. Войдите снова. Несохранённые данные нужно ввести повторно.',
 'en':'Your session expired. Sign in again and re-enter any unsaved data.',
 'de':'Deine Sitzung ist abgelaufen. Melde dich erneut an und gib ungespeicherte Daten nochmals ein.',
 'fr':'Votre session a expiré. Reconnectez-vous et saisissez à nouveau les données non enregistrées.',
 'es':'Tu sesión ha caducado. Inicia sesión de nuevo y vuelve a introducir los datos sin guardar.',
 'it':'La sessione è scaduta. Accedi di nuovo e reinserisci i dati non salvati.',
 'pt':'A sessão expirou. Entre novamente e volte a introduzir os dados não guardados.',
 'uk':'Сесія закінчилася. Увійдіть знову та повторно введіть незбережені дані.',
 'kk':'Сеанс аяқталды. Қайта кіріп, сақталмаған деректерді қайта енгізіңіз.',
 'ky':'Сеанстын мөөнөтү бүттү. Кайра кирип, сакталбаган маалыматтарды кайра киргизиңиз.',
 'tg':'Муҳлати ҷаласа тамом шуд. Аз нав ворид шавед ва маълумоти сабтнашударо дубора нависед.',
 'az':'Sessiyanın vaxtı bitdi. Yenidən daxil olun və saxlanmamış məlumatları təkrar daxil edin.',
 'uz-Latn':'Seans muddati tugadi. Qayta kiring va saqlanmagan ma’lumotlarni qayta kiriting.',
 'uz-Cyrl':'Сеанс муддати тугади. Қайта киринг ва сақланмаган маълумотларни қайта киритинг.',
 'ka':'სესია დასრულდა. ხელახლა შედით და თავიდან შეიყვანეთ შეუნახავი მონაცემები.',
 'hy':'Նիստն ավարտվել է։ Կրկին մուտք գործեք և նորից լրացրեք չպահպանված տվյալները։',
}

ONBOARDING = {
 'ru':['Создать личное пространство','Начните с личного пространства. Затем добавьте первую задачу, заметку или счёт. Для общих дел создайте пространство семьи.'],
 'en':['Create a personal space','Start with a personal space. Then add your first task, note or account. Create a family space for shared plans.'],
 'de':['Persönlichen Bereich erstellen','Beginne mit einem persönlichen Bereich. Füge eine Aufgabe, Notiz oder ein Konto hinzu. Erstelle für gemeinsame Pläne einen Familienbereich.'],
 'fr':['Créer un espace personnel','Créez un espace personnel, puis votre première tâche, note ou compte. Utilisez un espace familial pour vos projets communs.'],
 'es':['Crear un espacio personal','Empieza con un espacio personal y añade una tarea, nota o cuenta. Crea un espacio familiar para los planes compartidos.'],
 'it':['Crea uno spazio personale','Inizia con uno spazio personale, poi aggiungi una prima attività, nota o conto. Crea uno spazio famiglia per i piani condivisi.'],
 'pt':['Criar um espaço pessoal','Comece com um espaço pessoal e adicione uma tarefa, nota ou conta. Crie um espaço familiar para os planos partilhados.'],
 'uk':['Створити особистий простір','Почніть з особистого простору. Додайте перше завдання, нотатку або рахунок. Для спільних справ створіть сімейний простір.'],
 'kk':['Жеке кеңістік құру','Жеке кеңістіктен бастаңыз. Алғашқы тапсырманы, жазбаны немесе шотты қосыңыз. Ортақ жоспарлар үшін отбасылық кеңістік құрыңыз.'],
 'ky':['Жеке мейкиндик түзүү','Жеке мейкиндиктен баштаңыз. Биринчи тапшырманы, жазууну же эсепти кошуңуз. Жалпы иштер үчүн үй-бүлөлүк мейкиндик түзүңүз.'],
 'tg':['Сохтани фазои шахсӣ','Аз фазои шахсӣ оғоз кунед. Вазифа, ёддошт ё ҳисоби аввалро илова кунед. Барои нақшаҳои муштарак фазои оилавӣ созед.'],
 'az':['Şəxsi məkan yaradın','Şəxsi məkanla başlayın. İlk tapşırığı, qeydi və ya hesabı əlavə edin. Ortaq planlar üçün ailə məkanı yaradın.'],
 'uz-Latn':['Shaxsiy makon yaratish','Shaxsiy makondan boshlang. Birinchi vazifa, qayd yoki hisobni qo‘shing. Umumiy rejalar uchun oilaviy makon yarating.'],
 'uz-Cyrl':['Шахсий макон яратиш','Шахсий макондан бошланг. Биринчи вазифа, қайд ёки ҳисобни қўшинг. Умумий режалар учун оилавий макон яратинг.'],
 'ka':['პირადი სივრცის შექმნა','დაიწყეთ პირადი სივრცით. დაამატეთ პირველი დავალება, ჩანაწერი ან ანგარიში. საერთო გეგმებისთვის შექმენით ოჯახის სივრცე.'],
 'hy':['Ստեղծել անձնական տարածք','Սկսեք անձնական տարածքից։ Ավելացրեք առաջին առաջադրանքը, նշումը կամ հաշիվը։ Համատեղ ծրագրերի համար ստեղծեք ընտանեկան տարածք։'],
}

CHARTS = {
 'ru':['Столбцы','Круг','Линия'], 'en':['Bars','Donut','Line'],
 'de':['Balken','Ring','Linie'], 'fr':['Barres','Anneau','Courbe'],
 'es':['Barras','Anillo','Línea'], 'it':['Barre','Anello','Linea'],
 'pt':['Barras','Anel','Linha'], 'uk':['Стовпці','Коло','Лінія'],
 'kk':['Бағандар','Шеңбер','Сызық'], 'ky':['Мамычалар','Тегерек','Сызык'],
 'tg':['Сутунҳо','Доира','Хат'], 'az':['Sütunlar','Halqa','Xətt'],
 'uz-Latn':['Ustunlar','Halqa','Chiziq'], 'uz-Cyrl':['Устунлар','Ҳалқа','Чизиқ'],
 'ka':['სვეტები','რგოლი','ხაზი'], 'hy':['Սյունակներ','Օղակ','Գիծ'],
}

TOTALS = {
 'ru':'Суммы по доступным записям. Валюты учитываются отдельно.',
 'en':'Totals from accessible records. Currencies are kept separate.',
 'de':'Summen aus zugänglichen Einträgen. Währungen werden getrennt berechnet.',
 'fr':'Totaux des données accessibles. Les devises sont séparées.',
 'es':'Totales de los registros accesibles. Las monedas se calculan por separado.',
 'it':'Totali dei dati accessibili. Le valute vengono calcolate separatamente.',
 'pt':'Totais dos registos acessíveis. As moedas são calculadas separadamente.',
 'uk':'Суми за доступними записами. Валюти враховуються окремо.',
 'kk':'Қолжетімді жазбалардың жиынтығы. Валюталар бөлек есептеледі.',
 'ky':'Жеткиликтүү жазуулардын суммасы. Валюталар өзүнчө эсептелет.',
 'tg':'Ҷамъи сабтҳои дастрас. Асъорҳо алоҳида ҳисоб мешаванд.',
 'az':'Əlçatan qeydlərin cəmi. Valyutalar ayrıca hesablanır.',
 'uz-Latn':'Mavjud yozuvlar bo‘yicha jami. Valyutalar alohida hisoblanadi.',
 'uz-Cyrl':'Мавжуд ёзувлар бўйича жами. Валюталар алоҳида ҳисобланади.',
 'ka':'ხელმისაწვდომი ჩანაწერების ჯამი. ვალუტები ცალ-ცალკე ითვლება.',
 'hy':'Հասանելի գրառումների գումարները։ Արժույթները հաշվարկվում են առանձին։',
}

def main():
    source = (OUT / 'app.js').read_text()
    keys = set(re.findall(r"\bt\('([a-zA-Z0-9_]+)'\)", source))
    # Dynamic keys are explicit families of existing, Android-tested strings.
    prefixes = ('family_', 'account_', 'currency_')
    keys.update(['profile','today','widget_tasks','widget_notes','finances','account_manage','name','task_title','note_text','opening_balance','amount','family_kind_transaction','theme','palette','system','light','dark','income','expense','completed','save','cancel','delete','close','add','search','retry','edit','complete','home','feature_finance_hint'])
    packs = {}
    for path in sorted((ROOT / 'assets/locales').glob('*.json')):
        data = json.loads(path.read_text())
        strings = data['strings']
        missing = keys - strings.keys() - {'web_online', 'web_install','web_bar','web_donut','web_line','web_totals','web_mfa_hint','web_personal_create','web_onboarding'}
        if missing: raise ValueError((path, missing))
        selected = {k:v for k,v in strings.items() if k in keys or k.startswith(prefixes)}
        selected.update(zip(('web_online', 'web_install'), EXTRA[data['locale']]))
        selected.update(zip(('web_bar','web_donut','web_line'), CHARTS[data['locale']]))
        selected['web_totals'] = TOTALS[data['locale']]
        selected['web_mfa_hint'] = MFA_HINT[data['locale']]
        selected['family_error_unauthorized'] = WEB_SESSION_EXPIRED[data['locale']]
        selected.update(zip(('web_personal_create','web_onboarding'), ONBOARDING[data['locale']]))
        packs[data['locale']] = {'name': data['nativeName'], 'strings': selected}
    (OUT / 'locales.json').write_text(json.dumps(packs, ensure_ascii=False, separators=(',', ':')) + '\n')
    from PIL import Image, ImageDraw
    for size, name in ((192,'icon-192.png'),(512,'icon-512.png'),(180,'apple-touch-icon.png')):
        scale = 4
        image = Image.new('RGB',(size*scale,size*scale),'#194e45')
        draw = ImageDraw.Draw(image)
        # Safe-area U mark; no external image or font dependencies.
        s = size*scale
        draw.line([(s*.30,s*.29),(s*.30,s*.54)],fill='#d8efb2',width=int(s*.10))
        draw.line([(s*.70,s*.29),(s*.70,s*.54)],fill='#d8efb2',width=int(s*.10))
        draw.arc((s*.25,s*.30,s*.75,s*.79),0,180,fill='#d8efb2',width=int(s*.10))
        image.resize((size,size),Image.Resampling.LANCZOS).save(OUT/name)
    print(f'Built {len(packs)} complete PWA language catalogs and three icons.')


if __name__ == '__main__': main()
