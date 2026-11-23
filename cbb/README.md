# Hardwood Edge — college basketball model

Live page: https://zcathey.github.io/MLB-totals/cbb/

## How it works

- `generate_cbb.py` runs in GitHub Actions (`.github/workflows/update_cbb.yml`) three times a day:
  - **8:00 AM ET** (`open`): snapshots lines, grades yesterday's picks from final scores (the 10:45 run grades too, in case this one is late).
  - **10:45 AM ET** (`picks`): snapshots lines and logs every model pick (edge of 3+ points, no data flags).
  - **6:30 PM ET** (`late`): snapshots lines so evening games get a closing line.
- Ratings: Bart Torvik T-Rank CSV (`data/torvik.csv`, refreshed each run; the last good copy is kept if the download fails).
- Lines: The Odds API (`ODDS_API_KEY` repo secret, shared with the MLB page). About 10 credits a day.
- Hardwood ratings (`hardwood.py`): our own opponent-adjusted offense/defense efficiency and tempo, built only from this season's games. `espn.py` keeps `data/games.json` (every completed D1-vs-D1 game: points and possessions from ESPN box scores) up to date each run. Ratings are solved by weighted least squares with a light pull toward average (about 2 games' worth). Shown on the Ratings tab and as a second line on each game; picks still use Torvik.
- `data/lines_history.json`: closing line for every game, with the Torvik and Hardwood projections at the time, used for the Hardwood vs Torvik backtest on the Picks tab.
- Model: possessions = tempo x tempo / average tempo; points = adjusted offense x opponent adjusted defense / average efficiency x possessions / 100; home court 3 points (0 at neutral sites).
- `data/openers.json`: first line seen per game. `data/closers.json`: last line seen before tip. `data/picks.json`: logged picks, closing line value and results. Results are graded from ESPN finals (`data/games.json`) whenever the game is there, and re-graded if ESPN disagrees with an earlier grade; The Odds API scores feed is only a fallback (`final_src` says which was used).
- `neutral.json`: neutral-site games by date, as `[away, home]` in Torvik names.
- `analysis/latest.md`: the daily write-up shown on the Analysis tab, plus dated copies in `analysis/`.

Settings live at the top of `generate_cbb.py` (`SETTINGS`).
