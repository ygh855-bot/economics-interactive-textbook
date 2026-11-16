#!/usr/bin/env python3
"""Cache official ECOS observations. ECOS_API_KEY stays in GitHub Actions secrets."""
import json,os,sys,urllib.parse,urllib.request
from datetime import datetime,timedelta,timezone
from pathlib import Path
NOW=datetime.now(timezone(timedelta(hours=9)))
TODAY=NOW.date()
DEST=Path("data/ecos/series.json")
KEY=os.getenv("ECOS_API_KEY","").strip() or "sample"
FULL=KEY!="sample"
STEP=900 if FULL else 10
SERIES={
 "cpi":("901Y009","M","0","199001","소비자물가지수"),
 "gdp":("200Y001","A","20101","1990","실질 GDP 성장률"),
 "fx":("731Y001","D","0000001","20150101","원/달러 매매기준율"),
 "rate":("722Y001","D","0101000","20000101","한국은행 기준금리"),
}
def span(s):
 code,cyc,item,start,unit=s
 if not FULL:
  if cyc=="M":start=(TODAY-timedelta(days=270)).strftime("%Y%m")
  elif cyc=="A":start=str(TODAY.year-9)
  elif code=="722Y001":start=(TODAY-timedelta(days=730)).strftime("%Y%m%d")
  else:start=(TODAY-timedelta(days=17)).strftime("%Y%m%d")
 end=str(TODAY.year) if cyc=="A" else TODAY.strftime("%Y%m" if cyc=="M" else "%Y%m%d")
 return start,end
def get(s):
 code,cyc,item,_,unit=s
 start,end=span(s)
 pos,total,points=1,0,[]
 while True:
  last=pos+STEP-1
  p=["StatisticSearch",KEY,"json","kr",str(pos),str(last),code,cyc,start,end,item]
  url="https://ecos.bok.or.kr/api/"+"/".join(urllib.parse.quote(x,safe="") for x in p)
  # Never print the URL: it contains the secret key.
  with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"KH-ECOS/1.0"}),timeout=28) as r: data=json.load(r)
  if data.get("RESULT"):raise RuntimeError("ECOS "+str(data["RESULT"].get("CODE","ERR")))
  body=data.get("StatisticSearch") or {}
  if body.get("RESULT"):raise RuntimeError("ECOS "+str(body["RESULT"].get("CODE","ERR")))
  rows=body.get("row") or []
  total=int(body.get("list_total_count",len(rows)))
  for row in rows:
   try:
    t=str(row["TIME"]).strip()
    v=float(str(row["DATA_VALUE"]).replace(",","").strip())
    if t and abs(v)<float("inf"):
     points.append({"time":t,"value":v})
     unit=row.get("UNIT_NAME") or unit
   except (KeyError,TypeError,ValueError):continue
  if not FULL or len(rows)<STEP or last>=total:break
  pos+=STEP
  if pos>25000:raise RuntimeError("Too many ECOS rows")
 result=sorted({p["time"]:p for p in points}.values(),key=lambda x:x["time"])
 if not result:raise RuntimeError("ECOS no observations")
 return {"table":code,"item":item,"cycle":cyc,"start":start,"end":end,"unit":unit,
  "coverage":"full_query" if FULL else "sample_max_10",
  "returned_count":len(result),"reported_total":total,
  "observations":result,"updated_at":NOW.isoformat(timespec="seconds")}
def main():
 try:old=json.loads(DEST.read_text(encoding="utf-8")) if DEST.exists() else {}
 except (OSError,ValueError):old={}
 indicators=dict(old.get("indicators",{}))
 errors={}
 for name,s in SERIES.items():
  try:
   row=get(s)
   if row["coverage"]=="sample_max_10" and indicators.get(name,{}).get("coverage")=="full_query":
    print(name+": existing full cache retained")
   else:
    indicators[name]=row
    print(name+": "+str(row["returned_count"])+" observations")
  except Exception as e:
   # urllib exceptions can include the key-bearing URL; log type only.
   errors[name]=str(e) if isinstance(e,RuntimeError) else type(e).__name__
   print(name+": "+errors[name],file=sys.stderr)
 out={"provider":"한국은행 ECOS","generated_at":NOW.isoformat(timespec="seconds"),
      "mode":"authenticated" if FULL else "sample","indicators":indicators,
      "errors":errors,"notice":"sample은 최대 10건. 정식 키 설정 시 전체 조회."}
 DEST.parent.mkdir(parents=True,exist_ok=True)
 DEST.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("Updated public snapshot.")
if __name__=="__main__":main()
