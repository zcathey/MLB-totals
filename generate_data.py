#!/usr/bin/env python3
"""
generate_data.py
Runs daily via GitHub Actions. Fetches team stats, pitcher stats,
platoon splits, and recent form using pybaseball + MLB Stats API.
Outputs data.json which the HTML app reads instead of hitting APIs directly.
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

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
SEASON = datetime.date.today().year
TODAY  = datetime.date.today().isoformat()

# FanGraphs team name → our abbreviation
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

# ── 1. TEAM BATTING (wRC+ via multiple sources) ──────────────────────────────
print("Fetching team batting / wRC+...")
team_bat = {}

# Source A: Baseball Reference team stats CSV (publicly accessible)
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
    import io, csv
    # Baseball Reference team batting stats
    bref_url = f'https://www.baseball-reference.com/leagues/majors/{SEASON}-standard-batting.shtml'
    r = requests.get(bref_url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
    }, timeout=20)
    print(f"  BRef status: {r.status_code}")
    if r.ok:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', {'id': 'teams_standard_batting'})
        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                if 'thead' in row.get('class', []): continue
                cells = row.find_all(['td','th'])
                if not cells: continue
                name_cell = row.find('td', {'data-stat': 'team_name'})
                if not name_cell: continue
                name = name_cell.get_text(strip=True)
                abbr = BREF_TEAM_MAP.get(name, '')
                if not abbr: continue
                def get_stat(stat_name, default=0):
                    c = row.find('td', {'data-stat': stat_name})
                    try: return float(c.get_text(strip=True)) if c else default
                    except: return default
                runs = get_stat('R')
                games = get_stat('G', 1)
                ops = get_stat('onbase_plus_slugging')
                team_bat[abbr] = {
                    'wrc_plus': int(round((ops / 0.720) * 100)) if ops > 0 else 100,
                    'ops': round(ops, 3),
                    'r_g': round(runs / games, 2) if games > 0 else 4.45,
                    'games': int(games),
                }
            print(f"  BRef got {len(team_bat)} teams")
except ImportError:
    print("  BeautifulSoup not available")
except Exception as e:
    print(f"  BRef error: {e}")

# Source B: FanGraphs API direct
if not team_bat:
    print("  Trying FanGraphs API...")
    try:
        url = f'https://www.fangraphs.com/api/leaders/major-league/data?age=&pos=all&stats=bat&lg=all&qual=0&season={SEASON}&season1={SEASON}&ind=0&team=0,ts&rost=0&players=0&type=8&postseason=&sortdir=default&pageitems=2000000000&pagenum=1'
        d = fg_get(url)
        rows = (d.get('data') or []) if isinstance(d, dict) else []
        print(f"  FG rows: {len(rows)}, keys: {list(rows[0].keys())[:10] if rows else 'none'}")
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

# Source C: MLB Stats API OPS proxy
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

# ── 2. TEAM PITCHING (FIP, K%, BB% from FanGraphs API) ──────────────────────
print("Fetching team pitching from FanGraphs...")
team_pitch = {}
try:
    url = f'https://www.fangraphs.com/api/leaders/major-league/data?age=&pos=all&stats=pit&lg=all&qual=0&season={SEASON}&season1={SEASON}&ind=0&team=0,ts&rost=0&players=0&type=8&postseason=&sortdir=default&pageitems=2000000000&pagenum=1'
    d = fg_get(url)
    rows = d.get('data', []) if d else []
    for row in rows:
        name = str(row.get('TeamName', row.get('teamName', ''))).strip()
        abbr = FG_TEAM_MAP.get(name, '')
        if abbr:
            team_pitch[abbr] = {
                'fip':    round(float(row.get('FIP', 4.20) or 4.20), 2),
                'k_pct':  round(float(row.get('K%', 22.0) or 22.0), 1),
                'bb_pct': round(float(row.get('BB%', 8.5) or 8.5), 1),
                'era':    round(float(row.get('ERA', 4.50) or 4.50), 2),
            }
    print(f"  Got {len(team_pitch)} teams")
    if not team_pitch and rows:
        print(f"  Sample row keys: {list(rows[0].keys())[:15]}")
except Exception as e:
    print(f"  team pitching failed: {e}")

# ── 3. STARTER FIP/K%/BB% (FanGraphs API individual pitching) ───────────────
print("Fetching individual pitcher stats from FanGraphs...")
pitcher_stats = {}
try:
    url = f'https://www.fangraphs.com/api/leaders/major-league/data?age=&pos=all&stats=pit&lg=all&qual=10&season={SEASON}&season1={SEASON}&ind=0&team=0&rost=0&players=0&type=8&postseason=&sortdir=default&pageitems=2000000000&pagenum=1'
    d = fg_get(url)
    rows = d.get('data', []) if d else []
    for row in rows:
        name = str(row.get('PlayerName', row.get('playerName', row.get('Name','')))).strip()
        if name:
            ip = float(row.get('IP', 0) or 0)
            pitcher_stats[name] = {
                'fip':    round(float(row.get('FIP', 0) or 0), 2) if ip >= 10 else None,
                'k_pct':  round(float(row.get('K%', 0) or 0), 1),
                'bb_pct': round(float(row.get('BB%', 0) or 0), 1),
                'ip':     round(ip, 1),
                'era':    round(float(row.get('ERA', 0) or 0), 2),
            }
    print(f"  Got {len(pitcher_stats)} pitchers")
    if not pitcher_stats and rows:
        print(f"  Sample row keys: {list(rows[0].keys())[:15]}")
except Exception as e:
    print(f"  pitcher stats failed: {e}")

# ── 4. RECENT FORM — last 14 days R/G via MLB Stats API ─────────────────────
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
    time.sleep(0.05)  # be polite
print(f"  Got recent form for {len(recent_form)} teams")

# ── 5. PLATOON SPLITS — vs LHP / vs RHP OPS via MLB Stats API ───────────────
print("Fetching platoon splits from MLB Stats API...")
platoon = {}
for abbr, team_id in MLB_TEAM_ID.items():
    # Try statSplits with sitCodes
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

# ── 6. TODAY'S SCHEDULE + PROBABLE PITCHERS via MLB Stats API ────────────────
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
        # Fetch pitcher handedness directly if not in schedule hydration
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

# ── 7. ASSEMBLE + WRITE data.json ────────────────────────────────────────────
output = {
    'generated': datetime.datetime.utcnow().isoformat() + 'Z',
    'date': TODAY,
    'season': SEASON,
    'team_batting': team_bat,       # wrc_plus, ops, r_g per team
    'team_pitching': team_pitch,    # fip, k_pct, bb_pct per team (bullpen proxy)
    'pitcher_stats': pitcher_stats, # fip, k_pct, bb_pct, ip per pitcher name
    'recent_form': recent_form,     # last 14 days r_g per team
    'platoon': platoon,             # vsL, vsR OPS per team
    'schedule': schedule,           # today's games with probable pitchers
}

with open('data.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"\ndata.json written successfully")
print(f"  Teams with batting data:  {len(team_bat)}")
print(f"  Teams with pitching data: {len(team_pitch)}")
print(f"  Pitchers with stats:      {len(pitcher_stats)}")
print(f"  Teams with recent form:   {len(recent_form)}")
print(f"  Teams with platoon splits:{len(platoon)}")
print(f"  Games today:              {len(schedule)}")
