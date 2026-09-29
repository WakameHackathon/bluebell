"""Pure offline validation, NOT an executor, authenticator or authorization service.
host is a separate integration/test API; never a v1 wire extension.
All semantic witnesses must be independently established by the trusted host.
"""
import json
from pathlib import Path
from datetime import datetime
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA = json.loads((Path(__file__).resolve().parents[1]/'references/recover.schema.json').read_text(encoding='utf-8'))

def structural(value, name):
    s = {'$schema': SCHEMA['$schema'], '$defs': SCHEMA['$defs'], '$ref': '#/$defs/'+name}
    return [e.message for e in Draft202012Validator(s, format_checker=FormatChecker()).iter_errors(value)]

def instant(s):
    d = datetime.fromisoformat(s.replace('Z', '+00:00'))
    if d.tzinfo is None: raise ValueError('timezone_required')
    return d

def check(q, r, h):
    errors = ['request:'+e for e in structural(q, 'aftercare-recoverRequest')]
    errors += ['result:'+e for e in structural(r, 'aftercare-recoverResult')]
    def err(s):
        if s not in errors: errors.append(s)
    def done():
        # This skill never gives external-write permission, including successful validation.
        return {'errors': errors, 'hold_external_write': True, 'automatic_execution_allowed': False}
    if errors: return done()
    try:
        for k in ('call_id', 'task_id', 'contract_version', 'skill_id'):
            if q[k] != r[k]: err('response_binding:'+k)
        if q['skill_version'] != '1.0.0': err('unsupported_skill_version')
        if q['expected_task_revision'] != r['based_on_task_revision']: err('response_revision')
        def resolve(ref):
            if ref is None: return None
            a = h['registry'].get(ref['artifact_id'])
            if not a: err('missing_ref:'+ref['artifact_id']); return None
            if any(a[k] != ref[k] for k in ('kind', 'revision')): err('artifact_binding')
            if a['task_id'] != q['task_id'] or not a['accessible']: err('artifact_scope')
            wanted_trust='untrusted_skill_output' if ref['kind'] in ('PlatformView','OutcomeReport') else 'runtime_record'
            if a['trust']!=wanted_trust:err('artifact_provenance')
            for e in structural(a['data'], ref['kind']): err('artifact_schema:'+e)
            if a['data'].get('task_id', q['task_id']) != q['task_id']: err('record_task')
            return a['data']
        snap = resolve(q['task_snapshot'])
        f = resolve(q['inputs']['failure']); view = resolve(q['inputs']['platform_view'])
        ledger = resolve(q['inputs']['ledger']); outcome = resolve(q['inputs']['outcome'])
        if any(x is None for x in (snap, f, view, ledger)): return done()
        plan = r['data']
        if plan is None: err('plan_required'); return done()
        strategy = plan['strategy']; steps = plan['next_steps']
        active = strategy in ('reobserve','relocalize','reversible_explore','check_records')
        if len(steps)>1: err('one_current_step')
        if strategy=='stop' and steps: err('stop_has_steps')
        if strategy=='ask_user' and (not r['questions'] or r['status']!='needs_user'): err('ask_user_question')
        if any(i['retryable'] for i in r['issues']): err('automatic_retry_forbidden')
        if r['status'] in ('blocked','failed') and active: err('blocked_active_plan')
        if snap['task_revision']!=q['expected_task_revision'] or snap['mode']!=q['mode']: err('snapshot_binding')
        if view['platform_key']!=h['platform_key'] or view['environment']!=h['environment']: err('platform_binding')
        changed = (h['current_revision']!=q['expected_task_revision'] or h['mode']!=q['mode'] or
                   h['target_item_ref']!=snap['target_item_ref'] or h['page_revision']!=h['planned_page_revision'] or
                   h['observation_id']!=h['planned_observation_id'])
        if changed: err('plan_invalidated')
        if (snap['paused'] or h['paused']) and (strategy!='stop' or r['status']!='blocked'): err('pause_stop')
        b=snap['remaining_budget']; current=h['remaining_budget']
        if active and (min(b['actions'],current['actions'])<=0 or min(b['recovery_attempts'],current['recovery_attempts'])<=0 or
                       min(instant(b['deadline_at']),instant(current['deadline_at']))<=instant(h['now'])): err('budget_exhausted')
        if active and (h['expected_cost']['actions']>current['actions'] or h['expected_cost']['recovery_attempts']>current['recovery_attempts'] or
                       h['expected_cost']['milliseconds']> (instant(current['deadline_at'])-instant(h['now'])).total_seconds()*1000): err('estimated_budget_exceeded')
        if active and h['history']['attempted'] and (not h['fresh_evidence_ids'] or
                (h['history']['same_path_failed'] and not h['history']['conditions_changed'])): err('no_progress')
        cited=list(plan['new_evidence_refs'])
        for step in steps: cited+=step['required_evidence']
        for issue in r['issues']: cited+=issue['evidence_refs']
        for eid in set(cited):
            e=h['evidence'].get(eid)
            if not e: err('missing_evidence:'+eid); continue
            if not e['accessible'] or e['task_id']!=q['task_id'] or e['account_ref']!=h['account_ref']: err('evidence_scope')
            if instant(e['captured_at'])>instant(h['now']) or instant(e['valid_until'])<instant(h['now']): err('evidence_time')
            if eid in plan['new_evidence_refs'] and (eid not in h['fresh_evidence_ids'] or e['fingerprint'] in h['history']['evidence_fingerprints']): err('not_new_evidence')
        if active and h['history']['attempted'] and not plan['new_evidence_refs']: err('missing_new_basis')
        receipt=None
        if f['execution_ref']:
            ref=h['execution_index'].get(f['execution_ref'])
            if ref: receipt=resolve(ref)
            else: err('execution_unresolved')
        # Do not infer action or dispatch status from an exception or receipt absence.
        if receipt:
            p=h['proposals'].get(receipt['proposal_id'])
            if not p: err('proposal_unresolved')
            else:
                for e in structural(p['action'],'Action'): err('proposal_schema:'+e)
                if p['action']['task_id']!=q['task_id'] or p['action']['target_item_ref']!=snap['target_item_ref'] or p['payload_digest']!=receipt['action_payload_digest']: err('proposal_binding')
            if receipt['execution_id']!=f['execution_ref'] or receipt['target_item_ref']!=snap['target_item_ref']:err('receipt_binding')
        for event in ledger['events']:
            if event['execution_ref'] and event['execution_ref'] not in h['execution_index']:err('ledger_execution_unresolved')
        started={x['execution_ref'] for x in ledger['events'] if x['event_type']=='dispatch_started'}
        possible = bool(started-set(h['reconciled_executions']) or snap['pending_execution_refs'] or h['pending_business_keys'] or
                        f['dispatch_state']!='not_sent' or (receipt and receipt['dispatch_state']!='not_sent'))
        conflict=bool(h['conflicts'] or (receipt and receipt['dispatch_state']!=f['dispatch_state']))
        assessment=h['assessment']
        if assessment not in ('not_sent','no_effect','unknown','success'): err('assessment_enum')
        if assessment in ('success','no_effect') and (not h['assessment_evidence_refs'] or not outcome or
                outcome['effect_result']!=('confirmed_success' if assessment=='success' else 'confirmed_failure')): err('assessment_not_proven')
        if assessment in ('success','no_effect'):
            binding=h['assessment_binding']
            if not receipt or binding['execution_id']!=receipt['execution_id'] or binding['proposal_id']!=receipt['proposal_id'] or binding['content_digest']!=receipt['action_payload_digest'] or not binding['all_parts']:err('assessment_binding')
        for eid in h['assessment_evidence_refs']:
            if eid not in h['evidence'] or not h['evidence'][eid]['accessible'] or h['evidence'][eid]['task_id']!=q['task_id']: err('assessment_evidence')
        if assessment=='not_sent' and (possible or not h['history_complete'] or not h['not_sent_proof']): err('not_sent_not_proven')
        unresolved=conflict or assessment=='unknown' or (possible and assessment not in ('success','no_effect')) or bool(h['pending_business_keys'])
        if unresolved:
            if strategy not in ('check_records','ask_user','handoff','stop'): err('unknown_must_check_records')
            if any(s['next_skill_hint']!='aftercare-verify' for s in steps) and strategy=='check_records': err('unknown_route_verify')
            if strategy=='check_records' and not h['query_available']: err('query_unavailable')
            if active and plan['failure_class']!='ambiguous_write': err('ambiguous_write_class')
        if assessment=='success' and not conflict and (strategy!='stop' or steps): err('success_no_recovery')
        if strategy in ('relocalize','reversible_explore'):
            if not h['target_confirmed'] or not h['recipient_confirmed'] or not h['scope_allowed']: err('target_scope')
            if not h['current_page_complete'] or h['dom_visual_conflict'] or h['loading']: err('page_uncertain')
            if not h['fresh_evidence_ids'] or not plan['new_evidence_refs']:err('fresh_observation_required')
            if not h['adapter_available'] or not h['control_unique']: err('adapter_or_ambiguity')
        if strategy=='reversible_explore':
            rev=h['reversibility']
            if rev['effect']!='read_only' or rev['data_loss']!='none' or not rev['evidence_refs'] or not rev['postcondition']: err('reversibility_not_proven')
            if any(x not in h['evidence'] for x in rev['evidence_refs']): err('reversibility_evidence')
        if h['business_gap'] and strategy not in ('ask_user','handoff','stop'): err('business_not_ui')
        if h['user_changed_goal'] and strategy not in ('ask_user','handoff','stop'): err('respect_user_change')
        if h['login_required'] and (strategy not in ('ask_user','stop') or r['status'] not in ('needs_user','blocked')):err('login_user_only')
        if h['unsupported'] and strategy not in ('handoff','stop'):err('unsupported_stop')
        if strategy=='handoff' and not h['unresolved_questions']:err('handoff_details')
        return done()
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        err('host_context_invalid:'+str(exc)); return done()

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(); p.add_argument('request'); p.add_argument('result'); p.add_argument('host')
    a=p.parse_args()
    data=[json.loads(Path(x).read_text(encoding='utf-8-sig')) for x in (a.request,a.result,a.host)]
    result=check(*data); print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(bool(result['errors']))
