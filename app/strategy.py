from __future__ import annotations

import math
import threading
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from .market import CHINA_TZ, IpoProfile, Quote


def _pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return (numerator / denominator - 1) * 100


def _minute_of_day(value: datetime) -> int:
    return value.hour * 60 + value.minute


def _in_live_session(minute: int) -> bool:
    return 570 <= minute <= 690 or 780 <= minute <= 900


def _price(value: float | None) -> str:
    return "--" if value is None else f"{value:.2f} 元"


@dataclass(slots=True)
class SymbolState:
    session_date: date
    last_signature: tuple[Any, ...] | None = None
    unchanged_since: datetime | None = None
    below_vwap_since: datetime | None = None
    opening_range_high: float | None = None
    opening_range_frozen: float | None = None
    secondary_breakout: bool = False
    secondary_peak: float | None = None
    halt_level: int = 0
    resume_until: datetime | None = None


@dataclass(slots=True)
class Decision:
    action: str
    label: str
    sell_ratio_pct: int
    sell_quantity: int | None
    execution_reference: float | None
    protection_reference: float | None
    urgency: str
    best_window: str
    headline: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence: str = "low"
    metrics: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return asdict(self)


class SellWindowEngine:
    """Conservative, explainable first-day state machine.

    It detects executable windows; it deliberately does not predict the exact
    intraday high and never sends orders to a broker.
    """

    def __init__(self) -> None:
        self._states: dict[str, SymbolState] = {}
        self._lock = threading.RLock()

    def _state(self, code: str, session_date: date) -> SymbolState:
        state = self._states.get(code)
        if state is None or state.session_date != session_date:
            state = SymbolState(session_date=session_date)
            self._states[code] = state
        return state

    def analyze(
        self,
        quote: Quote,
        profile: IpoProfile | None,
        *,
        position: int | None = None,
        now: datetime | None = None,
    ) -> Decision:
        now = (now or datetime.now(CHINA_TZ)).astimezone(CHINA_TZ)
        effective_time = (
            quote.market_time
            if quote.market_time and quote.market_time.date() == now.date()
            else now
        )
        minute = _minute_of_day(effective_time)
        today = now.date()
        market_date = effective_time.date()

        if profile and profile.listing_date:
            try:
                listing_date = date.fromisoformat(profile.listing_date)
            except ValueError:
                listing_date = None
            if listing_date and listing_date > today:
                return self._fixed(
                    "WAIT", "等待上市", 0, position, quote,
                    f"{quote.name or profile.name} 将于 {listing_date.isoformat()} 上市",
                    "上市日 09:25 后重新输入代码",
                    ["当前还没有上市首日成交行情，系统不会提前生成卖出信号。"],
                )
            if listing_date and listing_date != today:
                return self._fixed(
                    "NOT_APPLICABLE", "非上市首日", 0, position, quote,
                    "该软件只判断北交所新股上市当天",
                    "无需继续自动刷新",
                    [f"发行资料显示上市日为 {listing_date.isoformat()}，今天为 {today.isoformat()}。"],
                )
        elif profile is None:
            return self._fixed(
                "VERIFY", "需要核验", 0, position, quote,
                "未找到北交所发行资料，暂停强卖出提示",
                "核对代码、上市日期和券商终端",
                ["仅凭一条公开行情无法确认这是上市首日新股。"],
                warnings=["发行资料缺失时不会给出分批或全部退出数量。"],
            )

        current, open_price, high, vwap = quote.price, quote.open, quote.high, quote.vwap
        if not all(value is not None and value > 0 for value in (current, open_price, high)):
            return self._fixed(
                "WAIT", "等待行情", 0, position, quote,
                "等待 09:25 集合竞价或首笔成交",
                "09:30 后开始结构判断",
                ["当前价、开盘价或最高价尚未形成。"],
            )

        with self._lock:
            state = self._state(quote.code, market_date)
            signature = (current, high, quote.volume_shares, quote.amount_yuan, quote.market_time)
            if signature != state.last_signature:
                if state.halt_level:
                    state.resume_until = now + timedelta(minutes=2)
                    state.halt_level = 0
                state.last_signature = signature
                state.unchanged_since = now
            elif state.unchanged_since is None:
                state.unchanged_since = now

            unchanged_seconds = max(0.0, (now - (state.unchanged_since or now)).total_seconds())
            below_vwap = bool(vwap and current <= vwap * 0.99)
            if below_vwap:
                state.below_vwap_since = state.below_vwap_since or now
            elif vwap and current >= vwap:
                state.below_vwap_since = None

            if 570 <= minute < 585:
                state.opening_range_high = max(state.opening_range_high or high, high)
            if minute >= 585 and state.opening_range_frozen is None:
                state.opening_range_frozen = state.opening_range_high or high
            opening_level = state.opening_range_frozen or state.opening_range_high
            if minute >= 585 and opening_level and vwap and current > opening_level and current >= vwap:
                state.secondary_breakout = True
            if state.secondary_breakout:
                state.secondary_peak = max(state.secondary_peak or high, high)

            threshold30, threshold60 = open_price * 1.30, open_price * 1.60
            tolerance = lambda level: max(0.02, level * 0.002)
            near30 = abs(current - threshold30) <= tolerance(threshold30)
            near60 = abs(current - threshold60) <= tolerance(threshold60)
            if unchanged_seconds >= 12 and (near30 or near60):
                state.halt_level = 60 if near60 else 30

            decision = self._decide(
                quote,
                profile,
                state,
                position,
                now,
                minute,
                unchanged_seconds,
            )
            return decision

    def _decide(
        self,
        quote: Quote,
        profile: IpoProfile | None,
        state: SymbolState,
        position: int | None,
        now: datetime,
        minute: int,
        unchanged_seconds: float,
    ) -> Decision:
        current = float(quote.price or 0)
        open_price = float(quote.open or 0)
        high = float(quote.high or current)
        vwap = float(quote.vwap or 0) or None
        issue = profile.issue_price if profile else None
        open_premium = _pct(open_price, issue)
        pullback = _pct(high, current)
        pullback = -pullback if pullback is not None else 0.0
        # _pct(high, current) yields high/current-1; convert to (high-current)/high.
        pullback = (high - current) / high * 100 if high > 0 else 0.0
        high_vs_open = _pct(high, open_price) or 0.0
        current_vs_open = _pct(current, open_price) or 0.0
        current_vs_vwap = _pct(current, vwap) if vwap else None
        below_seconds = (
            max(0.0, (now - state.below_vwap_since).total_seconds())
            if state.below_vwap_since else 0.0
        )
        source_age = (
            max(0.0, (now - quote.market_time).total_seconds())
            if quote.market_time else None
        )
        live = _in_live_session(minute)
        stale = live and (source_age is None or source_age > 20)

        profile_ready = bool(profile and profile.listing_date and profile.issue_price)
        confidence = "high" if profile_ready and vwap and source_age is not None and source_age <= 10 else "medium"
        warnings = ["公开行情可能延迟；执行前必须以券商终端可成交盘口复核。"]
        reasons: list[str] = []
        ratio = 0
        action = "HOLD"
        label = "继续观察"
        headline = "结构未确认转弱，暂不卖出"
        urgency = "持续监控"

        if minute < 565:
            action, label, headline = "WAIT", "等待竞价", "09:25 前不生成卖出数量"
            urgency = "09:25 后重评"
            reasons.append("集合竞价价格尚未完成，提前判断容易把试单当成真实承接。")
        elif minute < 570:
            action, label, headline = "HOLD", "竞价观察", "记录 09:25 竞价，等待开盘成交确认"
            urgency = "09:30 后重评"
            reasons.append("竞价换手和价格只用于准备预案，不单独触发卖出。")
        elif 690 < minute < 780:
            action, label, headline = "HOLD", "午间休市", "午间不更新强卖出提示"
            urgency = "13:00 复牌后重评"
            reasons.append("午间行情静止属于正常休市，不按数据停滞处理。")
        elif minute > 900:
            action, label, headline = "CLOSED", "已收盘", "当日交易已经结束"
            urgency = "查看券商成交回报"
            reasons.append("软件不使用盘后最高价反推盘中决策。")
        elif state.halt_level:
            action, label, headline = "HALT", "临时停牌", f"触及开盘价±{state.halt_level}%临停区，冻结普通卖出提示"
            urgency = "复牌集合竞价前核对委托"
            reasons.append("临停期间价格和成交量不更新是预期行为，不视为行情故障。")
        elif state.resume_until and now < state.resume_until:
            action, label, headline = "HOLD", "复牌观察", "复牌后 2 分钟重新定价，暂不追着盘口卖"
            urgency = "有效成交满 2 分钟后重评"
            reasons.append("复牌集合竞价可能造成瞬时跳价，先确认 VWAP 和开盘价承接。")
        elif stale:
            action, label, headline = "VERIFY", "行情待核验", "行情超过 20 秒未更新，暂停强卖出提示"
            urgency = "立即查看券商终端"
            reasons.append(f"公开源时间戳距服务器约 {source_age:.0f} 秒。" if source_age is not None else "公开源没有可核验时间戳。")
            confidence = "low"
        else:
            first_minute_failure = (
                571 <= minute < 575
                and current <= open_price * 0.95
                and vwap is not None
                and current <= vwap * 0.97
                and pullback >= 6
            )
            sustained_below = bool(vwap and current <= vwap * 0.99 and below_seconds >= 300)
            double_break = bool(vwap and current < open_price and current < vwap)
            hard_exit = double_break and (sustained_below or pullback >= 8)
            opening_spike_fade = (
                575 <= minute <= 630
                and high_vs_open >= 8
                and pullback >= 6
                and vwap is not None
                and current < vwap
            )
            opening_level = state.opening_range_frozen or state.opening_range_high
            first_rally_fade = (
                minute >= 585
                and open_premium is not None
                and 40 <= open_premium <= 150
                and high_vs_open >= 5
                and pullback >= 3.5
                and vwap is not None
                and current < vwap
            )
            tail_exit = bool(
                state.secondary_breakout
                and state.secondary_peak
                and current <= state.secondary_peak * 0.95
            )
            outlier_open = bool(open_premium is not None and open_premium >= 70)
            momentum_held = bool(vwap and current >= open_price and current >= vwap and pullback < 5)

            if minute >= 885:
                action, label, ratio = "EXIT", "全部退出", 100
                headline = "已进入 14:45 首日清仓窗口，不留隔夜仓"
                urgency = "14:55 前完成"
                reasons.append("首日时间规则优先于软性趋势判断。")
            elif minute >= 870:
                action, label, ratio = "TRIM", "至少卖出一半", 50
                headline = "14:30 后开始退出首日剩余仓位"
                urgency = "14:45 前完成首批"
                reasons.append("尾盘流动性和回撤风险上升，停止延长持有时间。")
            elif first_minute_failure:
                action, label, ratio = "TRIM", "兑现 50%", 50
                headline = "首分钟承接失败，先降低风险敞口"
                urgency = "立即，余仓等待反抽确认"
                reasons.append(f"当前较开盘 {current_vs_open:.1f}%，较 VWAP {current_vs_vwap:.1f}%，高点回撤 {pullback:.1f}%。")
            elif 570 <= minute < 575:
                action, label, headline = "HOLD", "开盘保护", "首个 5 分钟价格发现，硬保护期内暂不卖"
                urgency = "09:35 后重评"
                reasons.append("普通跌破、单笔下探和未确认回撤在开盘保护期内不产生卖出数量。")
            elif tail_exit:
                action, label, ratio = "EXIT", "退出尾仓", 100
                headline = "二次突破后从峰值回撤 5%，退出剩余仓位"
                urgency = "立即，按可成交盘口"
                reasons.append(f"二次突破峰值 {_price(state.secondary_peak)}，5% 移动保护已经触发。")
            elif hard_exit:
                action, label, ratio = "EXIT", "全部退出", 100
                headline = "开盘价与 VWAP 双破，硬退出已经确认"
                urgency = "立即，按可成交盘口"
                reasons.append(f"当前较开盘价 {current_vs_open:.1f}%，高点回撤 {pullback:.1f}%。")
                if sustained_below:
                    reasons.append(f"低于 VWAP 1% 已持续约 {below_seconds / 60:.1f} 分钟。")
            elif opening_spike_fade:
                action, label, ratio = "TRIM", "兑现 70%", 70
                headline = "极端高开后尖峰回落，先锁定大部分利润"
                urgency = "立即，余仓看 VWAP 反抽"
                reasons.append(f"最高价较开盘上冲 {high_vs_open:.1f}%，现已回撤 {pullback:.1f}% 并跌到 VWAP 下方。")
            elif first_rally_fade:
                action, label, ratio = "TRIM", "兑现 50%", 50
                headline = "首轮冲高回落，保留尾仓等待二次突破"
                urgency = "立即完成首批"
                reasons.append(f"开盘 15 分钟高点参考 {_price(opening_level)}；当前回撤 {pullback:.1f}% 且低于 VWAP。")
            elif outlier_open and momentum_held:
                action, label, headline = "HOLD", "动量保持", "超预期开盘但仍守住开盘价与 VWAP，暂不卖"
                urgency = "结构失败或临停复牌后重评"
                reasons.append(f"开盘较发行价溢价 {open_premium:.1f}%，静态估值线不用于机械清仓。")
                reasons.append("价格与 VWAP 同向，当前高换手不单独作为卖出理由。")
            elif state.secondary_breakout:
                action, label, headline = "HOLD", "尾仓跟踪", "二次突破成立，使用峰值 5% 移动保护"
                urgency = "跌破移动保护时处理余仓"
                reasons.append(f"二次突破峰值 {_price(state.secondary_peak)}。")
            elif vwap and current >= open_price and current >= vwap:
                action, label, headline = "HOLD", "结构健康", "价格守住开盘价与 VWAP，等待更明确卖出窗口"
                urgency = "持续监控"
                reasons.append("量价结构仍偏强，不因为涨幅大或换手高就抢跑。")
            elif vwap and current < vwap and pullback >= 5:
                action, label, ratio = "TRIM", "风险减仓", 50
                headline = "高点回撤并跌破 VWAP，先降低一半风险"
                urgency = "等待持续失守确认"
                reasons.append(f"当前高点回撤 {pullback:.1f}%，较 VWAP {current_vs_vwap:.1f}%。")
            else:
                reasons.append("当前只有单一软信号，尚未形成价格、VWAP 与回撤的组合确认。")

        hard_for_single = action == "EXIT" or minute >= 870 or "尖峰回落" in headline
        if position is not None and 0 < position < 200 and 0 < ratio < 100:
            if hard_for_single:
                ratio = 100
                action, label = "EXIT", "单手全部退出"
                reasons.insert(0, "不足 200 股无法分批，硬退出信号转换为全部卖出。")
            else:
                ratio = 0
                action, label = "HOLD", "单手继续观察"
                headline = "单手仓位不执行软性分批，等待硬退出双确认"
                reasons.insert(0, "100 股单手采用容错优先：软信号为 0 股。")

        quantity = self._quantity(position, ratio)
        execution = current if ratio > 0 else None
        protection = None
        if current > 0:
            candidates = [value for value in (open_price, vwap) if value]
            protection = max(candidates) * 0.99 if candidates else None
            if state.secondary_peak:
                protection = max(protection or 0, state.secondary_peak * 0.95)
        best_window = self._best_window(action, ratio, minute, headline)
        metrics = {
            "open_premium_pct": open_premium,
            "current_vs_open_pct": current_vs_open,
            "current_vs_vwap_pct": current_vs_vwap,
            "high_vs_open_pct": high_vs_open,
            "pullback_pct": pullback,
            "below_vwap_seconds": below_seconds,
            "quote_age_seconds": source_age,
            "turnover_pct": quote.turnover_pct,
        }
        state_payload = {
            "opening_range_high": state.opening_range_frozen or state.opening_range_high,
            "secondary_breakout": state.secondary_breakout,
            "secondary_peak": state.secondary_peak,
            "unchanged_seconds": unchanged_seconds,
            "halt_level": state.halt_level,
        }
        return Decision(
            action=action,
            label=label,
            sell_ratio_pct=ratio,
            sell_quantity=quantity,
            execution_reference=execution,
            protection_reference=protection,
            urgency=urgency,
            best_window=best_window,
            headline=headline,
            reasons=reasons[:6],
            warnings=warnings,
            confidence=confidence,
            metrics=metrics,
            state=state_payload,
        )

    @staticmethod
    def _quantity(position: int | None, ratio: int) -> int | None:
        if position is None or ratio <= 0:
            return 0 if position is not None else None
        if ratio >= 100:
            return position
        lots = math.floor(position * ratio / 100 / 100)
        return min(position, max(100, lots * 100)) if position >= 100 else position

    @staticmethod
    def _best_window(action: str, ratio: int, minute: int, headline: str) -> str:
        if ratio > 0:
            return f"当前窗口已确认｜{headline}"
        if action in {"VERIFY", "NOT_APPLICABLE", "CLOSED"}:
            return headline
        if minute < 570:
            return "09:30 开盘后等待价格确认"
        if minute < 575:
            return "09:35 首根 5 分钟线完成后重评"
        if minute < 600:
            return "09:45—10:00｜结合 VWAP、回撤与开盘区间"
        if minute < 630:
            return "10:00—10:30｜观察首小时冲高回落"
        if minute < 870:
            return "等待 VWAP 持续失守、反抽失败或移动保护触发"
        return "14:30—14:55｜完成首日清仓"

    def _fixed(
        self,
        action: str,
        label: str,
        ratio: int,
        position: int | None,
        quote: Quote,
        headline: str,
        urgency: str,
        reasons: list[str],
        *,
        warnings: list[str] | None = None,
    ) -> Decision:
        return Decision(
            action=action,
            label=label,
            sell_ratio_pct=ratio,
            sell_quantity=self._quantity(position, ratio),
            execution_reference=quote.price if ratio else None,
            protection_reference=None,
            urgency=urgency,
            best_window=headline,
            headline=headline,
            reasons=reasons,
            warnings=warnings or ["执行前必须以券商终端可成交盘口复核。"],
            confidence="low",
            metrics={},
            state={},
        )
