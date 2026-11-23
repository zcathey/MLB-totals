"""Hardwood ratings: our own opponent-adjusted efficiency ratings, built only from
this season's games (ESPN box scores), the same idea as the NFL page's ratings.

For every game, each team's offense produces points per 100 possessions. We solve,
by weighted least squares over all games at once:

    points per 100 = league average + offense(team) - defense(opponent) +/- home edge

so a team's offense rating is how many points per 100 possessions it scores above
average against an average defense, and its defense rating is how many it holds
opponents below average. Net = offense + defense. Tempo is solved the same way.

Each game is weighted by its possessions. A light ridge penalty (equal to about
two games of average play) keeps teams with few games, or few connections to the
rest of Division I, from getting extreme ratings in November.
"""
import statistics
from datetime import date

import numpy as np

PRIOR_GAMES = 2.0       # ridge strength, in games of average play
AVG_POSS = 69.0         # used to size the ridge and the home edge per 100 possessions


def rate(games, team_names, hfa_pts=3.0, before=None):
    """games: ESPN game dicts (home, away, home_pts, away_pts, poss, neutral, date).
    before: only use games with date < before (YYYY-MM-DD) for an as-of rating."""
    gs = [g for g in games if g['home'] in team_names and g['away'] in team_names
          and (before is None or g['date'] < before)]
    teams = sorted({g['home'] for g in gs} | {g['away'] for g in gs})
    if len(gs) < 50:
        return None
    ix = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    h = hfa_pts / 2 / AVG_POSS * 100  # home edge per side, points per 100 possessions

    # efficiency: unknowns = [mu, O_0..O_n-1, D_0..D_n-1]
    rows, y, w = [], [], []
    for g in gs:
        for off, de, pts, sgn in ((g['home'], g['away'], g['home_pts'], 1), (g['away'], g['home'], g['away_pts'], -1)):
            r = np.zeros(1 + 2 * n)
            r[0] = 1; r[1 + ix[off]] = 1; r[1 + n + ix[de]] = -1
            rows.append(r)
            y.append(100 * pts / g['poss'] - (0 if g['neutral'] else sgn * h))
            w.append(g['poss'])
    lam = PRIOR_GAMES * AVG_POSS
    for k in range(1, 1 + 2 * n):
        r = np.zeros(1 + 2 * n); r[k] = 1
        rows.append(r); y.append(0.0); w.append(lam)
    A, Y, W = np.array(rows), np.array(y), np.sqrt(np.array(w))
    x = np.linalg.lstsq(A * W[:, None], Y * W, rcond=None)[0]
    mu, O, D = x[0], x[1:1 + n], x[1 + n:]

    # tempo: possessions = tmu + T_home + T_away
    rows, y = [], []
    for g in gs:
        r = np.zeros(1 + n); r[0] = 1; r[1 + ix[g['home']]] = 1; r[1 + ix[g['away']]] = 1
        rows.append(r); y.append(g['poss'])
    for k in range(1, 1 + n):
        r = np.zeros(1 + n); r[k] = np.sqrt(PRIOR_GAMES)
        rows.append(r); y.append(0.0)
    xt = np.linalg.lstsq(np.array(rows), np.array(y), rcond=None)[0]
    tmu, T = xt[0], xt[1:]

    out = {}
    opps = {t: [] for t in teams}
    for g in gs:
        opps[g['home']].append(g['away']); opps[g['away']].append(g['home'])
    for t in teams:
        i = ix[t]
        out[t] = {'team': t, 'O': float(O[i]), 'D': float(D[i]), 'net': float(O[i] + D[i]),
                  'tempo': float(tmu + 2 * T[i]), 'T': float(T[i]), 'games': len(opps[t])}
    for t in teams:
        out[t]['sos'] = statistics.mean(out[o]['net'] for o in opps[t])
    for key, rk in (('net', 'rank'), ('O', 'off_rank'), ('D', 'def_rank'), ('sos', 'sos_rank')):
        for r, t in enumerate(sorted(teams, key=lambda t: -out[t][key]), 1):
            out[t][rk] = r
    return {'teams': out, 'mu': float(mu), 'tmu': float(tmu), 'h': h, 'games': len(gs)}


def project(R, away, home, neutral):
    """Projected score from a rate() result, or None if either team is unrated."""
    if not R or away not in R['teams'] or home not in R['teams']:
        return None
    a, hm = R['teams'][away], R['teams'][home]
    poss = R['tmu'] + a['T'] + hm['T']
    h = 0 if neutral else R['h']
    pa = (R['mu'] + a['O'] - hm['D'] - h) * poss / 100
    ph = (R['mu'] + hm['O'] - a['D'] + h) * poss / 100
    return {'poss': round(poss, 1), 'away_pts': round(pa, 1), 'home_pts': round(ph, 1),
            'home_spread': round(pa - ph, 1), 'total': round(pa + ph, 1)}


def backtest(rows, games, team_names, hfa_pts, threshold, total_threshold=4.0):
    """rows: dicts with date (ET), away, home, neutral, close (home spread), final [away, home],
    and optionally torvik (Torvik model home spread), total (closing total) and torvik_total
    (Torvik model total saved before tip). Each game is projected with ratings built only from
    games before its date. Returns a summary and per-game results."""
    cache, per = {}, []
    for r in rows:
        if r['date'] not in cache:
            cache[r['date']] = rate(games, team_names, hfa_pts, before=r['date'])
        p = project(cache[r['date']], r['away'], r['home'], r['neutral'])
        if not p or r.get('close') is None or not r.get('final'):
            continue
        fa, fh = r['final']
        margin = fh - fa
        item = {'date': r['date'], 'away': r['away'], 'home': r['home'], 'close': r['close'],
                'hardwood': p['home_spread'], 'torvik': r.get('torvik'), 'final': r['final']}
        for model in ('hardwood', 'torvik'):
            ms = item[model]
            if ms is None:
                continue
            edge = ms - r['close']
            item[f'{model}_edge'] = round(edge, 1)
            item[f'{model}_err'] = abs(-ms - margin)   # model margin is -spread
            if abs(edge) >= threshold:
                m = (margin + r['close']) * (-1 if edge > 0 else 1)
                item[f'{model}_res'] = 'W' if m > 0 else ('P' if m == 0 else 'L')
        item['close_err'] = abs(-r['close'] - margin)
        # totals: closing total vs each model's total; a 'pick' is a gap of total_threshold or more
        ct = r.get('total')
        if ct is not None:
            ft = fa + fh
            item.update({'close_total': ct, 'final_total': ft, 'hw_total': p['total'], 'tv_total': r.get('torvik_total')})
            for model, key in (('hardwood', 'hw_total'), ('torvik', 'tv_total')):
                mt = item[key]
                if mt is None:
                    continue
                gap = mt - ct
                item[f'{model}_tgap'] = round(gap, 1)
                item[f'{model}_terr'] = abs(mt - ft)
                if abs(gap) >= total_threshold:
                    m = (ft - ct) * (1 if gap > 0 else -1)
                    item[f'{model}_tres'] = ('O' if gap > 0 else 'U') + ('W' if m > 0 else ('P' if m == 0 else 'L'))
        per.append(item)

    def summ(model):
        res = [x[f'{model}_res'] for x in per if f'{model}_res' in x]
        errs = [x[f'{model}_err'] for x in per if f'{model}_err' in x]
        same = [x for x in per if f'{model}_err' in x]
        return {'games': len(errs), 'picks': len(res), 'w': res.count('W'), 'l': res.count('L'), 'p': res.count('P'),
                'mae': round(statistics.mean(errs), 2) if errs else None,
                'close_mae_same_games': round(statistics.mean(x['close_err'] for x in same), 2) if same else None}
    both = [x for x in per if 'hardwood_res' in x and 'torvik_res' in x
            and (x['hardwood_edge'] > 0) == (x['torvik_edge'] > 0)]
    agree = {'picks': len(both), 'w': sum(x['hardwood_res'] == 'W' for x in both),
             'l': sum(x['hardwood_res'] == 'L' for x in both)}
    def tsumm(model):
        res = [x[f'{model}_tres'] for x in per if f'{model}_tres' in x]
        errs = [x[f'{model}_terr'] for x in per if f'{model}_terr' in x]
        same = [x for x in per if f'{model}_terr' in x]
        out = {'games': len(errs), 'picks': len(res), 'w': sum(r[1] == 'W' for r in res),
               'l': sum(r[1] == 'L' for r in res), 'p': sum(r[1] == 'P' for r in res),
               'mae': round(statistics.mean(errs), 2) if errs else None,
               'close_mae_same_games': round(statistics.mean(abs(x['close_total'] - x['final_total']) for x in same), 2)
               if same else None}
        for side in ('O', 'U'):
            out[side.lower()] = [sum(r == side + 'W' for r in res), sum(r == side + 'L' for r in res)]
        return out
    tg = [x for x in per if 'close_total' in x]
    market = {'games': len(tg), 'overs': sum(x['final_total'] > x['close_total'] for x in tg),
              'unders': sum(x['final_total'] < x['close_total'] for x in tg),
              'avg_close': round(statistics.mean(x['close_total'] for x in tg), 1) if tg else None,
              'avg_final': round(statistics.mean(x['final_total'] for x in tg), 1) if tg else None}
    totals = {'threshold': total_threshold, 'hardwood': tsumm('hardwood'), 'torvik': tsumm('torvik'), 'market': market}
    return {'hardwood': summ('hardwood'), 'torvik': summ('torvik'), 'both_agree': agree, 'totals': totals}, per
