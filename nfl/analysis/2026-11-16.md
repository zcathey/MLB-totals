# Week 10 — Monday, Nov 16

**No play tonight.** Chargers at Ravens is QB-flagged (Baltimore is on a new starter), and neither edge clears the threshold anyway.

Data: the 8 AM run never fired today, so I started a picks run at 5:18 PM ET; it finished at 5:18. Lines OK (14 events, 8 books on tonight's game).

---

## Sunday's results

All eight logged picks from Sunday went 7-1. The only lean, Chiefs–Falcons over 47.5, won 35-13.

| Pick | Market | Result | CLV* |
|---|---|---|---|
| Miami +4.5 | against | W (22-24) | 0 |
| Carolina +1 | flat | W (20-17) | +0.5 |
| Jets +8.5 | against | L (31-12) | 0 |
| 49ers −4 | flat | W (46-40) | +0.5 |
| Over 47.5 KC–ATL | agrees | W (48) | 0 |
| Over 38 MIA–IND | against | W (46) | +0.5 |
| Under 51 BUF–NYJ | flat | W (43) | −0.5 |
| Over 45 JAX–TEN | against | W (63) | −0.5 |

*The page shows 0.0 CLV on every pick, but that's mostly not real: no line snapshot ran between the 9:32 AM picks run and the 1:00 PM kickoffs (the 11:30 AM "late" run fired at 2:19 PM), so the 1:00 games' "closing" line is the line at logging. The CLV column above uses nflverse's closing lines instead. By that measure, spreads averaged +0.25 and totals −0.13. Basically zero, which is what you'd expect from picks logged at 9:30 AM on game day.

Three of the four spreads I passed on won. Two wins came on market-against picks (Miami) and flat lines (Carolina, San Francisco), which the framework doesn't endorse. One Sunday doesn't change that rule; it's 8 picks.

## Running record (logged picks)

| | W-L | CLV |
|---|---|---|
| Spreads | 3-1 | +0.25 (nflverse close) |
| Totals | 4-0 | −0.13 (nflverse close) |
| Agrees | 1-0 (total only) | — |
| Against | 3-1 (1-1 spreads, 2-0 totals) | — |
| Flat | 3-0 (2-0 spreads, 1-0 total) | — |

The page's "agrees" bucket shows 0-0 because totals aren't tagged with a market direction in `picks.json`, and the page has no "flat" bucket at all. The split above uses the tags from Sunday's write-up.

## Backtest (Weeks 4–10, closing lines)

| | ATS | O/U |
|---|---|---|
| All edges | 28-27-2 (51%) | 28-20 (58%) |
| Clean (no QB flag) | 19-16-2 (54%) | 21-14 (60%) |
| QB-flagged | 9-11 (45%) | — |

Same pattern as last week: clean edges are modestly ahead, and flagged ones are below 50%.

---

## Tonight: Chargers at Ravens, 8:15 PM ET (outdoors)

| | Model | Market (open) | Edge | Move |
|---|---|---|---|---|
| Spread | BAL −3.1 | BAL −4.5 (−5) | 1.4 toward LAC | 0.5 toward model |
| Total | 42.7 | 39 (38.5) | 3.7 over | 0.5 toward model |

Best numbers: Chargers +4.5 (−106) and Ravens −4.5 (−104), both at Pinnacle. Over 39 (−108) at BetRivers; under 39.5 (−110) at BetOnline.

**Why it's a pass:**

- **QB flag.** Lamar Jackson is out 6–10 weeks with a thumb injury ([Ravens.com](https://www.baltimoreravens.com/news/injury-report-ravens-chargers-jaylinn-hawkins-2026)). The data lists Tyler Huntley as the starter, but the Ravens say Jacoby Brissett makes his first Baltimore start ([Ravens.com preview](https://www.baltimoreravens.com/news/game-preview-jacoby-brissett-ravens-first-start-week-10-against-chargers-monday-night-football), [BoltBeat](https://boltbeat.com/chargers-could-get-reinforcements-back-from-ir-in-final-week-10-injury-report)). Either way, Baltimore's rating is built mostly on Jackson's games.
- **Edges are small.** The spread edge is 1.4 (threshold 3) and the total edge is 3.7 (threshold 4). The half-point moves are noise.

**Injuries (Friday/Saturday reports; I couldn't find an official inactives list):**

- Chargers: WR Ladd McConkey (back) **out** and didn't travel; WR Brenen Thompson doubtful; TE David Njoku (fibula, on IR) questionable; G Kayode Awosika and G/T Trey Pipkins questionable; OL Branson Taylor, S Kendall Williamson and CB Isas Waxter out. Edge rushers Khalil Mack and Bud Dupree are off the report ([Chargers.com](https://www.chargers.com/news/chargers-vs-ravens-injury-report-ladd-mcconkey-daiyan-henley-2026), [BoltBeat](https://boltbeat.com/chargers-could-get-reinforcements-back-from-ir-in-final-week-10-injury-report)).
- Ravens: S Jaylinn Hawkins (knee) **out**; RB Adam Randall questionable. Stanley and Campbell sat Saturday for rest with no game designation ([Ravens.com](https://www.baltimoreravens.com/news/injury-report-ravens-chargers-jaylinn-hawkins-2026)). I couldn't find a 2026 status for Roquan Smith.

**Weather:** the National Weather Service forecast (issued Sunday afternoon) has Monday night mostly clear, low around 36, northwest wind around 6 mph ([NWS](https://forecast.weather.gov/MapClick.php?lat=39.28&lon=-76.58)). That's not a factor for the total. I couldn't find a kickoff-hour reading.

---

## Data notes

- **Skipped 8 AM run:** GitHub didn't run the scheduled picks job today. The last data before my manual run was from 10:11 PM Sunday.
- **Late-run timing:** Sunday's 11:30 AM line snapshot ran almost 3 hours late, after the 1:00 PM kickoffs. That's why CLV shows 0.0 for every 1:00 game. The Sunday Night closer was taken at 6:31 PM, about 2 hours before kickoff.
- **Stale QB:** nflverse still lists Huntley for Baltimore; the team says Brissett starts.
- **Record buckets:** totals have no `market` tag, so "agrees/against" undercount and there's no "flat" bucket.
