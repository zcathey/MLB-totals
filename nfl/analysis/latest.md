# Week 12 — Thanksgiving night, Thursday, Nov 26

**No play tonight.** Chiefs +2.5 was logged this morning (flat) and the Chiefs–Bills over 46 was logged (market against). Since then both have moved further away from the model: Bills −3, total 45.5–46. I'm not endorsing either. This morning's Lions +1.5 lost.

Data: this is an evening update of this morning's write-up. A scheduled picks run fired at 5:13 PM ET (it looks like the 8 AM run, nine hours late), so the data was 4 minutes old and I didn't start a run. Lines OK (26 events, 8 books on tonight's game). Written about 5:30 PM ET, before inactives (about 6:50 PM).

---

## Results since this morning

| Pick | Market | Result | CLV* |
|---|---|---|---|
| Lions +1 (endorsed at +1.5) | agrees | L (39-35 CHI) | −0.5 (0 at +1.5) |

*Against nflverse's close (DET +1.5). The page shows 0.0 because its last snapshot was my 9:36 AM run. The market drifted back toward Chicago by kickoff, so the "agrees" move didn't hold to the close. The first endorsed spread this season lost by 4, and it didn't beat the close.

Eagles–Cowboys is in progress. It was QB-flagged and nothing was logged.

## Running record (logged picks)

| | W-L | CLV (nflverse close) |
|---|---|---|
| Spreads | 7-3 | −0.05 |
| Totals | 4-1 | −0.10 |
| Agrees | 1-1 (0-1 spreads, 1-0 totals) | — |
| Against | 4-1 (2-1 spreads, 2-0 totals) | — |
| Flat | 6-2 (5-1 spreads, 1-1 totals) | — |

The page shows −0.10 for spreads and +0.10 for totals. It uses its own snapshots where it has them. Fifteen picks with CLV about zero is still no signal, whatever the 11-4 record says. The rule's one endorsed spread lost.

## Backtest (Weeks 4–12, closing lines)

| | ATS | O/U |
|---|---|---|
| All edges | 33-32-2 (51%) | 29-22 (57%) |
| Clean (no QB flag) | 22-18-2 (55%) | 21-16 (57%) |
| QB-flagged | 11-14 (44%) | 8-6 |

Lions–Bears added one clean ATS loss.

---

## Chiefs at Bills, 8:20 PM ET (Highmark Stadium, outdoors)

| | Model | Market (page open) | Edge | Move |
|---|---|---|---|---|
| Spread | KC −0.6 | BUF −3 (−2.5) | 3.6 toward KC | 0.5 toward BUF (against) |
| Total | 55.2 | 46 (48.5) | 9.2 over | 2.5 down (against) |

**Spread: pass.** It was logged at +2.5 as flat. It has since ticked to 3 (Pinnacle BUF −3 +101), away from the model, and the page now tags it "against." A half point onto 3 is a small move, but it's in the wrong direction. If you take it anyway, the number is **KC +3 (−110) at ESPN BET**. Don't take +2.5.

**Total: pass.** Every forecast I found calls for steady rain and strong gusts:

- NWS (via [Heavy/Yahoo, 4:25 PM ET](https://sports.yahoo.com/nfl/articles/chiefs-bills-game-faces-extreme-212540963.html)): 100% chance of rain, about 0.5–0.75 inch. Gusts of 34 mph at 8 PM, easing to 29 by 10 PM. Upper 30s, feels like the low-to-mid 20s. Lightning looks "highly unlikely," so a delay isn't expected.
- AccuWeather (via [Democrat and Chronicle/Yahoo, this morning](https://sports.yahoo.com/nfl/articles/bills-chiefs-game-day-weather-094436796.html)): 90% rain chance, ENE wind 18 mph with gusts to 37, around 35–40°F.

The model doesn't know about weather. That's the same blind spot as the Saints–Bears over that lost last Sunday. Heavy says the total opened at 50.5 before the forecast came in. Best over is 45.5 (−113, DraftKings), but the framework passes when the market is against.

**Injuries** (final reports, Nov 25; no game-day changes found):

- Chiefs **out**: RB Kenneth Walker III (groin), RT Jaylon Moore, DT Omarr Norman-Lott. Questionable: TE Noah Gray, DT Peter Woods ([Syracuse.com via Yahoo](https://sports.yahoo.com/nfl/articles/bills-thanksgiving-injury-report-5-190026800.html), [Heavy](https://heavy.com/sports/nfl/kansas-city-chiefs/chiefs-bills-final-injury-report-thanksgiving/)).
- Bills questionable: CB Christian Benford (groin), TE Dalton Kincaid (thumb/ankle), DL T.J. Sanders (shoulder), RG O'Cyrus Torrence (ankle), LB Dorian Williams (calf, game-time decision). RT Spencer Brown, OLB Greg Rousseau, DL Ed Oliver and C Connor McGovern have no designation ([Buffalo Wdown](https://buffalowdown.com/bills-vs-chiefs-final-week-12-injury-report-buffalo-in-a-solid-spot-01m85r6qq95x)). Torrence played through the ankle last week and hasn't missed a start in 61 games. Corbett is next up if he sits.
- Mahomes and Allen: no designation.

Inactives weren't out when I wrote this. Check Torrence and Benford around 6:50 PM.

---

## Data notes

- **The 8 AM run missed again** (third straight game day). A scheduled run finally fired at 5:13 PM ET, too late for the afternoon games. The 7:00 PM "late" run is the only snapshot left before kickoff.
- **The two afternoon games "closed" at the 9:36 AM line** on the page (DET +1, DAL −8.5). nflverse has Lions–Bears closing at DET +1.5.
- **Totals still have no market tag** in `picks.json`. The bucket splits above are tagged by hand.
- I couldn't load Action Network's odds page, so I don't have bet or money percentages.
