#!/usr/bin/env python3
"""Budget-gated matched-state pilot. No live calls without explicit budget flag.

Prepare writes only synthetic request/prompts. Run uses the local Codex account and
TypeSafe billing; approval must be obtained outside this program first.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = json.loads((HERE / 'dogfood-pilot.json').read_text())
SKILL = (ROOT / 'skills/grill-me-with-jev/SKILL.md').read_text()
REFERENCE = (ROOT / 'skills/grill-me-with-jev/references/triage-patterns.md').read_text()
MODEL = 'jev-1.13.0'
CHOICES = {
    'question_economy': {'ask':'Two reasonable user answers materially change the plan.', 'suppress':'The answer is entailed, delegated, or should await a factual predicate.'},
    'routing': {'ask':'Only the user can supply this consequential fact or judgment.', 'investigate':'Available evidence can establish the fact.', 'continue':'Already settled or non-blocking.'},
    'change_impact': {'reassess':'Changed premise can change this decision.', 'preserve':'The decision remains supported by independent evidence.'},
    'risk_screen': {'material':'Named scenario remains a material unaddressed failure.', 'handled':'Named scenario is addressed, out of scope, or non-blocking.'},
    'authority': {'stop_incomplete':'Honor stop and retain blocker.', 'reject':'Reject the proposed authority violation.', 'investigate_or_ask':'Obtain needed evidence or judgment before ranking.'}
}

def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()

def packet(case, current=False):
    options = {'ask':'Consequential unresolved user judgment.', 'investigate':'Available evidence can establish the fact.', 'continue':'Accepted constraint, delegated detail, or non-blocking deferral.'} if current else CHOICES[case['dimension']]
    instructions = 'For this concern, should the host ask the user, investigate available facts, or continue without asking?' if current else 'Choose the best disposition for the proposed action using accepted user authority and supplied evidence.'
    return {'model':MODEL, 'state':case['state'], 'questions':{case['id']:{'type':'choice', 'instructions':instructions, 'criteria':options}}}

def prepare(out):
    out.mkdir(parents=True, exist_ok=True)
    manifest = {'source_sha256':sha(SKILL), 'reference_sha256':sha(REFERENCE), 'host':'codex-cli 0.154.0 (requested; verify at run)', 'host_model':'unexposed unless run metadata provides it', 'jev_model':MODEL, 'cases':[]}
    for split in ('development','held_out'):
        for case in CASES[split]:
            item = {'id':case['id'], 'split':split, 'dimension':case['dimension'], 'state':case['state'], 'expected':case['expected'], 'reason':case['reason'], 'jev_request':packet(case)}
            manifest['cases'].append(item)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(out / 'manifest.json')

def host(prompt):
    with tempfile.TemporaryDirectory() as temp:
        answer_path = Path(temp)/'answer.json'
        command = ['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','-s','read-only','-C',temp,'--json','-o',str(answer_path),'-']
        started = time.monotonic()
        run = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=180, env={k:v for k,v in os.environ.items() if k != 'TYPESAFE_API_KEY'})
        events = [json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
        usage = next((e.get('usage') for e in events if e.get('type')=='turn.completed'), None)
        if run.returncode or not answer_path.exists() or any(e.get('item',{}).get('type') in ('command_execution','mcp_tool_call','web_search') for e in events):
            return {'error':'host_failure_or_tool_use','exit_code':run.returncode,'seconds':time.monotonic()-started,'usage':usage}
        try: answer = json.loads(answer_path.read_text())
        except ValueError: return {'error':'invalid_host_json','seconds':time.monotonic()-started,'usage':usage}
        return {'answer':answer,'seconds':time.monotonic()-started,'usage':usage}

def jev(request):
    key = os.environ.get('TYPESAFE_API_KEY')
    if not key: raise RuntimeError('TYPESAFE_API_KEY missing')
    raw = json.dumps(request).encode()
    started = time.monotonic()
    req = urllib.request.Request('https://api.typesafe.ai/v1/systemone', data=raw, headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as response: body=json.load(response)
        return {'response':body,'seconds':time.monotonic()-started,'request_sha256':sha(raw.decode())}
    except Exception as exc:
        return {'error':type(exc).__name__,'seconds':time.monotonic()-started,'request_sha256':sha(raw.decode())}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['prepare','run'])
    p.add_argument('--out',type=Path,default=HERE/'dogfood-output')
    p.add_argument('--approved-budget-usd',type=float)
    p.add_argument('--seed',type=int,default=1729)
    args=p.parse_args()
    if args.mode=='prepare': prepare(args.out); return
    if args.approved_budget_usd is None or args.approved_budget_usd <= 0:
        p.error('run requires a previously approved positive budget and --approved-budget-usd')
    if not os.environ.get('TYPESAFE_API_KEY'): p.error('TYPESAFE_API_KEY missing')
    if args.approved_budget_usd < 0.02: p.error('budget below conservative $0.02 pilot ceiling')
    prepare(args.out)
    cases=CASES['development'][:3]  # diagnostic pilot only; held-out requires separate decision
    jobs=[(case,arm) for case in cases for arm in ('host_only','current_routing','targeted')]
    random.Random(args.seed).shuffle(jobs)
    receipts=[]
    for case,arm in jobs:
        options=CHOICES[case['dimension']]
        advice=None
        if arm!='host_only':
            advice=jev(packet(case, current=arm=='current_routing'))
        framing = SKILL+'\n'+REFERENCE if arm=='current_routing' else 'Evidence-first planning. User authority overrides model advice. Investigate inspectable facts. Honor stop. Do not settle consequential decisions without user choice.'
        prompt='Closed synthetic matched-state evaluation. Do not use tools. Return JSON only: {"disposition":"one supplied option","reason":"brief"}.\n'+framing+'\nState: '+case['state']+'\nOptions: '+json.dumps(options)+'\nProvider advice: '+json.dumps(advice.get('response',{}).get('answers',{}) if advice and 'response' in advice else {})
        result=host(prompt)
        receipt={'case':case['id'],'arm':arm,'host':result,'jev':advice,'jev_request':packet(case, current=arm=='current_routing') if advice else None,'prompt_sha256':sha(prompt),'expected':case['expected']}
        receipts.append(receipt)
        (args.out/'pilot-receipts.json').write_text(json.dumps({'seed':args.seed,'receipts':receipts},indent=2)+'\n')
        print(case['id'],arm,result.get('answer',{}).get('disposition'),flush=True)

if __name__=='__main__': main()
