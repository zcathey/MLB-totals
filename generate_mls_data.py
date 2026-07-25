#!/usr/bin/env python3
"""
Pitch & Poisson — MLS Goal Totals — daily data generator
=========================================================
Sibling script to your existing generate_data.py (MLB). Runs as an
additional step in the same GitHub Actions workflow:

    1. Pull the full season's fixture list from API-Football (API-Sports) —
       one call gets every finished match (with scores) and every
       upcoming one. We aggregate home/away goals-for/against ourselves
       from the finished matches rather than relying on the /teams and
       /teams/statistics endpoints, which returned empty even with a
       confirmed-correct league ID and season during testing — raw
       fixture data is documented as available on every plan, including
       free, so this sidesteps whatever that restriction was.
    2. Feed them into the same Poisson engine from mls_model.py.
    3. Write mls_data.json at the repo root, next to your existing
       data.json — the MLS tab in diamonds_runs.html fetches it from
       './mls_data.json' the same way the MLB side fetches './data.json'.

If the API call fails (no key set yet, rate limit, network hiccup) this
falls back to the bundled SEED_TEAM_STATS so the site never ships a blank
page — it just shows slightly stale numbers with a "seed data" flag that
the frontend can display.

SETUP
-----
1. Get a free key by signing up directly at api-football.com — this is
   the api-sports.io key, NOT a RapidAPI subscription (their marketplace
   listing for this API has been unreliable, so skip it entirely):
   https://dashboard.api-football.com/register
   Free plan: 100 requests/day, no credit card, every endpoint included.
   Your key is under Account → My Access once you're logged in.
2. Add it as a GitHub Actions secret named APISPORTS_KEY on this repo
   (Settings → Secrets and variables → Actions → New repository secret).
   If you already added a secret called RAPIDAPI_KEY for this from an
   earlier step, either rename it to APISPORTS_KEY or add a second
   secret with the new name — either works, just make sure the workflow
   yaml's env: block matches whatever name you used.
3. You do NOT need to verify MLS_LEAGUE_ID yourself anymore — the script
   now looks it up at runtime via /leagues?search=MLS and logs exactly
   what it finds (candidate leagues, the resolved ID, and which seasons
   your plan has data for) to the Action log under "[diag]" lines. If
   the live pull still fails, check those lines first — a common cause
   on the free plan is the current in-progress season not being covered
   yet, in which case the log will show it falling back to the latest
   season your plan does have.
"""
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from itertools import product

import requests

# ── CONFIG ────────────────────────────────────────────────────────────────
# Direct api-sports.io key (from dashboard.api-football.com), NOT RapidAPI.
APISPORTS_KEY = os.environ.get("APISPORTS_KEY", "")
API_BASE = "https://v3.football.api-sports.io"
MLS_LEAGUE_ID = 253          # verify against your own dashboard, see docstring
SEASON = 2026
OUTPUT_PATH = "mls_data.json"          # repo root, alongside your existing data.json
HOME_ADV_MULT = 1.00

HEADERS = {
    "x-apisports-key": APISPORTS_KEY,
}

# ── TEAM NAME BOOK (abbr -> display name, plus fuzzy-match aliases) ────────
TEAM_NAMES = {
    "ATL": "Atlanta United", "AUS": "Austin FC", "MTL": "CF Montreal", "CLT": "Charlotte FC",
    "CHI": "Chicago Fire", "CIN": "FC Cincinnati", "COL": "Colorado Rapids", "CLB": "Columbus Crew",
    "DAL": "FC Dallas", "DCU": "D.C. United", "HOU": "Houston Dynamo", "MIA": "Inter Miami",
    "LAG": "LA Galaxy", "LAFC": "Los Angeles FC", "MIN": "Minnesota United", "NSH": "Nashville SC",
    "NE": "New England Revolution", "NYC": "New York City FC", "NYRB": "NY Red Bulls",
    "ORL": "Orlando City", "PHI": "Philadelphia Union", "POR": "Portland Timbers",
    "RSL": "Real Salt Lake", "SD": "San Diego FC", "SJ": "San Jose Earthquakes",
    "SEA": "Seattle Sounders", "SKC": "Sporting Kansas City", "STL": "St. Louis City",
    "TOR": "Toronto FC", "VAN": "Vancouver Whitecaps",
}

# Extra strings the API might use that don't normalize-match cleanly to the
# display names above. Add to this as you hit mismatches in practice.
ALIASES = {
    "montreal impact": "MTL", "cf montreal": "MTL", "cf montréal": "MTL",
    "la galaxy": "LAG", "los angeles galaxy": "LAG",
    "lafc": "LAFC", "los angeles fc": "LAFC",
    "dc united": "DCU", "d.c. united": "DCU",
    "ny red bulls": "NYRB", "new york red bulls": "NYRB",
    "nycfc": "NYC", "new york city fc": "NYC",
    "sporting kc": "SKC", "sporting kansas city": "SKC",
    "st. louis city": "STL", "st louis city sc": "STL", "st. louis city sc": "STL",
    "inter miami cf": "MIA", "inter miami": "MIA",
}


def normalize(name):
    return "".join(ch for ch in name.lower().strip() if ch.isalnum() or ch.isspace())


def match_abbr(api_team_name):
    norm = normalize(api_team_name)
    if norm in ALIASES:
        return ALIASES[norm]
    for abbr, display in TEAM_NAMES.items():
        if normalize(display) == norm:
            return abbr
    # loose fallback: substring match either direction
    for abbr, display in TEAM_NAMES.items():
        d = normalize(display)
        if d in norm or norm in d:
            return abbr
    return None


# ── SEED DATA (fallback if the live API call fails) ────────────────────────
# Real 2026 MLS home/away GF/GA splits, snapshot late July 2026 — the same
# numbers used in mls_model.py. Used only if the live pull doesn't work.
SEED_LG_AVG_HOME_GOALS = 1.92
SEED_LG_AVG_AWAY_GOALS = 1.29
SEED_TEAM_STATS = {
    "ATL":  {"gp_home": 8, "gp_away": 4, "gf_home": 11, "gf_away": 2,  "ga_home": 14, "ga_away": 6},
    "AUS":  {"gp_home": 6, "gp_away": 6, "gf_home": 8,  "gf_away": 10, "ga_home": 4,  "ga_away": 17},
    "MTL":  {"gp_home": 4, "gp_away": 7, "gf_home": 8,  "gf_away": 8,  "ga_home": 3,  "ga_away": 20},
    "CLT":  {"gp_home": 6, "gp_away": 6, "gf_home": 14, "gf_away": 6,  "ga_home": 7,  "ga_away": 14},
    "CHI":  {"gp_home": 7, "gp_away": 4, "gf_home": 14, "gf_away": 6,  "ga_home": 8,  "ga_away": 6},
    "CIN":  {"gp_home": 5, "gp_away": 7, "gf_home": 11, "gf_away": 13, "ga_home": 7,  "ga_away": 20},
    "COL":  {"gp_home": 5, "gp_away": 7, "gf_home": 14, "gf_away": 8,  "ga_home": 7,  "ga_away": 13},
    "CLB":  {"gp_home": 6, "gp_away": 6, "gf_home": 7,  "gf_away": 9,  "ga_home": 6,  "ga_away": 13},
    "DAL":  {"gp_home": 8, "gp_away": 4, "gf_home": 16, "gf_away": 7,  "ga_home": 13, "ga_away": 3},
    "DCU":  {"gp_home": 4, "gp_away": 8, "gf_home": 5,  "gf_away": 10, "ga_home": 8,  "ga_away": 9},
    "HOU":  {"gp_home": 6, "gp_away": 5, "gf_home": 7,  "gf_away": 10, "ga_home": 6,  "ga_away": 13},
    "MIA":  {"gp_home": 4, "gp_away": 8, "gf_home": 8,  "gf_away": 18, "ga_home": 9,  "ga_away": 12},
    "LAG":  {"gp_home": 6, "gp_away": 6, "gf_home": 9,  "gf_away": 9,  "ga_home": 7,  "ga_away": 11},
    "LAFC": {"gp_home": 7, "gp_away": 5, "gf_home": 14, "gf_away": 6,  "ga_home": 8,  "ga_away": 4},
    "MIN":  {"gp_home": 5, "gp_away": 7, "gf_home": 5,  "gf_away": 11, "ga_home": 3,  "ga_away": 15},
    "NSH":  {"gp_home": 5, "gp_away": 6, "gf_home": 18, "gf_away": 5,  "ga_home": 6,  "ga_away": 2},
    "NE":   {"gp_home": 6, "gp_away": 5, "gf_home": 15, "gf_away": 5,  "ga_home": 3,  "ga_away": 10},
    "NYC":  {"gp_home": 8, "gp_away": 4, "gf_home": 19, "gf_away": 3,  "ga_home": 13, "ga_away": 5},
    "NYRB": {"gp_home": 5, "gp_away": 7, "gf_home": 9,  "gf_away": 10, "ga_home": 11, "ga_away": 17},
    "ORL":  {"gp_home": 5, "gp_away": 7, "gf_home": 9,  "gf_away": 7,  "ga_home": 9,  "ga_away": 25},
    "PHI":  {"gp_home": 5, "gp_away": 7, "gf_home": 2,  "gf_away": 8,  "ga_home": 5,  "ga_away": 14},
    "POR":  {"gp_home": 5, "gp_away": 6, "gf_home": 13, "gf_away": 6,  "ga_home": 8,  "ga_away": 13},
    "RSL":  {"gp_home": 6, "gp_away": 5, "gf_home": 13, "gf_away": 7,  "ga_home": 7,  "ga_away": 10},
    "SD":   {"gp_home": 6, "gp_away": 6, "gf_home": 13, "gf_away": 7,  "ga_home": 8,  "ga_away": 12},
    "SJ":   {"gp_home": 6, "gp_away": 6, "gf_home": 14, "gf_away": 13, "ga_home": 3,  "ga_away": 5},
    "SEA":  {"gp_home": 4, "gp_away": 6, "gf_home": 9,  "gf_away": 5,  "ga_home": 3,  "ga_away": 3},
    "SKC":  {"gp_home": 5, "gp_away": 6, "gf_home": 5,  "gf_away": 3,  "ga_home": 11, "ga_away": 21},
    "STL":  {"gp_home": 4, "gp_away": 7, "gf_home": 6,  "gf_away": 4,  "ga_home": 6,  "ga_away": 12},
    "TOR":  {"gp_home": 9, "gp_away": 3, "gf_home": 17, "gf_away": 3,  "ga_home": 18, "ga_away": 6},
    "VAN":  {"gp_home": 8, "gp_away": 3, "gf_home": 21, "gf_away": 6,  "ga_home": 4,  "ga_away": 3},
}


# ── LIVE DATA PULL ──────────────────────────────────────────────────────────
def api_get(endpoint, params):
    resp = requests.get(f"{API_BASE}/{endpoint}", headers=HEADERS, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


_resolved_league_season = None  # cache so we only hit /leagues once per run

# Search "MLS" alone matches "MLS All-Star" and "MLS Next Pro" (the
# developmental third-tier league) but NOT the actual top-flight league,
# whose registered name is the full "Major League Soccer" — that string
# doesn't contain "MLS" as a literal substring, so the abbreviation search
# misses it entirely. Search the full name, and explicitly filter out the
# known non-top-flight competitions in case of ambiguity.
LEAGUE_SEARCH_TERM = "Major League Soccer"
EXCLUDE_NAME_SUBSTRINGS = ["all-star", "next pro", "next", "reserve", "u-", "youth", "women"]

def resolve_league_and_season():
    """Look up MLS's real league ID and a season your plan actually has data
    for, instead of trusting the hardcoded MLS_LEAGUE_ID/SEASON guesses.
    Logs everything it finds so a failure here is diagnosable from the
    Action log, not a mystery."""
    global _resolved_league_season
    if _resolved_league_season is not None:
        return _resolved_league_season

    resp = api_get("leagues", {"search": LEAGUE_SEARCH_TERM})
    candidates = resp.get("response", [])
    print(f"  [diag] /leagues?search={LEAGUE_SEARCH_TERM!r} returned {len(candidates)} candidate(s)", file=sys.stderr)

    match = None
    for entry in candidates:
        league = entry.get("league", {})
        country = entry.get("country", {})
        name = league.get("name", "")
        print(f"  [diag]   candidate: id={league.get('id')} name={name!r} "
              f"country={country.get('name')!r} type={league.get('type')!r}", file=sys.stderr)
        name_lower = name.lower()
        if any(bad in name_lower for bad in EXCLUDE_NAME_SUBSTRINGS):
            continue
        if country.get("name") == "USA" and league.get("type", "").lower() == "league":
            match = entry
            break
    if match is None and candidates:
        match = candidates[0]  # best-effort fallback to whatever came back first
    if match is None:
        raise RuntimeError(f"No MLS league found via /leagues?search={LEAGUE_SEARCH_TERM!r} — check your plan/key")

    league_id = match["league"]["id"]
    seasons = match.get("seasons", [])
    year_list = sorted(s["year"] for s in seasons)
    current_year = next((s["year"] for s in seasons if s.get("current")), None)
    print(f"  [diag] resolved league_id={league_id} ({match['league'].get('name')!r}), "
          f"available seasons={year_list}, API-flagged current season={current_year}", file=sys.stderr)

    # The /leagues response carries a per-season "coverage" object listing
    # exactly which data types API-Football actually tracks for this
    # competition (fixtures/events/lineups/statistics/standings/etc). If
    # this shows fixtures-related flags as false, that's a data-coverage
    # gap on the provider's side for this competition, not a bug in this
    # script or a season-timing issue.
    for s in sorted(seasons, key=lambda s: s["year"], reverse=True)[:2]:
        cov = s.get("coverage", {})
        print(f"  [diag] season {s['year']} coverage: {cov}", file=sys.stderr)

    season = current_year if current_year is not None else (year_list[-1] if year_list else SEASON)
    if season != SEASON:
        print(f"  [diag] using season={season} instead of the configured SEASON={SEASON}", file=sys.stderr)

    _resolved_league_season = (league_id, season)
    return _resolved_league_season


def fetch_season_fixtures(league_id, season):
    """One call gets the whole season's fixture list — both finished
    matches (with scores, which we aggregate into home/away GF/GA
    ourselves) and upcoming ones. This deliberately avoids /teams and
    /teams/statistics: those returned nothing in testing even with a
    confirmed-correct league_id/season, which pointed at those specific
    aggregate endpoints being free-plan-restricted while raw fixture
    data (scores, schedules) is documented as included on every plan.
    Doing the aggregation ourselves also cuts this down to ~2 API calls
    total per run instead of ~1 + (1 per team)."""
    resp = api_get("fixtures", {"league": league_id, "season": season})
    fixtures = resp.get("response", [])
    print(f"  [diag] /fixtures?league={league_id}&season={season} returned {len(fixtures)} fixture(s)",
          file=sys.stderr)

    if not fixtures:
        # /teams AND /fixtures both empty for a confirmed-correct league_id/
        # season points away from an endpoint-specific restriction and
        # toward the current season simply not being populated in
        # API-Football's system yet (their docs note a rollout lag between
        # a season's calendar and its match data landing in the API) —
        # OR a free-plan season limit that excludes the current season
        # entirely. Probe the prior season to tell these apart: if THAT
        # comes back non-empty, the account/key/league_id are all fine and
        # it's specifically 2026 that's missing; if it's also empty,
        # something more fundamental is off (auth, plan, account status).
        probe_season = season - 1
        probe_resp = api_get("fixtures", {"league": league_id, "season": probe_season})
        probe_fixtures = probe_resp.get("response", [])
        print(f"  [diag] probe: /fixtures?league={league_id}&season={probe_season} "
              f"returned {len(probe_fixtures)} fixture(s) — "
              f"{'season ' + str(season) + ' specifically has no data yet' if probe_fixtures else 'even the prior season is empty, so this is likely an account/plan/auth issue, not a season-availability gap'}",
              file=sys.stderr)

    return fixtures


FINISHED_STATUSES = {"FT", "AET", "PEN"}
UPCOMING_STATUSES = {"NS", "TBD", "PST"}  # not started / to-be-defined / postponed-but-not-cancelled


def build_team_stats_from_fixtures(fixtures):
    """Aggregate home/away GF/GA per team from raw finished-match scores."""
    agg = {abbr: {"gp_home": 0, "gp_away": 0, "gf_home": 0, "gf_away": 0, "ga_home": 0, "ga_away": 0}
           for abbr in TEAM_NAMES}
    total_home_goals = total_home_games = 0
    total_away_goals = total_away_games = 0
    unmatched = set()

    for f in fixtures:
        status = f.get("fixture", {}).get("status", {}).get("short")
        if status not in FINISHED_STATUSES:
            continue
        home_goals = f.get("goals", {}).get("home")
        away_goals = f.get("goals", {}).get("away")
        if home_goals is None or away_goals is None:
            continue
        home_name = f["teams"]["home"]["name"]
        away_name = f["teams"]["away"]["name"]
        home_abbr = match_abbr(home_name)
        away_abbr = match_abbr(away_name)
        if home_abbr is None:
            unmatched.add(home_name)
        if away_abbr is None:
            unmatched.add(away_name)
        if home_abbr is None or away_abbr is None:
            continue

        agg[home_abbr]["gp_home"] += 1
        agg[home_abbr]["gf_home"] += home_goals
        agg[home_abbr]["ga_home"] += away_goals
        agg[away_abbr]["gp_away"] += 1
        agg[away_abbr]["gf_away"] += away_goals
        agg[away_abbr]["ga_away"] += home_goals

        total_home_goals += home_goals
        total_home_games += 1
        total_away_goals += away_goals
        total_away_games += 1

    if unmatched:
        print(f"  [warn] no abbr match for API team name(s): {sorted(unmatched)}", file=sys.stderr)

    team_stats = {}
    for abbr, s in agg.items():
        if s["gp_home"] == 0 or s["gp_away"] == 0:
            team_stats[abbr] = SEED_TEAM_STATS[abbr]  # not enough games yet — use seed for this team only
        else:
            team_stats[abbr] = s

    if total_home_games == 0 or total_away_games == 0:
        raise RuntimeError("No finished fixtures with usable scores found — can't compute league averages")

    lg_avg_home = total_home_goals / total_home_games
    lg_avg_away = total_away_goals / total_away_games
    print(f"  [diag] built team stats from {total_home_games} finished fixtures, "
          f"lg_avg_home={lg_avg_home:.3f}, lg_avg_away={lg_avg_away:.3f}", file=sys.stderr)
    return team_stats, lg_avg_home, lg_avg_away


def extract_upcoming_fixtures(fixtures, n=15):
    """Pull the next N not-yet-played fixtures out of the same season list,
    sorted by kickoff time."""
    upcoming = []
    for f in fixtures:
        status = f.get("fixture", {}).get("status", {}).get("short")
        if status not in UPCOMING_STATUSES:
            continue
        home_abbr = match_abbr(f["teams"]["home"]["name"])
        away_abbr = match_abbr(f["teams"]["away"]["name"])
        if home_abbr is None or away_abbr is None:
            continue
        upcoming.append({
            "home": home_abbr, "away": away_abbr,
            "kickoff_utc": f["fixture"]["date"],
        })
    upcoming.sort(key=lambda g: g["kickoff_utc"] or "")
    return upcoming[:n]


# ── POISSON ENGINE (same math as mls_model.py) ──────────────────────────────
def team_strength(abbr, team_stats, lg_avg_home, lg_avg_away):
    t = team_stats[abbr]
    return {
        "home_attack": (t["gf_home"] / t["gp_home"]) / lg_avg_home,
        "away_attack": (t["gf_away"] / t["gp_away"]) / lg_avg_away,
        "home_defense": (t["ga_home"] / t["gp_home"]) / lg_avg_away,
        "away_defense": (t["ga_away"] / t["gp_away"]) / lg_avg_home,
    }


def expected_goals(home_abbr, away_abbr, team_stats, lg_avg_home, lg_avg_away):
    h = team_strength(home_abbr, team_stats, lg_avg_home, lg_avg_away)
    a = team_strength(away_abbr, team_stats, lg_avg_home, lg_avg_away)
    exp_home = lg_avg_home * h["home_attack"] * a["away_defense"] * HOME_ADV_MULT
    exp_away = lg_avg_away * a["away_attack"] * h["home_defense"]
    return round(exp_home, 3), round(exp_away, 3)


def poisson_pmf(k, lam):
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def scoreline_matrix(exp_home, exp_away, max_goals=6):
    home_probs = [poisson_pmf(i, exp_home) for i in range(max_goals + 1)]
    away_probs = [poisson_pmf(j, exp_away) for j in range(max_goals + 1)]
    return {(i, j): home_probs[i] * away_probs[j]
            for i, j in product(range(max_goals + 1), range(max_goals + 1))}


def market_probabilities(matrix, ou_line=2.5):
    home_win = draw = away_win = over = under = btts_yes = btts_no = 0.0
    for (i, j), p in matrix.items():
        if i > j: home_win += p
        elif i == j: draw += p
        else: away_win += p
        if i + j > ou_line: over += p
        else: under += p
        if i > 0 and j > 0: btts_yes += p
        else: btts_no += p
    return {
        "home_win": round(home_win, 4), "draw": round(draw, 4), "away_win": round(away_win, 4),
        "over": round(over, 4), "under": round(under, 4),
        "btts_yes": round(btts_yes, 4), "btts_no": round(btts_no, 4),
    }


def top_scorelines(matrix, n=5):
    top = sorted(matrix.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [{"home_goals": i, "away_goals": j, "prob": round(p, 4)} for (i, j), p in top]


# ── MAIN ─────────────────────────────────────────────────────────────────
def build_game(home_abbr, away_abbr, team_stats, lg_avg_home, lg_avg_away, kickoff_utc=None):
    exp_h, exp_a = expected_goals(home_abbr, away_abbr, team_stats, lg_avg_home, lg_avg_away)
    matrix = scoreline_matrix(exp_h, exp_a)
    return {
        "home": home_abbr, "away": away_abbr,
        "home_name": TEAM_NAMES[home_abbr], "away_name": TEAM_NAMES[away_abbr],
        "kickoff_utc": kickoff_utc,
        "exp_home_goals": exp_h, "exp_away_goals": exp_a,
        "exp_total_goals": round(exp_h + exp_a, 2),
        "top_scorelines": top_scorelines(matrix),
        "markets": market_probabilities(matrix, ou_line=2.5),
    }


def power_rankings(team_stats, lg_avg_home, lg_avg_away):
    rows = []
    for abbr in TEAM_NAMES:
        s = team_strength(abbr, team_stats, lg_avg_home, lg_avg_away)
        overall = (s["home_attack"] + s["away_attack"]) / (s["home_defense"] + s["away_defense"])
        rows.append({"abbr": abbr, "name": TEAM_NAMES[abbr], "index": round(overall, 3)})
    rows.sort(key=lambda r: r["index"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def main():
    data_source = "live"
    fixtures = []

    if not APISPORTS_KEY:
        print("[info] APISPORTS_KEY not set — using seed data", file=sys.stderr)
        team_stats, lg_avg_home, lg_avg_away = SEED_TEAM_STATS, SEED_LG_AVG_HOME_GOALS, SEED_LG_AVG_AWAY_GOALS
        data_source = "seed"
    else:
        try:
            league_id, season = resolve_league_and_season()
            season_fixtures = fetch_season_fixtures(league_id, season)
            team_stats, lg_avg_home, lg_avg_away = build_team_stats_from_fixtures(season_fixtures)
            fixtures = extract_upcoming_fixtures(season_fixtures)
        except Exception as e:
            print(f"[warn] live pull failed ({e}), falling back to seed data", file=sys.stderr)
            team_stats, lg_avg_home, lg_avg_away = SEED_TEAM_STATS, SEED_LG_AVG_HOME_GOALS, SEED_LG_AVG_AWAY_GOALS
            data_source = "seed"

    # If we didn't get real fixtures (seed mode, or empty API response), show
    # one demo matchup so the page still renders something meaningful.
    if not fixtures:
        fixtures = [{"home": "NSH", "away": "MIA", "kickoff_utc": None},
                    {"home": "VAN", "away": "SD", "kickoff_utc": None}]

    games = [build_game(f["home"], f["away"], team_stats, lg_avg_home, lg_avg_away, f.get("kickoff_utc"))
             for f in fixtures]

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": data_source,
        "league_avg_home_goals": round(lg_avg_home, 3),
        "league_avg_away_goals": round(lg_avg_away, 3),
        "games": games,
        "power_rankings": power_rankings(team_stats, lg_avg_home, lg_avg_away),
    }

    out_dir = os.path.dirname(OUTPUT_PATH)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Wrote {OUTPUT_PATH} ({len(games)} games, source={data_source})")


if __name__ == "__main__":
    main()
