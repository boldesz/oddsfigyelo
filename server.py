import os,json,time,urllib.request,urllib.parse,threading
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
ROOT=Path(__file__).parent
KEY=os.getenv('ODDS_API_KEY','')
CACHE={'at':0,'data':None}; LOCK=threading.Lock()
SPORTS=['soccer_epl','soccer_uefa_champs_league','soccer_spain_la_liga','soccer_germany_bundesliga','soccer_italy_serie_a','basketball_nba','tennis_atp_french_open','americanfootball_nfl','icehockey_nhl']
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'OddsMonitor/1.0'})
 with urllib.request.urlopen(req,timeout=12) as r:return json.load(r)
def get_data():
 if not KEY:return {'configured':False,'matches':[],'message':'Állítsd be az ODDS_API_KEY környezeti változót az élő adatokhoz.'}
 with LOCK:
  if CACHE['data'] is not None and time.time()-CACHE['at']<90:return CACHE['data']
  matches=[];errors=[]
  for sport in SPORTS:
   try:
    q=urllib.parse.urlencode({'apiKey':KEY,'regions':'eu','markets':'h2h','oddsFormat':'decimal'})
    items=fetch(f'https://api.the-odds-api.com/v4/sports/{sport}/odds/?{q}')
    for m in items:
     picks={}
     for book in m.get('bookmakers',[]):
      for market in book.get('markets',[]):
       if market.get('key')!='h2h':continue
       for o in market.get('outcomes',[]):
        name=o.get('name');price=o.get('price')
        if name and isinstance(price,(int,float)) and price>1:
         picks.setdefault(name,[]).append({'odds':price,'book':book.get('title','')})
     if not picks:continue
     best={n:max(v,key=lambda x:x['odds']) for n,v in picks.items()}
     # Vig-free implied probabilities from median bookmaker prices; this is a market estimate, NOT a predictive model.
     median={n:sorted(x['odds'] for x in v)[len(v)//2] for n,v in picks.items()}
     raw={n:1/o for n,o in median.items()};total=sum(raw.values())
     for n,b in best.items():
      p=raw[n]/total
      matches.append({'sport':sport,'home':m.get('home_team'),'away':m.get('away_team'),'start':m.get('commence_time'),'pick':n,'odds':b['odds'],'bookmaker':b['book'],'market_probability':round(p,4),'edge':round(p*b['odds']-1,4),'bookmakers':len(picks[n])})
   except Exception as e:errors.append(f'{sport}: {str(e)[:130]}')
  matches.sort(key=lambda x:(x['market_probability']>=.75,x['edge']),reverse=True)
  result={'configured':True,'matches':matches,'updated':int(time.time()),'errors':errors,'message':'A valószínűség piaci becslés, nem független előrejelzés. A különböző fogadóirodák árai eltérhetnek a Tippmix kínálatától.'}
  CACHE.update(at=time.time(),data=result)
  return result
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
 def do_GET(self):
  if self.path.startswith('/api/odds'):
   try:data=get_data();status=200
   except Exception as e:data={'error':str(e)};status=502
   body=json.dumps(data,ensure_ascii=False).encode()
   self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
  else:super().do_GET()
if __name__=='__main__':
 port=int(os.getenv('PORT','8080'))
 print(f'Nyisd meg: http://localhost:{port}');ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
