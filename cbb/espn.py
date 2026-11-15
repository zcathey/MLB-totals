"""Game-by-game box scores from ESPN's public scoreboard/summary JSON.

Keeps cbb/data/games.json up to date: one record per completed Division I vs
Division I game, with points and possessions for each side. Only new games are
fetched each run, so after the first backfill a run makes a few dozen requests.

Possessions per team = FGA - OREB + TO + 0.475 * FTA; a game's possessions are
the average of the two teams' estimates (the standard tempo-free formula).
"""
import json, os, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

try:
    import requests
except ImportError:
    requests = None

BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball'
SEASON_START = date(2026, 11, 2)
HDRS = {'User-Agent': 'HardwoodEdge/1.0 (personal CBB model; https://github.com/zcathey/MLB-totals)'}


def _get(url, params=None, tries=3):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=HDRS, timeout=30)
            if r.ok:
                return r.json()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1.5 * (i + 1))
    return None


def _stat(stats, name):
    for s in stats:
        if s.get('name') == name:
            return s.get('displayValue')
    return None


def _box(event_id):
    """Return {espn_team_id: {fga, fta, oreb, to}} from the game summary, or None."""
    d = _get(f'{BASE}/summary', {'event': event_id})
    if not d:
        return None
    out = {}
    for t in (d.get('boxscore') or {}).get('teams') or []:
        st = t.get('statistics') or []
        try:
            fgm_a = _stat(st, 'fieldGoalsMade-fieldGoalsAttempted').split('-')
            ftm_a = _stat(st, 'freeThrowsMade-freeThrowsAttempted').split('-')
            to = _stat(st, 'totalTurnovers') or _stat(st, 'turnovers')
            out[t['team']['id']] = {'fga': int(fgm_a[1]), 'fta': int(ftm_a[1]),
                                    'oreb': int(_stat(st, 'offensiveRebounds')), 'to': int(to)}
        except (AttributeError, IndexError, TypeError, ValueError):
            return None
    return out if len(out) == 2 else None


def poss(b):
    return b['fga'] - b['oreb'] + b['to'] + 0.475 * b['fta']


def update(path, match, today=None, log=print):
    """Refresh the cache at `path`. `match(name) -> Torvik name or None` resolves ESPN names.

    Returns (games list, stats dict)."""
    cache = {'games': {}, 'dates_done': [], 'unmatched': {}}
    if os.path.exists(path):
        with open(path) as f:
            cache = json.load(f)
    if requests is None or os.environ.get('CBB_OFFLINE'):
        return list(cache['games'].values()), {'status': 'offline', 'new': 0}

    today = today or datetime.now(timezone(timedelta(hours=-5))).date()
    done = set(cache.get('dates_done', []))
    unmatched = cache.get('unmatched', {})
    todo, new, failed = [], 0, 0
    d = SEASON_START
    while d <= today:
        ds = d.strftime('%Y%m%d')
        if ds not in done:
            sb = _get(f'{BASE}/scoreboard', {'dates': ds, 'groups': 50, 'limit': 500})
            if sb is None:
                log(f'  ESPN scoreboard {ds} failed')
                d += timedelta(days=1)
                continue
            events = sb.get('events') or []
            all_final = True
            for ev in events:
                c = ev['competitions'][0]
                st = c['status']['type']
                if not st.get('completed'):
                    if st.get('state') != 'post':   # scheduled or in progress
                        all_final = False
                    continue
                if ev['id'] in cache['games']:
                    continue
                teams = {}
                for comp in c['competitors']:
                    t = comp['team']
                    nm = match(t.get('location') or '') or match(t.get('shortDisplayName') or '')
                    if not nm:
                        key = t.get('location') or t.get('displayName')
                        unmatched[key] = unmatched.get(key, 0) + 1
                    teams[comp['homeAway']] = {'id': t['id'], 'name': nm, 'pts': int(comp.get('score') or 0)}
                if 'home' not in teams or 'away' not in teams or not teams['home']['name'] or not teams['away']['name']:
                    continue  # non-Division I opponent (or a name to add to ALIASES)
                todo.append((ev['id'], ds, bool(c.get('neutralSite')), teams))
            # a date is finished once every game on it is final and the date is in the past
            if all_final and d < today:
                done.add(ds)
        d += timedelta(days=1)

    def fetch(item):
        eid, ds, neutral, teams = item
        return item, _box(eid)

    with ThreadPoolExecutor(max_workers=8) as ex:
        for (eid, ds, neutral, teams), box in ex.map(fetch, todo):
            h, a = teams['home'], teams['away']
            if not box or h['id'] not in box or a['id'] not in box:
                failed += 1
                done.discard(ds)  # retry this date next run
                continue
            p = (poss(box[h['id']]) + poss(box[a['id']])) / 2
            if p < 40 or p > 110:  # junk box score
                failed += 1
                continue
            cache['games'][eid] = {'id': eid, 'date': f'{ds[:4]}-{ds[4:6]}-{ds[6:]}', 'neutral': neutral,
                                   'home': h['name'], 'away': a['name'], 'home_pts': h['pts'], 'away_pts': a['pts'],
                                   'poss': round(p, 1)}
            new += 1

    cache['dates_done'] = sorted(done)
    cache['unmatched'] = dict(sorted(unmatched.items(), key=lambda kv: -kv[1])[:60])
    with open(path, 'w') as f:
        json.dump(cache, f, separators=(',', ':'))
    log(f'  ESPN: {new} new games, {failed} failed, {len(cache["games"])} cached')
    return list(cache['games'].values()), {'status': 'ok', 'new': new, 'failed': failed}
