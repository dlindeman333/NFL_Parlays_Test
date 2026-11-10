#!/usr/bin/env python3
"""Offline grading for immutable model-baseline forecasts (NOT betting picks).

Observations must come from a separately verified postgame final-stat feed.
No network access or database writes occur here.
"""
import datetime as dt
import hashlib
import json
import math
from phase3_forecast_snapshot import canonical
from phase3d37l_serializer_dry_run import parse_time

METRIC_KEYS = {'pass_attempts', 'pass_yards', 'rush_attempts', 'rush_yards', 'targets', 'receptions', 'rec_yards'}


def grade_forecast_artifact(artifact, observations, evaluated_at=None):
    now = evaluated_at or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError('evaluation_time_requires_timezone')
    now = now.astimezone(dt.timezone.utc)
    payload = artifact.get('payload')
    if not isinstance(payload, dict) or payload.get('schema') != 'phase3_model_forecast_v1':
        raise ValueError('unsupported_forecast_schema')
    if hashlib.sha256(canonical(payload)).hexdigest() != artifact.get('payload_sha256'):
        raise ValueError('forecast_artifact_integrity_failure')
    if payload.get('classification') != 'MODEL_BASELINE_NOT_SPORTSBOOK_PICK':
        raise ValueError('invalid_forecast_classification')
    captured = parse_time(payload.get('captured_at_utc'))
    if not captured or captured > now:
        raise ValueError('invalid_capture_timestamp')
    forecasts = payload.get('forecasts')
    if not isinstance(forecasts, list) or len(forecasts) != payload.get('forecast_count'):
        raise ValueError('forecast_count_mismatch')
    by_key = {}
    for observation in observations:
        key = observation.get('logical_key')
        if not isinstance(key, str) or key in by_key:
            raise ValueError('duplicate_or_missing_observation_identity')
        by_key[key] = observation
    seen = set()
    graded = []
    statuses = {'graded': 0, 'pending_final': 0, 'invalid_observation': 0}
    for f in forecasts:
        key = f.get('logical_key')
        if not key or key in seen:
            raise ValueError('duplicate_or_missing_forecast_identity')
        seen.add(key)
        kickoff = parse_time(f.get('kickoff_at'))
        if not kickoff or captured >= kickoff:
            raise ValueError('forecast_not_captured_pregame')
        metric = f.get('metric')
        baseline = f.get('baseline')
        if metric not in METRIC_KEYS or isinstance(baseline, bool) or not isinstance(baseline, (int, float)) or not math.isfinite(baseline) or baseline <= 0:
            raise ValueError('invalid_forecast_baseline')
        observation = by_key.get(key)
        row = {'logical_key': key, 'metric': metric, 'baseline': baseline, 'status': 'pending_final'}
        if observation is not None:
            final_at = parse_time(observation.get('final_verified_at_utc'))
            actual = observation.get('actual')
            if (observation.get('game_id') != f.get('game_id') or
                observation.get('espn_id') != f.get('espn_id') or
                observation.get('metric') != metric or
                observation.get('status') != 'final' or
                final_at is None or final_at < kickoff or final_at > now or
                isinstance(actual, bool) or not isinstance(actual, (int, float)) or
                not math.isfinite(actual) or actual < 0):
                row['status'] = 'invalid_observation'
            else:
                row.update(status='graded', actual=actual, error=round(actual - baseline, 6), absolute_error=round(abs(actual - baseline), 6))
        statuses[row['status']] += 1
        graded.append(row)
    result = {'schema': 'phase3_model_forecast_grade_v1', 'forecast_payload_sha256': artifact['payload_sha256'],
              'evaluated_at_utc': now.isoformat(), 'classification': 'MODEL_FORECAST_ACCURACY_NOT_BETTING_RESULTS',
              'counts': statuses, 'grades': graded, 'sportsbook_hits': 0, 'sportsbook_misses': 0,
              'database_writes': 0}
    return {'payload': result, 'payload_sha256': hashlib.sha256(canonical(result)).hexdigest()}
