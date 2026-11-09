"""College basketball data generator.

Runs in GitHub Actions. Pulls Bart Torvik ratings and The Odds API lines,
projects every game with an efficiency model, tracks openers and line moves,
logs model picks and grades them, then writes cbb/data.json for cbb/index.html.

Env:
  ODDS_API_KEY   The Odds API key (repo secret, shared with the MLB page)
  CBB_MODE       "open"  - early run: snapshot lines, grade yesterday
                 "picks" - main run: snapshot lines and log model picks
                 "late"  - evening run: snapshot lines (closing-line tracking)
  CBB_OFFLINE    path to a saved odds JSON file (testing only)
"""
import csv, io, json, os, re, statistics, sys
from datetime import datetime, timedelta, timezone

try:
    import requests
except ImportError:  # offline testing
    requests = None

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
OUT = os.path.join(HERE, 'data.json')
TORVIK_URL = 'https://barttorvik.com/{season}_team_results.csv'
SEASON = 2027  # Torvik labels a season by the year it ends (2026-27 -> 2027)
ODDS_BASE = 'https://api.the-odds-api.com/v4/sports/basketball_ncaab'
# Up to 10 books = 1 credit per market. Pinnacle is the sharp reference line.
BOOKS = 'pinnacle,draftkings,fanduel,betmgm,williamhill_us,betrivers,espnbet,fanatics,bovada,betonlineag'
BOOK_NAMES = {'pinnacle': 'Pinnacle', 'draftkings': 'DraftKings', 'fanduel': 'FanDuel', 'betmgm': 'BetMGM',
              'williamhill_us': 'Caesars', 'betrivers': 'BetRivers', 'espnbet': 'ESPN BET', 'fanatics': 'Fanatics',
              'bovada': 'Bovada', 'betonlineag': 'BetOnline'}

SETTINGS = {
    'hfa': 3.0,              # points to the home team, 0 at neutral sites
    'edge_threshold': 3.0,   # model vs market gap needed to log a pick
    'tempo_outlier': 8.0,    # flag teams this far from league-average tempo (small samples)
}

ET = timezone(timedelta(hours=-5))  # display only; DST handled loosely (season is Nov-Apr)


def now_utc():
    return datetime.now(timezone.utc)


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, obj):
    with open(path, 'w') as f:
        json.dump(obj, f, indent=1, sort_keys=False)


# ── 1. Ratings ───────────────────────────────────────────────────────────────
def fetch_torvik(download=True):
    """Download fresh ratings (once a day, on the early run); fall back to the last saved copy."""
    path = os.path.join(DATA, 'torvik.csv')
    status = 'cached'
    if download and requests is not None and not os.environ.get('CBB_OFFLINE'):
        try:
            # Honest, identifiable client so the site owner can see who this is (one request a day).
            hdrs = {'User-Agent': 'HardwoodEdge/1.0 (personal CBB model, 1 request/day; https://github.com/zcathey/MLB-totals)'}
            r = requests.get(TORVIK_URL.format(season=SEASON), timeout=30, headers=hdrs)
            text = r.text
            if r.ok and text.startswith('rank,team') and text.count('\n') > 300:
                with open(path, 'w') as f:
                    f.write(text)
                status = 'fresh'
            else:
                print(f'  Torvik returned {r.status_code}, {len(text)} bytes; using cached ratings')
                print(f'  Torvik response starts: {text[:300]!r}')
        except Exception as e:  # noqa: BLE001
            print(f'  Torvik error: {e}; using cached ratings')
    rows = list(csv.DictReader(open(path)))
    teams = {}
    for r in rows:
        try:
            teams[r['team']] = {
                'rank': int(r['rank']), 'team': r['team'], 'conf': r['conf'], 'record': r['record'],
                'adjoe': float(r['adjoe']), 'adjde': float(r['adjde']), 'adjt': float(r['adjt']),
                'barthag': float(r['barthag']),
            }
        except (KeyError, ValueError):
            continue
    if status == 'fresh':
        save_json(os.path.join(DATA, 'torvik_meta.json'), {'fetched_at': now_utc().isoformat(), 'via': 'actions'})
    # A daily task on Zach's computer fetches the CSV through the desktop app's browser
    # (Torvik blocks cloud IPs) and records when in torvik_meta.json.
    meta = load_json(os.path.join(DATA, 'torvik_meta.json'), {})
    mtime = meta.get('fetched_at') or datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat()
    age_h = (now_utc() - datetime.fromisoformat(mtime)).total_seconds() / 3600
    if status != 'fresh' and age_h < 30:
        status = 'fresh'
    return teams, status, mtime


# ── 2. Name matching (Odds API "Iona Gaels" -> Torvik "Iona") ────────────────
ALIASES = {
    'uconn': 'Connecticut', 'ole miss': 'Mississippi', 'miami': 'Miami FL', 'miami fl': 'Miami FL',
    'miami hurricanes': 'Miami FL', 'miami oh': 'Miami OH', 'loyola chi': 'Loyola Chicago',
    'loyola chicago': 'Loyola Chicago', 'loyola md': 'Loyola MD', 'loyola maryland': 'Loyola MD',
    'texas a&m cc': 'Texas A&M Corpus Chris', 'texas a&m corpus christi': 'Texas A&M Corpus Chris',
    'texas a&m commerce': 'East Texas A&M', 'omaha': 'Nebraska Omaha', 'kansas city': 'UMKC',
    'iupui': 'IU Indy', 'iu indianapolis': 'IU Indy', 'sam houston': 'Sam Houston St.',
    'seattle u': 'Seattle', 'ul monroe': 'Louisiana Monroe', 'louisiana monroe': 'Louisiana Monroe',
    'florida intl': 'FIU', 'florida international': 'FIU', 'ut martin': 'Tennessee Martin',
    'tenn martin': 'Tennessee Martin', 'csu bakersfield': 'Cal St. Bakersfield',
    'csu fullerton': 'Cal St. Fullerton', 'csu northridge': 'Cal St. Northridge', 'cs northridge': 'Cal St. Northridge',
    'cal st bakersfield': 'Cal St. Bakersfield', 'cal st fullerton': 'Cal St. Fullerton',
    'nc state': 'N.C. State', 'north carolina st': 'N.C. State', 'st francis pa': 'Saint Francis',
    'st francis': 'Saint Francis', 'liu': 'LIU', 'long island': 'LIU', 'umass': 'Massachusetts',
    'ut rio grande valley': 'UT Rio Grande Valley', 'utrgv': 'UT Rio Grande Valley',
    'app st': 'Appalachian St.', 'appalachian st': 'Appalachian St.', 'gw': 'George Washington',
    'siu edwardsville': 'SIU Edwardsville', 'siue': 'SIU Edwardsville', 'southern mississippi': 'Southern Miss',
    'grambling': 'Grambling St.', 'wisconsin green bay': 'Green Bay', 'wisc green bay': 'Green Bay',
    'wisconsin milwaukee': 'Milwaukee', 'tx arlington': 'UT Arlington', 'ut arlington': 'UT Arlington',
    'hawaii': 'Hawaii', 'pennsylvania': 'Penn', 'central connecticut st': 'Central Connecticut',
    'detroit': 'Detroit Mercy', 'arkansas little rock': 'Little Rock', 'ualr': 'Little Rock',
    'southeastern louisiana': 'Southeastern Louisiana', 'se louisiana': 'Southeastern Louisiana',
    'se missouri st': 'Southeast Missouri St.', 'southeast missouri st': 'Southeast Missouri St.',
    'mcneese': 'McNeese St.', 'nicholls': 'Nicholls St.', 'queens university': 'Queens',
    'albany ny': 'Albany', 'ualbany': 'Albany', 'st thomas mn': 'St. Thomas', 'saint marys ca': "Saint Mary's",
    'east texas a&m': 'East Texas A&M', 'american': 'American', 'army knights': 'Army',
}


def norm(s):
    s = s.lower().replace('’', "'").replace("'", '').replace('.', '')
    s = re.sub(r'[()\-/,]', ' ', s)
    s = re.sub(r'\bsaint\b', 'st', s)
    s = re.sub(r'\bstate\b', 'st', s)
    s = re.sub(r'\buniversity\b', '', s)
    return re.sub(r'\s+', ' ', s).strip()


class Matcher:
    def __init__(self, teams):
        self.teams = teams
        self.by_norm = {norm(t): t for t in teams}
        self.alias = {norm(k): v for k, v in ALIASES.items() if v in teams}
        self.cache = {}

    def __call__(self, name):
        if name in self.cache:
            return self.cache[name]
        words = norm(name).split()
        hit = None
        # longest prefix first, so "North Carolina A&T Aggies" beats "North Carolina"
        for n in range(len(words), 0, -1):
            key = ' '.join(words[:n])
            if key in self.alias:
                hit = self.alias[key]; break
            if key in self.by_norm:
                hit = self.by_norm[key]; break
        self.cache[name] = hit
        return hit


# ── 3. Odds ──────────────────────────────────────────────────────────────────
def fetch_odds():
    """Return (events, credits_remaining, status)."""
    off = os.environ.get('CBB_OFFLINE')
    if off:
        return load_json(off, []), None, 'offline'
    key = os.environ.get('ODDS_API_KEY', '')
    if not key or requests is None:
        return [], None, 'no key'
    try:
        r = requests.get(f'{ODDS_BASE}/odds/', timeout=30, params={
            'apiKey': key, 'markets': 'spreads,totals', 'oddsFormat': 'american', 'bookmakers': BOOKS})
        rem = r.headers.get('x-requests-remaining')
        if not r.ok:
            print(f'  Odds API {r.status_code}: {r.text[:200]}')
            return [], rem, f'error {r.status_code}'
        return r.json(), rem, 'ok'
    except Exception as e:  # noqa: BLE001
        print(f'  Odds API error: {e}')
        return [], None, 'error'


def fetch_scores():
    if os.environ.get('CBB_OFFLINE'):
        return []
    key = os.environ.get('ODDS_API_KEY', '')
    if not key or requests is None:
        return []
    try:
        r = requests.get(f'{ODDS_BASE}/scores/', timeout=30, params={'apiKey': key, 'daysFrom': 3})
        return r.json() if r.ok else []
    except Exception as e:  # noqa: BLE001
        print(f'  Scores error: {e}')
        return []


def summarize_lines(ev):
    """Per event: reference home spread/total (Pinnacle, else median) and best prices by side."""
    home, away = ev['home_team'], ev['away_team']
    spreads, totals = {}, {}
    for b in ev.get('bookmakers') or []:
        for m in b.get('markets') or []:
            if m['key'] == 'spreads':
                h = next((o for o in m['outcomes'] if o['name'] == home), None)
                a = next((o for o in m['outcomes'] if o['name'] == away), None)
                if h and a and h.get('point') is not None:
                    spreads[b['key']] = {'home_pt': h['point'], 'home_px': h['price'], 'away_pt': a['point'], 'away_px': a['price']}
            elif m['key'] == 'totals':
                o = next((x for x in m['outcomes'] if x['name'] == 'Over'), None)
                u = next((x for x in m['outcomes'] if x['name'] == 'Under'), None)
                if o and u and o.get('point') is not None:
                    totals[b['key']] = {'pt': o['point'], 'over_px': o['price'], 'under_px': u['price']}
    out = {'books': len(spreads)}
    if spreads:
        ref = spreads.get('pinnacle')
        out['spread_src'] = 'Pinnacle' if ref else 'median'
        out['home_spread'] = ref['home_pt'] if ref else statistics.median(s['home_pt'] for s in spreads.values())

        def best(side):
            # most points for the bettor, then best price
            k, s = max(spreads.items(), key=lambda kv: (kv[1][f'{side}_pt'], kv[1][f'{side}_px']))
            return {'pt': s[f'{side}_pt'], 'px': s[f'{side}_px'], 'book': BOOK_NAMES.get(k, k)}
        out['best_home'] = best('home')
        out['best_away'] = best('away')
    if totals:
        ref = totals.get('pinnacle')
        out['total'] = ref['pt'] if ref else statistics.median(t['pt'] for t in totals.values())
    return out


# ── 4. Model ─────────────────────────────────────────────────────────────────
def project(a, h, neutral, avg_e, avg_t):
    poss = a['adjt'] * h['adjt'] / avg_t
    pa = a['adjoe'] * h['adjde'] / avg_e * poss / 100
    ph = h['adjoe'] * a['adjde'] / avg_e * poss / 100
    hfa = 0 if neutral else SETTINGS['hfa']
    ph += hfa / 2
    pa -= hfa / 2
    return {'poss': round(poss, 1), 'away_pts': round(pa, 1), 'home_pts': round(ph, 1),
            'home_spread': round(pa - ph, 1), 'total': round(pa + ph, 1)}


def fmt_pt(x):
    return 'PK' if x == 0 else f'{x:+g}'


# ── 5. Main ──────────────────────────────────────────────────────────────────
def main():
    mode = os.environ.get('CBB_MODE', 'picks')
    os.makedirs(DATA, exist_ok=True)
    t0 = now_utc()
    print(f'CBB generator, mode={mode}, {t0.isoformat()}')

    teams, rstatus, rtime = fetch_torvik(download=(mode == 'open'))
    print(f'  Ratings: {len(teams)} teams ({rstatus})')
    avg_e = statistics.mean(t['adjoe'] for t in teams.values())
    avg_t = statistics.mean(t['adjt'] for t in teams.values())
    match = Matcher(teams)

    events, credits, ostatus = fetch_odds()
    print(f'  Odds: {len(events)} events ({ostatus}), credits remaining {credits}')

    openers = load_json(os.path.join(DATA, 'openers.json'), {})
    closers = load_json(os.path.join(DATA, 'closers.json'), {})
    picks = load_json(os.path.join(DATA, 'picks.json'), [])
    neutral = load_json(os.path.join(HERE, 'neutral.json'), {})
    neutral_pairs = {(p[0], p[1]) for k, v in neutral.items() if not k.startswith('_') for p in v}
    logged = {p['event_id'] for p in picks}

    games, unmatched, name_map = [], set(), {}
    horizon = t0 + timedelta(hours=40)
    for ev in events:
        tip = datetime.fromisoformat(ev['commence_time'].replace('Z', '+00:00'))
        if tip > horizon:
            continue
        an, hn = match(ev['away_team']), match(ev['home_team'])
        name_map[ev['away_team']] = an
        name_map[ev['home_team']] = hn
        lines = summarize_lines(ev)
        eid = ev['id']
        started = tip <= t0

        # opener = first line we ever saw; closer = last line seen before tip
        if 'home_spread' in lines and not started:
            openers.setdefault(eid, {'home_spread': lines['home_spread'], 'total': lines.get('total'), 'seen': t0.isoformat()})
            closers[eid] = {'home_spread': lines['home_spread'], 'total': lines.get('total'), 'seen': t0.isoformat()}

        g = {'event_id': eid, 'tip': ev['commence_time'], 'away': an or ev['away_team'], 'home': hn or ev['home_team'],
             'away_raw': ev['away_team'], 'home_raw': ev['home_team'], 'started': started,
             'neutral': (an, hn) in neutral_pairs, 'books': lines.get('books', 0),
             'mkt_spread': lines.get('home_spread'), 'mkt_total': lines.get('total'), 'spread_src': lines.get('spread_src'),
             'best_home': lines.get('best_home'), 'best_away': lines.get('best_away'),
             'open_spread': openers.get(eid, {}).get('home_spread'), 'open_total': openers.get(eid, {}).get('total')}
        flags = []
        if not an:
            unmatched.add(ev['away_team']); flags.append('away not matched')
        if not hn:
            unmatched.add(ev['home_team']); flags.append('home not matched')
        if an and hn:
            A, H = teams[an], teams[hn]
            g['model'] = project(A, H, g['neutral'], avg_e, avg_t)
            g['away_rank'], g['home_rank'] = A['rank'], H['rank']
            for side, T in (('away', A), ('home', H)):
                if abs(T['adjt'] - avg_t) > SETTINGS['tempo_outlier']:
                    flags.append(f'{side} tempo outlier ({T["adjt"]:.0f})')
        g['flags'] = flags
        if g.get('model') and g['mkt_spread'] is not None:
            edge = round(g['model']['home_spread'] - g['mkt_spread'], 1)
            g['edge'] = edge
            if g['open_spread'] is not None:
                g['move'] = round(g['mkt_spread'] - g['open_spread'], 1)
            if g.get('mkt_total') is not None:
                g['total_edge'] = round(g['model']['total'] - g['mkt_total'], 1)
            if abs(edge) >= SETTINGS['edge_threshold'] and not flags:
                side = 'away' if edge > 0 else 'home'
                pt = -g['mkt_spread'] if side == 'away' else g['mkt_spread']
                g['pick'] = f"{g[side]} {fmt_pt(pt)}"
                g['pick_side'] = side
                mv = g.get('move')
                g['market'] = 'flat' if not mv else ('agrees' if (edge > 0) == (mv > 0) else 'against')
                if mode == 'picks' and not started and eid not in logged:
                    picks.append({'event_id': eid, 'date': tip.astimezone(ET).strftime('%Y-%m-%d'), 'tip': ev['commence_time'],
                                  'away': g['away'], 'home': g['home'], 'side': side, 'pick': g['pick'],
                                  'line': g['mkt_spread'], 'model_spread': g['model']['home_spread'], 'edge': edge,
                                  'market': g['market'], 'move_at_pick': mv, 'best': g[f'best_{side}'],
                                  'logged': t0.isoformat()})
                    logged.add(eid)
        games.append(g)

    # ── grading ──
    scores = fetch_scores() if mode in ('open', 'picks') else []  # grade on both morning runs in case one is late
    final = {}
    for s in scores:
        if s.get('completed') and s.get('scores'):
            sc = {x['name']: int(x['score']) for x in s['scores'] if x.get('score') is not None}
            if s['home_team'] in sc and s['away_team'] in sc:
                final[s['id']] = (sc[s['away_team']], sc[s['home_team']])
    for p in picks:
        c = closers.get(p['event_id'])
        tipped = datetime.fromisoformat(p['tip'].replace('Z', '+00:00')) <= t0
        if c and tipped:  # closers are only written before tip, so this is the last pre-game line we saw
            p['close'] = c['home_spread']
            p['clv'] = round((p['close'] - p['line']) if p['side'] == 'away' else (p['line'] - p['close']), 1)
        if p['event_id'] in final and 'result' not in p:
            fa, fh = final[p['event_id']]
            p['final'] = [fa, fh]
            m = (fh - fa + p['line']) * (-1 if p['side'] == 'away' else 1)
            p['result'] = 'W' if m > 0 else ('P' if m == 0 else 'L')

    def record(ps):
        w = sum(p.get('result') == 'W' for p in ps); l = sum(p.get('result') == 'L' for p in ps)
        pu = sum(p.get('result') == 'P' for p in ps)
        clvs = [p['clv'] for p in ps if 'clv' in p]
        return {'w': w, 'l': l, 'p': pu, 'picks': len(ps),
                'avg_clv': round(statistics.mean(clvs), 2) if clvs else None,
                'beat_close': round(sum(c > 0 for c in clvs) / len(clvs), 3) if clvs else None}

    # keep state files small
    cutoff = (t0 - timedelta(days=4)).isoformat()
    live_ids = {g['event_id'] for g in games}
    openers = {k: v for k, v in openers.items() if v['seen'] >= cutoff or k in live_ids}
    closers = {k: v for k, v in closers.items() if v['seen'] >= cutoff or k in live_ids}
    save_json(os.path.join(DATA, 'openers.json'), openers)
    save_json(os.path.join(DATA, 'closers.json'), closers)
    save_json(os.path.join(DATA, 'picks.json'), picks)

    games.sort(key=lambda g: (g['tip'], g['home']))
    out = {
        'generated_at': t0.isoformat(), 'mode': mode,
        'ratings': {'status': rstatus, 'updated': rtime, 'teams': len(teams), 'avg_eff': round(avg_e, 2), 'avg_tempo': round(avg_t, 2)},
        'lines': {'status': ostatus, 'events': len(events), 'credits_remaining': credits},
        'settings': SETTINGS,
        'games': games,
        'unmatched': sorted(unmatched),
        'name_map': name_map,
        'picks': picks[-150:],
        'record': {'all': record(picks),
                   'agrees': record([p for p in picks if p.get('market') == 'agrees']),
                   'against': record([p for p in picks if p.get('market') == 'against']),
                   'flat': record([p for p in picks if p.get('market') == 'flat'])},
        'teams': sorted(teams.values(), key=lambda t: t['rank']),
    }
    save_json(OUT, out)
    print(f'  Wrote {OUT}: {len(games)} games, {sum("pick" in g for g in games)} model edges, {len(unmatched)} unmatched names')


if __name__ == '__main__':
    main()
