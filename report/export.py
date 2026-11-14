"""Выгрузка всей таблицы docs из Supabase в JSON. python3 export.py out.json  (env SB_URL, SB_SECRET)"""
import os,sys,json,urllib.request
U,K=os.environ['SB_URL'],os.environ['SB_SECRET'];out=[];f=0
while True:
    r=urllib.request.Request(U+'/rest/v1/docs?select=coll,id,data&order=coll,id',headers={'apikey':K,'Authorization':'Bearer '+K,'Range':f'{f}-{f+999}'})
    a=json.loads(urllib.request.urlopen(r,timeout=120).read());out+=a
    if len(a)<1000:break
    f+=1000
json.dump(out,open(sys.argv[1],'w'),ensure_ascii=False);print('docs:',len(out))
