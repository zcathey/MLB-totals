#!/usr/bin/env python3
"""
generate_data.py
Runs daily via GitHub Actions. Fetches team stats, pitcher stats,
platoon splits, and recent form using pybaseball + MLB Stats API.
Outputs data.json which the HTML app reads instead of hitting APIs directly.
"""

import json, datetime, warnings, time, requests
warnings.filterwarnings('ignore')

from pybaseball import (
    fg_team_batting_data,
    fg_team_pitching_data,
    fg_pitching_data,
    schedule_and_record,
)

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

# ── 1. TEAM BATTING (wRC+, OPS, R/G from FanGraphs) ─────────────────────────
print("Fetching team batting from FanGraphs...")
team_bat = {}
try:
    df = fg_team_batting_data(SEASON, split_seasons=False)
    for _, row in df.iterrows():
        abbr = FG_TEAM_MAP.get(row.get('teamName') or row.get('Team') or '', '')
        if not abbr:
            # Try matching by abbreviation column if present
            abbr = str(row.get('Tm', row.get('Abrv', ''))).strip()
        if abbr:
            team_bat[abbr] = {
                'wrc_plus': int(row.get('wRC+', 100) or 100),
                'ops':      round(float(row.get('OPS', 0.720) or 0.720), 3),
                'r_g':      round(float(row.get('R/G', 4.45) or 4.45), 2),
                'games':    int(row.get('G', 0) or 0),
            }
    print(f"  Got {len(team_bat)} teams")
except Exception as e:
    print(f"  fg_team_batting_data failed: {e}")

# ── 2. TEAM PITCHING (FIP, K%, BB% from FanGraphs) ──────────────────────────
print("Fetching team pitching from FanGraphs...")
team_pitch = {}
try:
    df = fg_team_pitching_data(SEASON, split_seasons=False)
    for _, row in df.iterrows():
        abbr = FG_TEAM_MAP.get(row.get('teamName') or row.get('Team') or '', '')
        if not abbr:
            abbr = str(row.get('Tm', row.get('Abrv', ''))).strip()
        if abbr:
            team_pitch[abbr] = {
                'fip':   round(float(row.get('FIP', 4.20) or 4.20), 2),
                'k_pct': round(float(row.get('K%', 22.0) or 22.0), 1),
                'bb_pct':round(float(row.get('BB%', 8.5) or 8.5), 1),
                'era':   round(float(row.get('ERA', 4.50) or 4.50), 2),
            }
    print(f"  Got {len(team_pitch)} teams")
except Exception as e:
    print(f"  fg_team_pitching_data failed: {e}")

# ── 3. STARTER FIP/K%/BB% (FanGraphs individual pitching) ───────────────────
print("Fetching individual pitcher stats from FanGraphs...")
pitcher_stats = {}
try:
    df = fg_pitching_data(SEASON, qual=10, split_seasons=False)
    for _, row in df.iterrows():
        name = str(row.get('Name', '')).strip()
        if name:
            ip = float(row.get('IP', 0) or 0)
            pitcher_stats[name] = {
                'fip':    round(float(row.get('FIP', 0) or 0), 2) if ip >= 10 else None,
                'k_pct':  round(float(row.get('K%', 0) or 0), 1),
                'bb_pct': round(float(row.get('BB%', 0) or 0), 1),
                'ip':     round(ip, 1),
                'era':    round(float(row.get('ERA', 0) or 0), 2),
                'hand':   str(row.get('Throws', row.get('hand', ''))),
            }
    print(f"  Got {len(pitcher_stats)} pitchers")
except Exception as e:
    print(f"  fg_pitching_data failed: {e}")

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
        schedule.append({
            'away': aa, 'home': ha,
            'game_date': g.get('gameDate',''),
            'game_pk': g.get('gamePk'),
            'status': status,
            'away_pitcher': {
                'id':   away_pp.get('id'),
                'name': away_pp.get('fullName','TBD'),
                'hand': away_pp.get('pitchHand',{}).get('code'),
            },
            'home_pitcher': {
                'id':   home_pp.get('id'),
                'name': home_pp.get('fullName','TBD'),
                'hand': home_pp.get('pitchHand',{}).get('code'),
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
