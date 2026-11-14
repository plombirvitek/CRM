"""PDF-сводка для директора в формате «Сводка по активности менеджеров».
python3 pdf.py docs.json YYYY-MM-DD(понедельник) narrative.json out_dir
narrative.json (пишет Claude по данным недели): {"money":[{"m","client","what","sum"}],"money_text":"...","pipeline":"...","gps_text":"...","notes":["..."]}
Без narrative.json (или с --facts) печатает facts.json — сырьё для текста."""
import json,sys,os,datetime as dt,collections,html,asyncio
src,mon=sys.argv[1],dt.date.fromisoformat(sys.argv[2]);NJ=sys.argv[3];out=sys.argv[4]
sun=mon+dt.timedelta(days=6)
MON=['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря']
def period():
    return f"{mon.day}–{sun.day} {MON[sun.month-1]} {sun.year}" if mon.month==sun.month else f"{mon.day} {MON[mon.month-1]} – {sun.day} {MON[sun.month-1]} {sun.year}"
D=json.load(open(src))
reg={r['id']:r['data'].get('manager','') for r in D if r['coll']=='reg'}
EXCL={'Лейман Виктор'};OWNER='u_hgT9ICEs5lsbeakc9Uzojg'
raw=[]
for r in D:
    if not r['coll'].endswith('/activities'):continue
    a=r['data'];u=r['coll'].split('/')[1]
    if not a.get('date') or not(mon.isoformat()<=a['date']<=sun.isoformat()):continue
    m=a.get('manager') or reg.get(u,'')
    if not m or m in EXCL:continue
    raw.append((m,u,a))
seen=set();acts=[]
for m,u,a in sorted(raw,key=lambda x:(x[2].get('status')!='done',)):
    k=(m,a['date'],(a.get('client') or '').strip().lower(),a.get('type'))
    if k in seen:continue
    seen.add(k);acts.append((m,u,a))
dups=len(raw)-len(acts)
foreign=[(m,a) for m,u,a in acts if u==OWNER]
st=lambda a:{'done':'вып.','failed':'не вып.'}.get(a.get('status'),'план')
ok=lambda s:bool((s or '').strip())
kpi=lambda a:a.get('status')=='done' and ok(a.get('contact')) and ok(a.get('plan')) and ok(a.get('result'))
CALL={'Звонок','WhatsApp','Другое'}
order=['Жукашев Абай','Жигарь Василий','Жамбулов Саят','Бурковский Николай','Айтпаев Азамат','Бурковский Роман','Гладких Михаил','Орлов Александр','Екатеринский Вячеслав']
mg=sorted({m for m,_,_ in acts},key=lambda m:(order.index(m) if m in order else 99,m))
T=[]
for m in mg:
    w=[a for mm,_,a in acts if mm==m]
    T.append([m,len(w),sum(a.get('type')=='Выезд' for a in w),sum(a.get('type') in CALL for a in w),sum(a.get('type')=='Встреча в офисе' for a in w),
      sum(a.get('status')=='done' for a in w),sum(a.get('status')=='failed' for a in w),sum(a.get('status') not in('done','failed') for a in w),
      sum(kpi(a) and a.get('type')=='Выезд' for a in w),sum(kpi(a) and a.get('type')!='Выезд' for a in w)])
tot=['Итого']+[sum(r[i] for r in T) for i in range(1,10)]
silent=sorted(m for m in set(reg.values())-set(mg)-EXCL if m)
gps=[]
for r in D:
    if r['coll'].endswith('/gps') and mon.isoformat()<=r['data'].get('date','')<=sun.isoformat():
        g=r['data'];home=next((i.get('p') for i in g.get('items',[]) if i.get('k')=='home'),'')
        for i in g.get('items',[]):
            if i.get('k')=='trip':gps.append([g['date'],f"{g.get('mgr','')}, {g.get('car','')}",home,i.get('p',''),i.get('d','').replace(' р-н',''),', '.join(i.get('f',[])) or '—',f"{i.get('t','')}, {i.get('m','')} мин"])
facts={'period':period(),'totals':dict(zip(['записей','выезды','звонки','встречи','выполнено','не_выполнено','без_отметки','kpi_выезды','kpi_прочие'],tot[1:])),
  'managers':mg,'silent':silent,'gps_days':sorted({x[0] for x in gps}),
  'records':[{'m':m,'date':a['date'],'type':a.get('type'),'client':a.get('client'),'status':a.get('status'),'plan':a.get('plan'),'result':a.get('result'),'pay':a.get('pay')} for m,_,a in acts]}
os.makedirs(out,exist_ok=True)
if not os.path.exists(NJ) or '--facts' in sys.argv:
    json.dump(facts,open(os.path.join(out,'facts.json'),'w'),ensure_ascii=False,indent=1);print('facts.json');sys.exit()
N=json.load(open(NJ));e=lambda s:html.escape(str(s if s is not None else ''))
fmt=lambda n:f'{n:,.0f}'.replace(',',' ')
def table(head,rows,cls=''):
    return f"<table class='{cls}'><thead><tr>"+''.join(f'<th>{e(h)}</th>' for h in head)+"</tr></thead><tbody>"+''.join('<tr>'+''.join(f'<td>{c}</td>' for c in r)+'</tr>' for r in rows)+'</tbody></table>'
t=facts['totals'];P=period()
intro=(f"За неделю {P.rsplit(' ',1)[0]} {len(mg)} менеджеров внесли в CRM {t['записей']} уникальных записей: {t['выезды']} выездов, {t['звонки']} звонков и сообщений, "
       f"{t['встречи']} встреч в офисе. Выполнено {t['выполнено']}, в зачёт KPI идут {t['kpi_выезды']+t['kpi_прочие']}. ")+N.get('intro_money','')
H=[f"<h1>Сводка по активности менеджеров, {e(P)}</h1><div class=meta><span>{dt.date.today():%d.%m.%Y}</span> · <span>@Виктор</span></div><p>{e(intro)}</p>",
"<h2>Итоги по менеджерам</h2>",table(['Менеджер','Записей','Выезды','Звонки и WhatsApp','Встречи в офисе','Выполнено','Не выполнено','Без отметки','В KPI: выезды','В KPI: прочие'],[[e(c) for c in r] for r in T]+[[f'<b>{e(c)}</b>' for c in tot]],'small'),
"<p>В KPI зачитываются выполненные записи с контактом, планом и результатом; норма на квартал — 30 выездов и 30 прочих контактов на менеджера.</p>"]
if silent:H.append(f"<p>Не внесли ни одной записи за неделю: {e(', '.join(silent))}.</p>")
H.append("<h2>Деньги и сделки</h2>")
if N.get('money_text'):H.append(f"<p>{e(N['money_text'])}</p>")
if N.get('money'):H.append(table(['Менеджер','Клиент','Что произошло','Сумма, ₸'],[[e(x['m']),e(x['client']),e(x['what']),e(fmt(x['sum']) if isinstance(x.get('sum'),(int,float)) else x.get('sum'))] for x in N['money']]))
for k in('money_after','pipeline'):
    if N.get(k):H.append(f"<p>{e(N[k])}</p>")
H.append("<h2>Перемещения</h2>")
if N.get('gps_text'):H.append(f"<p>{e(N['gps_text'])}</p>")
if gps:H.append(table(['Дата','Водитель / машина','База','Поездка','Район','Хозяйства по треку','Время, стоянка'],[[e(c if i else c[8:10]+'.'+c[5:7]) for i,c in enumerate(r)] for r in sorted(gps,key=lambda r:(r[0],r[6].zfill(12)))],'small'))
if N.get('gps_after'):H.append(f"<p>{e(N['gps_after'])}</p>")
H.append(f"<h2>Полный журнал</h2><p>Все {t['записей']} записей по менеджерам; «план» — запись без отметки о выполнении.</p>")
for m in mg:
    w=sorted([a for mm,_,a in acts if mm==m],key=lambda a:a['date'])
    H.append(f"<h3>{e(m)}</h3>"+table(['Дата','Тип','Клиент','Статус','Результат'],[[e(a['date'][8:10]+'.'+a['date'][5:7]),e(a.get('type')),e(a.get('client')),e(st(a)),e(a.get('result') or '—')] for a in w],'journal'))
notes=[]
if dups:notes.append(f"<b>Дубли убраны.</b> В базе {len(raw)} записей, в сводке {len(acts)}: повторы (тот же менеджер, дата, клиент и тип) посчитаны один раз.")
nk=t['записей']-t['kpi_выезды']-t['kpi_прочие']
if nk:notes.append(f"<b>{nk} записей не идут в KPI:</b> {t['не_выполнено']} «не выполнено», {t['без_отметки']} без отметки о выполнении и {nk-t['не_выполнено']-t['без_отметки']} выполненных, но без результата, плана или контактного лица.")
if foreign:notes.append(f"<b>Часть записей лежит не у своих менеджеров.</b> {len(foreign)} записей сохранены под учётной записью владельца CRM; в сводке они отнесены к своим менеджерам.")
notes+= [e(x) for x in N.get('notes',[])]
if notes:H.append("<h2>Оговорки</h2><ul>"+''.join(f'<li>{x}</li>' for x in notes)+"</ul>")
CSS="""@page{size:A4;margin:16mm 15mm 18mm}body{font:13px/1.5 'Noto Sans','DejaVu Sans',Arial,sans-serif;color:#222}
h1{font:400 30px/1.2 'Noto Serif','DejaVu Serif',Georgia,serif;margin:0 0 10px}h2{font:400 22px 'Noto Serif','DejaVu Serif',Georgia,serif;margin:26px 0 10px}h3{font:400 17px 'Noto Serif','DejaVu Serif',Georgia,serif;margin:18px 0 8px}
.meta span{background:#f1f0ec;border-radius:4px;padding:2px 7px;font-size:11px;color:#555}.meta{margin-bottom:10px}
table{width:100%;border-collapse:collapse;margin:8px 0 12px;page-break-inside:auto}tr{page-break-inside:avoid}th{background:#f4f3ef;color:#555;font-weight:400;text-align:left}th,td{border:1px solid #e3e2dc;padding:6px 8px;vertical-align:top}
table.small{font-size:10.5px}table.small th,table.small td{padding:5px}table.journal td:nth-child(1){width:42px}table.journal td:nth-child(4){width:48px}li{margin-bottom:6px}td:last-child{white-space:nowrap}table.journal td:last-child,table.small td:last-child{white-space:normal}"""
doc=f"<!doctype html><html><head><meta charset=utf-8><style>{CSS}</style></head><body>{''.join(H)}</body></html>"
fn=os.path.join(out,f"Сводка по активности менеджеров {mon.day}-{sun.day} {MON[sun.month-1]} {sun.year}.pdf")
open(os.path.join(out,'report.html'),'w').write(doc)
from playwright.async_api import async_playwright
async def run():
    async with async_playwright() as p:
        b=await p.chromium.launch();pg=await b.new_page();await pg.set_content(doc,wait_until='load')
        await pg.pdf(path=fn,format='A4',print_background=True,display_header_footer=True,margin={'top':'16mm','bottom':'18mm','left':'15mm','right':'15mm'},
          header_template=f"<div style='font-size:7px;color:#999;margin-left:15mm'>Сводка по активности менеджеров, {e(P)}</div>",
          footer_template="<div style='font-size:7px;color:#999;width:100%;text-align:right;margin-right:15mm'>Page <span class=pageNumber></span> of <span class=totalPages></span></div>")
        await b.close()
asyncio.run(run());print(fn)
