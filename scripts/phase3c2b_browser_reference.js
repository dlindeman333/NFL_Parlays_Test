'use strict';
// Independent JavaScript implementation of index.html pstat(), advLogs(), advMetrics().
// It checks calculation parity, NOT live browser UI, roster accuracy, or sportsbook lines.
const fs=require('fs');
const [sourceFile,previewFile,outputFile]=process.argv.slice(2);
const {baselines:B,rows}=JSON.parse(fs.readFileSync(sourceFile,'utf8'));
const preview=JSON.parse(fs.readFileSync(previewFile,'utf8'));
const aliases={JAX:'JAC',JAC:'JAC',LAR:'LA',LA:'LA',WSH:'WAS',WAS:'WAS'};
const norm=x=>aliases[String(x||'').trim().toUpperCase()]||String(x||'').trim().toUpperCase();
const normName=x=>String(x||'').toLowerCase().replace(/[^a-z0-9]/g,'');
const S={};for(const [team,entry] of Object.entries(B.teams))S[team]={pf:0,pa:0,n:0,w:entry[1],l:entry[2]};
for(const [h,a,hs,as] of B.completed_scores){for(const [team,pf,pa] of [[h,hs,as],[a,as,hs]]){S[team].pf+=pf;S[team].pa+=pa;S[team].n++}}
for(const s of Object.values(S)){s.ppg=(s.pf+22.5*3)/(s.n+3);s.opp=(s.pa+22.5*3)/(s.n+3);s.rt=(s.w/(s.w+s.l)-.5)*12+(s.ppg-s.opp)*.35}
const hist=new Map();for(const r of rows){if(String(r.game_status).toUpperCase()!=='COMPLETED')continue;const key=norm(r.team)+'|'+normName(r.player);if(!hist.has(key))hist.set(key,[]);hist.get(key).push(r)}
const pool=new Map();for(const [market,arr] of Object.entries(B.player_pools))for(const [team,name,total] of arr)pool.set(market+'|'+norm(team)+'|'+normName(name),{team:norm(team),name,total,market});
const num=x=>x===''||x===null||x===undefined?null:(Number.isFinite(Number(x))?Number(x):null);
const clamp=(lo,hi,v)=>Math.max(lo,Math.min(hi,v));
const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:null;
const tests=[];let missing=0;
for(const x of preview.predictions){
 const [away0,home0]=x.game.split(' @ ');const away=norm(away0),home=norm(home0),team=norm(x.team);
 const p=pool.get(x.market+'|'+team+'|'+normName(x.player));
 if(!p||!S[away]||!S[home]||!(team===away||team===home)){missing++;tests.push({player:x.player,game:x.game,market:x.market,status:'MISSING_MODEL_INPUT'});continue}
 const logs=(hist.get(team+'|'+normName(x.player))||[]).filter(r=>Number(r.week)<Number(x.week)).sort((a,b)=>Number(b.week)-Number(a.week));
 const field={ps:'passing_yards',ru:'rushing_yards',td:'touchdowns'}[x.market];
 const vals=logs.map(r=>num(r[field])).filter(v=>v!==null);
 const base=p.total/(S[team].w+S[team].l);
 const blended=vals.length?(avg(vals)+base)/2:base;
 const margin=S[home].rt-S[away].rt+2;
 const total=(S[home].ppg+S[away].opp)/2+(S[away].ppg+S[home].opp)/2;
 const ownMargin=team===home?margin:-margin;
 const pts=total/2+ownMargin/2;
 const sc=pts/S[team].ppg;
 let proj,line;
 if(x.market==='td'){proj=blended*sc;line=null}
 else if(x.market==='ps'){proj=blended*(.6+.4*sc)*(1-.006*ownMargin);line=Math.floor(blended)+.5}
 else{proj=blended*(1+.01*ownMargin)*(.85+.15*sc);line=Math.floor(blended)+.5}
 const opp=team===home?away:home;
 const defenseFactor=clamp(.85,1.15,S[opp].opp/22.5);
 // Crucial: browser advMetrics uses original bundled p.v, not blended sourcePlayer().v.
 const last5=avg(vals.slice(0,5));
 const recentFactor=last5===null||base<=0?1:clamp(.8,1.2,last5/base);
 const projection=Math.max(0,proj*defenseFactor*(.75+.25*recentFactor));
 const spread=vals.length>=3?Math.max(1,Math.sqrt(avg(vals.map(v=>(v-avg(vals))**2)))):Math.max(x.market==='td'?.5:10,base*(x.market==='ps'?.22:.38));
 const probability=line===null?clamp(.05,.95,1-Math.exp(-projection)):clamp(.05,.95,1/(1+Math.exp(-1.7*((projection-line)/spread))));
 const score=(probability-.5)*100+(Math.min(5,vals.length)>=3?Math.min(5,vals.length):0);
 const checks={line:line===x.reference_line,projection:Math.abs(projection-x.projection)<=.00051,probability:Math.abs(probability-x.model_over_probability)<=.0000051,score:Math.abs(score-x.score)<=.000051,logs:vals.length===x.historical_games};
 const pass=Object.values(checks).every(Boolean);
 tests.push({player:x.player,game:x.game,week:x.week,market:x.market,status:pass?'PASS':'FAIL',checks,python:{line:x.reference_line,projection:x.projection,probability:x.model_over_probability,score:x.score,logs:x.historical_games},browser_formula:{line,projection:Number(projection.toFixed(3)),probability:Number(probability.toFixed(5)),score:Number(score.toFixed(4)),logs:vals.length}});
}
const passed=tests.filter(t=>t.status==='PASS').length,failed=tests.filter(t=>t.status==='FAIL').length;
const report={status:failed===0&&missing===0&&tests.length>0?'PASS':'FAIL',compared:tests.length,passed,failed,missing_data:missing,known_limitations:['Formula comparison is an independent JS reference based on uploaded index.html; not a live browser UI execution','Uses the existing preview candidate list; cannot validate missing candidates or schedule eligibility','Team aliases are normalized only in JS reference; the Python preview may still block JAX matchups','No sportsbook odds, roster verification, fresh injury data, or predictive accuracy test','No pregame snapshots or database writes'],failures:tests.filter(t=>t.status!=='PASS').slice(0,100)};
fs.writeFileSync(outputFile,JSON.stringify(report,null,2));
console.log(`Formula parity: ${report.status}; ${passed}/${tests.length} passed; ${failed} mismatches; ${missing} missing inputs`);
process.exit(report.status==='PASS'?0:2);
