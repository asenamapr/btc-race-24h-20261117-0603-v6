"""BTC champion hybrid bot (v6) for make.fun btc-race-24h-20261117-0603.

Two-mode long-only bot. Every component earned its place with measured
numbers on the frozen dev window + 8 out-of-sample 24h BTC windows
(see BACKTEST.md); everything else was tried and rejected.

* DIP mode (from v1 "SMA240 Dip Buyer", measured dev +$13.21, d0 +$9.51):
  price deep below the 240-min SMA with a short-term bounce, a shallowing
  dip, no downtrend, AND momentum confirmation (close above its close 10
  bars ago, from v5). The confirmation costs $0.63 of dev profit but buys
  +$1.91 of out-of-sample mean and +$0.38 of worst case.
* RECOVERY mode (from v2's Donchian/EMA breakout, measured: v2 won +$11.56
  on the crash-recovery day d2 where v1 lost -$5.69): after a washout
  (close >=150 bps below SMA240 within 240 bars), buy the Donchian
  breakout (close above the highest high of the previous 60 bars) only
  when the EMA20/60 cross is fresh (<=60 bars) with a 30-100 bps spread
  and the close above EMA20. The washout + EMA filters are what keep it
  from buying every dead-cat bounce (the unfiltered breakout lost -$24.56
  on d2). Exits on a two-stage trailing stop (100/60 bps), which rides the
  recovery; on d2 it captured +$14.52.
* Exits: dip trades exit v1-style (recover to +40 bps above SMA240, or
  +150 bps take-profit, or -100 bps stop-loss). Recovery trades exit on
  the trailing stop (or +400 bps take-profit).
* Discipline: at most 2 dip round trips + 1 recovery round trip per
  window (separate budgets, so one mode cannot starve the other), 120-bar
  cooldown after a stop-loss, no trades before 241 closes.

Rejected with numbers (see BACKTEST.md): v3's ATR trailing stop as a dip
exit (dev +$13.21 -> -$7.96), v3's EMA-crossover entry (dev 0.0 on 639/640
grid rows — fails the dev gate), my own trend-pullback entry (dev -10.31),
v4's Bollinger entry as a standalone (dev -15.19 at N20, -3.98 OOS mean at
N240 final), scale-in (dev 10.99), tighter stop-loss (75 bps), more round
trips (3), later exits (+60/+80 bps above SMA), stop-after-loss, and
late-entry cutoffs. v1's own parameters are a local optimum; the hybrid
beats v1 only by ADDING the recovery trade, not by retuning v1.

Deterministic: plain float arithmetic, no clock/random/network/files.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
MAX_SLIPPAGE_BPS = 100

# --- parameters (module level so the replay harness can override them) ---
SLOW_BARS = 240
MID_BARS = 60
FAST_BARS = 15
DIP_BELOW_BPS = 60
DIP_EXIT_ABOVE_BPS = 40
TAKE_PROFIT_BPS = 150
STOP_LOSS_BPS = 100
TREND_TOL_BPS = 100
TREND_PULLBACK_BPS = 80   # trend entry: close within this of SMA60 (above it)
TREND_BOUNCE_BPS = 0      # trend entry: close above SMA15 by at least this
ATR_LEN = 14
TRAIL_MULT = 2.5          # ATR trailing stop multiple (v3-style)
MAX_ROUND_TRIPS = 2
STOP_COOLDOWN_BARS = 120
MAX_HOLD_BARS = 1440
WARMUP_CLOSES = 241
Z_RISE_MIN_BPS = 0      # extra bounce confirmation: z_now - z_15_ago >= this
STOP_AFTER_LOSS = False # stop new entries after any losing round trip
SCALE_IN = False        # half-size first buy; add rest when z >= -30 bps
LATE_CUTOFF = 1440      # no new entries at/after this bar (1440 = off)
MODE_REC = True           # recovery-breakout entry (v2 Donchian + washout filter)
MOM_BARS = 10           # dip-entry momentum confirmation: close > close MOM_BARS ago (v5-style)
REC_WASHOUT_BPS = 150     # washout: close was this far below SMA240 in last REC_LOOKBACK bars
REC_LOOKBACK = 240        # bars to look back for the washout
REC_DONCHIAN_BARS = 60    # breakout: close above highest high of previous N bars
REC_TRAIL1_BPS = 100      # stage-1 trail below peak close
REC_TRAIL2_BPS = 60       # stage-2 trail (tighter) once peak gain >= REC_STAGE_BPS
REC_STAGE_BPS = 100       # peak gain at which trail tightens
REC_TP_BPS = 400          # recovery take-profit
REC_MAX_RT = 1            # max recovery round trips per window

MODE_DIP = True           # v1 dip-buy entry
MODE_TREND = False        # uptrend pullback entry (OFF: measured worse, see BACKTEST.md)
EXIT_STYLE = "v1"         # "v1" | "trail" | "both" (trail measured worse for dip exits)


class Series:
    """Rolling SMAs + Wilder ATR + EMA gap over closes/highs/lows."""

    def __init__(self):
        self.closes = []
        self.highs = []
        self.lows = []
        self.slow_hist = []
        self._sum_slow = 0.0
        self._sum_mid = 0.0
        self._sum_fast = 0.0
        self._atr = None
        self._trs = []
        self.ema_fast = None
        self.ema_slow = None
        self._a_ef = 2.0 / (20 + 1)
        self._a_es = 2.0 / (60 + 1)
        self.last_cross = -10**9

    def push(self, close, high, low):
        c = float(close)
        prev_ef, prev_es = self.ema_fast, self.ema_slow
        if self.ema_fast is None:
            self.ema_fast = c
            self.ema_slow = c
        else:
            self.ema_fast = self._a_ef * c + (1.0 - self._a_ef) * self.ema_fast
            self.ema_slow = self._a_es * c + (1.0 - self._a_es) * self.ema_slow
        if (prev_ef is not None and prev_ef <= prev_es
                and self.ema_fast > self.ema_slow):
            self.last_cross = len(self.closes)  # index of this bar (0-based, pre-push)
        self.closes.append(c)
        self.highs.append(float(high))
        self.lows.append(float(low))
        self._sum_slow += c
        self._sum_mid += c
        self._sum_fast += c
        n = len(self.closes)
        if n > SLOW_BARS:
            self._sum_slow -= self.closes[n - 1 - SLOW_BARS]
        if n > MID_BARS:
            self._sum_mid -= self.closes[n - 1 - MID_BARS]
        if n > FAST_BARS:
            self._sum_fast -= self.closes[n - 1 - FAST_BARS]
        if n >= SLOW_BARS:
            self.slow_hist.append(self._sum_slow / SLOW_BARS)
        else:
            self.slow_hist.append(0.0)
        # Wilder ATR(14)
        if n == 1:
            tr = self.highs[0] - self.lows[0]
        else:
            tr = max(self.highs[-1] - self.lows[-1],
                     abs(self.highs[-1] - self.closes[-2]),
                     abs(self.lows[-1] - self.closes[-2]))
        self._trs.append(tr)
        if n == ATR_LEN:
            self._atr = sum(self._trs) / ATR_LEN
        elif n > ATR_LEN:
            self._atr = (self._atr * (ATR_LEN - 1) + tr) / ATR_LEN

    @property
    def slow(self):
        return self._sum_slow / SLOW_BARS

    @property
    def mid(self):
        return self._sum_mid / MID_BARS

    @property
    def fast(self):
        return self._sum_fast / FAST_BARS

    @property
    def atr(self):
        return self._atr if self._atr is not None else 0.0

    def z_now(self):
        return (self.closes[-1] - self.slow) / self.slow

    def z_15_ago(self):
        i = len(self.closes) - 1 - FAST_BARS
        c = self.closes[i]
        s = self.slow_hist[i]
        if s == 0.0:
            return self.z_now()
        return (c - s) / s


series = Series()
entry_price = None
entry_seq = -1
max_close = 0.0
round_trips = 0
cool_until_seq = -1
pending_buy = False
pending_sell = False
my_orders = {}
lost_rt = False         # set True when a round trip closed at a loss
added_leg = False       # scale-in: second leg already bought
last_sell_pnl = 0.0     # pnl of the last completed round trip (approx, bps)
entry_mode = None       # 'dip' | 'rec' for the open position
rec_trips = 0           # completed recovery round trips
peak_close = 0.0        # highest close since entry (for trailing exits)


def on_batch(state, batch):
    global entry_price, entry_seq, max_close, round_trips, cool_until_seq
    global pending_buy, pending_sell, lost_rt, added_leg, last_sell_pnl
    global entry_mode, rec_trips, peak_close

    for fill in batch.get("fills", []):
        side = my_orders.get(fill.get("client_id"))
        if side is None:
            continue
        if fill.get("status") == "filled":
            if side == "buy":
                entry_price = int(fill["price"])
                entry_seq = state.seq
                max_close = series.closes[-1] if series.closes else float(entry_price)
                peak_close = max_close
                entry_mode = my_orders.get(fill.get("client_id") + ":mode", "dip")
                pending_buy = False
            else:
                round_trips += 1
                if entry_mode == "rec":
                    rec_trips += 1
                if entry_price:
                    last_sell_pnl = int(fill["price"]) / entry_price - 1.0
                    if last_sell_pnl < 0:
                        lost_rt = True
                entry_price = None
                entry_mode = None
                pending_sell = False
                added_leg = False
        else:
            if side == "buy":
                pending_buy = False
            else:
                pending_sell = False

    bar = None
    for b in batch.get("bars", []):
        if b.get("symbol") == SYMBOL:
            bar = b
            break
    if bar is None or state.warming_up:
        return []
    series.push(int(bar["c"]), int(bar["h"]), int(bar["l"]))
    if len(series.closes) < WARMUP_CLOSES:
        return []

    held = state.positions.get(SYMBOL)
    close = series.closes[-1]
    z = series.z_now()

    if held is None:
        if pending_buy:
            return []
        dip_left = (round_trips - rec_trips) < MAX_ROUND_TRIPS
        rec_left = rec_trips < REC_MAX_RT
        if not dip_left and not rec_left:
            return []
        if state.seq < cool_until_seq:
            return []
        fire = False
        rec_fire = False
        # RECOVERY mode: washout happened recently (close was >= REC_WASHOUT_BPS
        # below SMA240 within REC_LOOKBACK bars) and now the close breaks above
        # the highest high of the previous REC_DONCHIAN_BARS bars (v2's trigger,
        # filtered to post-washout recoveries only).
        if MODE_REC and rec_left:
            lo = max(0, len(series.closes) - REC_LOOKBACK)
            washed = any(
                (series.closes[i] - series.slow_hist[i]) / series.slow_hist[i] <= -REC_WASHOUT_BPS / 10000.0
                for i in range(lo, len(series.closes))
                if series.slow_hist[i] > 0
            )
            highs = series.highs
            if washed and len(highs) > REC_DONCHIAN_BARS:
                don_high = max(highs[-REC_DONCHIAN_BARS - 1:-1])
                spread = (series.ema_fast - series.ema_slow) / series.ema_slow if series.ema_slow else 0.0
                cross_recent = (len(series.closes) - 1 - series.last_cross) <= 60
                if (close > don_high
                        and cross_recent
                        and 30 / 10000.0 <= spread <= 100 / 10000.0
                        and close > series.ema_fast):
                    rec_fire = True
                    fire = True
        # DIP mode: v1's entry (deep dip + bounce + shallowing + no downtrend).
        if MODE_DIP and dip_left and (
            z <= -DIP_BELOW_BPS / 10000.0
            and close > series.fast
            and z > series.z_15_ago()
            and (z - series.z_15_ago()) >= Z_RISE_MIN_BPS / 10000.0
            and (MOM_BARS == 0 or (len(series.closes) > MOM_BARS and close > series.closes[-1 - MOM_BARS]))
            and series.mid >= series.slow * (1 - TREND_TOL_BPS / 10000.0)
            and not (STOP_AFTER_LOSS and lost_rt)
            and state.seq < LATE_CUTOFF
        ):
            fire = True
        # TREND mode: uptrend pullback. Price above slow SMA, mid above slow
        # SMA, close pulled back near the mid SMA and bouncing off the fast.
        if not fire and MODE_TREND and dip_left and (
            close > series.slow
            and series.mid > series.slow
            and close >= series.mid * (1 - TREND_PULLBACK_BPS / 10000.0)
            and close <= series.mid * (1 + TREND_PULLBACK_BPS / 10000.0)
            and close > series.fast * (1 + TREND_BOUNCE_BPS / 10000.0)
            and z > series.z_15_ago()
        ):
            fire = True
        if fire:
            notional = state.cash // 2 if SCALE_IN else state.cash
            if notional < int(state.hello["fees"]["min_notional_quote_units"]):
                return []
            added_leg = not SCALE_IN
            pending_buy = True
            cid = state.client_id()
            my_orders[cid] = "buy"
            my_orders[cid + ":mode"] = "rec" if rec_fire else "dip"
            return [{
                "side": "buy",
                "client_id": cid,
                "symbol": SYMBOL,
                "notional_quote_units": notional,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }]
        return []

    # --- holding: scale-in second leg (buy rest when dip half-recovered) ---
    if SCALE_IN and not added_leg and not pending_buy and not pending_sell:
        if z >= -30 / 10000.0 and state.cash >= int(state.hello["fees"]["min_notional_quote_units"]):
            added_leg = True
            pending_buy = True
            cid = state.client_id()
            my_orders[cid] = "buy"
            return [{
                "side": "buy",
                "client_id": cid,
                "symbol": SYMBOL,
                "notional_quote_units": state.cash,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }]

    # --- holding: exits ---
    if pending_sell:
        return []
    if close > max_close:
        max_close = close
    if close > peak_close:
        peak_close = close
    ret = close / entry_price - 1.0 if entry_price else 0.0
    hold_bars = state.seq - entry_seq
    stop_hit = ret <= -STOP_LOSS_BPS / 10000.0
    sell = False
    if entry_mode == "rec":
        peak_gain_bps = (peak_close / entry_price - 1.0) * 10000.0 if entry_price else 0.0
        trail_bps = REC_TRAIL2_BPS if peak_gain_bps >= REC_STAGE_BPS else REC_TRAIL1_BPS
        trail = peak_close * (1 - trail_bps / 10000.0)
        if (close <= trail
                or ret >= REC_TP_BPS / 10000.0
                or hold_bars >= MAX_HOLD_BARS):
            sell = True
    else:
        if EXIT_STYLE in ("v1", "both"):
            if (z >= DIP_EXIT_ABOVE_BPS / 10000.0
                    or ret >= TAKE_PROFIT_BPS / 10000.0
                    or stop_hit
                    or hold_bars >= MAX_HOLD_BARS):
                sell = True
        if EXIT_STYLE in ("trail", "both"):
            trail = max_close - TRAIL_MULT * series.atr
            if close <= trail or stop_hit or hold_bars >= MAX_HOLD_BARS:
                sell = True
    if sell:
        if stop_hit:
            cool_until_seq = state.seq + STOP_COOLDOWN_BARS
        pending_sell = True
        cid = state.client_id()
        my_orders[cid] = "sell"
        return [{
            "side": "sell",
            "client_id": cid,
            "symbol": SYMBOL,
            "qty": held.qty,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    return []


makefun_bars.run(on_batch)
