"""NFL data generator (Gridiron Edge).

Runs in GitHub Actions. Pulls the season schedule and per-game team stats from
nflverse, builds schedule-adjusted yards-per-play ratings, projects the current
week, compares with The Odds API lines, tracks openers and closers, logs and
grades model picks, backtests every past week against closing lines, then
writes nfl/data.json for nfl/index.html.

Env:
  ODDS_API_KEY   The Odds API key (repo secret, shared with the MLB and CBB pages)
  NFL_MODE       "picks" - morning run: refresh stats, snapshot lines, log picks for
                           games kicking off today (ET), grade finished picks
                 "late"  - pre-kickoff run: snapshot lines only (closing-line tracking)
  NFL_OFFLINE    "1" = use the cached nflverse files and skip The Odds API (testing)
  NFL_ODDS_FILE  path to a saved Odds API JSON response (testing)
"""
import csv, io, json, os, statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

try:
    import requests
except ImportError:  # offline testing
    requests = None

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
OUT = os.path.join(HERE, 'data.json')
SEASON = 2026  # nflverse labels a season by the year it starts
SCHEDULE_URL = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
STATS_URL = f'https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_{SEASON}.csv'
ODDS_BASE = 'https://api.the-odds-api.com/v4/sports/americanfootball_nfl'
BOOKS = 'pinnacle,draftkings,fanduel,betmgm,williamhill_us,betrivers,espnbet,fanatics,bovada,betonlineag'
BOOK_NAMES = {'pinnacle': 'Pinnacle', 'draftkings': 'DraftKings', 'fanduel': 'FanDuel', 'betmgm': 'BetMGM',
              'williamhill_us': 'Caesars', 'betrivers': 'BetRivers', 'espnbet': 'ESPN BET', 'fanatics': 'Fanatics',
              'bovada': 'Bovada', 'betonlineag': 'BetOnline'}
ET = ZoneInfo('America/New_York')

SETTINGS = {
    'points_base': 23.0,        # league points per game (2025 average)
    'pts_per_ypp': 6.01,        # points per game for 1.0 yard per play (2025 fit, ~61 plays/game)
    'hfa': 1.5,                 # points to the home team; 0 at neutral sites and shared stadiums
    'edge_threshold': 3.0,      # spread gap needed to log a pick
    'total_threshold': 4.0,     # total gap needed to log a pick
    'qb_share_flag': 0.6,       # flag a team when this week's QB started less than 60% of its games
    'min_games': 3,             # flag teams with fewer games than this
    'backtest_start_week': 4,   # first week graded in the backtest (3 games of data behind it)
}
SHARED_STADIUM = [{'LA', 'LAC'}, {'NYG', 'NYJ'}]

NAMES = {'ARI': 'Arizona', 'ATL': 'Atlanta', 'BAL': 'Baltimore', 'BUF': 'Buffalo', 'CAR': 'Carolina', 'CHI': 'Chicago',
         'CIN': 'Cincinnati', 'CLE': 'Cleveland', 'DAL': 'Dallas', 'DEN': 'Denver', 'DET': 'Detroit', 'GB': 'Green Bay',
         'HOU': 'Houston', 'IND': 'Indianapolis', 'JAX': 'Jacksonville', 'KC': 'Kansas City', 'LV': 'Las Vegas',
         'LAC': 'LA Chargers', 'LA': 'LA Rams', 'MIA': 'Miami', 'MIN': 'Minnesota', 'NE': 'New England',
         'NO': 'New Orleans', 'NYG': 'NY Giants', 'NYJ': 'NY Jets', 'PHI': 'Philadelphia', 'PIT': 'Pittsburgh',
         'SF': 'San Francisco', 'SEA': 'Seattle', 'TB': 'Tampa Bay', 'TEN': 'Tennessee', 'WAS': 'Washington'}
ODDS_NAMES = {'Arizona Cardinals': 'ARI', 'Atlanta Falcons': 'ATL', 'Baltimore Ravens': 'BAL', 'Buffalo Bills': 'BUF',
              'Carolina Panthers': 'CAR', 'Chicago Bears': 'CHI', 'Cincinnati Bengals': 'CIN', 'Cleveland Browns': 'CLE',
              'Dallas Cowboys': 'DAL', 'Denver Broncos': 'DEN', 'Detroit Lions': 'DET', 'Green Bay Packers': 'GB',
              'Houston Texans': 'HOU', 'Indianapolis Colts': 'IND', 'Jacksonville Jaguars': 'JAX',
              'Kansas City Chiefs': 'KC', 'Las Vegas Raiders': 'LV', 'Los Angeles Chargers': 'LAC',
              'Los Angeles Rams': 'LA', 'Miami Dolphins': 'MIA', 'Minnesota Vikings': 'MIN',
              'New England Patriots': 'NE', 'New Orleans Saints': 'NO', 'New York Giants': 'NYG',
              'New York Jets': 'NYJ', 'Philadelphia Eagles': 'PHI', 'Pittsburgh Steelers': 'PIT',
              'San Francisco 49ers': 'SF', 'Seattle Seahawks': 'SEA', 'Tampa Bay Buccaneers': 'TB',
              'Tennessee Titans': 'TEN', 'Washington Commanders': 'WAS'}


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
        json.dump(obj, f, indent=1)


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ── 1. nflverse data ─────────────────────────────────────────────────────────
def fetch_nflverse():
    """Refresh the season schedule and team game stats; fall back to the cached copies."""
    status = {}
    for key, url, path, keep in (
            ('schedule', SCHEDULE_URL, os.path.join(DATA, 'schedule.csv'), lambda r: r['season'] == str(SEASON)),
            ('stats', STATS_URL, os.path.join(DATA, 'team_stats.csv'), lambda r: r['season_type'] == 'REG')):
        status[key] = 'cached'
        if requests is not None and not os.environ.get('NFL_OFFLINE'):
            try:
                r = requests.get(url, timeout=60)
                if r.ok and r.text.count('\n') > 30:
                    rows = [x for x in csv.DictReader(io.StringIO(r.text)) if keep(x)]
                    if rows:
                        with open(path, 'w', newline='') as f:
                            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                            w.writeheader(); w.writerows(rows)
                        status[key] = 'fresh'
                else:
                    print(f'  {key}: HTTP {r.status_code}; using cached copy')
            except Exception as e:  # noqa: BLE001
                print(f'  {key} error: {e}; using cached copy')
    sched = list(csv.DictReader(open(os.path.join(DATA, 'schedule.csv'))))
    stats = list(csv.DictReader(open(os.path.join(DATA, 'team_stats.csv'))))
    return sched, stats, status


def kickoff(g):
    t = datetime.strptime(f"{g['gameday']} {g['gametime'] or '13:00'}", '%Y-%m-%d %H:%M').replace(tzinfo=ET)
    return t.astimezone(timezone.utc)


def is_neutral(g):
    return g['location'] == 'Neutral' or {g['home_team'], g['away_team']} in SHARED_STADIUM


def game_lines(sched, stats):
    """One row per team per completed regular-season game: plays and yards for and against."""
    by = {(r['game_id'], r['team']): r for r in stats}

    def side(r):
        plays = int(r['attempts']) + int(r['carries']) + int(r['sacks_suffered'])
        yards = int(r['passing_yards']) + int(r['sack_yards_lost']) + int(r['rushing_yards'])  # sack yards are negative
        give = int(r['passing_interceptions']) + int(num(r.get('fumbles_lost_total')) or 0)
        return plays, yards, give

    out = []
    for g in sched:
        if g['game_type'] != 'REG' or g['home_score'] == '':
            continue
        h, a = by.get((g['game_id'], g['home_team'])), by.get((g['game_id'], g['away_team']))
        if not h or not a:
            continue  # stats not posted yet
        hp, hy, hg = side(h)
        ap, ay, ag = side(a)
        wk = int(g['week'])
        hs, as_ = int(g['home_score']), int(g['away_score'])
        out.append({'week': wk, 'team': g['home_team'], 'opp': g['away_team'], 'plays': hp, 'yards': hy, 'oplays': ap, 'oyards': ay,
                    'give': hg, 'take': ag, 'pf': hs, 'pa': as_, 'qb': g['home_qb_name']})
        out.append({'week': wk, 'team': g['away_team'], 'opp': g['home_team'], 'plays': ap, 'yards': ay, 'oplays': hp, 'oyards': hy,
                    'give': ag, 'take': hg, 'pf': as_, 'pa': hs, 'qb': g['away_qb_name']})
    return out


# ── 2. Ratings ───────────────────────────────────────────────────────────────
def rate(rows):
    """Schedule-adjusted offense and defense, in yards per play vs. average, solved together.

    off_t - avg = O_t - mean(D of opponents)      avg_def - def_t = D_t - mean(O of opponents)
    with sum(O) = sum(D) = 0, solved by least squares (an SRS-style rating).
    """
    agg = defaultdict(lambda: {'plays': 0, 'yards': 0, 'oplays': 0, 'oyards': 0, 'opp': [], 'give': 0, 'take': 0,
                               'pf': 0, 'pa': 0, 'w': 0, 'l': 0, 't': 0, 'g': 0})
    for r in rows:
        a = agg[r['team']]
        for k in ('plays', 'yards', 'oplays', 'oyards', 'give', 'take', 'pf', 'pa'):
            a[k] += r[k]
        a['opp'].append(r['opp']); a['g'] += 1
        a['w' if r['pf'] > r['pa'] else 'l' if r['pf'] < r['pa'] else 't'] += 1
    T = sorted(agg)
    n, ix = len(T), {t: i for i, t in enumerate(T)}
    off = {t: agg[t]['yards'] / agg[t]['plays'] for t in T}
    de = {t: agg[t]['oyards'] / agg[t]['oplays'] for t in T}
    avg_o, avg_d = statistics.mean(off.values()), statistics.mean(de.values())
    A, b = [], []
    for t in T:
        k = len(agg[t]['opp'])
        r = np.zeros(2 * n); r[ix[t]] = 1
        for o in agg[t]['opp']:
            r[n + ix[o]] -= 1 / k
        A.append(r); b.append(off[t] - avg_o)
        r = np.zeros(2 * n); r[n + ix[t]] = 1
        for o in agg[t]['opp']:
            r[ix[o]] -= 1 / k
        A.append(r); b.append(avg_d - de[t])
    r = np.zeros(2 * n); r[:n] = 1; A.append(r); b.append(0)
    r = np.zeros(2 * n); r[n:] = 1; A.append(r); b.append(0)
    x = np.linalg.lstsq(np.array(A), np.array(b), rcond=None)[0]
    O = {t: float(x[ix[t]]) for t in T}
    D = {t: float(x[n + ix[t]]) for t in T}
    teams = {}
    for t in T:
        a = agg[t]
        teams[t] = {'team': t, 'name': NAMES.get(t, t), 'games': a['g'], 'record': f"{a['w']}-{a['l']}" + (f"-{a['t']}" if a['t'] else ''),
                    'off_ypp': off[t], 'def_ypp': de[t], 'raw': off[t] - de[t], 'O': O[t], 'D': D[t], 'adj': O[t] + D[t],
                    'sos_off': statistics.mean(D[o] for o in a['opp']),   # quality of defenses faced
                    'sos_def': statistics.mean(O[o] for o in a['opp']),   # quality of offenses faced
                    'to_pg': (a['take'] - a['give']) / a['g'], 'margin_pg': (a['pf'] - a['pa']) / a['g'],
                    'opps': a['opp']}
    for t in T:
        teams[t]['sos'] = statistics.mean(teams[o]['adj'] for o in teams[t]['opps'])
    return teams


def rank(teams, key):
    vals = {t: round(v[key], 2) for t, v in teams.items()}
    return {t: 1 + sum(1 for u in vals if vals[u] > vals[t]) for t in vals}


def project(teams, away, home, neutral):
    S = SETTINGS
    hf = 0 if neutral else S['hfa'] / 2
    A, H = teams[away], teams[home]
    pa = S['points_base'] + S['pts_per_ypp'] * (A['O'] - H['D']) - hf
    ph = S['points_base'] + S['pts_per_ypp'] * (H['O'] - A['D']) + hf
    return {'away_pts': round(pa, 1), 'home_pts': round(ph, 1), 'home_spread': round(pa - ph, 1), 'total': round(pa + ph, 1)}


# ── 3. Odds ──────────────────────────────────────────────────────────────────
def fetch_odds():
    """Return (events, credits_remaining, status)."""
    f = os.environ.get('NFL_ODDS_FILE')
    if f:
        return load_json(f, []), None, 'offline'
    key = os.environ.get('ODDS_API_KEY', '')
    if os.environ.get('NFL_OFFLINE') or not key or requests is None:
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


def summarize_lines(ev):
    """Reference home spread/total (Pinnacle, else median) and best prices by side."""
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
            k, s = max(spreads.items(), key=lambda kv: (kv[1][f'{side}_pt'], kv[1][f'{side}_px']))
            return {'pt': s[f'{side}_pt'], 'px': s[f'{side}_px'], 'book': BOOK_NAMES.get(k, k)}
        out['best_home'], out['best_away'] = best('home'), best('away')
    if totals:
        ref = totals.get('pinnacle')
        out['total'] = ref['pt'] if ref else statistics.median(t['pt'] for t in totals.values())

        def best_t(side, hi):
            # under wants the highest number, over the lowest; then the best price
            k, s = max(totals.items(), key=lambda kv: (kv[1]['pt'] * (1 if hi else -1), kv[1][f'{side}_px']))
            return {'pt': s['pt'], 'px': s[f'{side}_px'], 'book': BOOK_NAMES.get(k, k)}
        out['best_under'], out['best_over'] = best_t('under', True), best_t('over', False)
    return out


def fmt_pt(x):
    return 'PK' if x == 0 else f'{x:+g}'


# ── 4. Quarterback flags ─────────────────────────────────────────────────────
def surname(name):
    parts = [p for p in name.split() if p.rstrip('.') not in ('Jr', 'Sr', 'II', 'III', 'IV', 'V')]
    return parts[-1] if parts else name


def qb_note(rows, team, qb):
    """Flag when this week's listed QB started under qb_share_flag of the games behind the rating."""
    starts = Counter(r['qb'] for r in rows if r['team'] == team and r['qb'])
    total = sum(starts.values())
    if not qb or not total:
        return None, starts
    share = starts.get(qb, 0) / total
    if share < SETTINGS['qb_share_flag']:
        main = starts.most_common(1)[0][0]
        last = surname(qb)
        if starts.get(qb, 0) == 0:
            return f"{NAMES[team]}: {last} has no starts; rating is from {surname(main)} ({starts[main]} of {total})", starts
        return f"{NAMES[team]}: {last} started {starts[qb]} of {total}", starts
    return None, starts


# ── 5. Backtest against closing lines ────────────────────────────────────────
def grade_spread(home_margin, home_spread, pick_home):
    m = (home_margin + home_spread) * (1 if pick_home else -1)
    return 'W' if m > 0 else ('P' if m == 0 else 'L')


def grade_total(total, line, over):
    m = (total - line) * (1 if over else -1)
    return 'W' if m > 0 else ('P' if m == 0 else 'L')


def backtest(sched, rows, last_week):
    out = []
    for wk in range(SETTINGS['backtest_start_week'], last_week + 1):
        prior = [r for r in rows if r['week'] < wk]
        if not prior:
            continue
        teams = rate(prior)
        for g in sched:
            if g['game_type'] != 'REG' or int(g['week']) != wk or g['home_score'] == '':
                continue
            a, h = g['away_team'], g['home_team']
            if a not in teams or h not in teams or num(g['spread_line']) is None:
                continue
            m = project(teams, a, h, is_neutral(g))
            mkt = -num(g['spread_line'])            # nflverse: positive = home favored
            tot = num(g['total_line'])
            hs, as_ = int(g['home_score']), int(g['away_score'])
            edge = round(m['home_spread'] - mkt, 1)  # > 0: model likes the away side
            qa, _ = qb_note(prior, a, g['away_qb_name'])
            qh, _ = qb_note(prior, h, g['home_qb_name'])
            row = {'week': wk, 'away': a, 'home': h, 'model': m['home_spread'], 'line': mkt, 'edge': edge,
                   'final': [as_, hs], 'qb_flag': bool(qa or qh),
                   'ats': grade_spread(hs - as_, mkt, edge < 0) if edge != 0 else None,
                   'su': ('W' if (m['home_spread'] < 0) == (hs > as_) else 'L') if hs != as_ and m['home_spread'] != 0 else None}
            if tot is not None:
                te = round(m['total'] - tot, 1)
                row.update({'model_total': m['total'], 'total_line': tot, 'total_edge': te,
                            'ou': grade_total(hs + as_, tot, te > 0) if te != 0 else None})
            out.append(row)
    return out


def tally(results):
    w = sum(r == 'W' for r in results); l = sum(r == 'L' for r in results); p = sum(r == 'P' for r in results)
    return {'w': w, 'l': l, 'p': p, 'pct': round(w / (w + l), 3) if w + l else None}


# ── 6. Main ──────────────────────────────────────────────────────────────────
def main():
    mode = os.environ.get('NFL_MODE', 'picks')
    os.makedirs(DATA, exist_ok=True)
    t0 = now_utc()
    print(f'NFL generator, mode={mode}, {t0.isoformat()}')
    S = SETTINGS

    sched, stats, nstatus = fetch_nflverse()
    rows = game_lines(sched, stats)
    print(f'  nflverse: {len(sched)} games, {len(rows)//2} with stats ({nstatus})')
    done_weeks = sorted({r['week'] for r in rows})
    last_week = done_weeks[-1] if done_weeks else 0
    open_weeks = sorted({int(g['week']) for g in sched if g['game_type'] == 'REG' and g['home_score'] == ''})
    week = open_weeks[0] if open_weeks else None

    teams = rate(rows)
    prev = rate([r for r in rows if r['week'] < last_week]) if last_week > 1 else {}
    rk, rko, rkd, rks = rank(teams, 'adj'), rank(teams, 'O'), rank(teams, 'D'), rank(teams, 'sos')
    rkso, rksd = rank(teams, 'sos_off'), rank(teams, 'sos_def')
    prk = rank(prev, 'adj') if prev else {}
    for t, v in teams.items():
        _, starts = qb_note(rows, t, None)
        v.update({'rank': rk[t], 'off_rank': rko[t], 'def_rank': rkd[t], 'sos_rank': rks[t], 'sos_off_rank': rkso[t],
                  'sos_def_rank': rksd[t], 'prev_rank': prk.get(t),
                  'proj_pf': round(S['points_base'] + S['pts_per_ypp'] * v['O'], 1),
                  'proj_pa': round(S['points_base'] - S['pts_per_ypp'] * v['D'], 1),
                  'qb_starts': starts.most_common()})

    # ── this week's slate ──
    events, credits, ostatus = fetch_odds()
    print(f'  Odds: {len(events)} events ({ostatus}), credits remaining {credits}')
    ev_by_pair = {}
    for ev in events:
        a, h = ODDS_NAMES.get(ev['away_team']), ODDS_NAMES.get(ev['home_team'])
        if a and h:
            ev_by_pair[(a, h)] = ev
    openers = load_json(os.path.join(DATA, 'openers.json'), {})
    closers = load_json(os.path.join(DATA, 'closers.json'), {})
    picks = load_json(os.path.join(DATA, 'picks.json'), [])
    logged = {(p['game_id'], p['type']) for p in picks}
    today_et = t0.astimezone(ET).date()

    games = []
    for g in sched:
        if g['game_type'] != 'REG' or week is None or int(g['week']) != week:
            continue
        a, h, gid = g['away_team'], g['home_team'], g['game_id']
        ko = kickoff(g)
        started = ko <= t0
        ev = ev_by_pair.get((a, h))
        lines = summarize_lines(ev) if ev else {}
        src = lines.get('spread_src')
        if 'home_spread' not in lines and num(g['spread_line']) is not None:  # fall back to nflverse's line
            lines['home_spread'] = -num(g['spread_line']); src = 'nflverse'
        if 'total' not in lines and num(g['total_line']) is not None:
            lines['total'] = num(g['total_line'])
        if 'home_spread' in lines and not started and ev:
            openers.setdefault(gid, {'home_spread': lines['home_spread'], 'total': lines.get('total'), 'seen': t0.isoformat()})
            closers[gid] = {'home_spread': lines['home_spread'], 'total': lines.get('total'), 'seen': t0.isoformat()}
        row = {'game_id': gid, 'kickoff': ko.isoformat(), 'away': a, 'home': h, 'away_name': NAMES[a], 'home_name': NAMES[h],
               'away_rank': rk.get(a), 'home_rank': rk.get(h), 'neutral': is_neutral(g), 'started': started,
               'away_qb': g['away_qb_name'], 'home_qb': g['home_qb_name'], 'books': lines.get('books', 0),
               'mkt_spread': lines.get('home_spread'), 'mkt_total': lines.get('total'), 'spread_src': src,
               'best_home': lines.get('best_home'), 'best_away': lines.get('best_away'),
               'best_over': lines.get('best_over'), 'best_under': lines.get('best_under'),
               'open_spread': openers.get(gid, {}).get('home_spread'), 'open_total': openers.get(gid, {}).get('total')}
        flags = []
        for side, team in (('away', a), ('home', h)):
            if team not in teams:
                flags.append(f'{NAMES[team]}: no games yet'); continue
            if teams[team]['games'] < S['min_games']:
                flags.append(f"{NAMES[team]}: only {teams[team]['games']} games")
            note, _ = qb_note(rows, team, g[f'{side}_qb_name'])
            if note:
                flags.append(note)
        row['flags'] = flags
        if a in teams and h in teams:
            m = project(teams, a, h, row['neutral'])
            row['model'] = m
            if row['mkt_spread'] is not None:
                edge = round(m['home_spread'] - row['mkt_spread'], 1)
                row['edge'] = edge
                if row['open_spread'] is not None:
                    row['move'] = round(row['mkt_spread'] - row['open_spread'], 1)
                if abs(edge) >= S['edge_threshold']:
                    side = 'away' if edge > 0 else 'home'
                    pt = -row['mkt_spread'] if side == 'away' else row['mkt_spread']
                    row['pick'] = f"{NAMES[row[side]]} {fmt_pt(pt)}"; row['pick_side'] = side
                    mv = row.get('move')
                    row['market'] = 'flat' if not mv else ('agrees' if (edge > 0) == (mv > 0) else 'against')
            if row['mkt_total'] is not None:
                te = round(m['total'] - row['mkt_total'], 1)
                row['total_edge'] = te
                if row['open_total'] is not None:
                    row['total_move'] = round(row['mkt_total'] - row['open_total'], 1)
                if abs(te) >= S['total_threshold']:
                    row['total_pick'] = f"{'Over' if te > 0 else 'Under'} {row['mkt_total']:g}"
                    row['total_side'] = 'over' if te > 0 else 'under'
            row['blocked'] = bool(flags)  # edges on flagged games are shown but never logged as picks
            # log picks on the morning of kickoff, only from live lines and with no data flags
            if mode == 'picks' and not started and not flags and ev and ko.astimezone(ET).date() == today_et:
                base = {'game_id': gid, 'week': week, 'date': str(today_et), 'kickoff': row['kickoff'], 'away': a, 'home': h,
                        'model_spread': m['home_spread'], 'model_total': m['total'], 'logged': t0.isoformat()}
                if row.get('pick') and (gid, 'spread') not in logged:
                    picks.append({**base, 'type': 'spread', 'side': row['pick_side'], 'pick': row['pick'], 'line': row['mkt_spread'],
                                  'edge': row['edge'], 'market': row['market'], 'best': row[f"best_{row['pick_side']}"]})
                    logged.add((gid, 'spread'))
                if row.get('total_pick') and (gid, 'total') not in logged:
                    picks.append({**base, 'type': 'total', 'side': row['total_side'], 'pick': row['total_pick'], 'line': row['mkt_total'],
                                  'edge': row['total_edge'], 'best': row.get(f"best_{row['total_side']}")})
                    logged.add((gid, 'total'))
        games.append(row)

    # ── grade logged picks from nflverse finals ──
    final = {g['game_id']: (int(g['away_score']), int(g['home_score'])) for g in sched if g['home_score'] != ''}
    close_nv = {g['game_id']: (num(g['spread_line']), num(g['total_line'])) for g in sched}
    for p in picks:
        c = closers.get(p['game_id'])
        if datetime.fromisoformat(p['kickoff']) <= t0:
            if p['type'] == 'spread':
                close = c['home_spread'] if c else (-close_nv[p['game_id']][0] if close_nv[p['game_id']][0] is not None else None)
                if close is not None:
                    p['close'] = close
                    p['clv'] = round((close - p['line']) if p['side'] == 'away' else (p['line'] - close), 1)
            else:
                close = c['total'] if c and c.get('total') is not None else close_nv[p['game_id']][1]
                if close is not None:
                    p['close'] = close
                    p['clv'] = round((close - p['line']) if p['side'] == 'over' else (p['line'] - close), 1)
        if p['game_id'] in final and 'result' not in p:
            fa, fh = final[p['game_id']]
            p['final'] = [fa, fh]
            if p['type'] == 'spread':
                p['result'] = grade_spread(fh - fa, p['line'], p['side'] == 'home')
            else:
                p['result'] = grade_total(fa + fh, p['line'], p['side'] == 'over')

    def record(ps):
        r = tally([p.get('result') for p in ps])
        clvs = [p['clv'] for p in ps if 'clv' in p]
        r.update({'picks': len(ps), 'avg_clv': round(statistics.mean(clvs), 2) if clvs else None,
                  'beat_close': round(sum(c > 0 for c in clvs) / len(clvs), 3) if clvs else None})
        return r

    # ── backtest ──
    bt = backtest(sched, rows, last_week)
    clean = [r for r in bt if not r['qb_flag']]
    btsum = {
        'weeks': [S['backtest_start_week'], last_week],
        'all_ats': tally([r['ats'] for r in bt]),
        'edge_ats': tally([r['ats'] for r in bt if abs(r['edge']) >= S['edge_threshold']]),
        'edge_ats_clean': tally([r['ats'] for r in clean if abs(r['edge']) >= S['edge_threshold']]),
        'edge_ats_flagged': tally([r['ats'] for r in bt if r['qb_flag'] and abs(r['edge']) >= S['edge_threshold']]),
        'su': tally([r['su'] for r in bt]),
        'all_ou': tally([r.get('ou') for r in bt]),
        'edge_ou': tally([r.get('ou') for r in bt if abs(r.get('total_edge') or 0) >= S['total_threshold']]),
        'edge_ou_clean': tally([r.get('ou') for r in clean if abs(r.get('total_edge') or 0) >= S['total_threshold']]),
        'by_week': [{'week': w, 'ats': tally([r['ats'] for r in bt if r['week'] == w and abs(r['edge']) >= S['edge_threshold'] and not r['qb_flag']]),
                     'ou': tally([r.get('ou') for r in bt if r['week'] == w and abs(r.get('total_edge') or 0) >= S['total_threshold'] and not r['qb_flag']]),
                     'all': tally([r['ats'] for r in bt if r['week'] == w])}
                    for w in sorted({r['week'] for r in bt})],
    }

    live = {g['game_id'] for g in games}
    cutoff = (t0 - timedelta(days=10)).isoformat()
    openers = {k: v for k, v in openers.items() if v['seen'] >= cutoff or k in live}
    closers = {k: v for k, v in closers.items() if v['seen'] >= cutoff or k in live}
    save_json(os.path.join(DATA, 'openers.json'), openers)
    save_json(os.path.join(DATA, 'closers.json'), closers)
    save_json(os.path.join(DATA, 'picks.json'), picks)

    games.sort(key=lambda g: (g['kickoff'], g['home']))
    team_list = sorted(teams.values(), key=lambda v: -v['adj'])
    for v in team_list:
        for k in ('off_ypp', 'def_ypp', 'raw', 'O', 'D', 'adj', 'sos', 'sos_off', 'sos_def', 'to_pg', 'margin_pg'):
            v[k] = round(v[k], 3)
    out = {
        'generated_at': t0.isoformat(), 'mode': mode, 'season': SEASON, 'week': week, 'through_week': last_week,
        'nflverse': nstatus, 'lines': {'status': ostatus, 'events': len(events), 'credits_remaining': credits},
        'settings': S, 'games': games, 'teams': team_list,
        'picks': picks[-200:],
        'record': {'spreads': record([p for p in picks if p['type'] == 'spread']),
                   'totals': record([p for p in picks if p['type'] == 'total']),
                   'agrees': record([p for p in picks if p.get('market') == 'agrees']),
                   'against': record([p for p in picks if p.get('market') == 'against'])},
        'backtest': {'summary': btsum, 'games': bt},
    }
    save_json(OUT, out)
    print(f'  Wrote {OUT}: week {week}, {len(games)} games, {sum("pick" in g for g in games)} spread edges, '
          f'{sum("total_pick" in g for g in games)} total edges, backtest {len(bt)} games')


if __name__ == '__main__':
    main()
