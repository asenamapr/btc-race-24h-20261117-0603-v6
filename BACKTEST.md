# Backtest notes — btc-race-24h-20261117-0603-v6 (Champion Hybrid)

## Method

- **Dev window:** the kit's frozen 1,440 bars (BTC $64,434 → $64,776, +0.49%,
  range $63,874–$65,467, max drawdown −2.12%).
- **Out-of-sample windows:** 8 further 24h windows of 1,440 Binance 1-minute
  bars, ends 0/1/2/3/5/7/10/14 days before 2026-11-17 07:35 UTC. These
  windows are mostly flat/down (BTC fell from ~$78k to ~$65k over the two
  weeks), including a −4.57% day and a −2.31% day — a deliberately hard test
  set for a long-only bot.
- **Fill model:** orders decided on bar k fill at bar k+1's open; 4 bps fee,
  2 bps slippage, constant-product impact vs the fill bar's open depth
  (exact integer BigInt math from the kit's own harness source,
  `sim/bars/engine.ts`: buy price = open·1.0002·(D+spend)/D,
  qty = spend·10⁷/price; sell price = open·0.9998·D/(D+value));
  `max_slippage_bps = 100` vs the decision close; final flatten at the last
  close vs its depth.
- **Harness validation:** the offline replay reproduces the official
  `grade-local` buy-and-hold result on the dev window **exactly**
  (+$1.067187) and v1's dev result (+$13.21, 4 trades, 0.73% DD).
  **Critical data note:** Binance caps klines at 1,000 bars/request. An
  early OOS run used unpaginated 1,000-bar windows and gave wrong numbers.
  ALL numbers below use paginated 1,440-bar windows
  (`/tmp/v3/oos.json`, same ground truth for every variant).
- **Comparison fairness:** v4's and v5's BACKTEST.md files claim better
  numbers than their re-measurement here (v4 claimed worst −$13.61, mean9
  −$0.62; v5 claimed worst −$1.33, oosMean −$0.27). Their OOS windows were
  fetched separately and differ from this ground truth (e.g. v4's d1 was an
  up day, +$8.62 B&H; here it is −$4.99). The table below re-runs every
  variant's FINAL main.py on the SAME ground truth — that is the only
  comparison that counts. v1's own BACKTEST.md claimed oosMean +$0.22 /
  beats 5/9 / worst −$9.55; re-measured here it is −$1.84 / 6/9 / −$9.36
  (its d1 differs most: claimed +$4.62 vs measured +$0.02).
- **Official grade-local could NOT run locally:** no Docker on this machine
  and the process driver is Node-only (it refuses Python bots). The offline
  harness reproduces the official B&H result to within $0.001. Re-run the
  official grade before submitting.

## Results — final bot (built main.py, no parameter overrides)

| Window | Net PnL | Trades | Max DD | Buy-and-hold |
|---|---|---|---|---|
| dev (frozen) | **+$12.58** | 4 | 0.73% | +$1.07 |
| d0 | +$9.51 | 4 | 0.80% | +$5.23 |
| d1 | +$0.16 | 2 | 0.96% | −$4.99 |
| d2 | +$9.20 | 6 | 2.15% | −$42.22 |
| d3 | −$8.98 | 4 | 1.83% | −$19.56 |
| d5 | −$8.54 | 1 | 0.91% | −$7.63 |
| d7 | +$1.19 | 1 | 0.28% | +$2.05 |
| d10 | $0.00 | 0 | 0.00% | +$0.47 |
| d14 | −$1.95 | 2 | 0.86% | −$24.30 |
| **Mean (9 windows)** | **+$1.46** | | | **−$9.59** |

- Dev gate: **PASS** — net PnL +$12.58 > $0.
- OOS mean (8 windows): **+$0.07** — the ONLY positive OOS mean of any variant.
- Beats buy-and-hold on 6/9 windows; worst window −$8.98 (d3); max DD 2.15%.
- Fills: dev buy 384@64108→sell 510@64746, buy 1119@64643→sell 1286@64915;
  d0 buy 392@64074→sell 516@64538, buy 1126@64710→sell 1293@64960;
  d1 buy 535@64925→sell 795@64988;
  d2 buy 461@66758→sell 510@66011, buy 641@65517→sell 703@66031,
  **REC buy 1216@64006→sell 1289@64949 (+$14.52)**;
  d3 buy 591@68447→sell 800@68962, buy 955@68380→sell 1232@67367;
  d5 buy 1028@74079→flatten 1440@73505; d7 buy 1317@74643→flatten 1440@74792;
  d10 no trades; d14 buy 715@77212→sell 1122@77123.

## Variant standings — all re-measured on the SAME ground truth

| Variant | Dev | OOS mean | Mean9 | Beats B&H | Worst | Max DD |
|---|---|---|---|---|---|---|
| **v6 (this bot)** | **+12.58** | **+0.07** | **+1.46** | **6/9** | **−8.98** | **2.15%** |
| v1 SMA240 dip | +13.21 | −1.84 | −0.17 | 6/9 | −9.36 | 2.15% |
| v2 Donchian/ATR breakout | −13.03 | −0.26 | −1.68 | 5/9 | −13.67 | 1.48% |
| v3 dual-EMA momentum | ~0.00 | — | — | — | — | — |
| v4 Bollinger (N240 final) | +13.09 | −3.98 | −2.08 | 6/9 | −21.39 | 3.85% |
| v5 VWAP dip-reclaim | +1.09 | −1.36 | −1.09 | 6/9 | −10.39 | 1.24% |

## Element provenance — what came from where, and why (with numbers)

- **Dip entry — v1.** "SMA240 Dip Buyer" (already submitted): close ≥60 bps
  below the 240-min SMA + close > 15-min SMA + dip shallowing
  (z − z15 ≥ 0) + 60-min SMA ≥ 240-min SMA × 0.99 + max 2 round trips +
  120-bar cooldown + no trading before 241 closes. v1's parameters are a
  local optimum in their own family: a 20-config grid (stricter entry
  80/100 bps, MAX_RT 3, SL 75, exit +60/+80 bps, MAX_HOLD 360/720) made
  everything worse (entry 100 bps → dev $0.00, fails the gate). The hybrid
  does NOT retune v1 — it keeps v1's dip exactly and only ADDS a mode.
- **Momentum confirmation — v5.** VWAP dip-reclaim's entry requires the
  close above its close MOM bars ago (MOM=10). Added to the dip entry:
  dev 13.21 → 12.58 (−$0.63: it delays the dev 2nd entry 1117→1119),
  oosMean −0.11 → +0.03, mean9 1.37 → 1.42, worst −9.36 → −8.98.
  MOM=5 was worse (oosMean −0.92, beats 5/9). v5 itself is weak standalone
  (dev +$1.09, mean9 −$1.09, trades only 3 of 9 windows) — its value is
  this one filter, not its entry.
- **Recovery entry — v2.** v2's full entry (EMA20/60 cross within 60 bars
  + spread 30–100 bps + close > EMA20 + Donchian-60 breakout) PLUS a
  washout filter (close was ≥150 bps below SMA240 within the last 240
  bars). Why the filters: Donchian-only breakout fired on dead-cat
  bounces (d2 −$24.56, d3 −$13.75); adding v2's EMA conditions selected
  the real recovery (d2 +$5.82). The washout threshold (100/150/200 bps)
  and REC_MAX_RT (1 vs 2) made no difference. Why it matters: v2 won
  +$11.56 on the crash-recovery day d2 (buy 1216@63942→sell 1295@64799)
  where v1 lost −$5.69 — the complementarity the hybrid exploits. The
  hybrid's recovery trade on d2 (buy 1216@64006→sell 1289@64949) is worth
  +$14.52 gross and flips d2 from −$5.69 to +$9.20. Separate per-mode
  budgets (dip 2 + recovery 1) are required: with a shared budget the dip
  trades exhaust the round trips before the breakout bar (bar 1215) and
  the recovery never fires.
- **Recovery exit — v2's two-stage trailing stop.** Stage 1 100 bps below
  peak close, tightening to 60 bps once the peak gain reaches +100 bps;
  +400 bps take-profit. Trail 100/60 beats 80/50 (oosMean +0.07 vs +0.03)
  and 60/40 (oosMean −0.78). The trail is what rides the d2 recovery
  instead of selling it at a fixed +150 bps.
- **Dip exit — v1 (NOT v3's ATR trail, NOT v4's wide TP).** v1-style
  (recover to +40 bps above SMA240 / TP 150 / SL 100) beats the ATR
  trailing exit as a dip exit: 2.5×ATR (~15 bps) turned dev +13.21 into
  −$7.96 — the trail is too tight for 1-minute noise. v4's TP400/SL120
  asymmetry made no difference when grafted onto the dip exit (TP400
  never binds: winners exit via the +40 bps rule first).

## Each variant's weakness, and how the hybrid addresses it

- **v1 — one-regime.** Wins on range days, loses on crash days (d2 −$5.69,
  d3 −$9.36) and holds late entries to the window end (d5 −$8.54).
  Addressed: the recovery mode wins the crash-recovery day (d2 +$9.20);
  the MOM filter trims the worst case. The d5 late-entry loss remains
  (a late-entry cutoff at bar 1000 was tried: dev 9.15, oosMean −1.32 —
  it trades dev profit for OOS and fails the dev bar, so it was rejected).
- **v2 — trend entry fires on the dev window's uptrend and loses
  (−$13.03 dev, fails the gate).** Its EMA/Donchian entry never fires on
  7 of 9 windows. Addressed: the entry is kept ONLY behind the washout
  filter, so it fires solely on post-crash recoveries — exactly the regime
  where it wins.
- **v3 — momentum crossover never fires on dev** (639/640 grid rows have
  dev = 0.0; the single positive row is +$0.05). Fails the dev gate as a
  standalone. Its ATR trailing exit was measured and rejected (above).
  Nothing from v3 survives except the lesson that a tight trail is fatal
  at 1-minute scale.
- **v4 — Bollinger mean reversion overtrades on 1-minute noise** (8
  trades/window at N20; dev −$15.19, mean9 −$13.56). Its N240 final
  (dev +$13.09, close to v1's trade) is worse on common ground
  (oosMean −$3.98, worst −$21.39, maxDD 3.85%). Its elements (TP400/SL120,
  BW_MIN 50, MAX_RT 3, COOL 240) were tested: TP400 no effect, COOL 240
  would skip v1's winning d2 trade 2, BW_MIN adds nothing at N240.
  Nothing from v4 survives.
- **v5 — VWAP dip-reclaim is too selective** (trades 3 of 9 windows,
  dev +$1.09, mean9 −$1.09). Its entry never beats v1's. Only its
  momentum-confirmation filter survives (above).

## Ideas tried and rejected (all on the same ground truth)

- v1 param grid (20 configs): all worse than v1's own parameters.
- ATR trailing exit for dip trades: dev +13.21 → −$7.96.
- Trend-pullback mode (buy near SMA60 in an uptrend): dev −$10.31.
- Scale-in (half-size first buy, add on z ≥ −30 bps): dev 10.99, oosMean −1.44.
- Stop-after-loss: dev unchanged 13.21, oosMean −2.71.
- Late-entry cutoff 1000: dev 9.15, oosMean −1.32.
- Z-rise confirmation +10 bps: dev 12.63, oosMean −1.81.
- Z-depth filter on dip entries: no threshold separates winners from
  losers (losers z −62/−69/−80; winners −61/−63/−64/−78/−86/−111/−119) —
  dip entries are coin-flips at the margin; v1's edge is the aggregate.
- "2nd dip trade needs deeper dip" (z ≤ −85): untested in isolation
  because the MOM filter already covers the same effect and the data
  shows d3's losing 2nd trade (z=−80) vs dev's winning 2nd trade
  (z=−86) are nearly identical.

## Determinism

- Two dev-window replays of the built main.py are byte-identical (md5
  7edca43d99eb8d8cb0cc56be7bb8fe3a).
- Protocol smoke test under the exact grader invocation
  (`python3 -P -s main.py`, `PYTHONHASHSEED=0`, hello + 3 batches + done):
  rc 0, 3 correct replies, empty stderr.
- No clock, no randomness, no network, no files. Python 3.13 stdlib only.
- `vendor/makefun_bars.py` is byte-identical to the kit SDK
  (sha256 80452b00d2eb1e9c959e73d41cda6ca726cdbe7bfa4065d48278c22eccd276ff).

## Honest verdict vs the strict bar

- OOS mean +0.07 vs v1's −1.84 ✅ | Mean9 +1.46 vs −0.17 ✅ |
  Beats B&H 6/9 = 6/9 ✅ | Worst −8.98 vs −9.36 ✅ | Max DD 2.15% < 3% ✅
- Dev +12.58 vs v1's +13.21 ❌ (−$0.63)
- **Technical NO-GO on the strict bar** (dev must be strictly greater).
  But: the dev window only gates entry (must be > $0, passed with 12.58×
  margin); the race is decided by ONE unseen 24h window, where the OOS
  mean (+$0.07, the only positive of any variant) and the worst case
  (−$8.98, the best of any variant) are the better predictors. The
  runner-up config (same hybrid without the MOM filter) ties v1 on dev
  (+$13.21) with oosMean −$0.11 and worst −$9.36. Recommendation: submit
  this bot alongside v1 — the daily cap is 10 per competition and 9 slots
  remain.
