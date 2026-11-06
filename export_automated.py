"""Export 2026 NFL weekly player stats, trends, matchups and future schedule.

Install: py -m pip install --upgrade nflreadpy pandas pyarrow
Run:     py export.py
Output:  nfl_player_stats.csv (in the same directory as this script)

Includes original matchup/trend/red-zone metrics plus standardized weekly
passing, rushing, receiving, touchdown and snap columns for prop grading.

Historical player-game rows have game_status=COMPLETED. Future scheduled rows
have game_status=SCHEDULED and blank actual statistics. A player is projected
onto future team schedules using their most recently recorded 2026 team;
this is NOT a confirmed roster or availability forecast.
"""
from pathlib import Path
import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
import warnings
import numpy as np
import pandas as pd
import nflreadpy as nfl

SEASON = int(os.environ.get("NFL_SEASON", "2026"))
POSITIONS = {"QB", "RB", "WR", "TE"}
OUTPUT = Path(__file__).with_name("nfl_player_stats.csv")
STATS = {
    "attempts": "pass_attempts", "completions": "pass_completions",
    "passing_yards": "pass_yards", "passing_tds": "pass_tds",
    "interceptions": "pass_interceptions", "passing_interceptions": "pass_interceptions",
    "carries": "rush_attempts", "rushing_yards": "rush_yards",
    "rushing_tds": "rush_tds", "targets": "targets",
    "receptions": "receptions", "receiving_yards": "rec_yards",
    "receiving_tds": "rec_tds",
    "sacks_suffered": "sacks_suffered",
}
TRACK = ["pass_attempts", "pass_completions", "pass_yards", "pass_tds",
         "pass_interceptions", "rush_attempts", "rush_yards", "rush_tds",
         "targets", "receptions", "rec_yards", "rec_tds", "sacks_suffered"]
RZ = ["rz_rush_20", "rz_rush_10", "rz_rush_5", "rz_targets_20",
      "rz_targets_10", "rz_targets_5", "rz_pass_attempts_20"]
DEF = ["opp_pass_yds_allowed_pg", "opp_rush_yds_allowed_pg",
       "opp_pass_def_rank", "opp_rush_def_rank"]


def frame(obj):
    return obj.to_pandas() if hasattr(obj, "to_pandas") else pd.DataFrame(obj)


def first_column(df, options, required=False):
    for c in options:
        if c in df.columns:
            return c
    if required:
        raise ValueError("Missing expected column; tried: " + ", ".join(options))
    return None


def load_schedule():
    print("Loading NFL schedule...")
    sc = frame(nfl.load_schedules([SEASON]))
    sc = sc.copy()
    week_col = first_column(sc, ["week"], True)
    home_col = first_column(sc, ["home_team"], True)
    away_col = first_column(sc, ["away_team"], True)
    type_col = first_column(sc, ["game_type", "season_type"])
    if type_col:
        sc = sc[sc[type_col].astype(str).str.upper().isin(["REG", "REGULAR"])].copy()
    sc["week"] = pd.to_numeric(sc[week_col], errors="coerce")
    sc = sc.dropna(subset=["week"])
    sc["week"] = sc["week"].astype(int)
    home_score = first_column(sc, ["home_score"])
    away_score = first_column(sc, ["away_score"])
    # Both final scores populated are the published-data signal for a completed game.
    if home_score and away_score:
        completed = pd.to_numeric(sc[home_score], errors="coerce").notna() & pd.to_numeric(sc[away_score], errors="coerce").notna()
    else:
        completed = pd.Series(False, index=sc.index)
        warnings.warn("Schedule has no final-score columns; completed games will be inferred from published player stats.")
    sc["game_status"] = np.where(completed, "COMPLETED", "SCHEDULED")
    date_col = first_column(sc, ["gameday", "game_date", "date"])
    time_col = first_column(sc, ["gametime", "game_time"])
    sc["game_date"] = sc[date_col].astype(str) if date_col else ""
    sc["game_time"] = sc[time_col].astype(str) if time_col else ""
    parts = []
    for team_col, opp_col, venue in [(home_col, away_col, "HOME"), (away_col, home_col, "AWAY")]:
        t = sc[["week", "game_status", "game_date", "game_time", team_col, opp_col]].copy()
        t.columns = ["week", "game_status", "game_date", "game_time", "team", "opponent_team"]
        t["home_away"] = venue
        parts.append(t)
    return pd.concat(parts, ignore_index=True).drop_duplicates(["team", "week"])


def load_players():
    print("Loading weekly player statistics...")
    raw = frame(nfl.load_player_stats([SEASON]))
    type_col = first_column(raw, ["season_type", "game_type"])
    if type_col:
        raw = raw[raw[type_col].astype(str).str.upper().eq("REG")].copy()
    position_col = first_column(raw, ["position", "position_group"], True)
    raw = raw[raw[position_col].isin(POSITIONS)].copy()
    if raw.empty:
        raise RuntimeError(f"No {SEASON} regular-season player stats available.")
    id_col = first_column(raw, ["player_id"], True)
    name_col = first_column(raw, ["player_display_name", "player_name"], True)
    team_col = first_column(raw, ["recent_team", "team"], True)
    week_col = first_column(raw, ["week"], True)
    raw["week"] = pd.to_numeric(raw[week_col], errors="coerce")
    raw = raw.dropna(subset=["week"]).copy()
    raw["week"] = raw["week"].astype(int)
    base = raw[[id_col, name_col, team_col, position_col, "week"]].copy()
    base.columns = ["player_id", "name", "team", "pos", "week"]
    # Prefer published weekly stats. Missing columns remain NA, not invented zeros.
    # Multiple source aliases can map to the same output; take the first available.
    for source, dest in STATS.items():
        if source in raw.columns and dest not in base.columns:
            base[dest] = pd.to_numeric(raw[source], errors="coerce")
    for col in TRACK:
        if col not in base:
            base[col] = np.nan
    base = base.groupby(["player_id", "name", "team", "pos", "week"], as_index=False)[TRACK].sum(min_count=1)
    return base


def add_supplemental_player_fields(df):
    """Expose app-friendly aliases and touchdowns without replacing missing data.

    Touchdown total counts rushing + receiving TDs only. Passing TDs are kept
    separate to avoid double-counting QB passing scores as player touchdowns.
    """
    aliases = {
        "player": "name", "player_display_name": "name", "position": "pos",
        "passing_yards": "pass_yards", "passing_tds": "pass_tds",
        "passing_attempts": "pass_attempts", "attempts": "pass_attempts",
        "completions": "pass_completions", "passing_completions": "pass_completions",
        "passing_interceptions": "pass_interceptions", "interceptions": "pass_interceptions",
        "rushing_yards": "rush_yards", "rushing_tds": "rush_tds",
        "rushing_attempts": "rush_attempts", "carries": "rush_attempts",
        "receiving_yards": "rec_yards", "receiving_tds": "rec_tds",
        "receiving_receptions": "receptions", "receiving_targets": "targets",
    }
    for alias, canonical in aliases.items():
        df[alias] = df[canonical]
    # NaN if either TD component is unavailable; zero is a legitimate actual.
    df["total_tds"] = df[["rush_tds", "rec_tds"]].sum(axis=1, min_count=2)
    df["touchdowns"] = df["total_tds"]
    df["anytime_touchdown"] = np.where(df["total_tds"].notna(),
                                        (df["total_tds"] > 0).astype(int), np.nan)
    df["yards_per_carry"] = (df["rush_yards"] /
                              df["rush_attempts"].replace(0, np.nan))
    df["yards_per_reception"] = (df["rec_yards"] /
                                  df["receptions"].replace(0, np.nan))
    # Snap counts require a separate source; don't invent them.
    for col in ("offense_snaps", "team_offense_snaps", "snap_share"):
        if col not in df:
            df[col] = np.nan
    return df


def add_redzone(df):
    print("Loading play-by-play for red-zone opportunities and defensive rankings...")
    for c in RZ:
        df[c] = np.nan
    try:
        pbp = frame(nfl.load_pbp([SEASON]))
        if "season_type" in pbp:
            pbp = pbp[pbp["season_type"].eq("REG")].copy()
        for c in ["week", "yardline_100", "yards_gained"]:
            if c in pbp:
                pbp[c] = pd.to_numeric(pbp[c], errors="coerce")
        if "week" not in pbp or "yardline_100" not in pbp:
            raise ValueError("PBP missing week or yardline_100")
        rz = pbp[pbp["yardline_100"].le(20)].copy()
        metrics = []
        for kind, idcol, cutoff, outcol in [
            ("run", "rusher_player_id", 20, "rz_rush_20"),
            ("run", "rusher_player_id", 10, "rz_rush_10"),
            ("run", "rusher_player_id", 5, "rz_rush_5"),
            ("pass", "receiver_player_id", 20, "rz_targets_20"),
            ("pass", "receiver_player_id", 10, "rz_targets_10"),
            ("pass", "receiver_player_id", 5, "rz_targets_5"),
            ("pass", "passer_player_id", 20, "rz_pass_attempts_20"),
        ]:
            if idcol not in rz:
                continue
            x = rz[(rz["play_type"] == kind) & rz["yardline_100"].le(cutoff) & rz[idcol].notna()]
            count = x.groupby([idcol, "week"]).size().rename(outcol).reset_index()
            count = count.rename(columns={idcol: "player_id"})
            metrics.append(count)
        for m in metrics:
            col = m.columns[-1]
            df = df.drop(columns=[col]).merge(m, on=["player_id", "week"], how="left")
        for c in RZ:
            df[c] = df[c].fillna(0)
        df["rz_total_opportunities_20"] = df["rz_rush_20"] + df["rz_targets_20"]
        return df, pbp
    except Exception as e:
        warnings.warn(f"Red-zone/PBP data unavailable: {e}")
        df["rz_total_opportunities_20"] = np.nan
        return df, None


def defense_table(pbp, schedule):
    """Weekly defense allowed: rank 1 is fewest yards allowed per game.

    Historical opponent ranks use games BEFORE the matchup (no look-ahead).
    Future opponent ranks use all currently completed games.
    """
    if pbp is None:
        return pd.DataFrame(columns=["team", "week"] + DEF)
    needed = {"week", "defteam", "play_type", "yards_gained"}
    if not needed.issubset(pbp.columns):
        return pd.DataFrame(columns=["team", "week"] + DEF)
    x = pbp[pbp["play_type"].isin(["run", "pass"]) & pbp["defteam"].notna()].copy()
    x["pass_allowed"] = np.where(x["play_type"].eq("pass"), x["yards_gained"], 0)
    x["rush_allowed"] = np.where(x["play_type"].eq("run"), x["yards_gained"], 0)
    by_week = x.groupby(["defteam", "week"], as_index=False)[["pass_allowed", "rush_allowed"]].sum()
    completed_weeks = schedule.loc[schedule.game_status.eq("COMPLETED"), ["team", "week"]].drop_duplicates()
    by_week = by_week.merge(completed_weeks.rename(columns={"team": "defteam"}), on=["defteam", "week"], how="inner")
    rows = []
    for wk in sorted(schedule["week"].unique()):
        # Completed games in week N get a pre-week N ranking; scheduled games
        # get the latest available ranking, including earlier completed weeks.
        for status in ["COMPLETED", "SCHEDULED"]:
            if status == "COMPLETED":
                eligible = by_week[by_week.week < wk]
            else:
                eligible = by_week[(by_week.week < wk) | (by_week.week == wk)]
            if eligible.empty:
                continue
            d = eligible.groupby("defteam", as_index=False).agg(
                pass_total=("pass_allowed", "sum"), rush_total=("rush_allowed", "sum"),
                games=("week", "nunique"))
            d["opp_pass_yds_allowed_pg"] = d.pass_total / d.games
            d["opp_rush_yds_allowed_pg"] = d.rush_total / d.games
            d["opp_pass_def_rank"] = d.opp_pass_yds_allowed_pg.rank(method="min", ascending=True)
            d["opp_rush_def_rank"] = d.opp_rush_yds_allowed_pg.rank(method="min", ascending=True)
            d = d.rename(columns={"defteam": "opponent_team"})
            d["week"] = wk
            d["game_status"] = status
            rows.append(d[["opponent_team", "week", "game_status"] + DEF])
    if not rows:
        return pd.DataFrame(columns=["opponent_team", "week", "game_status"] + DEF)
    return pd.concat(rows, ignore_index=True)


def main():
    schedule = load_schedule()
    players = load_players()
    # Link weekly stats to schedule; scores define game completion.
    historical = players.merge(schedule, on=["team", "week"], how="left", validate="many_to_one")
    historical["game_status"] = historical["game_status"].fillna("COMPLETED")
    historical = historical[historical["game_status"].eq("COMPLETED")].copy()
    historical["is_future"] = False
    historical, pbp = add_redzone(historical)
    # Most recent known team per player; future assignments are provisional.
    latest = historical.sort_values("week").drop_duplicates("player_id", keep="last")
    future_games = schedule[schedule["game_status"].eq("SCHEDULED")].copy()
    future = latest[["player_id", "name", "team", "pos"]].merge(future_games, on="team", how="inner")
    future = future[["player_id", "name", "team", "pos", "week", "game_status", "game_date", "game_time", "opponent_team", "home_away"]]
    future["is_future"] = True
    for c in TRACK + RZ + ["rz_total_opportunities_20"]:
        future[c] = np.nan
    df = pd.concat([historical, future], ignore_index=True)
    df = df.sort_values(["player_id", "week", "is_future"]).drop_duplicates(["player_id", "week"], keep="first")
    df = df.sort_values(["player_id", "week"]).reset_index(drop=True)
    df["season"] = SEASON
    # Game averages and hit rates use completed games only. For future rows,
    # the latest values are carried forward; no future results enter history.
    df["games_played_to_date"] = df.groupby("player_id")["is_future"].transform(lambda s: (~s).cumsum())
    avg_stats = TRACK + RZ + ["rz_total_opportunities_20"]
    # Compute on actual played games only, then carry the last known form
    # into future schedule rows. Future blanks must never enter rolling windows.
    completed_mask = ~df["is_future"]
    actual = df.loc[completed_mask].copy()
    for stat in avg_stats:
        if stat not in df:
            continue
        for n, suffix in [(3, "last3_avg"), (5, "last5_avg")]:
            col = f"{stat}_{suffix}"
            actual[col] = actual.groupby("player_id")[stat].transform(
                lambda s: s.rolling(n, min_periods=1).mean())
        actual[f"{stat}_season_avg"] = actual.groupby("player_id")[stat].transform(
            lambda s: s.expanding(min_periods=1).mean())
    # Hit rate thresholds are reference benchmarks, NOT live sportsbook lines.
    for stat, marks in {"rush_yards": [25, 50, 75, 100],
                        "rec_yards": [25, 50, 75, 100],
                        "receptions": [3, 5, 7], "targets": [5, 8, 10]}.items():
        for mark in marks:
            key = f"{stat}_hit_rate_{mark}plus"
            actual[key] = actual.groupby("player_id")[stat].transform(
                lambda s: s.ge(mark).expanding(min_periods=1).mean())
    actual["rush_50plus_last5_rate"] = actual.groupby("player_id")["rush_yards"].transform(
        lambda s: s.ge(50).rolling(5, min_periods=1).mean())
    actual["rec_50plus_last5_rate"] = actual.groupby("player_id")["rec_yards"].transform(
        lambda s: s.ge(50).rolling(5, min_periods=1).mean())
    trend_cols = [c for c in actual.columns if c not in df.columns]
    df = df.merge(actual[["player_id", "week"] + trend_cols],
                  on=["player_id", "week"], how="left")
    df[trend_cols] = df.groupby("player_id")[trend_cols].ffill()
    ranks = defense_table(pbp, schedule)
    if not ranks.empty:
        df = df.merge(ranks, on=["opponent_team", "week", "game_status"], how="left")
    for c in DEF:
        if c not in df:
            df[c] = np.nan
    # An explicit next opponent column, repeated across historical rows, helps
    # dashboard filtering without requiring the user to select a future row.
    upcoming = future.sort_values("week").drop_duplicates("player_id")[["player_id", "opponent_team", "week", "game_date"]]
    upcoming = upcoming.rename(columns={"opponent_team": "next_opponent", "week": "next_game_week", "game_date": "next_game_date"})
    df = df.merge(upcoming, on="player_id", how="left")
    df["matchup_label"] = df["team"].astype(str) + " " + np.where(df["home_away"].eq("HOME"), "vs ", "@ ") + df["opponent_team"].fillna("TBD").astype(str)
    df["future_team_assignment_provisional"] = df["is_future"]
    df["stat_data_available"] = ~df["is_future"]
    df = add_supplemental_player_fields(df)
    # Make grading fields easy to discover in CSV, while keeping existing columns.
    num = df.select_dtypes(include=["number"]).columns
    df[num] = df[num].round(3)
    preferred = ["season", "week", "game_status", "is_future", "game_date", "game_time",
                 "player_id", "name", "pos", "team", "opponent_team", "home_away", "matchup_label",
                 "next_opponent", "next_game_week", "next_game_date", "games_played_to_date"]
    df = df[[c for c in preferred if c in df] + [c for c in df if c not in preferred]]
    df.to_csv(OUTPUT, index=False)
    upload_to_supabase(df)
    print(f"\nCreated {OUTPUT} with {len(df):,} player-week rows.")
    print(f"Completed: {(df.game_status == 'COMPLETED').sum():,}; scheduled: {(df.game_status == 'SCHEDULED').sum():,}")
    print("Rank 1 = fewest yards allowed. Future team assignments are provisional.")
    print("A scheduled row is not a confirmed active roster, injury status, or live game feed.")
    print("Player prop columns: passing_yards, rushing_yards, receiving_yards, passing_tds,")
    print("  rushing_tds, receiving_tds, total_tds, touchdowns, receptions, targets.")
    print("Touchdowns = rushing + receiving only; passing TDs are separate.")
    print("Snap share remains blank unless a verified snap source is added.")


def upload_to_supabase(df):
    """Optional shared export upload. Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.

    Service-role credentials belong in GitHub Actions secrets, never in HTML.
    A failed upload exits nonzero, so the scheduled workflow reports failure.
    """
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("Supabase upload skipped (set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY). CSV still generated.")
        return
    payload = json.dumps({
        "season": SEASON,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(df),
        "csv_text": OUTPUT.read_text(encoding="utf-8-sig"),
    }, allow_nan=False).encode("utf-8")
    request = urllib.request.Request(
        url + "/rest/v1/nfl_stat_exports?on_conflict=season",
        data=payload, method="POST",
        headers={"apikey": key, "Authorization": "Bearer " + key,
                 "Content-Type": "application/json",
                 "Prefer": "resolution=merge-duplicates,return=minimal"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            print("Supabase NFL statistics upload completed:", response.status)
    except urllib.error.HTTPError as error:
        raise RuntimeError("Supabase upload failed (HTTP %s): %s" % (
            error.code, error.read().decode("utf-8", "replace")[:800])) from error


if __name__ == "__main__":
    main()
