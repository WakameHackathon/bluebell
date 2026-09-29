"""Pure partial semantic checker. No I/O except loading the bundled schema.
Host witnesses are NOT wire fields, authenticated facts, locks or permissions.
All external execution remains disabled; no database/browser/skill calls.
"""
import json
from datetime import datetime
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / 'references/resume.schema.json').read_text(encoding='utf-8'))

def structural(value, name):
    schema = {'$schema': SCHEMA['$schema'], '$defs': SCHEMA['$defs'], '$ref': '#/$defs/' + name}
    return [e.message for e in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value)]

def instant(value):
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('timezone required')
    return d

def check(q, r, h):
    errors = ['request:' + e for e in structural(q, 'aftercare-resumeRequest')]
    errors += ['result:' + e for e in structural(r, 'aftercare-resumeResult')]
    blockers = []
    disposition = 'hold'
    def error(code):
        if code not in errors:
            errors.append(code)
    def block(code):
        if code not in blockers:
            blockers.append(code)
    def finish():
        return {'errors': errors, 'blockers': blockers,
                'planning_disposition': 'hold' if errors or blockers else disposition,
                'automatic_execution_allowed': False}
    if errors:
        return finish()
    try:
        for k in ('contract_version', 'skill_id', 'task_id', 'call_id'):
            if q[k] != r[k]: error('response_binding:' + k)
        if q['skill_version'] != '1.0.0': error('skill_version')
        if r['based_on_task_revision'] != q['expected_task_revision']: error('result_revision')
        if q['expected_task_revision'] != h['current_revision']: block('task_revision_changed')
        if q['mode'] != h['mode']: block('mode_changed')
        if h['record_health'] != 'ok': block('history_' + h['record_health'])
        if not h['runtime_ready']: block('runtime_binding_gap')
        if not h['history_complete']: block('history_incomplete')
        if h['write_inflight']: block('task_mutex')
        if h['request_epoch'] != h['current_epoch']: block('lease_changed')
        if h['user_request']['task_id'] != q['task_id'] or h['user_request']['source'] != 'user_event':
            block('task_not_selected')
        purpose = h['user_request']['purpose']
        if purpose not in ('continue', 'view', 'stop'): block('resume_intent_unknown')
        def resolve(ref):
            a = h['registry'].get(ref['artifact_id'])
            if not a:
                block('missing_record'); return None
            if any(a[k] != ref[k] for k in ('kind', 'revision')): error('reference_binding')
            if a['task_id'] != q['task_id']: error('reference_task')
            if not a['accessible']:
                block('record_access_denied'); return None
            trust = 'runtime_record' if ref['kind'] in ('TaskSnapshot', 'OperationLedger') else 'untrusted_skill_output'
            if a['trust'] != trust: error('record_provenance')
            for e in structural(a['data'], ref['kind']): error('record_schema:' + e)
            return a['data']
        current = resolve(q['task_snapshot'])
        saved = resolve(q['inputs']['saved_task'])
        view = resolve(q['inputs']['platform_view'])
        outcome = resolve(q['inputs']['current_outcome'])
        ledger = resolve(q['inputs']['ledger'])
        p = r['data']
        if p is None:
            error('plan_required'); return finish()
        if not all((current, saved, view, outcome, ledger)):
            if r['status'] == 'completed' or p['next_steps'] or p['confirmed_target_item_ref'] or p['latest_outcome_ref']:
                error('missing_context_claim')
            return finish()
        if errors: return finish()
        if current['task_revision'] != q['expected_task_revision'] or current['mode'] != q['mode']:
            error('current_snapshot_binding')
        if current['task_id'] != q['task_id'] or saved['task_id'] != q['task_id'] or ledger['task_id'] != q['task_id']:
            error('record_body_task')
        if q['inputs']['saved_task'] not in h['ancestors']: block('history_lineage_unknown')
        # Artifact, task, ledger and page revisions deliberately remain separate.
        if ledger['ledger_revision'] != h['ledger_revision']: block('ledger_changed')
        if current['paused'] or h['paused']: block('user_paused')
        identity = h['identity']
        identity_ok = all(identity['saved'][k] == identity['current'][k] for k in ('platform', 'account', 'order', 'item', 'case'))
        identity_ok = identity_ok and identity['current_page_bound'] and identity['unique_item']
        identity_ok = identity_ok and view['platform_key'] == identity['current']['platform']
        if not identity_ok: block('identity_unresolved')
        selection = h['selection']
        target_ok = (identity_ok and selection['valid'] and selection['source'] == 'user_event'
                     and selection['task_id'] == q['task_id'] and selection['item_ref'] == current['target_item_ref']
                     and selection['receipt_ref'] == current['selection_receipt_ref']
                     and current['target_item_ref'] == identity['current']['item'])
        if not target_ok: block('target_unconfirmed')
        if p['confirmed_target_item_ref'] is not None and (not target_ok or p['confirmed_target_item_ref'] != current['target_item_ref']):
            error('invented_target_confirmation')
        if target_ok and r['status'] == 'completed' and p['confirmed_target_item_ref'] != current['target_item_ref']:
            error('missing_confirmed_target')
        binding = h['outcome_binding']
        outcome_ok = (identity_ok and binding['ref'] == q['inputs']['current_outcome']
                      and binding['platform_view_ref'] == q['inputs']['platform_view']
                      and binding['producer_skill'] == 'aftercare-verify' and binding['accepted']
                      and binding['task_id'] == q['task_id'] and binding['identity'] == identity['current']
                      and binding['observation_id'] == h['observation_id']
                      and binding['page_revision'] == h['page_revision']
                      and instant(binding['captured_at']) <= instant(h['now']) <= instant(binding['valid_until'])
                      and not binding['cached'] and bool(outcome['evidence_refs']))
        for eid in outcome['evidence_refs']:
            e = h['evidence'].get(eid)
            if not e or not e['accessible'] or e['task_id'] != q['task_id'] or e['identity'] != identity['current']:
                outcome_ok = False
            elif e['observation_id'] != h['observation_id'] or e['page_revision'] != h['page_revision']:
                outcome_ok = False
        if not outcome_ok: block('outcome_unusable')
        if p['latest_outcome_ref'] is not None and (not outcome_ok or p['latest_outcome_ref'] != q['inputs']['current_outcome']['artifact_id']):
            error('invalid_latest_outcome')
        if outcome_ok and r['status'] == 'completed' and p['latest_outcome_ref'] != q['inputs']['current_outcome']['artifact_id']:
            error('missing_latest_outcome')
        # A verified event by itself cannot clear a possible send.
        pending = set(current['pending_execution_refs']) | set(saved['pending_execution_refs'])
        pending |= {e['execution_ref'] for e in ledger['events'] if e['event_type'] in ('dispatch_started', 'tool_returned') and e['execution_ref']}
        pending |= set(h['possible_execution_refs'])
        reconciled = set()
        for record in h['reconciliations']:
            if (outcome_ok and record['outcome_ref'] == q['inputs']['current_outcome']
                and record['association'] == 'exact' and record['host_verified']
                and record['identity'] == identity['current'] and record['evidence_refs']
                and set(record['evidence_refs']).issubset(outcome['evidence_refs'])):
                reconciled.add(record['execution_ref'])
        if pending - reconciled: block('unresolved_dispatch')
        if h['conflicts']: block('evidence_conflict')
        if h['goal_changed']: block('goal_changed')
        if not h['remedy_valid']: block('remedy_changed')
        if not h['materials_valid']: block('materials_changed')
        changes = {c['field']: c for c in h['changes']}
        if len(changes) != len(h['changes']): error('duplicate_host_change')
        reported = [m['field'] for m in p['mismatches']]
        if len(set(reported)) != len(reported): error('duplicate_mismatch')
        # Required host-known differences must be covered. A model can notice an
        # additional difference; its cited evidence is checked below, while its
        # meaning still needs host/human semantic review. Do not require exact wording.
        if not set(changes).issubset(reported): error('comparison_coverage')
        for m in p['mismatches']:
            if m['field'] in changes:
                c = changes[m['field']]
                for k in ('previous_evidence_ref', 'current_evidence_ref'):
                    if m[k] != c[k]: error('mismatch_evidence_binding')
        cited = [e for m in p['mismatches'] for e in (m['previous_evidence_ref'], m['current_evidence_ref']) if e]
        cited += [e for s in p['next_steps'] for e in s['required_evidence']]
        cited += [e for issue in r['issues'] for e in issue['evidence_refs']]
        for eid in cited:
            ev = h['evidence'].get(eid)
            if not ev or ev['task_id'] != q['task_id'] or not ev['accessible']: error('citation_unavailable')
        if len(p['next_steps']) > 1: error('multi_step_chain')
        hints = [s['next_skill_hint'] for s in p['next_steps']]
        if any(hint not in h['allowed_next_skills'] for hint in hints): error('unsupported_handoff')
        if any(hint == 'aftercare-interact' for hint in hints) and blockers: error('blocked_business_progression')
        if blockers and r['status'] == 'completed': error('unresolved_completed')
        if purpose in ('view', 'stop') or current['paused'] or h['paused']:
            if p['next_steps']: error('no_continuation_requested')
        if outcome_ok and outcome['case_terminal'] and p['next_steps']: error('terminal_new_steps')
        if outcome_ok and outcome['platform_state'] == 'rejected' and outcome['user_todos'] and outcome['case_terminal']:
            error('appeal_not_terminal')
        # Current state alone cannot establish receipt of money or any action attribution.
        if h['replay_requested']:
            block('historical_proposal_replay')
            if r['status'] == 'completed': error('replay_marked_completed')
        if r['status'] != 'completed' and 'aftercare-interact' in hints: error('noncompleted_interact')
        disposition = 'review_only' if purpose in ('view', 'stop') or q['mode'] != 'auto' or outcome['case_terminal'] else 'eligible_for_host_review'
        return finish()
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        error('host_context_invalid:' + str(exc))
        return finish()
