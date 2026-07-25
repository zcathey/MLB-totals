#!/usr/bin/env python3
"""
Pitch & Poisson — MLS Goal Totals — daily data generator
=========================================================
Sibling script to your existing generate_data.py (MLB). Runs as an
additional step in the same GitHub Actions workflow:

    1. Pull real, current team stats (home/away goals for/against) and
       today's/upcoming fixtures from API-Football (API-Sports).
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
3. Verify MLS_LEAGUE_ID below against your own dashboard (Ids → Leagues →
   search "MLS") before relying on this for real games — league IDs are
   stable per API but not something I can verify without your key, so
   double-check it once.
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


def fetch_live_team_stats():
    """Returns (team_stats_dict, lg_avg_home, lg_avg_away) or raises on failure."""
    teams_resp = api_get("teams", {"league": MLS_LEAGUE_ID, "season": SEASON})
    teams = teams_resp.get("response", [])
    if not teams:
        raise RuntimeError("No teams returned — check MLS_LEAGUE_ID/SEASON")

    team_stats = {}
    total_home_goals = total_home_games = 0
    total_away_goals = total_away_games = 0

    for entry in teams:
        api_id = entry["team"]["id"]
        api_name = entry["team"]["name"]
        abbr = match_abbr(api_name)
        if abbr is None:
            print(f"  [warn] no abbr match for API team '{api_name}', skipping", file=sys.stderr)
            continue

        stats = api_get("teams/statistics",
                         {"league": MLS_LEAGUE_ID, "season": SEASON, "team": api_id})
        r = stats.get("response", {})
        try:
            gp_home = r["fixtures"]["played"]["home"]
            gp_away = r["fixtures"]["played"]["away"]
            gf_home = r["goals"]["for"]["total"]["home"]
            gf_away = r["goals"]["for"]["total"]["away"]
            ga_home = r["goals"]["against"]["total"]["home"]
            ga_away = r["goals"]["against"]["total"]["away"]
        except (KeyError, TypeError):
            print(f"  [warn] incomplete stats for {abbr}, using seed values", file=sys.stderr)
            team_stats[abbr] = SEED_TEAM_STATS[abbr]
            continue

        if gp_home == 0 or gp_away == 0:
            # Not enough games yet this season to trust — fall back for this team only
            team_stats[abbr] = SEED_TEAM_STATS[abbr]
            continue

        team_stats[abbr] = {
            "gp_home": gp_home, "gp_away": gp_away,
            "gf_home": gf_home, "gf_away": gf_away,
            "ga_home": ga_home, "ga_away": ga_away,
        }
        total_home_goals += gf_home
        total_home_games += gp_home
        total_away_goals += gf_away
        total_away_games += gp_away

    # fill in any team we never matched at all
    for abbr in TEAM_NAMES:
        team_stats.setdefault(abbr, SEED_TEAM_STATS[abbr])

    if total_home_games == 0 or total_away_games == 0:
        raise RuntimeError("Could not compute league averages from live data")

    lg_avg_home = total_home_goals / total_home_games
    lg_avg_away = total_away_goals / total_away_games
    return team_stats, lg_avg_home, lg_avg_away


def fetch_upcoming_fixtures(n=15):
    """Next N MLS fixtures league-wide, regardless of date."""
    resp = api_get("fixtures", {"league": MLS_LEAGUE_ID, "season": SEASON, "next": n})
    fixtures = []
    for f in resp.get("response", []):
        home_name = f["teams"]["home"]["name"]
        away_name = f["teams"]["away"]["name"]
        home_abbr = match_abbr(home_name)
        away_abbr = match_abbr(away_name)
        if home_abbr is None or away_abbr is None:
            continue
        fixtures.append({
            "home": home_abbr, "away": away_abbr,
            "kickoff_utc": f["fixture"]["date"],
        })
    return fixtures


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
            team_stats, lg_avg_home, lg_avg_away = fetch_live_team_stats()
            fixtures = fetch_upcoming_fixtures()
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
