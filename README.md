[![make.fun · btc-race-24h-20261117-0603](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![rank](https://make.fun/badge/btc-race-24h-20261117-0603/asenamapr/btc-race-24h-20261117-0603-v6/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![reward](https://make.fun/badge/btc-race-24h-20261117-0603/asenamapr/btc-race-24h-20261117-0603-v6/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)

# BTC Champion Hybrid Bot (v6) — make.fun `btc-race-24h-20261117-0603`

Entry for the [make.fun bounty](https://make.fun/bounty/btc-race-24h-20261117-0603): Race a BTC trading bot live for 24 hours.

A bot that trades cbBTC (CBBTC) against USDC on 1-minute bars with $1,000 of
paper money, for the make.fun competition "Race a BTC trading bot live for
24 hours". Python 3.13, standard library only.

This is the **champion hybrid (v6)**: it merges the best *measured* elements
of five sibling variants (v1–v5), each kept only because it improved a number
on the same dev + 8 out-of-sample windows. Full provenance and every rejected
idea are in BACKTEST.md.

## Strategy

1-minute BTC noise (~6 bps/min) is far below the ~30 bps round-trip cost
(4 bps fee + 2 bps slippage + constant-product impact), so 1-minute signals
lose. This bot trades **multi-hour mean reversion plus one crash-recovery
mode**:

- **DIP mode (from v1):** close ≥ 60 bps **below** the 240-min SMA, **and**
  close above the 15-min SMA (short-term bounce), **and** the dip is
  shallowing (today's z-score above the z-score 15 bars ago), **and** the
  60-min SMA sits no more than 100 bps below the 240-min SMA (no falling
  knife), **and** close is above its close 10 bars ago (momentum
  confirmation, from v5).
- **RECOVERY mode (from v2):** after a washout (close ≥ 150 bps below the
  240-min SMA within the last 240 bars), buy the Donchian breakout (close
  above the highest high of the previous 60 bars) only when the EMA20/60
  cross is fresh (≤ 60 bars) with a 30–100 bps spread and the close above
  EMA20.
- **Exits:** dip trades exit v1-style — close recovers to 40 bps **above**
  the 240-min SMA, or +150 bps take-profit, or −100 bps stop-loss.
  Recovery trades exit on a two-stage trailing stop (100 bps, tightening
  to 60 bps once the peak gain reaches +100 bps), or +400 bps take-profit.
- **Discipline:** at most **2 dip round trips + 1 recovery round trip**
  per window (separate budgets, so one mode cannot starve the other) and
  a **120-bar cooldown** after a stop-loss exit.
- **Cold start:** no trading until 241 closes have been seen, so every
  indicator is fully formed.

Orders are full-size (up to 100% of equity), `max_slippage_bps = 100`, one
position at a time, long only. Fully deterministic: plain float arithmetic
over the bars as they arrive — no clock, no randomness, no network, no files.

## Results (see BACKTEST.md for full detail)

| Window | Net PnL | Trades | Max DD | Buy-and-hold |
|---|---|---|---|---|
| Dev (frozen) | **+$12.58** | 4 | 0.73% | +$1.07 |
| 8 other recent 24h BTC windows | mean **+$0.07**, worst −$8.98 | — | ≤ 2.15% | mean −$9.59 |

The only variant with a **positive out-of-sample mean** (+$0.07 vs v1's
−$1.84) and the best worst window (−$8.98 vs v1's −$9.36). It beats
buy-and-hold on 6/9 windows and loses far less than buy-and-hold on crash
windows (e.g. +$9.20 vs −$42.22 on a −4.6% day, because the recovery mode
caught the crash rebound). Honest caveat: dev profit is $0.63 below v1's
+$13.21 — the momentum filter that buys the better OOS profile costs a
little on the dev window. The dev window only gates entry (must be > $0);
the race itself is one unseen 24h window, where the OOS mean and worst
case are the better predictors.

## Files

- `main.py` — the bot (entrypoint, run as `python3 -P -s main.py`)
- `vendor/makefun_bars.py` — byte-identical copy of the kit's Python SDK shim
- `BACKTEST.md` — backtest notes (dev + out-of-sample windows, determinism, element provenance)
- `LICENSE` — MIT
- `.makefun/owner.json` — claim file for the payout wallet

## Run / grade locally

```sh
# inside this repo
python3 -P -s main.py        # the grader invocation (PYTHONHASHSEED=0)
```
