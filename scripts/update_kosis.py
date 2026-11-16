#!/usr/bin/env python3
"""Refresh a verified KOSIS statistical table using a secret API key.
Strictly preserve the source identity; never use regional CPI as national CPI.
"""
import json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
NOW=datetime.now(timezone(timedelta(hours=9)))
OUT=Path("data/kosis/series.json")
KEY=os.getenv("KOSIS_API_KEY","").strip()
SOURCES={
 "cpi":{
  "orgId":"101","tblId":"DT_1J22003","itmId":"T","objL1":"ALL",
  "prdSe":"M","from":"201001","unit":"2020=100",
  "filter_col":"C1_NM","filter_values":["전국","전국(총지수)"]
 }
}
def fetch(source):
 end=NOW.strftime("%Y%m")
 params={
   "method":"getList","apiKey":KEY,"format":"json","jsonVD":"Y",
   "orgId":source["orgId"],"tblId":source["tblId"],"itmId":source["itmId"],
   "objL1":source["objL1"],"prdSe":source["prdSe"],
   "startPrdDe":source["from"],"endPrdDe":end
 }
 url="https://kosis.kr/openapi/Param/statisticsParameterData.do?"+urllib.parse.urlencode(params)
 # NEVER log the URL: it contains the API key.
 req=urllib.request.Request(url,headers={"User-Agent":"KH-KOSIS/1.0"})
 with urllib.request.urlopen(req,timeout=35) as response: data=json.load(response)
 if not isinstance(data,list):raise RuntimeError("KOSIS response is not a data array")
 selected={}
 for row in data:
  if str(row.get(source["filter_col"],"")).strip() not in source["filter_values"]:continue
  if str(row.get("ITM_ID",""))!=source["itmId"]:continue
  try:
   time=str(row["PRD_DE"]).strip()
   value=float(str(row["DT"]).replace(",","").strip())
   if not time or abs(value)==float("inf"):continue
   selected[time]={"time":time,"value":value}
  except (TypeError,ValueError,KeyError):continue
 if not selected:raise RuntimeError("KOSIS national CPI rows not verified; no update")
 return {"orgId":source["orgId"],"tblId":source["tblId"],"itmId":source["itmId"],
  "cycle":source["prdSe"],"coverage":"official_api","unit":source["unit"],
  "observations":sorted(selected.values(),key=lambda row:row["time"]),
  "updated_at":NOW.isoformat(timespec="seconds"),
  "selection":"Only rows with C1_NM 전국 and ITM_ID T"}
def main():
 if not KEY:
  print("KOSIS_API_KEY is missing; refusing to publish unverified data.")
  return
 try: previous=json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
 except (ValueError,OSError):previous={}
 indicators=dict(previous.get("indicators") or {})
 errors={}
 for name,metadata in SOURCES.items():
  try:
   data=fetch(metadata)
   indicators[name]=data
   print(name+": "+str(len(data["observations"]))+" verified observations")
  except Exception as exc:
   # Do not print urllib errors, which may expose the secret-bearing URL.
   errors[name]=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
   print(name+": "+errors[name],file=sys.stderr)
 if not indicators:
  print("No validated KOSIS data; no snapshot published.")
  return
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps({"provider":"KOSIS","generated_at":NOW.isoformat(timespec="seconds"),
  "indicators":indicators,"errors":errors},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
