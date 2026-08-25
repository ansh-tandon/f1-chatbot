"""
Context Builder: assembles compact context from Graph, PostgreSQL, Analytics, and Qdrant.
Produces a well-structured prompt context for the LLM.
Never dumps raw telemetry or huge tables into the prompt.
"""
import json
from typing import Any
from app.agent.orchestrator import OrchestratorResult


def _fmt_time(seconds: float | None) -> str:
    if seconds is None:
        return "N/A"
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins}:{secs:06.3f}"


def _compact_stints(stints_data: dict | None) -> str:
    if not stints_data:
        return "No stint data"
    stints = stints_data.get("stints", [])
    if not stints:
        return "No stints found"
    lines = []
    for s in stints:
        avg = _fmt_time(s.get("avg_lap_time_s"))
        best = _fmt_time(s.get("best_lap_time_s"))
        lines.append(
            f"  Stint {s.get('stint_number')}: {s.get('compound','?')} | "
            f"Laps {s.get('lap_start')}–{s.get('lap_end')} ({s.get('lap_count')} laps) | "
            f"Avg: {avg} | Best: {best}"
        )
    pits = stints_data.get("pit_stops", [])
    for p in pits:
        dur = f"{p.get('duration_s', 'N/A'):.1f}s" if p.get("duration_s") else "N/A"
        lines.append(
            f"  Pit Stop {p.get('stop_number')}: Lap {p.get('lap_number')} | "
            f"{p.get('compound_in','?')} → {p.get('compound_out','?')} | Duration: {dur}"
        )
    return "\n".join(lines) if lines else "No data"


def build_context(orch_result: OrchestratorResult, question: str) -> str:
    """Build a compact, structured context string for the LLM prompt."""
    parts = []

    # ── Race overview ──────────────────────────────────────────────────────
    race = orch_result.graph_context.get("race", {})
    if race:
        parts.append(f"""## Race
Race: {race.get('race', 'Monaco Grand Prix')}
Circuit: {race.get('circuit', 'Circuit de Monaco')}, {race.get('country', 'Monaco')}
Date: {race.get('date', '2024-05-26')}""")

    # ── Weather ────────────────────────────────────────────────────────────
    weather = orch_result.graph_context.get("weather", {})
    if weather:
        rain = "Yes" if weather.get("rainfall") else "No"
        parts.append(
            f"## Weather\n"
            f"Air temp: {weather.get('air_temp_c', 'N/A')}°C | "
            f"Track temp: {weather.get('track_temp_c', 'N/A')}°C | "
            f"Rainfall: {rain}"
        )

    # ── Race results ───────────────────────────────────────────────────────
    race_results = orch_result.analytics.get("race_results", [])
    if race_results:
        lines = ["## Results"]
        for r in race_results[:3]:
            lines.append(f"  P{r.get('position', '?')}: {r.get('driver')} | Status: {r.get('status', '?')} | Points: {r.get('points', '?')}")
        parts.append("\n".join(lines))

    # ── LEC stints (from graph) ────────────────────────────────────────────
    lec_stints = orch_result.graph_context.get("lec_stints")
    nor_stints = orch_result.graph_context.get("nor_stints")
    if lec_stints or nor_stints:
        parts.append(f"## LEC Stints/Pit Stops\n{_compact_stints(lec_stints)}")
        parts.append(f"## NOR Stints/Pit Stops\n{_compact_stints(nor_stints)}")

    # ── Strategy comparison ────────────────────────────────────────────────
    strategy = orch_result.analytics.get("strategy_comparison", {})
    if strategy:
        parts.append(
            f"## Strategy Comparison\n"
            f"{strategy.get('strategy_summary', '')}\n"
            f"LEC total stops: {strategy.get('driver_a_total_stops', '?')} | "
            f"NOR total stops: {strategy.get('driver_b_total_stops', '?')}"
        )

    # ── Sector comparison ──────────────────────────────────────────────────
    sector_cmp = orch_result.analytics.get("sector_comparison", {})
    if sector_cmp:
        deltas = sector_cmp.get("sector_deltas", [])
        lines = [f"## Sector Performance ({sector_cmp.get('session_type', '')})"]
        for d in deltas:
            a_t = _fmt_time(d.get("driver_a_best_s"))
            b_t = _fmt_time(d.get("driver_b_best_s"))
            delta = d.get("delta_s")
            delta_str = f"{delta:+.3f}s" if delta is not None else "N/A"
            adv = d.get("advantage", "")
            lines.append(f"  S{d.get('sector')}: LEC {a_t} | NOR {b_t} | Δ {delta_str} ({adv})")
        overall = sector_cmp.get("overall_best_lap_delta_s")
        if overall is not None:
            lines.append(f"  Overall best lap delta: {overall:+.3f}s | Advantage: {sector_cmp.get('overall_advantage')}")
        parts.append("\n".join(lines))

    # ── Telemetry comparison ───────────────────────────────────────────────
    tel_cmp = orch_result.analytics.get("telemetry_comparison", {})
    if tel_cmp and any(tel_cmp.get(k) for k in ["driver_a_avg_speed", "driver_b_avg_speed"]):
        parts.append(
            f"## Telemetry (Fastest Lap)\n"
            f"Avg speed: LEC {tel_cmp.get('driver_a_avg_speed', 'N/A'):.1f} km/h | NOR {tel_cmp.get('driver_b_avg_speed', 'N/A'):.1f} km/h\n"
            f"Max speed: LEC {tel_cmp.get('driver_a_max_speed', 'N/A'):.1f} km/h | NOR {tel_cmp.get('driver_b_max_speed', 'N/A'):.1f} km/h\n"
            f"Full throttle: LEC {tel_cmp.get('driver_a_full_throttle_pct', 'N/A'):.1f}% | NOR {tel_cmp.get('driver_b_full_throttle_pct', 'N/A'):.1f}%\n"
            f"DRS usage: LEC {tel_cmp.get('driver_a_drs_pct', 'N/A'):.1f}% | NOR {tel_cmp.get('driver_b_drs_pct', 'N/A'):.1f}%"
        )

    # ── Lap pace ───────────────────────────────────────────────────────────
    lec_pace = orch_result.analytics.get("lec_pace", {})
    nor_pace = orch_result.analytics.get("nor_pace", {})
    if lec_pace or nor_pace:
        lines = ["## Lap Pace"]
        for code, pace in [("LEC", lec_pace), ("NOR", nor_pace)]:
            if pace:
                lines.append(
                    f"  {code}: Best {_fmt_time(pace.get('best_lap_time_s'))} | "
                    f"Avg {_fmt_time(pace.get('avg_lap_time_s'))} | "
                    f"Valid laps: {pace.get('valid_lap_count', 0)}"
                )
        parts.append("\n".join(lines))

    # ── Tyre degradation ───────────────────────────────────────────────────
    lec_deg = orch_result.analytics.get("lec_degradation", {})
    nor_deg = orch_result.analytics.get("nor_degradation", {})
    if lec_deg or nor_deg:
        lines = ["## Tyre Degradation"]
        for code, deg in [("LEC", lec_deg), ("NOR", nor_deg)]:
            if deg:
                rate = deg.get("degradation_rate_s_per_lap")
                rate_str = f"{rate:+.4f}s/lap" if rate is not None else "N/A"
                lines.append(f"  {code}: {rate_str}")
        parts.append("\n".join(lines))

    # ── Documents (top 3 most relevant) ───────────────────────────────────
    docs = orch_result.documents[:3]
    if docs:
        lines = ["## Relevant Documents"]
        for d in docs:
            lines.append(f"\n[Source: {d.get('title','?')} | {d.get('source','?')} | Score: {d.get('score', 0):.3f}]")
            text = d.get("text", "")
            # Limit document text in context to prevent LLM overload
            lines.append(text[:350] + ("..." if len(text) > 350 else ""))
        parts.append("\n".join(lines))

    # ── Sources used ───────────────────────────────────────────────────────
    parts.append(f"## Data Sources Used\n{', '.join(orch_result.sources_used)}")

    full_context = "\n\n".join(parts)

    # ── Token Guard: Enforce strict safety ceiling (~3,000 tokens / 12,000 chars) ──
    # Guarantees no query or tool payload will ever exceed LLM rate limits
    MAX_CHARS = 12000
    if len(full_context) > MAX_CHARS:
        full_context = full_context[:MAX_CHARS] + "\n\n[Context truncated for token safety ceiling]"

    return full_context
