"""Еженедельный отчёт для директора. Вход: docs.json (выгрузка таблицы docs: [{coll,id,data}]).
Использование: python3 weekly.py docs.json YYYY-MM-DD(понедельник) out_dir"""
import json,sys,os,datetime as dt,collections
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter
src,mon,out=sys.argv[1],dt.date.fromisoformat(sys.argv[2]),sys.argv[3]
sun=mon+dt.timedelta(days=6);nmon=sun+dt.timedelta(days=1);nsun=nmon+dt.timedelta(days=6)
D=json.load(open(src))
def C(suffix):return [(r['coll'],r['data']) for r in D if r['coll'].endswith(suffix)]
reg={r['id']:r['data'].get('manager','') for r in D if r['coll']=='reg'}
EXCL={'Лейман Виктор'}
acts=[(c,a) for c,a in C('/activities') if a.get('date')]
mname=lambda c,a:a.get('manager') or reg.get(c.split('/')[1],'')
ms=lambda d:dt.datetime.fromtimestamp(d/1000).date() if d else None
inw=lambda s:mon.isoformat()<=s<=sun.isoformat()
week=[(mname(c,a),a) for c,a in acts if inw(a['date'])]
nxt=[(mname(c,a),a) for c,a in acts if nmon.isoformat()<=a['date']<=nsun.isoformat()]
mgrs=sorted({m for m in reg.values() if m and m not in EXCL})
SRU={'client':'Клиент','contact':'Был контакт','refused':'Отказ','none':'Нет контакта'}
DST={'lead':'Лид','talks':'Переговоры','offer':'КП отправлено','contract':'Договор','ship':'Отгрузка','paid':'Оплачено','lost':'Потеряно'}
# сводка по менеджерам
rows=[]
for m in mgrs:
    w=[a for n,a in week if n==m];last=max([a['date'] for n,a in ((mname(c,a),a) for c,a in acts) if n==m and a['date']<=sun.isoformat()]+[''])
    t=collections.Counter(a.get('type','') for a in w)
    rows.append({'m':m,'all':len(w),'visit':t['Выезд'],'call':t['Звонок'],'wa':t['WhatsApp'],'office':t['Встреча в офисе'],
      'failed':sum(1 for a in w if a.get('status')=='failed'),'clients':len({a.get('client') for a in w if a.get('client')}),
      'next':sum(1 for n,a in nxt if n==m),'last':last})
rows.sort(key=lambda r:-r['all'])
# охват: смены этапов за неделю
farms=[(c,f) for c,f in C('/farms')]
dist={(r['coll'].split('/')[1],r['id']):r['data'] for r in D if r['coll'].endswith('/districts')}
moves=[]
for c,f in farms:
    sa=ms(f.get('stageAt'))
    if sa and mon<=sa<=sun and f.get('stage')!=f.get('stagePrev'):
        moves.append({'m':f.get('manager') or reg.get(c.split('/')[1],''),'farm':f.get('name',''),'from':SRU.get(f.get('stagePrev'),f.get('stagePrev') or ''),'to':SRU.get(f.get('stage'),f.get('stage')),'date':sa.isoformat()})
cov=collections.defaultdict(collections.Counter);seen={}
RK={'client':3,'contact':2,'refused':1,'none':0}
for c,f in farms:
    u,did=c.split('/')[1],c.split('/')[3];d=dist.get((u,did),{})
    k=(d.get('region') or '—',d.get('name',''),(f.get('name') or '').strip().lower());st=f.get('stage') or 'none'
    if k not in seen or RK.get(st,0)>RK.get(seen[k],0):seen[k]=st
for (rg,_,_),st in seen.items():cov[rg][st]+=1
deals=[d for c,d in C('/deals')]
stale=[r for r in rows if r['m'] and (not r['last'] or (sun-dt.date.fromisoformat(r['last'])).days>=5)]
# Excel
wb=Workbook();H=Font(bold=True,color='FFFFFF');F=PatternFill('solid',fgColor='2F7D3B')
def sheet(ws,head,data,widths):
    ws.append(head)
    for i,_ in enumerate(head,1):c=ws.cell(1,i);c.font=H;c.fill=F;c.alignment=Alignment(wrap_text=True,vertical='center')
    for r in data:ws.append(r)
    for i,w in enumerate(widths,1):ws.column_dimensions[get_column_letter(i)].width=w
    ws.freeze_panes='A2'
ws=wb.active;ws.title='Сводка'
sheet(ws,['Менеджер','Всего действий','Выезды','Звонки','WhatsApp','Встречи в офисе','Не состоялось','Разных хозяйств','План на след. неделю','Последняя запись'],
  [[r['m'],r['all'],r['visit'],r['call'],r['wa'],r['office'],r['failed'],r['clients'],r['next'],r['last']] for r in rows],[24,10,9,9,10,10,10,11,11,14])
ws.append([]);ws.append(['Итого',sum(r['all'] for r in rows),sum(r['visit'] for r in rows),sum(r['call'] for r in rows),sum(r['wa'] for r in rows),sum(r['office'] for r in rows),sum(r['failed'] for r in rows),'',sum(r['next'] for r in rows)])
ws.cell(ws.max_row,1).font=Font(bold=True)
sheet(wb.create_sheet('Журнал недели'),['Дата','Менеджер','Тип','Хозяйство','Контакт','Цель','Результат','Статус'],
  [[a['date'],n,a.get('type',''),a.get('client',''),a.get('contact',''),a.get('plan',''),a.get('result',''),{'done':'Проведено','failed':'Не состоялось'}.get(a.get('status'),'')] for n,a in sorted(week,key=lambda x:(x[1]['date'],x[0]))],[11,22,12,28,28,34,48,13])
sheet(wb.create_sheet('Охват'),['Область','Нет контакта','Был контакт','Клиент','Отказ','Всего','Охвачено, %'],
  [[k,v['none'],v['contact'],v['client'],v['refused'],sum(v.values()),round(100*(sum(v.values())-v['none'])/max(1,sum(v.values())),1)] for k,v in sorted(cov.items())],[24,12,12,10,9,9,12])
ws=wb['Охват'];ws.append([]);ws.append(['Сдвиги этапов за неделю']);ws.cell(ws.max_row,1).font=Font(bold=True);ws.append(['Дата','Менеджер','Хозяйство','Было','Стало'])
for x in sorted(moves,key=lambda x:x['date']):ws.append([x['date'],x['m'],x['farm'],x['from'],x['to']])
sheet(wb.create_sheet('Сделки'),['Менеджер','Хозяйство','Этап','Сумма, тг','Предоплата, тг','Дата закрытия','Продукты'],
  [[d.get('manager',''),d.get('client',''),DST.get(d.get('stage'),d.get('stage')),d.get('amount',0),d.get('prepay',0),d.get('close',''),d.get('products','')] for d in deals],[22,28,14,14,14,13,60])
sheet(wb.create_sheet('План на неделю'),['Дата','Менеджер','Тип','Хозяйство','Цель'],
  [[a['date'],n,a.get('type',''),a.get('client',''),a.get('plan','')] for n,a in sorted(nxt,key=lambda x:(x[1]['date'],x[0]))],[11,22,12,30,50])
os.makedirs(out,exist_ok=True)
fn=os.path.join(out,f'Отчёт_продажи_{mon:%d.%m}-{sun:%d.%m.%Y}.xlsx');wb.save(fn)
# письмо
fmt=lambda n:f'{n:,.0f}'.replace(',',' ')
tot=sum(r['all'] for r in rows)
top=', '.join(f"{r['m']} ({r['all']})" for r in rows[:3] if r['all'])
L=[f"<p>Ольга, добрый день!</p><p>Отчёт отдела продаж за неделю <b>{mon:%d.%m} – {sun:%d.%m.%Y}</b>. Подробности во вложении.</p>",
f"<p><b>Активность:</b> {tot} действий в журнале — выезды {sum(r['visit'] for r in rows)}, звонки {sum(r['call'] for r in rows)}, WhatsApp {sum(r['wa'] for r in rows)}, встречи в офисе {sum(r['office'] for r in rows)}. Самые активные: {top or '—'}.</p>",
"<table border=1 cellpadding=4 cellspacing=0 style='border-collapse:collapse;font-size:13px'><tr style='background:#2F7D3B;color:#fff'><th>Менеджер</th><th>Действий</th><th>Выезды</th><th>Звонки</th><th>План на след. неделю</th></tr>"+
''.join(f"<tr><td>{r['m']}</td><td align=center>{r['all']}</td><td align=center>{r['visit']}</td><td align=center>{r['call']}</td><td align=center>{r['next']}</td></tr>" for r in rows)+"</table>",
f"<p><b>Охват:</b> за неделю сменили этап {len(moves)} хозяйств"+(" — "+', '.join(f"{k} {v}" for k,v in collections.Counter(x['to'] for x in moves).most_common()) if moves else '')+". Всего охвачено "+fmt(sum(sum(v.values())-v['none'] for v in cov.values()))+" из "+fmt(sum(sum(v.values()) for v in cov.values()))+" хозяйств.</p>",
f"<p><b>Сделки:</b> {len(deals)} в работе на {fmt(sum(d.get('amount',0) for d in deals))} тг.</p>",
("<p><b>Нет записей 5+ дней:</b> "+', '.join(f"{r['m']} (последняя {r['last'] or 'никогда'})" for r in stale)+"</p>") if stale else "<p>Все менеджеры вносили записи на этой неделе.</p>"]
open(os.path.join(out,'email.html'),'w').write('\n'.join(L))
print(fn)
