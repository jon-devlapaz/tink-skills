#!/usr/bin/env python3
"""Opt-in evaluation harness; never loaded by the runtime skill.

Uses the locally configured Codex CLI and synthetic fixtures. `ablation` sends
only public fixture fields to TypeSafe. No SDK installs or credential files.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def host(prompt):
    """Record actual CLI usage and wall time; never infer metrics from model prose."""
    started = time.monotonic()
    env = {k: v for k, v in os.environ.items() if k != 'TYPESAFE_API_KEY'}
    with tempfile.TemporaryDirectory(prefix='grill-eval-') as tmp:
        output = Path(tmp) / 'answer.json'
        command = ['codex', 'exec', '--ignore-user-config', '--ephemeral',
                   '--skip-git-repo-check', '-s', 'read-only', '-C', tmp,
                   '--json', '-o', str(output), '-']
        try:
            process = subprocess.run(command, input='Do not use tools, read files, or invoke other agents. '
                                     'This is a closed synthetic evaluation. Return JSON only.\n' + prompt,
                                     text=True, capture_output=True, timeout=180, env=env)
        except subprocess.TimeoutExpired:
            return {'error': 'host_timeout', 'seconds': time.monotonic() - started}
        events = []
        for line in process.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        usage = next((e.get('usage') for e in events if e.get('type') == 'turn.completed'), None)
        tool_used = any(e.get('item', {}).get('type') in
                        ('command_execution', 'mcp_tool_call', 'web_search') for e in events)
        result = {'seconds': round(time.monotonic() - started, 3), 'usage': usage,
                  'exit_code': process.returncode, 'tool_used': tool_used,
                  'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}
        if process.returncode or tool_used or not output.exists():
            failure_text = (process.stdout + process.stderr).lower()
            category = next((tag for needles, tag in [
                (('usage limit', 'usage_limit', 'rate_limit_exceeded'), 'usage_limit'),
                (('unauthorized', 'authentication', '401'), 'authentication'),
                (('timed out', 'connection', 'network'), 'transport')]
                if any(n in failure_text for n in needles)), 'unclassified')
            return {**result, 'error': 'host_failed_or_used_tools', 'failure_category': category}
        try:
            result['answer'] = json.loads(output.read_text())
        except ValueError:
            result['error'] = 'host_invalid_json'
        return result


def valid_answer(answer, kind):
    def probability(value):
        return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
    if not isinstance(answer, dict) or answer.get('type') != kind:
        return False
    if kind == 'noul':
        return probability(answer.get('noul'))
    probs = answer.get('probabilities', {})
    return (isinstance(probs, dict) and set(probs) == {'ask', 'investigate', 'continue'} and
            all(probability(v) for v in probs.values()) and
            abs(sum(probs.values()) - 1) <= .001 and
            answer.get('choice') in probs and
            probs[answer['choice']] == max(probs.values()) and
            probability(answer.get('confidence')))


def provider_once(state, kind, timeout=15):
    if kind == 'choice':
        questions = {c['id']: {'type': 'choice',
            'instructions': 'For concern ' + c['text'] + ' should the host ask the user, investigate available facts, or continue without asking?',
            'criteria': {'ask': 'Consequential unresolved user judgment.',
                         'investigate': 'Available evidence can establish the fact before asking.',
                         'continue': 'Accepted constraints, delegated details, or non-blocking deferral.'}}
                     for c in state['concerns']}
    else:
        c = state['review']
        questions = {c['id']: {'type': 'noul',
            'instructions': 'Does this specific concern expose an unresolved consequential decision or major failure mode? ' + c['text'],
            'criteria': {'true': 'Unresolved material concern.',
                         'false': 'Addressed, out of scope, or non-blocking.'}}}
    packet = {'model': 'jev-1.13.0', 'state': state, 'questions': questions}
    raw = json.dumps(packet).encode()
    receipt = {'request': packet, 'request_sha256': hashlib.sha256(raw).hexdigest()}
    key = os.environ.get('TYPESAFE_API_KEY')
    if not key:
        return {**receipt, 'error': 'missing_key'}
    if key.encode() in raw:
        return {'error': 'credential_in_payload'}
    started = time.monotonic()
    req = urllib.request.Request('https://api.typesafe.ai/v1/systemone', data=raw,
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = json.load(response)
        if not isinstance(body, dict) or body.get('model') != packet['model']:
            return {**receipt, 'error': 'invalid_response_or_model_drift', 'seconds': round(time.monotonic() - started, 3)}
        answers = body.get('answers', {})
        if not isinstance(answers, dict):
            answers = {}
        valid = {k: a for k, a in answers.items() if k in questions and valid_answer(a, kind)}
        receipt.update(model=body.get('model'), usage=body.get('usage'), answers=valid,
                       invalid_ids=sorted(set(questions) - set(valid)))
    except urllib.error.HTTPError as exc:
        receipt['error'] = 'http_' + str(exc.code)
        retry_after = exc.headers.get('Retry-After') if exc.headers else None
        if retry_after:
            try:
                receipt['retry_after'] = max(0, float(retry_after))
            except ValueError:
                receipt['retry_after_unparsed'] = True
    except ValueError:
        receipt['error'] = 'invalid_json'
    except OSError:
        receipt['error'] = 'transport_error'
    receipt['seconds'] = round(time.monotonic() - started, 3)
    return receipt


def provider(state, kind):
    first = provider_once(state, kind)
    if first.get('error') not in {'http_429', 'http_500', 'http_502', 'http_503', 'http_504', 'http_529', 'transport_error'}:
        return first
    delay = max(1, first.get('retry_after', 0))
    remaining = 30 - first.get('seconds', 0) - delay
    if remaining <= 0 or first.get('retry_after_unparsed'):
        return first
    time.sleep(delay)
    second = provider_once(state, kind, min(15, remaining))
    second['attempts'] = [{k: v for k, v in first.items() if k != 'request'},
                          {k: v for k, v in second.items() if k != 'request'}]
    second['seconds'] = round(first.get('seconds', 0) + delay + second.get('seconds', 0), 3)
    return second


def activation():
    suite = read(HERE / 'activation.json')
    prompts = [{k: c[k] for k in ('id', 'prompt')} for c in suite['cases']]
    result = host('Select whether to activate skill grill-me-with-jev based ONLY on this description: '
                  + suite['candidate_description'] + '\nPrompts: ' + json.dumps(prompts)
                  + '\nReturn {"predictions":[{"id":"...","activate":true,"reason":"..."}]}.')
    if 'answer' in result:
        predictions = {p['id']: p['activate'] for p in result['answer']['predictions']}
        result['wrong_ids'] = [c['id'] for c in suite['cases'] if predictions.get(c['id']) != c['activate']]
    write(HERE / 'results/activation-candidate.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'answer'}), flush=True)


def ablation():
    suite = read(HERE / 'ablation.json')
    contract = (HERE.parent / 'SKILL.md').read_text() + '\n' + (HERE.parent / 'references/triage-patterns.md').read_text()
    advice = {}
    for case in suite['cases']:
        public = {k: v for k, v in case.items() if k != 'oracle'}
        for kind in ('choice', 'noul'):
            state = public if kind == 'choice' else {'goal': case['goal'], 'settled': case['oracle']['answers'], 'review': case['review']}
            advice[case['id'] + '-' + kind] = provider(state, kind)
    write(HERE / 'results/provider.json', advice)
    arms = {'local': (False, False), 'choice': (True, False), 'noul': (False, True), 'both': (True, True)}
    jobs = [(case, arm, flags) for case in suite['cases'] for arm, flags in arms.items()]

    def run(job):
        case, arm, (choice, noul) = job
        public = {k: v for k, v in case.items() if k not in ('oracle', 'review')}
        history, rounds, answers = [], [], {}
        for _ in range(3):
            prompt = contract + '\nEVALUATION OVERRIDE: no provider calls; only use supplied real advice, '
            prompt += 'or local judgment when no advice supplied. Do not save files or request confirmation. '
            prompt += 'Handle interview choices only; completion review is a separate snapshot. '
            prompt += 'Return {"ask_ids":[],"investigate_ids":[],"accepted":{},"ready_for_review":false,"reason":"..."}. '
            prompt += 'IDs must come from the supplied concerns. accepted maps only actual answered/delegated decisions to values. '
            prompt += '\nCASE: ' + json.dumps(public) + '\nHISTORY: ' + json.dumps(history)
            prompt += '\nAdvice: ' + json.dumps(advice[case['id'] + '-choice'].get('answers', {}) if choice else {})
            run_result = host(prompt)
            rounds.append(run_result)
            if 'error' in run_result:
                break
            output = run_result['answer']
            asked = output.get('ask_ids', [])
            if not isinstance(asked, list) or any(i not in {c['id'] for c in case['concerns']} for i in asked):
                run_result['error'] = 'invalid_ask_ids'
                break
            reply = {i: case['oracle']['answers'].get(i, 'Use available evidence or the delegated default; this does not need my decision.') for i in asked}
            answers.update({i: v for i, v in reply.items() if i in case['oracle']['answers']})
            investigations = {i: case['oracle']['facts'][i] for i in output.get('investigate_ids', []) if i in case['oracle']['facts']}
            history.append({'assistant': output, 'user': reply, 'investigation_results': investigations})
            if output.get('ready_for_review') or (not asked and not investigations):
                break
        review = host(contract + '\nEVALUATION OVERRIDE: this is a separate completion-review snapshot. '
                      'All interview choices below are now settled; no API calls or files. '
                      'Assess the one supplied provisional candidate, with supplied real advice or local judgment. '
                      'Return {"material":true,"action":"ask/investigate/continue","reason":"..."}.\n'
                      + json.dumps({'goal': case['goal'], 'settled': case['oracle']['answers'], 'candidate': case['review'],
                                    'advice': advice[case['id'] + '-noul'].get('answers', {}) if noul else {}}))
        required = set(case['oracle']['required'])
        all_asks = [i for r in rounds for i in r.get('answer', {}).get('ask_ids', [])]
        last = rounds[-1].get('answer', {})
        accepted = last.get('accepted', {})
        resolved = required & answers.keys() & accepted.keys()
        interruptions = sum(bool(r.get('answer', {}).get('ask_ids')) for r in rounds)
        invalid = sum(len(set(r.get('answer', {}).get('accepted', {})) & required -
                          set().union(*(set(h['user']) for h in history[:index]))) for index, r in enumerate(rounds))
        metrics = {'consequential_omissions': sorted(required - resolved),
                   'unnecessary_questions': len([i for i in all_asks if i not in required]),
                   'user_interruptions': interruptions, 'resolved_decisions': len(resolved),
                   'decisions_per_interruption': len(resolved) / interruptions if interruptions else None,
                   'turns_to_settled_choices': len(rounds) if not (required - resolved) and last.get('ready_for_review') else None,
                   'synthetic_user_corrections': len([i for i in all_asks if i not in required]),
                   'invalid_acceptances': invalid, 'reasked_decisions': len(all_asks) - len(set(all_asks)),
                   'review_correct': review.get('answer', {}).get('material') == case['oracle']['review_material']}
        result = {'case': case['id'], 'arm': arm, 'rounds': rounds, 'review': review, 'metrics': metrics}
        write(HERE / ('results/ablation-' + case['id'] + '-' + arm + '.json'), result)
        print(json.dumps({'case': case['id'], 'arm': arm, 'metrics': metrics}), flush=True)
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, jobs))
    write(HERE / 'results/ablation-summary.json', {'method': suite['protocol'], 'results': [
        {'case': r['case'], 'arm': r['arm'], 'metrics': r['metrics'],
         'host_seconds': round(sum(x['seconds'] for x in r['rounds'] + [r['review']]), 3),
         'host_usage': [x.get('usage') for x in r['rounds'] + [r['review']]],
         'errors': [x['error'] for x in r['rounds'] + [r['review']] if 'error' in x]}
        for r in results]})


def retention(resume=False):
    suite = read(HERE / 'retention.json')
    contract = (HERE.parent / 'SKILL.md').read_text() + '\n' + (HERE.parent / 'references/triage-patterns.md').read_text()
    history, results = [], []
    saved = HERE / 'results/retention.json'
    if resume and saved.exists():
        previous = read(saved)['turns']
        write(HERE / 'results/retention-interrupted.json', {'turns': previous})
        results = [r for r in previous if 'error' not in r]
        history = [{'user': r['user'], 'assistant': r['answer']} for r in results]
    for index, message in enumerate(suite['turns'][len(results):], len(results) + 1):
        result = host(contract + '\nEVALUATION: Jev is unavailable. No tools or actual file writes. '
                      'Apply each user turn, maintain the ledger, and give the next response. '
                      'Return {"nodes":{},"constraints":[],"revision":0,"confirmed":false,'
                      '"implementation_authorized":false,"response":"..."}. '
                      'nodes is a map of stable IDs to status, answer, prerequisites and history. '
                      '\nHistory: ' + json.dumps(history) + '\nUser: ' + message)
        results.append({'turn': index, 'user': message, **result})
        write(HERE / 'results/retention.json', {'method': suite['method'], 'turns': results})
        print(json.dumps({'retention_turn': index, 'error': result.get('error'), 'seconds': result['seconds']}), flush=True)
        if 'error' in result:
            break
        history.append({'user': message, 'assistant': result['answer']})


def question_economy():
    case = read(HERE / 'question-economy.json')['case']
    contract = (HERE.parent / 'SKILL.md').read_text() + '\n' + (HERE.parent / 'references/triage-patterns.md').read_text()
    result = host(contract + '\nNo tools or APIs. Apply question selection to the supplied case. '
                  'Return {"ask":true,"reason":"...","next_action":"..."}.\n' + json.dumps(case))
    write(HERE / 'results/question-economy.json', {'case': case, 'result': result})
    print(json.dumps(result), flush=True)


def score_retention():
    suite = read(HERE / 'retention.json')
    run = read(HERE / 'results/retention.json')
    turns = run['turns']
    final = turns[-1].get('answer', {})
    expected = suite['expected_final']
    checks = {key: text.lower() in str(final.get('nodes', {}).get(key, {}).get('answer', '')).lower()
              for key, text in expected.items() if key not in ('forbidden', 'confirmed', 'implementation_authorized')}
    checks.update({key: final.get(key) == expected[key] for key in ('confirmed', 'implementation_authorized')})
    report = {'completed_turns': len([t for t in turns if 'answer' in t]),
              'expected_turns': len(suite['turns']), 'literal_field_checks': checks,
              'constraints_for_manual_review': final.get('constraints'),
              'seconds': round(sum(t['seconds'] for t in turns), 3),
              'input_tokens': sum((t.get('usage') or {}).get('input_tokens', 0) for t in turns),
              'output_tokens': sum((t.get('usage') or {}).get('output_tokens', 0) for t in turns),
              'note': 'Literal ID checks only. Inspect collision remapping and answer history manually; do not equate keyword checks with semantic correctness.'}
    write(HERE / 'results/retention-assessment.json', report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiment', choices=['activation', 'ablation', 'retention', 'question-economy', 'score-retention'])
    parser.add_argument('--resume', action='store_true', help='Resume retention from its successful prefix')
    args = parser.parse_args()
    if args.experiment == 'retention':
        retention(args.resume)
    else:
        {'activation': activation, 'ablation': ablation, 'question-economy': question_economy, 'score-retention': score_retention}[args.experiment]()
