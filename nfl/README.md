# Gridiron Edge — NFL model

Live page: https://zcathey.github.io/MLB-totals/nfl/

## How it works

- `generate_nfl.py` runs in GitHub Actions (`.github/workflows/update_nfl.yml`):
  - **8:00 AM ET daily** (`picks`): refreshes nflverse stats, snapshots lines, logs model picks for games kicking off that day, grades finished picks.
  - **Before each kickoff window** (`late`): Thursday 7:00 PM, Saturday 3:45 PM, Sunday 11:30 AM / 2:45 PM / 6:45 PM, Monday 6:45 PM ET. Snapshots lines so every game gets a closing line.
- Data: nflverse (`nfldata/games.csv` for the schedule, results, closing lines, neutral sites and starting quarterbacks; `stats_team_week_2026.csv` for per-game team stats). Cached copies of the current season are kept in `data/` in case a download fails.
- Lines: The Odds API (`ODDS_API_KEY` repo secret, shared with the MLB and CBB pages), about 2 credits a run, ~26 a week. Without a key, the page shows nflverse's lines.
- Model:
  - Plays = pass attempts + sacks + rushes. Yards = passing yards − sack yards + rushing yards.
  - Offense and defense yards per play are adjusted for every opponent at once (least squares, SRS-style): `off − avg = O − mean(opponents' D)`, `avg − def = D − mean(opponents' O)`.
  - Points per game vs. an average opponent = 23.0 + 6.01 × rating (2025 fit). Home field 1.5 points; 0 at neutral sites and shared stadiums (Rams–Chargers, Giants–Jets).
  - Picks: spread edge of 3+ points, total edge of 4+, logged on the morning of the game from live lines.
  - Quarterback flag: if a team's listed starter started under 60% of the games behind its rating (or it has fewer than 3 games), the game is flagged and its edges are never logged.
- `data/openers.json`: first line seen per game. `data/closers.json`: last line seen before kickoff. `data/picks.json`: logged picks, closing line value and results.
- Backtest: every week from Week 4 is re-graded with ratings built only from earlier games, against nflverse's closing lines.
- `analysis/latest.md`: the write-up shown on the Analysis tab.

Settings live at the top of `generate_nfl.py` (`SETTINGS`).
