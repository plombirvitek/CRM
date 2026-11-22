"""Стоянки машин из Salam GPS → таблица docs в Supabase (mgr/<владелец>/gps/<машина>_<дата>).
python3 gps_sync.py [YYYY-MM-DD [YYYY-MM-DD]]   (без дат — вчера и сегодня по Астане)
Переменные окружения: SB_URL, SB_SECRET, GPS_EMAIL, GPS_PASS."""
import os,sys,json,time,math,re,datetime as dt,urllib.request,urllib.parse,urllib.error
SB,SK=os.environ['SB_URL'],os.environ['SB_SECRET'];GE,GP=os.environ['GPS_EMAIL'],os.environ['GPS_PASS']
OWNER='u_hgT9ICEs5lsbeakc9Uzojg';G='https://www.salam-gps.online'
CARS={'H 5727 01':'Баялин Б.','064 CT 01':'Жукашев'}
BASES={'Баялин Б.':[(54.719,66.952,3,'home','Казанка'),(54.8971,69.147,0.6,'office','Петропавловск, офис')],'Жукашев':[(53.283,69.40,12,'home','Кокшетау')]}
TODAY=dt.datetime.now(dt.timezone(dt.timedelta(hours=5))).date()
# без аргументов: вчера и сегодня (по Астане)
d1=dt.date.fromisoformat(sys.argv[1]) if len(sys.argv)>1 else TODAY-dt.timedelta(days=1)
d2=dt.date.fromisoformat(sys.argv[2]) if len(sys.argv)>2 else (d1 if len(sys.argv)>1 else TODAY)
def http(url,data=None,h={},method=None):
    r=urllib.request.Request(url,data=json.dumps(data).encode() if data is not None else None,method=method or ('POST' if data is not None else 'GET'),headers={'Content-Type':'application/json','User-Agent':'fmrus-crm/1.0 (a.savenkov@fmrus.kz)',**h})
    return json.loads(urllib.request.urlopen(r,timeout=90).read() or b'null')
try:tok=http(G+'/api/session/token',{'email':GE,'password':GP})['token']['token']
except Exception as e:print('GPS_LOGIN_FAILED',e);sys.exit(2)
A={'Authorization':'Bearer '+tok}
devs=http(G+'/api/devices',h=A)
devs=devs if isinstance(devs,list) else devs.get('items',devs.get('data',[]))
SH={'apikey':SK,'Authorization':'Bearer '+SK}
def sb(q):
    out=[];f=0
    while True:
        a=http(SB+'/rest/v1/docs?'+q,h={**SH,'Range':f'{f}-{f+999}'});out+=a
        if len(a)<1000:return out
        f+=1000
farms=sb('coll=like.*%2Ffarms&select=coll,data');dists={(r['coll'].split('/')[1],r['id']):r['data'] for r in sb('coll=like.*%2Fdistricts&select=coll,id,data')}
norm=lambda s:re.sub(r'^(с|г|п|пос|ст|а|аул)\.\s*','',(s or '').strip().lower()).replace('ё','е')
byS={}
for r in farms:
    p=r['coll'].split('/');dn=(dists.get((p[1],p[3])) or {}).get('name','')
    byS.setdefault(norm(r['data'].get('settlement')),[]).append((dn.lower(),r['data'].get('name','')))
def km(a,b,c,d):
    R=6371;x=math.radians;return 2*R*math.asin(math.sqrt(math.sin(x(c-a)/2)**2+math.cos(x(a))*math.cos(x(c))*math.sin(x(d-b)/2)**2))
geo={}
def rev(lat,lon):
    k=(round(lat,3),round(lon,3))
    if k in geo:return geo[k]
    for w in (1.2,5,15,40):
        time.sleep(w)
        try:j=http('https://nominatim.openstreetmap.org/reverse?'+urllib.parse.urlencode({'lat':lat,'lon':lon,'format':'json','accept-language':'ru','zoom':14}));break
        except urllib.error.HTTPError as x:
            if x.code!=429:raise
    else:geo[k]=('','');return geo[k]
    a=j.get('address',{});p=a.get('village') or a.get('town') or a.get('city') or a.get('hamlet') or a.get('suburb') or '';d=(a.get('county') or a.get('city') or '').replace(' район',' р-н')
    if d==p and a.get('city'):d='г. '+p
    geo[k]=(p,d);return geo[k]
n=0;days=(d2-d1).days+1
for dev in devs:
    car=dev.get('name','');mgr=CARS.get(car,car)
    for i in range(days):
        day=d1+dt.timedelta(days=i)
        rep=http(f"{G}/api/reports/devices?deviceId={dev['id']}&template=Parkings",{'period':{'from':f'{day}T00:00:00+05:00','to':f'{day}T23:59:59+05:00'}},h=A)
        # пустой день Salam GPS иногда отдаёт списком, а не объектом — считаем, что стоянок нет
        pk=rep.get('Parkings') if isinstance(rep,dict) else None
        gt=pk.get('groupedTracks') if isinstance(pk,dict) else None
        ev=[e for g in (gt if isinstance(gt,list) else []) if isinstance(g,dict) for e in (g.get('parkingEvents') or []) if isinstance(e,dict) and (e.get('duration') or 0)>=900]
        if not ev:continue
        items=[];seen=set()
        for e in sorted(ev,key=lambda e:e['start']):
            lat,lon=e['waypoint'][0],e['waypoint'][1]
            b=next((x for x in BASES.get(mgr,[]) if km(lat,lon,x[0],x[1])<=x[2]),None)
            if b:
                if b[4] not in seen:seen.add(b[4]);items.append({'k':b[3],'p':b[4]})
                continue
            p,d=rev(lat,lon)
            t=dt.datetime.fromisoformat(e['start'].replace('Z','+00:00')).astimezone(dt.timezone(dt.timedelta(hours=5)))
            it={'k':'trip','p':p,'d':d,'t':t.strftime('%H:%M'),'m':round(e['duration']/60),'lat':round(lat,5),'lon':round(lon,5)}
            dn=d.replace(' р-н','').lower()
            ff=[nm for ds,nm in byS.get(norm(p),[]) if not dn or dn in ds or ds in dn] or [nm for ds,nm in byS.get(norm(p),[])]
            if ff and p:it['f']=sorted(set(ff))[:8]
            items.append(it)
        doc={'coll':f'mgr/{OWNER}/gps','id':car.replace(' ','')+'_'+day.isoformat(),'data':{'mgr':mgr,'car':car,'date':day.isoformat(),'items':items},'updated_at':dt.datetime.now(dt.timezone.utc).isoformat()}
        http(SB+'/rest/v1/docs?on_conflict=coll,id',[doc],h={**SH,'Prefer':'resolution=merge-duplicates,return=minimal'})
        n+=1;print(day,mgr,sum(1 for x in items if x['k']=='trip'),'выездов:',', '.join(f"{x['p']} {x['t']}" for x in items if x['k']=='trip'))
print('OK, период',d1,'—',d2,', записано дней:',n)
