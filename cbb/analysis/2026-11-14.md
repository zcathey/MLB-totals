# CBB — Saturday, Nov 14, 2026

**Card (paper trades): Stonehill +39.5 · Coppin St. +26 · Delaware St. +16 · Northwestern St. +10.5 (weakest)**

All picks are paper trades until about mid-December, when Torvik's preseason priors wash out. Every play today is a big underdog against a power-conference or mid-major home team.

Data: picks run started manually at 11:44 AM ET (the 8:00 and 10:45 scheduled runs never fired). Lines OK (408 Odds API credits left). Ratings from Nov 13, 8:08 AM ET (about 28 hours old).

---

## Yesterday (Nov 13)

| Bucket | W-L-P | Avg CLV | Beat close |
|---|---|---|---|
| Flat | 11-3-0 | +1.75 | 11/14 |
| Against | 3-5-1 | −0.30 | 0/9 |
| Agrees | none | — | — |
| **All** | **14-8-1** | **+0.95** | **11/23** |

The flat big-dog picks did well against the close, not just on results: Northern Arizona +4.0, Arizona +4.0, Central Arkansas +3.5, Milwaukee +3.2. The market-against picks didn't beat a single close, which is why they're passes.

### Season to date

| Bucket | W-L-P | Avg CLV | Beat close |
|---|---|---|---|
| Agrees | 4-3-0 | −0.47 | 29% |
| Against | 26-30-1 | +0.06 | 30% |
| Flat | 28-17-1 | +0.37 | 44% |
| **All** | **58-50-2** | **+0.15** | **36%** |

One honest caveat: the "agrees" bucket has the worst CLV so far. That's only 7 graded picks, but it's no proof yet that market confirmation adds value. The flat bucket is carrying the model.

---

## Today's card

| Play | Best price | Tip (ET) | Edge | Move |
|---|---|---|---|---|
| Stonehill +39.5 @ Texas Tech | BetRivers −112 | 2:00 | 8.6 | 40.25 → 39 |
| Coppin St. +26 @ South Florida | Pinnacle −115 | 2:00 | 3.5 | 27.5 → 26 |
| Delaware St. +16 @ East Carolina | Bovada −110 | 4:00 | 5.2 | 16.5 → 16 |
| Northwestern St. +10.5 @ Little Rock | ESPN BET −110 | 8:00 | 4.1 | 9.75 → 9.5 |

**Stonehill +39.5.** The model has Texas Tech −30.4, and the market is at −39. The line has come down 1.25 from the open. Texas Tech (3-0) is still without JT Toppin (ACL, [Covers](https://www.covers.com/sport/basketball/ncaab/injuries)). Dra Gibbs-Lawhorn was helped off with a lower-body injury in the Illinois win on Nov 10 ([ESPN](https://www.espn.com/mens-college-basketball/recap/_/gameId/401913527)), and his status today isn't listed anywhere I found. If he sits, that helps the dog. Jamichael Stillwell just became eligible, which helps Tech. It's a home game in Lubbock. A 40-point spread is noisy, and the 9-point gap is partly the model's priors being too generous to low-major teams.

**Coppin St. +26.** The model has USF −22.5. The market opened at 27.5 and has come down. It's a home game at the Yuengling Center ([USF](https://gousfbulls.com/news/2026/11/14/mens-basketball-usf-basketball-returns-to-yuengling-center-saturday-to-face-coppin-state)). USF lists J. Lewis as questionable (knee) and A. Dancler as out for the season ([Covers](https://www.covers.com/sport/basketball/ncaab/injuries)). Coppin lists no injuries. Note: USF beat Coppin 100-50 last November, but this is a new USF team under first-year coach Chris Mack. This is the thinnest edge on the card, and the best number costs −115.

**Delaware St. +16.** The model has ECU −10.8. The line moved only half a point, toward the dog. It's a home game in Greenville ([ECU](https://ecupirates.com/news/2026/11/13/mens-basketball-pirates-set-to-host-delaware-state-on-saturday)). Neither team lists injuries. Delaware St. lost by 5 at Georgetown on Nov 10, which fits the model's view that they're not a 16-point dog to a 176th-ranked team.

**Northwestern St. +10.5 (weakest).** The model has Little Rock −5.4. Confirmation is minimal: only a 0.25-point move. Northwestern St. "has yet to play with a full roster" and was missing three rotation players last game ([BVM Sports](https://bvmsports.com/2026/11/13/northwestern-state-demons-head-to-little-rock-for-saturday-game/)). Their ratings may overstate the roster that actually plays. Shop for the +10.5; at +9.5 I'd pass.

No neutral sites among these. All four are true home games.

---

## Logged but passing

**Market against (line moved away from the model):**

| Pick | Edge | Move |
|---|---|---|
| Colorado +12.5 @ Providence | 5.0 | −2.5 |
| Gardner-Webb +27.5 @ South Carolina | 5.0 | −2.0 |
| NJIT +12 @ Fairfield | 4.9 | −0.5 |
| St. Thomas −6 @ Army | 4.6 | −1.5 |
| Jackson St. +9 @ Winthrop | 4.3 | −1.5 |
| West Georgia +5 @ Charleston So. | 3.3 | −1.5 |
| UNC Asheville +17.5 @ Georgia Tech | 3.2 | −1.0 |
| Morehead St. +2.5 vs IU Indy | 3.4 | +0.5 |

**Bad data — ignore:** *South Carolina +9 @ Campbell* is really **USC Upstate** at Campbell. The name matcher mapped "South Carolina Upstate Spartans" to South Carolina, which produced a fake 16.5-point edge. This pick will pollute the "against" record, so delete it from picks.json.

**Logged earlier as flat (Nov 13 run), lines since moved:**

- Utah Valley +11.5: now 9.5. Two points of CLV banked; no edge left at the current number.
- Portland St. +10.5: now 9.5. Moved toward the model, so it agrees at the current number, but the edge is exactly at the 3.0 threshold, and the only +10.5 left is BetRivers −122. Don't chase.
- Montana +0.75: Montana is now −1.5. CLV banked; current edge 1.1.
- Northern Iowa +1 (edge 5.4), Southern Utah +18.5, Rider +35.5, Louisiana Monroe +31.5: lines haven't moved, still flat.
- Detroit Mercy +10, Dayton +6.5, Santa Clara +2: lines moved slightly against.

**Flagged, not logged:** Brown +11 @ Siena (edge 4.0) has a home tempo outlier (81), and the line moved 3 points against Brown. I found no news to explain the move. Siena's Y. Steger has been out for the season since October.

---

## Notes

- **Workflow:** The 8:00 AM and 10:45 AM scheduled runs never ran today. The last automatic run was at 10:27 PM ET last night. I started the picks run manually at 11:44 AM ET.
- **Alias fixes for `ALIASES` in generate_cbb.py:**
  - `'south carolina upstate': 'USC Upstate'`: this one is urgent. The longest-prefix matcher falls back to "South Carolina", so any "X Y Z" name whose first words match another team can mis-map silently. It may be worth logging a warning whenever a match uses fewer than all the words.
  - `'n colorado': 'Northern Colorado'`: currently unmatched.
- **South Dakota St. @ Northern Colorado:** recorded open was UNC −4, now +3.5, a 7.5-point flip. No projection because of the unmatched name. I found no news. It could be a bad opener snapshot.
- **Possible duplicate:** Idaho St. @ Seattle is logged twice: "+16" with a Sat 10 PM ET tip, and "+16.5" with a Sun 4 PM ET tip, under different event IDs. Only one game appears to exist ([schedule listing](https://www.sportbusy.com/games/ncaam/14463456-idaho-state-bengals-at-seattle-redhawks-2026-11-14/)). Check before grading.
- **Neutral sites:** LSU @ Gonzaga is at Spokane Arena (Bad Boy Mowers Spokane Series, [Gonzaga](https://gozags.com/news/2026/6/15/mens-basketball-gonzaga-and-lsu-to-meet-in-bad-boy-mowers-spokane-series-nov-14.aspx)). It's off campus but in Gonzaga's city with a home crowd, so I left it as a home game. There's no pick either way. No changes to neutral.json.
- **Totals (tracking only):** Two large gaps aren't explained by tempo flags: Utah Tech @ California (model 147.5 vs 159) and Longwood @ Old Dominion (147.4 vs 136.5). UTRGV @ UT Arlington (−13) is explained by a tempo outlier.
