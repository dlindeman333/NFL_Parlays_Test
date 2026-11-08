#!/usr/bin/env python3
"""Read-only candidate-to-pick contract audit; never produces fabricated betting picks."""
import argparse,collections,datetime as dt,hashlib,json,math,pathlib
UTC=dt.timezone.utc
METRICS={"pass_attempts","pass_yards","rush_attempts","rush_yards","targets","receptions","rec_yards"}
REQUIRED_BET_FIELDS={"market","side","model_line","probability","label"}

def parse_time(value):
    try:
        d=dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return d.astimezone(UTC) if d.tzinfo else None
    except (ValueError,TypeError): return None

def audit_candidates(manifest,candidates,now,existing_keys=(),minimum_lead_minutes=15):
    accepted=[];rejected=collections.Counter();seen=set();games=collections.defaultdict(list)
    season=manifest.get("season");week=manifest.get("week")
    for c in candidates:
        try:
            gid=str(c["game_id"]);pid=str(c["espn_id"]);metric=c["metric"]
            key=f"{season}/{week}/{gid}/{pid}/{metric}"
            if c.get("logical_key")!=key or metric not in METRICS or not pid.isdigit() or not gid.isdigit(): raise ValueError("invalid_identity")
            if key in seen: raise ValueError("duplicate_identity")
            seen.add(key)
            if c.get("source_sha256")!=manifest.get("source_sha256"): raise ValueError("source_mismatch")
            value=c["baseline"]
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0: raise ValueError("invalid_baseline")
            kickoff=parse_time(c.get("kickoff_at"))
            if kickoff is None or kickoff<=now+dt.timedelta(minutes=minimum_lead_minutes): raise ValueError("kickoff_gate")
            if not c.get("history_weeks") or any(not isinstance(w,int) or w>=week or w<1 for w in c["history_weeks"]):raise ValueError("invalid_history")
            # A projection is deliberately NOT a sportsbook pick. No synthetic odds, lines, side or probability.
            item={"logical_key":key,"espn_id":pid,"metric":metric,"baseline":value,"position":c.get("position"),"kickoff_at":c["kickoff_at"],"source_sha256":c["source_sha256"],"classification":"STATISTICAL_BASELINE_NOT_BETTING_PICK"}
            accepted.append(item);games[(season,week,gid)].append(item)
        except (ValueError,TypeError,KeyError) as e: rejected[str(e) or "invalid_candidate"]+=1
    plans=[]
    for (s,w,gid),items in sorted(games.items()):
        ids=sorted(x["logical_key"] for x in items)
        plans.append({"season":s,"week":w,"game_id":gid,"candidate_count":len(items),"status":"SKIP_EXISTING" if (s,w,gid) in existing_keys else "BLOCKED_NO_VERIFIED_BETTING_PICK_CONTRACT","candidate_keys_sha256":hashlib.sha256("\n".join(ids).encode()).hexdigest()})
    return accepted,plans,dict(rejected)

def inspect_contract_shape(pick_shapes):
    # Only validates field presence; never treats source-derived baselines as real picks.
    return {"player_pick_fields_observed":sorted(set().union(*(set(x) for x in pick_shapes))) if pick_shapes else [],"required_betting_fields":sorted(REQUIRED_BET_FIELDS),"serializer_ready":False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--input-dir",default="phase3d37h-output");ap.add_argument("--output-dir",default="phase3d37l-output");a=ap.parse_args()
    src=pathlib.Path(a.input_dir);out=pathlib.Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((src/"manifest.json").read_text());candidates=json.loads((src/"candidates.json").read_text());raw=(src/"source.csv").read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest.get("source_sha256"):raise ValueError("source_fingerprint_mismatch")
    if len(candidates)!=manifest.get("candidate_metrics"):raise ValueError("candidate_count_mismatch")
    now=dt.datetime.now(UTC);accepted,plans,rejections=audit_candidates(manifest,candidates,now)
    report={"phase":"3D37L","mode":"READ_ONLY_SERIALIZER_CONTRACT_DRY_RUN","evaluated_at_utc":now.isoformat(),"season":manifest.get("season"),"week":manifest.get("week"),"source_sha256":manifest.get("source_sha256"),"candidates_input":len(candidates),"baseline_candidates_accepted":len(accepted),"game_plans":plans,"rejections":rejections,"pick_container_expected":"array","betting_picks_serialized":0,"snapshots_inserted":0,"database_writes":0,"readiness":"BLOCKED_PENDING_VERIFIED_LINES_PROBABILITIES_APP_READER_AND_EXPLICIT_WRITE_APPROVAL","limitations":["Statistical baselines cannot be serialized as sportsbook recommendations without verified lines, side and calibrated probabilities","Existing app reader JavaScript was not inspected by this workflow","Historical snapshot picks are not altered","Current roster data does not prove historical roster assignments","No network write methods are present"]}
    (out/"serializer_contract_report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"accepted":len(accepted),"games":len(plans),"rejected":sum(rejections.values()),"writes":0,"readiness":report["readiness"]}))
if __name__=="__main__":main()
