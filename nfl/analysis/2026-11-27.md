# Week 12 — Black Friday, Nov 27

**No play today.** Broncos–Steelers is QB-flagged: Mason Rudolph starts for the benched Aaron Rodgers. Even without the flag, the model has no edge (0.6 on the spread, 0.8 on the total). Nothing was logged.

Data: the 8 AM run hadn't fired by 11:15 AM ET (the last NFL data was the 12:53 AM ET "late" run), so I started a picks run at 11:16 AM ET. It finished at 11:16. Lines OK (26 events, 8 books on today's game). Written about 11:30 AM ET, before inactives.

---

## Results since last night's write-up

| Pick | Market | Result | CLV* |
|---|---|---|---|
| Chiefs +2.5 | flat (against by kickoff) | L (10-13) | −0.5 |
| Over 46 KC–BUF | against | L (23) | +0.5 |

*Against nflverse's close (BUF −3, 46.5). The page shows 0.0 on the total because its last pre-game snapshot was 5:13 PM (46).

Both were passes, and both lost. The weather call on the total was right: 23 points in rain and wind. The spread lost by exactly 3. At the +3 I listed as the only number worth taking, it would have pushed. At the logged +2.5 it's a loss.

Eagles 39, Cowboys 38. That game was QB-flagged and not logged (the model was on PHI +8.5; it would have won).

## Running record (logged picks)

| | W-L | CLV (nflverse close) |
|---|---|---|
| Spreads | 7-4 | −0.09 |
| Totals | 4-2 | 0.00 |
| Agrees | 1-1 (0-1 spreads, 1-0 totals) | — |
| Against | 4-2 (2-1 spreads, 2-1 totals) | — |
| Flat | 6-3 (5-2 spreads, 1-1 totals) | — |

The page shows −0.14 for spreads and +0.08 for totals; it uses its own snapshots where it has them. Seventeen picks, CLV about zero. Thursday went 0-3, and the one endorsed play lost. Still no evidence of an edge either way.

## Backtest (Weeks 4–12, closing lines)

| | ATS | O/U |
|---|---|---|
| All edges | 34-32-3 (52%) | 29-23 (56%) |
| Clean (no QB flag) | 22-18-3 (55%) | 21-17 (55%) |
| QB-flagged | 12-14 (46%) | 8-6 |

Thursday added a clean ATS loss (DET), a clean push (KC at the closing 3), a flagged ATS win (PHI) and a clean O/U loss (KC–BUF over).

---

## Broncos at Steelers, 3:00 PM ET (Acrisure Stadium, outdoors)

| | Model | Market (page open) | Edge | Move |
|---|---|---|---|---|
| Spread | DEN −3.9 | DEN −4.5 (−2.5) | 0.6 toward PIT | 2 toward DEN |
| Total | 37.8 | 37 (38) | 0.8 over | 1 down |

**QB-flagged, never a play. Also no edge.** Best numbers if you're curious: PIT +5 (−110, BetMGM), DEN −4.5 (−106, Pinnacle), under 37.5 (−120, ESPN BET).

**The 2-point move is the QB news.** The Steelers announced late Tuesday that Rodgers will be inactive and Rudolph will start ([NFL.com](https://www.nfl.com/news/aaron-rodgers-will-be-inactive-for-steelers-friday-vs-broncos-mason-rudolph-to-start)). ESPN reports it was a coaches' decision, not an injury ([ESPN, Nov 24](https://www.espn.com/nfl/story/_/id/50589757/steelers-bench-struggling-qb-aaron-rodgers-start-mason-rudolph)). The page's opener was seen Monday night, before the news. Rudolph has thrown four passes this season. The model's Pittsburgh rating is built entirely on Rodgers' 10 starts, so it can't tell us how Pittsburgh plays with Rudolph. The flag exists for exactly this case.

**Weather:** 93% chance of rain, 41°F at kickoff, sustained wind 15 mph with gusts to about 35 (MySportsWeather via [The Big Lead/Yahoo, this morning](https://sports.yahoo.com/nfl/articles/broncos-vs-steelers-weather-forecast-134710647.html)). Sean Payton: "this is a weather game" ([Denver Sports](https://denversports.com/nfl/denver-broncos/sean-payton-on-black-friday-in-pittsburgh-this-is-a-weather-game)). The total has already dropped to 37. That's the same pattern as Thursday night, but here the model doesn't disagree with the market.

**Injuries.** I couldn't find a final injury report for either team; the steelers.com result was from 2018. What I did find:

- Broncos: RB J.K. Dobbins is suspended one game for conduct detrimental to the team ([Denver Sports](https://denversports.com/nfl/denver-broncos/sean-payton-on-black-friday-in-pittsburgh-this-is-a-weather-game)). A related headline there says DL Sai'vion Jones won't play; I didn't read that article. Bo Nix is starting.
- Steelers: the AP preview on [CBS](https://www.cbssports.com/nfl/gametracker/preview/NFL_20261127_DEN@PIT/) has Spencer Anderson replacing the injured Mason McCormick at left guard, and WR Michael Pittman Jr. possibly coming off IR. I only got a partial read of that page, so treat both as unconfirmed.

---

## Data notes

- **The 8 AM run missed again** (fourth straight game day). Thursday's 7 PM "late" run fired at 12:53 AM ET, after the game, so Chiefs–Bills "closed" on the page at the 5:13 PM line.
- **The KC +2.5 / +3 gap matters.** The pick is logged at the morning line (+2.5), not at the best available number. That's why it shows as a loss instead of a push.
- **Totals still have no market tag** in `picks.json`. The bucket splits above are tagged by hand.
- The model's numbers for Thursday's games have moved since they were logged (KC–BUF is now 51.0 instead of 55.2) because the ratings were refit with Thursday's results. Logged picks keep the morning numbers.
