"""Pure offline checks. Host context is a TEST/INTEGRATION API, never wire input.
Witness claims must come from an independently checked adapter/host, not this report.
No browser, storage, network, retry, or authorization functionality.
"""
import json
from pathlib import Path
from datetime import datetime
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA = json.loads((Path(__file__).resolve().parents[1]/'references/verify.schema.json').read_text(encoding='utf-8'))

def structural(value, name):
    schema = {'$schema': SCHEMA['$schema'], '$defs': SCHEMA['$defs'], '$ref': '#/$defs/'+name}
    return [e.message for e in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value)]

def instant(s):
    d = datetime.fromisoformat(s.replace('Z', '+00:00'))
    if d.tzinfo is None: raise ValueError('timezone required')
    return d

def check(q, r, h):
    """Return diagnostics; empty errors are NOT permission or proof of business truth.
    h: registry of immutable central artifacts, evidence registry with host witnesses,
    current_revision, target_item_ref, case_ref, account_ref, platform_key,
    observation_id/page_revision, now, proposals (Action+digest), target,
    pending_business_keys, conflicts, adapter_supported, history_complete.
    Caller authenticates all h fields. Missing h fails closed.
    """
    errors = ['request:'+e for e in structural(q,'aftercare-verifyRequest')]
    errors += ['result:'+e for e in structural(r,'aftercare-verifyResult')]
    if errors: return {'errors':errors,'hold_external_write':True}
    def err(x):
        if x not in errors: errors.append(x)
    try:
        for k in ('call_id','task_id','contract_version','skill_id'):
            if q[k] != r[k]: err('response_binding:'+k)
        if q['skill_version']!='1.0.0':err('unsupported_skill_version')
        if q['expected_task_revision'] != h['current_revision'] or r['based_on_task_revision']!=h['current_revision']:err('task_revision')
        def resolve(ref):
            if ref is None:return None
            a=h['registry'].get(ref['artifact_id'])
            if not a:err('missing_ref:'+ref['artifact_id']); return None
            if any(a[k]!=ref[k] for k in ('kind','revision')):err('artifact_binding')
            if a['task_id']!=q['task_id'] or not a['accessible']:err('artifact_scope')
            runtime=ref['kind']!='PlatformView'
            if a['trust']!=('runtime_record' if runtime else 'untrusted_skill_output'):err('artifact_trust')
            for e in structural(a['data'],ref['kind']):err('artifact_schema:'+e)
            return a['data']
        snap=resolve(q['task_snapshot']); view=resolve(q['inputs']['platform_view'])
        receipt=resolve(q['inputs']['receipt']); ledger=resolve(q['inputs']['ledger'])
        if not all((snap,view,ledger)):return {'errors':errors,'hold_external_write':True}
        if snap['task_id']!=q['task_id'] or ledger['task_id']!=q['task_id']:err('record_task')
        if snap['task_revision']!=h['current_revision'] or snap['mode']!=q['mode']:err('snapshot_revision_mode')
        if snap['target_item_ref']!=h['target_item_ref'] or h['target_item_ref'] is None:err('target_binding')
        if view['platform_key']!=h['platform_key']:err('platform_binding')
        target=h.get('target')
        action=None
        if receipt:
            if receipt['task_id']!=q['task_id'] or receipt['target_item_ref']!=h['target_item_ref']:err('receipt_binding')
            p=h['proposals'].get(receipt['proposal_id'])
            if p:
                action=p['action']
                for e in structural(action,'Action'):err('proposal_schema:'+e)
                if action['proposal_id']!=receipt['proposal_id'] or action['task_id']!=q['task_id'] or action['target_item_ref']!=receipt['target_item_ref'] or p['payload_digest']!=receipt['action_payload_digest']:err('proposal_binding')
                if target and target['proposal_id']!=receipt['proposal_id']:err('verification_target_binding')
        report=r['data']
        if report is None:err('outcome_required');return {'errors':errors,'hold_external_write':True}
        usable=[]
        # Check every output citation, not only the union used for data claims.
        cited=list(report['evidence_refs'])
        for issue in r['issues']:cited+=issue['evidence_refs']
        for todo in report['user_todos']:cited+=todo['required_evidence']
        for ref in set(cited):
            e=h['evidence'].get(ref)
            if not e:err('missing_evidence:'+ref);continue
            ok=True
            for k,want in [('task_id',q['task_id']),('item_ref',h['target_item_ref']),('case_ref',h['case_ref']),('account_ref',h['account_ref'])]:
                if e[k]!=want:err('evidence_binding:'+k);ok=False
            if not e['accessible'] or instant(e['valid_until'])<instant(h['now']):err('expired_or_denied_evidence');ok=False
            if instant(e['captured_at'])>instant(h['now']):err('future_evidence');ok=False
            if e['source']=='platform':
                if e['observation_id']!=h['observation_id'] or e['page_revision']!=h['page_revision']:err('stale_observation');ok=False
                if not e['official'] or not e['complete']:err('page_identity_or_incomplete');ok=False
            if ok and ref in report['evidence_refs']:usable.append(e)
        platform=[e for e in usable if e['source']=='platform']
        # Conflict entries contain affected claim scopes; unrelated known claims can survive.
        def witnesses(key,value,evs):
            return [e for e in evs if e['claims'].get(key)==value and key not in h['conflicts']]
        if report['platform_state']!='unknown':
            if not h['adapter_supported'] or not witnesses('platform_state',report['platform_state'],platform):err('unsupported_platform_claim')
        effect=report['effect_result']
        matching=[]
        if target:
            for e in platform:
                effect_claim=e['claims'].get('effect')
                if not effect_claim:continue
                after=target.get('after_at')
                if not after or instant(e['captured_at'])<=instant(after):continue
                # A newly observed OLD record cannot establish attribution.
                if effect_claim.get('target_id')!=target['target_id'] or effect_claim.get('association')!='exact':continue
                if effect_claim.get('content_digest')!=target['content_digest']:continue
                if effect_claim.get('business_key')!=target['business_key']:continue
                if target['actor']=='agent' and (not receipt or not action):continue
                if effect_claim.get('all_parts') is not True:continue
                if 'effect' not in h['conflicts']:matching.append(e)
        if effect in ('confirmed_success','confirmed_failure'):
            if not h['adapter_supported'] or not any(e['claims']['effect']['result']==effect for e in matching):err('effect_not_proven')
        if effect=='not_attempted':
            if not (receipt and action and receipt['dispatch_state']=='not_sent' and receipt['tool_state']=='not_started' and h['history_complete'] and not h['pending_business_keys'] and not snap['pending_execution_refs']):err('not_attempted_not_proven')
        if report['stage_complete']:
            if not target or not target['stage_id'] or not any(e['claims'].get('stage_id')==target['stage_id'] for e in matching if e['claims']['effect']['result']=='confirmed_success'):err('stage_not_proven')
        terminal=report['business_result']
        finals=('refund_reported','final_rejection','user_withdrawn','other_final')
        if report['case_terminal']!=(terminal in finals):err('terminal_consistency')
        if terminal in finals:
            accepted=usable if terminal=='user_withdrawn' else platform
            if not witnesses('business_result',terminal,accepted):err('terminal_not_proven')
        arrival=report['actual_receipt_confirmed']
        if arrival!='unknown':
            # Central v1 lacks reliable source distinction: opt-in only in local proposed API.
            if not h.get('receipt_source_binding_enabled',False):err('receipt_source_contract_gap')
            eligible=[e for e in usable if e['source'] in ('user_statement','independent_receipt')]
            if not witnesses('actual_receipt_confirmed',arrival,eligible):err('arrival_not_proven')
        pending=bool(h['pending_business_keys'] or snap['pending_execution_refs'])
        # Ledger raw dispatch events remain pending unless host has verified reconciliation.
        dispatched={e['execution_ref'] for e in ledger['events'] if e['event_type']=='dispatch_started'}
        reconciled=set(h.get('reconciled_execution_refs',[]))
        pending=pending or bool(dispatched-reconciled)
        if effect=='confirmed_failure' and pending and h.get('other_unresolved_attempts',True):err('unresolved_other_attempts')
        if r['status']=='completed' and (not h['adapter_supported'] or h['conflicts']):err('unresolved_blocker')
        return {'errors':errors,'hold_external_write':bool(errors or pending or effect=='unknown')}
    except (KeyError,TypeError,ValueError) as e:
        err('host_context_invalid:'+str(e))
        return {'errors':errors,'hold_external_write':True}
