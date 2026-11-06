"""Capture immutable pre-kickoff picks using the exact browser model in index.html.

Runs in GitHub Actions. Requires playwright Chromium, SUPABASE_URL and
SUPABASE_SERVICE_ROLE_KEY. Never commits credentials to the repository.
"""
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from playwright.sync_api import sync_playwright

SEASON = int(os.getenv('NFL_SEASON', str(datetime.now(timezone.utc).year)))
MODEL_SEASON = 2026
BASE = os.environ['SUPABASE_URL'].rstrip('/')
KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
ROOT = Path(__file__).resolve().parent


def fetch(url, *, service=False):
    headers = {'User-Agent': 'NFLParlayAutomation/1.0'}
    if service:
        headers.update({'apikey': KEY, 'Authorization': 'Bearer ' + KEY})
    with urlopen(Request(url, headers=headers), timeout=40) as r:
        return json.load(r)


def schedule():
    now = datetime.now(timezone.utc)
    result = []
    for week in range(1, 19):
        url = f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={SEASON}&seasontype=2&week={week}&limit=100'
        data = fetch(url)
        for e in data.get('events', []):
            comp = (e.get('competitions') or [{}])[0]
            teams = {x.get('homeAway'): x.get('team', {}).get('abbreviation') for x in comp.get('competitors', [])}
            kickoff = datetime.fromisoformat(e['date'].replace('Z', '+00:00'))
            if kickoff <= now + timedelta(minutes=30) or kickoff > now + timedelta(days=8):
                continue
            if e.get('status', {}).get('type', {}).get('completed'):
                continue
            result.append({'week': week, 'id': str(e['id']), 'a': teams.get('away'), 'h': teams.get('home'), 'kickoff': kickoff.isoformat()})
    return result


def main():
    if SEASON != MODEL_SEASON:
        raise RuntimeError(f"Pregame snapshots disabled for {SEASON}: browser model inputs are still based on {MODEL_SEASON}. Update and validate the model before archiving forecasts.")
    events = schedule()
    if not events:
        print('No eligible future games within eight days; nothing to capture.')
        return
    existing = fetch(BASE + f'/rest/v1/nfl_prediction_snapshots?select=week,game_id&season=eq.{SEASON}', service=True)
    seen = {(int(x['week']), x['game_id']) for x in existing}
    pending = [e for e in events if (e['week'], e['id']) not in seen]
    if not pending:
        print('All eligible games already have immutable snapshots.')
        return
    stats = fetch(BASE + f'/rest/v1/nfl_stat_exports?select=csv_text&season=eq.{SEASON}&limit=1', service=True)
    if not stats or not stats[0].get('csv_text'):
        raise RuntimeError('No cloud NFL statistics available. Run export_automated.py first.')
    html = ROOT / 'index.html'
    if not html.exists():
        raise RuntimeError('Place the updated app in the repository as index.html')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(html.as_uri(), wait_until='domcontentloaded', timeout=60000)
        page.evaluate('(csv) => loadCSV(csv, {persist:false})', stats[0]['csv_text'])
        for e in pending:
            if not e['a'] or not e['h']:
                continue
            result = page.evaluate('''e => {
              const a=normalizeTeam(e.a),h=normalizeTeam(e.h);
              if(!T[a]||!T[h])return null;
              const g=build([['espn'+e.id,a,h,'Scheduled',null]])[0];
              const best=bestFor(g).filter(x=>x.m==='ml'||/^p\\d+$/.test(x.m));
              const picks=best.map(x=>{
                const base={away_team:a,home_team:h,market:x.m==='ml'?'ml':'player',side:x.s,
                  probability:x.p,model_line:null,label:performancePickName(g,x)};
                if(x.m==='ml')return {...base,team:x.s==='h'?h:a};
                const p=PLY[Number(x.m.slice(1))],stat=p.k==='ps'?'passing_yards':p.k==='ru'?'rushing_yards':'touchdowns';
                const line=p.k==='td'?0.5:pstat(p,g).line;
                return {...base,player_name:p.n,team:p.tm,stat,line};
              });
              return {away_team:a,home_team:h,picks};
            }''', e)
            if not result or not result['picks']:
                continue
            row = {'season': SEASON, 'week': e['week'], 'game_id': e['id'],
                   'away_team': result['away_team'], 'home_team': result['home_team'],
                   'kickoff_at': e['kickoff'], 'model_version': 'browser-model-2026-v1',
                   'picks': result['picks']}
            request = Request(BASE + '/rest/v1/nfl_prediction_snapshots?on_conflict=season,week,game_id',
                              data=json.dumps(row).encode(), method='POST',
                              headers={'apikey': KEY, 'Authorization': 'Bearer '+KEY,
                                       'Content-Type': 'application/json',
                                       'Prefer': 'resolution=ignore-duplicates,return=minimal'})
            try:
                with urlopen(request, timeout=40) as r:
                    print('Archived week', e['week'], result['away_team'], '@', result['home_team'], r.status)
            except HTTPError as err:
                raise RuntimeError(f'Prediction snapshot upload HTTP {err.code}: {err.read().decode()[:500]}') from err
        browser.close()


if __name__ == '__main__':
    main()
