#!/usr/bin/env python3
"""
generate_data.py
Runs daily via GitHub Actions. Outputs data.json for the MLB totals app.
"""

import json, datetime, warnings, time, requests
warnings.filterwarnings('ignore')

FG_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.fangraphs.com/leaders/major-league',
    'Origin': 'https://www.fangraphs.com',
}

def fg_get(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=FG_HEADERS, timeout=20)
            if r.ok:
                return r.json()
            print(f"  FG status {r.status_code} for {url[:80]}")
        except Exception as e:
            print(f"  FG retry {i+1}: {e}")
            time.sleep(3)
    return None

SEASON = datetime.date.today().year
TODAY  = datetime.date.today().isoformat()

FG_TEAM_MAP = {
    'Angels':'LAA','Astros':'HOU','Athletics':'ATH','Blue Jays':'TOR',
    'Braves':'ATL','Brewers':'MIL','Cardinals':'STL','Cubs':'CHC',
    'Diamondbacks':'ARI','Dodgers':'LAD','Giants':'SFG','Guardians':'CLE',
    'Mariners':'SEA','Marlins':'MIA','Mets':'NYM','Nationals':'WSH',
    'Orioles':'BAL','Padres':'SDP','Phillies':'PHI','Pirates':'PIT',
    'Rangers':'TEX','Rays':'TBR','Red Sox':'BOS','Reds':'CIN',
    'Rockies':'COL','Royals':'KCR','Tigers':'DET','Twins':'MIN',
    'White Sox':'CWS','Yankees':'NYY',
}

MLB_TEAM_ID = {
    'LAA':108,'ARI':109,'BAL':110,'BOS':111,'CHC':112,'CIN':113,
    'CLE':114,'COL':115,'DET':116,'HOU':117,'KCR':118,'LAD':119,
    'WSH':120,'NYM':121,'ATH':133,'PIT':134,'SDP':135,'SEA':136,
    'SFG':137,'STL':138,'TBR':139,'TEX':140,'TOR':141,'MIN':142,
    'PHI':143,'ATL':144,'CWS':145,'MIA':146,'NYY':147,'MIL':158,
}

MLB_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept': 'application/json',
    'Origin': 'https://www.mlb.com',
    'Referer': 'https://www.mlb.com/',
}

def mlb_get(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=MLB_HEADERS, timeout=15)
            if r.ok:
                return r.json()
        except Exception as e:
            print(f"  Retry {i+1} for {url.split('?')[0]}: {e}")
            time.sleep(2)
    return None

# ── 1. TEAM BATTING ───────────────────────────────────────────────────────────
print("Fetching team batting / wRC+...")
team_bat = {}

BREF_TEAM_MAP = {
    'Arizona Diamondbacks':'ARI','Atlanta Braves':'ATL','Baltimore Orioles':'BAL',
    'Boston Red Sox':'BOS','Chicago Cubs':'CHC','Chicago White Sox':'CWS',
    'Cincinnati Reds':'CIN','Cleveland Guardians':'CLE','Colorado Rockies':'COL',
    'Detroit Tigers':'DET','Houston Astros':'HOU','Kansas City Royals':'KCR',
    'Los Angeles Angels':'LAA','Los Angeles Dodgers':'LAD','Miami Marlins':'MIA',
    'Milwaukee Brewers':'MIL','Minnesota Twins':'MIN','New York Mets':'NYM',
    'New York Yankees':'NYY','Oakland Athletics':'ATH','Philadelphia Phillies':'PHI',
    'Pittsburgh Pirates':'PIT','San Diego Padres':'SDP','San Francisco Giants':'SFG',
    'Seattle Mariners':'SEA','St. Louis Cardinals':'STL','Tampa Bay Rays':'TBR',
    'Texas Rangers':'TEX','Toronto Blue Jays':'TOR','Washington Nationals':'WSH',
    'Athletics':'ATH',
}

try:
    from bs4 import BeautifulSoup, Comment
    bref_url = f'https://www.baseball-reference.com/leagues/majors/{SEASON}-standard-batting.shtml'
    r = requests.get(bref_url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
    }, timeout=30)
    print(f"  BRef status: {r.status_code}, size: {len(r.text)} chars")
    if r.ok:
        soup = BeautifulSoup(r.text, 'html.parser')
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            cs = str(comment)
            if 'teams_standard_batting' in cs or 'onbase_plus_slugging' in cs:
                soup.append(BeautifulSoup(cs, 'html.parser'))
        table = None
        for tid in ['teams_standard_batting', 'batting_team', 'teams_batting']:
            table = soup.find('table', {'id': tid})
            if table:
                print(f"  Found table: {tid}")
                break
        if not table:
            tables = soup.find_all('table')
            print(f"  Tables found: {len(tables)}, ids: {[t.get('id','') for t in tables[:10]]}")
            for t in tables:
                if t.find('td', {'data-stat': 'onbase_plus_slugging'}):
                    table = t
                    print(f"  Found table by OPS column: {t.get('id','')}")
                    break
        if table:
            for row in table.find('tbody').find_all('tr'):
                if row.get('class') and 'thead' in row.get('class', []):
                    continue
                name_cell = row.find('td', {'data-stat': 'team_name'})
                if not name_cell:
                    name_cell = row.find('th', {'data-stat': 'team_name'})
                if not name_cell:
                    continue
                name = name_cell.get_text(strip=True).replace('*','').replace('+','').strip()
                abbr = BREF_TEAM_MAP.get(name, '')
                if not abbr:
                    continue
                def gs(stat, default=0):
                    c = row.find('td', {'data-stat': stat})
                    try: return float(c.get_text(strip=True).replace(',','')) if c and c.get_text(strip=True) else default
                    except: return default
                runs = gs('R'); games = gs('G', 1); ops = gs('onbase_plus_slugging')
                ops_plus = gs('onbase_plus_slugging_plus')
                team_bat[abbr] = {
                    'wrc_plus': int(ops_plus) if ops_plus > 0 else (int(round((ops/0.720)*100)) if ops > 0 else 100),
                    'ops': round(ops, 3),
                    'r_g': round(runs/games, 2) if games > 0 else 4.45,
                    'games': int(games),
                }
            print(f"  BRef got {len(team_bat)} teams")
        else:
            print("  BRef: no table found")
except ImportError:
    print("  BeautifulSoup not available")
except Exception as e:
    print(f"  BRef error: {e}")

if not team_bat:
    print("  Trying FanGraphs API...")
    try:
        url = f'https://www.fangraphs.com/api/leaders/major-league/data?age=&pos=all&stats=bat&lg=all&qual=0&season={SEASON}&season1={SEASON}&ind=0&team=0,ts&rost=0&players=0&type=8&postseason=&sortdir=default&pageitems=2000000000&pagenum=1'
        d = fg_get(url)
        rows = (d.get('data') or []) if isinstance(d, dict) else []
        for row in rows:
            name = str(row.get('TeamName') or row.get('teamName') or '').strip()
            abbr = FG_TEAM_MAP.get(name, '')
            if abbr:
                wrc = float(row.get('wRC+') or row.get('wrcplus') or 100)
                team_bat[abbr] = {
                    'wrc_plus': int(wrc),
                    'ops': round(float(row.get('OPS', 0.720) or 0.720), 3),
                    'r_g': round(float(row.get('R/G') or row.get('RG') or 4.45), 2),
                    'games': int(row.get('G', 0) or 0),
                }
        print(f"  FG got {len(team_bat)} teams")
    except Exception as e:
        print(f"  FG error: {e}")

if not team_bat:
    print("  Trying MLB Stats API OPS proxy...")
    LG_OPS = 0.720
    for abbr, team_id in MLB_TEAM_ID.items():
        d = mlb_get(f'https://statsapi.mlb.com/api/v1/teams/{team_id}/stats?stats=season&group=hitting&season={SEASON}')
        if d:
            st = (d.get('stats') or [{}])[0].get('splits') or []
            if st:
                s = st[0].get('stat', {})
                try:
                    ops = float(s.get('ops', 0) or 0)
                    runs = int(s.get('runs', 0) or 0)
                    games = int(s.get('gamesPlayed', 1) or 1)
                    team_bat[abbr] = {
                        'wrc_plus': round((ops / LG_OPS) * 100) if ops > 0 else 100,
                        'ops': round(ops, 3),
                        'r_g': round(runs / games, 2) if games > 0 else 4.45,
                        'games': games,
                    }
                except: pass
        time.sleep(0.05)
    print(f"  MLB API got {len(team_bat)} teams")

print(f"  Team batting total: {len(team_bat)} teams")

# ── 2. TEAM PITCHING from MLB Stats API ───────────────────────────────────────
print("Fetching team pitching from MLB Stats API...")
team_pitch = {}
for abbr, team_id in MLB_TEAM_ID.items():
    d = mlb_get(f'https://statsapi.mlb.com/api/v1/teams/{team_id}/stats?stats=season&group=pitching&season={SEASON}')
    if d:
        sp = (d.get('stats') or [{}])[0].get('splits') or []
        if sp:
            s = sp[0].get('stat', {})
            try:
                era  = float(s.get('era', 4.20) or 4.20)
                k9   = float(s.get('strikeoutsPer9Inn', 8.5) or 8.5)
                bb9  = float(s.get('walksPer9Inn', 3.2) or 3.2)
                team_pitch[abbr] = {
                    'era':    round(era, 2),
                    'k_pct':  round(k9 / 4.3, 1),
                    'bb_pct': round(bb9 / 4.3, 1),
                    'fip':    round(era, 2),  # ERA proxy until xFIP available
                }
            except: pass
    time.sleep(0.05)
print(f"  Got {len(team_pitch)} teams pitching")

# ── 3. INDIVIDUAL PITCHER STATS (xFIP) from Baseball Savant ───────────────────
print("Fetching individual pitcher xFIP from Baseball Savant...")
pitcher_stats = {}
try:
    savant_url = (
        f'https://baseballsavant.mlb.com/leaderboard/custom'
        f'?year={SEASON}&type=pitcher&filter=&sort=4&sortDir=asc&min=5'
        f'&selections=xfip,k_percent,bb_percent,p_formatted_ip,player_id'
        f'&csv=true'
    )
    r = requests.get(savant_url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,*/*',
        'Referer': 'https://baseballsavant.mlb.com/',
    }, timeout=30)
    print(f"  Savant status: {r.status_code}, size: {len(r.text)} chars")
    if r.ok and r.text.strip():
        import csv, io
        reader = csv.DictReader(io.StringIO(r.text))
        count = 0
        for row in reader:
            # Player name field varies - try common keys
            last  = row.get('last_name', '').strip()
            first = row.get('first_name', '').strip()
            # Build both name formats for matching
            name_lastfirst = f"{last}, {first}" if last and first else ''
            name_firstlast = f"{first} {last}".strip() if last and first else ''
            mlb_id = str(row.get('player_id') or row.get('mlbam_id') or '').strip()
            if not name_firstlast and not mlb_id:
                continue
            try:
                xfip   = float(row.get('xfip') or row.get('xFIP') or 0) or None
                k_pct  = float(row.get('k_percent') or row.get('k%') or 0) or 0.0
                bb_pct = float(row.get('bb_percent') or row.get('bb%') or 0) or 0.0
                ip_str = (row.get('p_formatted_ip') or row.get('ip') or '0').replace('-','.')
                ip     = float(ip_str) if ip_str else 0.0
                if xfip and ip >= 5:
                    entry = {
                        'xfip':   round(xfip, 2),
                        'k_pct':  round(k_pct, 1),
                        'bb_pct': round(bb_pct, 1),
                        'ip':     round(ip, 1),
                        'mlb_id': mlb_id,
                    }
                    # Store under all name variants + MLB ID for robust matching
                    if name_firstlast:
                        pitcher_stats[name_firstlast] = entry
                    if name_lastfirst:
                        pitcher_stats[name_lastfirst] = entry
                    if mlb_id:
                        pitcher_stats[mlb_id] = entry
                    count += 1
            except (ValueError, TypeError):
                continue
        print(f"  Got xFIP for {count} pitchers")
        if count == 0:
            print(f"  CSV headers: {reader.fieldnames}")
    else:
        print(f"  Savant returned no data")
except Exception as e:
    print(f"  Savant xFIP error: {e}")

# ── 4. RECENT FORM ────────────────────────────────────────────────────────────
print("Fetching recent form (L14 R/G) from MLB Stats API...")
recent_form = {}
end_date   = datetime.date.today()
start_date = end_date - datetime.timedelta(days=14)
for abbr, team_id in MLB_TEAM_ID.items():
    url = (f'https://statsapi.mlb.com/api/v1/teams/{team_id}/stats'
           f'?stats=byDateRange&group=hitting&season={SEASON}'
           f'&startDate={start_date}&endDate={end_date}')
    d = mlb_get(url)
    if d:
        sp = (d.get('stats') or [{}])[0].get('splits') or []
        if sp:
            st = sp[0].get('stat', {})
            g = int(st.get('gamesPlayed', 0) or 0)
            r = int(st.get('runs', 0) or 0)
            if g >= 5:
                recent_form[abbr] = {'rg': round(r/g, 2), 'games': g}
    time.sleep(0.05)
print(f"  Got recent form for {len(recent_form)} teams")

# ── 5. PLATOON SPLITS ─────────────────────────────────────────────────────────
print("Fetching platoon splits from MLB Stats API...")
platoon = {}
for abbr, team_id in MLB_TEAM_ID.items():
    url = (f'https://statsapi.mlb.com/api/v1/teams/{team_id}/stats'
           f'?stats=statSplits&group=hitting&season={SEASON}&sitCodes=vl,vr')
    d = mlb_get(url)
    vsL = vsR = None
    if d:
        for block in (d.get('stats') or []):
            for s in (block.get('splits') or []):
                code = (s.get('split', {}).get('code') or
                        s.get('split', {}).get('description') or '').lower().replace(' ','')
                ops = None
                try: ops = float(s.get('stat', {}).get('ops') or 0) or None
                except: pass
                if ops and 0.3 <= ops <= 1.5:
                    if code in ('vl','vsleft','vslhp','l'): vsL = round(ops, 3)
                    if code in ('vr','vsright','vsrhp','r'): vsR = round(ops, 3)
    if vsL or vsR:
        platoon[abbr] = {'vsL': vsL, 'vsR': vsR}
    time.sleep(0.05)
print(f"  Got platoon splits for {len(platoon)} teams")

# ── 6. SCHEDULE ───────────────────────────────────────────────────────────────
print("Fetching today's schedule...")
schedule = []
url = (f'https://statsapi.mlb.com/api/v1/schedule'
       f'?sportId=1&date={TODAY}&hydrate=probablePitcher,team,linescore')
d = mlb_get(url)
TEAM_ID_MAP = {v:k for k,v in MLB_TEAM_ID.items()}
if d:
    for g in ((d.get('dates') or [{}])[0].get('games') or []):
        status = (g.get('status', {}).get('detailedState') or '').lower()
        if any(x in status for x in ['final','postponed','cancelled']): continue
        at = g['teams']['away']['team']
        ht = g['teams']['home']['team']
        aa = TEAM_ID_MAP.get(at['id'], at.get('abbreviation','???'))
        ha = TEAM_ID_MAP.get(ht['id'], ht.get('abbreviation','???'))
        away_pp = g['teams']['away'].get('probablePitcher') or {}
        home_pp = g['teams']['home'].get('probablePitcher') or {}
        def get_hand(pp):
            hand = pp.get('pitchHand',{}).get('code')
            if not hand and pp.get('id'):
                d2 = mlb_get(f'https://statsapi.mlb.com/api/v1/people/{pp["id"]}?hydrate=pitchHand')
                hand = (d2 or {}).get('people',[{}])[0].get('pitchHand',{}).get('code')
            return hand
        schedule.append({
            'away': aa, 'home': ha,
            'game_date': g.get('gameDate',''),
            'game_pk': g.get('gamePk'),
            'status': status,
            'away_pitcher': {
                'id':   away_pp.get('id'),
                'name': away_pp.get('fullName','TBD'),
                'hand': get_hand(away_pp),
            },
            'home_pitcher': {
                'id':   home_pp.get('id'),
                'name': home_pp.get('fullName','TBD'),
                'hand': get_hand(home_pp),
            },
        })
print(f"  Got {len(schedule)} games")

# ── 7. SHARP PICKS — auto-identify today's edges & grade yesterday ───────────
print("Fetching Vegas lines + grading yesterday's picks...")
picks_history = []

# Load existing history
try:
    with open('data.json', 'r') as f:
        old_data = json.load(f)
    picks_history = old_data.get('picks_history', [])
    # Grade pending picks from yesterday
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    pending = [p for p in picks_history if p.get('result') == 'PENDING' and p.get('date') == yesterday]
    if pending:
        print(f"  Grading {len(pending)} pending picks from {yesterday}...")
        scores_d = mlb_get(f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={yesterday}&hydrate=linescore')
        finals = {}
        if scores_d:
            for g in ((scores_d.get('dates') or [{}])[0].get('games') or []):
                if 'final' in (g.get('status', {}).get('detailedState') or '').lower():
                    at_id = g['teams']['away']['team']['id']
                    ht_id = g['teams']['home']['team']['id']
                    aa = TEAM_ID_MAP.get(at_id, '')
                    ha = TEAM_ID_MAP.get(ht_id, '')
                    total = (g['teams']['away'].get('score') or 0) + (g['teams']['home'].get('score') or 0)
                    finals[f"{aa}@{ha}"] = total
        for p in pending:
            key = f"{p['away']}@{p['home']}"
            if key in finals:
                final_total = finals[key]
                p['final_total'] = final_total
                if p['pick'] == 'OVER':
                    p['result'] = 'WIN' if final_total > p['line'] else ('PUSH' if final_total == p['line'] else 'LOSS')
                else:
                    p['result'] = 'WIN' if final_total < p['line'] else ('PUSH' if final_total == p['line'] else 'LOSS')
                print(f"  Graded {key}: {p['pick']} {p['line']} — Final {final_total} -> {p['result']}")
except FileNotFoundError:
    print("  No existing data.json — starting fresh picks history")
except Exception as e:
    print(f"  Picks grading error: {e}")

# Load today's full-model picks saved by the HTML app (picks_today.json)
# Falls back to simple baseline model if file not available yet
today_picks = []
existing_today = {f"{p['away']}@{p['home']}" for p in picks_history if p.get('date') == TODAY}

full_model_loaded = False
try:
    with open('picks_today.json', 'r') as f:
        full_picks = json.load(f)
    # Only use picks from today
    for p in full_picks:
        if p.get('date') == TODAY and f"{p['away']}@{p['home']}" not in existing_today:
            today_picks.append(p)
            print(f"  Full model pick: {p['game']} {p['pick']} {p['line']} (model {p['model']}, edge {p['edge']:+.1f}R)")
    if today_picks:
        full_model_loaded = True
        print(f"  Loaded {len(today_picks)} full-model picks from picks_today.json")
except FileNotFoundError:
    print("  picks_today.json not found — using baseline model")
except Exception as e:
    print(f"  picks_today.json error: {e}")

# Fallback: simple baseline model if full model picks not available
if not full_model_loaded:
    RBAT = {'CHC':134,'LAD':129,'ATL':122,'HOU':119,'WSH':110,'TEX':109,'NYY':108,
            'BAL':107,'MIA':107,'LAA':105,'DET':103,'MIN':102,'PIT':101,'TBR':100,
            'STL':99,'CWS':97,'CLE':97,'ARI':96,'SEA':96,'ATH':93,'MIL':93,
            'SDP':90,'TOR':90,'KCR':89,'COL':88,'CIN':83,'BOS':82,'PHI':81,'SFG':81,'NYM':80}
    PF = {'COL':1.12,'ARI':1.05,'MIN':1.04,'BAL':1.03,'CIN':1.02,'TOR':1.02,'LAD':1.02,
          'BOS':1.02,'PHI':1.02,'WSH':1.01,'DET':1.01,'LAA':1.01,'NYY':1.01,'HOU':1.01,
          'ATL':1.00,'KCR':1.00,'MIA':1.00,'PIT':1.00,'NYM':0.99,'CWS':0.99,'SFG':0.98,
          'STL':0.98,'CLE':0.98,'MIL':0.98,'SDP':0.97,'CHC':0.95,'TBR':0.95,'TEX':0.92,
          'SEA':0.92,'ATH':1.03}
    ESPN_MAP = {'LAD':'LAD','COL':'COL','HOU':'HOU','CLE':'CLE','STL':'STL','MIA':'MIA',
                'ATL':'ATL','WSH':'WSH','CHC':'CHC','PHI':'PHI','NYY':'NYY','BOS':'BOS',
                'BAL':'BAL','KC':'KCR','MIN':'MIN','NYM':'NYM','MIL':'MIL','DET':'DET',
                'TOR':'TOR','LAA':'LAA','TB':'TBR','CIN':'CIN','PIT':'PIT','SF':'SFG',
                'SEA':'SEA','TEX':'TEX','ARI':'ARI','SD':'SDP','OAK':'ATH','ATH':'ATH',
                'CWS':'CWS','CHW':'CWS','AZ':'ARI','WSN':'WSH','KCR':'KCR','TBR':'TBR'}
    LG = 4.45
    vegas_lines = {}
    try:
        ed = mlb_get(f'https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates={TODAY.replace("-","")}&lang=en&region=us&limit=100')
        for g in (ed.get('events') or []):
            comp = (g.get('competitions') or [{}])[0]
            odds = (comp.get('odds') or [{}])[0]
            if odds.get('overUnder'):
                ou = float(odds['overUnder'])
                if 5 <= ou <= 14:
                    teams = sorted([ESPN_MAP.get(c['team']['abbreviation'], c['team']['abbreviation']) for c in comp.get('competitors', [])])
                    vegas_lines['|'.join(teams)] = ou
        print(f"  Got {len(vegas_lines)} Vegas lines for baseline picks")
    except Exception as e:
        print(f"  ESPN odds error: {e}")
    for g in schedule:
        aa, ha = g['away'], g['home']
        if f"{aa}@{ha}" in existing_today: continue
        key = '|'.join(sorted([aa, ha]))
        ou = vegas_lines.get(key)
        if not ou: continue
        away_rg = LG * (RBAT.get(aa, 100) / 100)
        home_rg = LG * (RBAT.get(ha, 100) / 100) * 1.05
        af = recent_form.get(aa, {}).get('rg')
        hf = recent_form.get(ha, {}).get('rg')
        if af: away_rg = 0.70 * away_rg + 0.30 * af
        if hf: home_rg = 0.70 * home_rg + 0.30 * hf
        proj = round((away_rg + home_rg) * PF.get(ha, 1.00), 1)
        edge = round(proj - ou, 1)
        if abs(edge) >= 1.0:
            pick = 'OVER' if edge > 0 else 'UNDER'
            today_picks.append({'date':TODAY,'away':aa,'home':ha,'game':f"{aa} @ {ha}",'pick':pick,'line':ou,'model':proj,'edge':edge,'result':'PENDING','final_total':None,'source':'baseline'})
            print(f"  Baseline pick: {aa} @ {ha} {pick} {ou} (model {proj}, edge {edge:+.1f})")

picks_history.extend(today_picks)
cutoff = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
picks_history = [p for p in picks_history if p.get('date','') >= cutoff]
picks_history.sort(key=lambda x: x.get('date',''), reverse=True)
print(f"  Total picks in history: {len(picks_history)}")

# ── 8. IL MOVES — flag teams with recent key player transactions ─────────────
print("Fetching recent IL moves...")
il_moves = {}
try:
    # MLB transactions endpoint — IL placements in last 5 days
    il_start = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
    tx_url = f'https://statsapi.mlb.com/api/v1/transactions?sportId=1&startDate={il_start}&endDate={TODAY}&limit=200'
    tx_d = mlb_get(tx_url)
    if tx_d:
        for tx in (tx_d.get('transactions') or []):
            tx_type = (tx.get('typeCode') or '').upper()
            desc = tx.get('description') or ''
            # Only care about IL placements (not activations)
            if tx_type not in ('IL','DL') and '10-Day' not in desc and '15-Day' not in desc and '60-Day' not in desc:
                continue
            if 'reinstated' in desc.lower() or 'activated' in desc.lower():
                continue
            player = tx.get('player', {})
            player_name = player.get('fullName', '')
            team_id = tx.get('toTeam', tx.get('team', {})).get('id')
            team_abbr = TEAM_ID_MAP.get(team_id, '')
            if not team_abbr or not player_name:
                continue
            # Flag position players only (skip pitchers — we already handle them)
            position = player.get('primaryPosition', {}).get('abbreviation', '')
            if position == 'P':
                continue
            tx_date = tx.get('date', TODAY)
            if team_abbr not in il_moves:
                il_moves[team_abbr] = []
            il_moves[team_abbr].append({
                'player': player_name,
                'date': tx_date,
                'description': desc[:120],
            })
    print(f"  IL moves found for {len(il_moves)} teams")
    # Deduplicate by player name per team
    for abbr in il_moves:
        seen = set()
        unique = []
        for m in il_moves[abbr]:
            if m['player'] not in seen:
                seen.add(m['player'])
                unique.append(m)
        il_moves[abbr] = unique
except Exception as e:
    print(f"  IL moves error: {e}")

# ── 8b. MONEYLINES from The Odds API ─────────────────────────────────────────
print("Fetching moneylines from The Odds API...")
moneylines = {}
import os
ODDS_API_KEY = os.environ.get('ODDS_API_KEY', '')
FULL_TO_ABBR = {
    'Washington Nationals':'WSH','Arizona Diamondbacks':'ARI','Los Angeles Dodgers':'LAD',
    'Colorado Rockies':'COL','Houston Astros':'HOU','Cleveland Guardians':'CLE',
    'St. Louis Cardinals':'STL','Miami Marlins':'MIA','Atlanta Braves':'ATL',
    'Chicago Cubs':'CHC','Philadelphia Phillies':'PHI','New York Yankees':'NYY',
    'Boston Red Sox':'BOS','Baltimore Orioles':'BAL','Kansas City Royals':'KCR',
    'Minnesota Twins':'MIN','New York Mets':'NYM','Milwaukee Brewers':'MIL',
    'Detroit Tigers':'DET','Toronto Blue Jays':'TOR','Los Angeles Angels':'LAA',
    'Tampa Bay Rays':'TBR','Cincinnati Reds':'CIN','Pittsburgh Pirates':'PIT',
    'San Francisco Giants':'SFG','Seattle Mariners':'SEA','Texas Rangers':'TEX',
    'San Diego Padres':'SDP','Athletics':'ATH','Oakland Athletics':'ATH',
    'Chicago White Sox':'CWS',
}
if ODDS_API_KEY:
    try:
        odds_url = (f'https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/'
                    f'?apiKey={ODDS_API_KEY}&regions=us&markets=h2h'
                    f'&oddsFormat=american&bookmakers=draftkings')
        odds_r = requests.get(odds_url, timeout=15)
        if odds_r.ok:
            for game in odds_r.json():
                home_abbr = FULL_TO_ABBR.get(game.get('home_team',''))
                away_abbr = FULL_TO_ABBR.get(game.get('away_team',''))
                if not home_abbr or not away_abbr:
                    continue
                dk = next((b for b in (game.get('bookmakers') or []) if b['key']=='draftkings'), None)
                h2h = next((m for m in (dk.get('markets') or []) if m['key']=='h2h'), None) if dk else None
                if not h2h:
                    continue
                home_odds = next((o['price'] for o in h2h['outcomes'] if FULL_TO_ABBR.get(o['name'])==home_abbr), None)
                away_odds = next((o['price'] for o in h2h['outcomes'] if FULL_TO_ABBR.get(o['name'])==away_abbr), None)
                if home_odds is not None and away_odds is not None:
                    key = '|'.join(sorted([away_abbr, home_abbr]))
                    moneylines[key] = {
                        'away': {'abbr': away_abbr, 'ml': away_odds},
                        'home': {'abbr': home_abbr, 'ml': home_odds},
                    }
            print(f"  Got moneylines for {len(moneylines)} games")
            remaining = odds_r.headers.get('x-requests-remaining','?')
            print(f"  Odds API requests remaining: {remaining}")
        else:
            print(f"  Odds API status: {odds_r.status_code}")
    except Exception as e:
        print(f"  Odds API error: {e}")
else:
    print("  ODDS_API_KEY not set — skipping moneylines")

# ── 9. WRITE data.json ────────────────────────────────────────────────────────
output = {
    'generated': datetime.datetime.utcnow().isoformat() + 'Z',
    'date': TODAY,
    'season': SEASON,
    'team_batting': team_bat,
    'team_pitching': team_pitch,
    'pitcher_stats': pitcher_stats,
    'recent_form': recent_form,
    'platoon': platoon,
    'schedule': schedule,
    'picks_history': picks_history,
    'il_moves': il_moves,
    'moneylines': moneylines,
}

with open('data.json', 'w') as f:
    json.dump(output, f, indent=2)

# Force git to always see a change so push never gets skipped
with open('.last_update', 'w') as f:
    f.write(datetime.datetime.utcnow().isoformat() + 'Z\n')

print(f"\ndata.json written successfully")
print(f"  Teams with batting data:  {len(team_bat)}")
print(f"  Teams with pitching data: {len(team_pitch)}")
print(f"  Pitchers with stats:      {len(pitcher_stats)}")
print(f"  Teams with recent form:   {len(recent_form)}")
print(f"  Teams with platoon splits:{len(platoon)}")
print(f"  Games today:              {len(schedule)}")
