"""Offline, partial validator. Context is an untrusted test witness, not a wire API.
Never authorizes, executes, authenticates a source, mutates a ledger or calls skills.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / 'references/logistics.schema.json').read_text(encoding='utf-8'))
CONTEXT = json.loads((ROOT / 'references/context.schema.json').read_text(encoding='utf-8'))


def structural(value, name):
    schema = {'$defs': SCHEMA['$defs'], '$ref': '#/$defs/' + name}
    return [e.message for e in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value)]


def instant(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('timezone_required')
    return dt


def assess(q, h, snapshot):
    """Conservative disposition of synthetic/independently established host facts.
    This is NOT a platform parser or production decision engine.
    """
    f = h['facts']
    def d(status, stage, code, route=None):
        return dict(status=status, stage=stage, code=code, route=route)
    if snapshot['paused'] or h['paused']:
        return d('blocked', 'not_ready', 'user_paused')
    if q['mode'] != h['mode'] or q['expected_task_revision'] != h['current_revision']:
        return d('needs_observation', 'not_ready', 'stale_observation', 'aftercare-resume')
    if h['session_epoch'] != h['request_epoch'] or f['resuming']:
        return d('needs_observation', 'not_ready', 'stale_observation', 'aftercare-resume')
    if f['login_required']:
        return d('blocked', 'not_ready', 'needs_login')
    if not f['permission']:
        return d('blocked', 'not_ready', 'needs_consent')
    if not f['target_confirmed']:
        return d('blocked', 'not_ready', 'target_unconfirmed', 'aftercare-order')
    if not f['remedy_confirmed']:
        return d('needs_user', 'not_ready', 'missing_input', 'aftercare-remedy')
    # A missing receipt or incomplete history never proves no prior dispatch.
    if snapshot['pending_execution_refs'] or not f['history_complete'] or f['action_state'] in ('sent', 'unknown'):
        return d('needs_observation', 'problem', 'ambiguous_result', 'aftercare-verify')
    if f['page_changed'] or instant(h['now']) >= instant(h['observation_expires_at']):
        return d('needs_observation', 'not_ready', 'stale_observation', 'aftercare-recover')
    if f['conflict'] or f['address_conflict']:
        return d('needs_observation', 'problem', 'ambiguous_result', 'aftercare-verify')
    if f['requested_operation'] in ('cancel', 'reschedule'):
        return d('blocked', 'problem', 'unsupported', 'aftercare-handoff')
    if f['payment_page']:
        return d('blocked', 'not_ready', 'unsupported')
    if f['user_cannot_answer']:
        return d('needs_observation', 'not_ready', 'missing_input', 'aftercare-handoff')
    if f['remedy_kind'] == 'refund_only':
        return d('completed', 'not_ready', None)
    if f['remedy_kind'] != 'return_refund':
        return d('blocked', 'not_ready', 'unsupported', 'aftercare-remedy')
    if f['logistics_exception'] or f['deadline_state'] in ('expired', 'near'):
        return d('needs_observation', 'problem', 'policy_unknown', 'aftercare-verify')
    if f['shipping_state'] != 'none':
        if f['tracking_match'] != 'verified_return':
            return d('needs_user', 'tracking', 'missing_input')
        return d('completed', 'tracking', None)
    if f['action_state'] == 'booked':
        return d('completed', 'await_user_shipping', None)
    if f['return_allowed'] == 'no':
        return d('blocked', 'not_ready', 'policy_unknown', 'aftercare-verify')
    if f['return_allowed'] != 'yes' or f['deadline_state'] == 'unknown':
        return d('needs_observation', 'not_ready', 'missing_input', 'aftercare-verify')
    if not f['return_instructions'] or h['return_address_ref'] is None:
        return d('needs_observation', 'not_ready', 'missing_input', 'aftercare-verify')
    if f['method'] == 'unselected':
        return d('needs_user', 'not_ready', 'missing_input')
    if f['method'] == 'self_shipping':
        return d('blocked', 'await_user_shipping', 'contract_error')
    if not f['pickup_entry']:
        return d('blocked', 'not_ready', 'unsupported', 'aftercare-handoff')
    if h['pickup_address_ref'] is None or h['time_slot_ref'] is None or not f['service_selected'] or not f['package_selected']:
        return d('needs_user', 'prepare_pickup', 'missing_input')
    slot = h['objects'][h['time_slot_ref']]
    if instant(h['now']) >= instant(slot['expires_at']) or slot['page_revision'] != h['page_revision']:
        return d('needs_observation', 'prepare_pickup', 'stale_observation', 'aftercare-recover')
    if f['fee_kind'] in ('unknown', 'rule_only') or not f['extra_fees_resolved']:
        return d('needs_observation', 'prepare_pickup', 'policy_unknown', 'aftercare-verify')
    # v1 lacks two-address semantics and typed booking/waybill bindings.
    return d('blocked', 'prepare_pickup', 'contract_error')


def check(q, r, h):
    errors = ['request:' + x for x in structural(q, 'aftercare-logisticsRequest')]
    errors += ['result:' + x for x in structural(r, 'aftercare-logisticsResult')]
    errors += ['context:' + e.message for e in Draft202012Validator(CONTEXT, format_checker=FormatChecker()).iter_errors(h)]
    decision = None
    def err(code):
        if code not in errors:
            errors.append(code)
    def finish():
        return {'errors': errors, 'assessment': decision, 'automatic_execution_allowed': False,
                'hold_external_write': True, 'scope': 'offline_partial_checks'}
    if errors:
        return finish()
    try:
        for k in ('contract_version', 'skill_id', 'call_id', 'task_id'):
            if q[k] != r[k]: err('response_binding:' + k)
        if q['skill_version'] != '1.0.0': err('skill_version')
        if q['expected_task_revision'] != r['based_on_task_revision']: err('result_revision')
        now = instant(h['now'])
        if instant(h['observed_at']) > now: err('future_observation')
        if instant(h['observed_at']) >= instant(h['observation_expires_at']): err('observation_interval')

        def bound(a):
            for key, value in [('task_id', q['task_id']), ('item_ref', h['item_ref']), ('case_ref', h['case_ref']), ('account_ref', h['account_ref']), ('platform_key', h['platform_key'])]:
                if a[key] != value: err('reference_binding:' + key)
            if not a['accessible']: err('reference_permission')
        def resolve(ref):
            a = h['registry'].get(ref['artifact_id'])
            if a is None:
                err('reference_missing'); return None
            bound(a)
            if a['kind'] != ref['kind'] or a['revision'] != ref['revision']: err('reference_version_or_kind')
            if not a['current']: err('reference_stale')
            for x in structural(a['data'], ref['kind']): err('artifact_schema:' + x)
            return a['data']
        bodies = {'snapshot': resolve(q['task_snapshot'])}
        for key, ref in q['inputs'].items():
            bodies[key] = resolve(ref) if ref else None
        if errors: return finish()
        s, order, remedy = bodies['snapshot'], bodies['order'], bodies['remedy']
        if s['task_id'] != q['task_id'] or s['task_revision'] != q['expected_task_revision'] or s['mode'] != q['mode']: err('snapshot_binding')
        if s['target_item_ref'] != h['item_ref'] or order['selected_item_ref'] != h['item_ref']: err('target_binding')
        if s['remedy_ref'] != q['inputs']['remedy'] or s['outcome_ref'] != q['inputs']['outcome']: err('snapshot_artifacts')
        selected = [o for o in remedy['options'] if o['option_id'] == remedy['chosen_option_id']]
        if h['facts']['remedy_confirmed'] and (len(selected) != 1 or selected[0]['kind'] != h['facts']['remedy_kind'] or remedy['choice_receipt_ref'] is None): err('remedy_binding')
        if h['facts']['target_confirmed'] and (not order['selection_receipt_ref'] or s['selection_receipt_ref'] != order['selection_receipt_ref'] or h['item_ref'] not in [c['item_ref'] for c in order['candidates']]): err('selection_binding')
        if bodies['platform_view']['platform_key'] != h['platform_key']: err('platform_binding')
        if bodies['outcome']['platform_state'] != h['facts']['platform_state']: err('outcome_binding')

        def object_ref(ref, role=None):
            a = h['objects'].get(ref)
            if a is None:
                err('object_missing'); return None
            bound(a)
            if not a['current']: err('object_stale')
            if h['object_versions'].get(ref) != a['revision']: err('object_version_binding')
            if role and a['role'] != role: err('object_role:' + role)
            if instant(a['observed_at']) > now: err('object_future')
            # Time slots may be expired so assess can request a new observation.
            if a['role'] != 'time_slot' and now >= instant(a['expires_at']): err('object_expired')
            return a
        def walk(value):
            if isinstance(value, dict):
                for k, v in value.items():
                    if k in ('evidence_refs', 'required_evidence', 'scope_grant_refs', 'pending_execution_refs', 'related_artifact_refs'):
                        for ref in v:
                            if ref in h['registry']:
                                a = h['registry'][ref]; resolve({'artifact_id': ref, 'kind': a['kind'], 'revision': a['revision']})
                            else: object_ref(ref)
                    elif k.endswith('_ref') and isinstance(v, str): object_ref(v)
                    else: walk(v)
            elif isinstance(value, list):
                for v in value: walk(v)
        for body in bodies.values(): walk(body)
        for key, role in [('pickup_address_ref', 'pickup_address'), ('return_address_ref', 'return_address'), ('time_slot_ref', 'time_slot'), ('tracking_ref', 'tracking')]:
            if h[key]:
                a = object_ref(h[key], role)
                if a and role in ('pickup_address', 'return_address'):
                    if not a['verified']: err('address_unverified')
                    if role == 'return_address' and a['source'] != 'platform': err('return_address_source')
                if a and role == 'time_slot':
                    if instant(a['starts_at']) >= instant(a['ends_at']): err('slot_interval')
                    if instant(a['expires_at']) > instant(a['starts_at']): err('slot_validity')
        for ref in h['facts']['evidence_refs']: object_ref(ref, 'evidence')
        if not h['facts']['evidence_refs']: err('facts_without_source')
        if h['facts']['shipping_state'] != 'none' and h['facts']['tracking_match'] == 'verified_return':
            t = object_ref(h['tracking_ref'], 'tracking') if h['tracking_ref'] else None
            if not t or not t['verified'] or t['direction'] != 'return': err('tracking_witness_conflict')
        if bodies['user_decision']:
            u = bodies['user_decision']
            if u['task_id'] != q['task_id'] or u['based_on_task_revision'] != q['expected_task_revision']: err('decision_binding')
            if instant(u['recorded_at']) > now: err('decision_future')
            if h['time_slot_ref'] and u['selected_value_ref'] != h['time_slot_ref']: err('decision_slot')
        elif h['time_slot_ref']:
            err('missing_time_decision')
        if errors: return finish()
        decision = assess(q, h, s)
        p = r['data']
        if p is None:
            err('plan_required'); return finish()
        if r['status'] != decision['status'] or p['stage'] != decision['stage']: err('business_disposition')
        if decision['code'] and r['status'] != 'needs_user' and not any(i['code'] == decision['code'] for i in r['issues']): err('missing_issue')
        if p['address_ref'] is not None: err('v1_address_role_undefined')
        if p['time_slot_ref']:
            a = object_ref(p['time_slot_ref'], 'time_slot')
            if p['time_slot_ref'] != h['time_slot_ref'] or a is None or now >= instant(a['expires_at']) or a['page_revision'] != h['page_revision']: err('invalid_output_slot')
        if p['tracking_ref']:
            a = object_ref(p['tracking_ref'], 'tracking')
            if p['tracking_ref'] != h['tracking_ref'] or h['facts']['tracking_match'] != 'verified_return' or not a or not a['verified'] or a['direction'] != 'return': err('tracking_not_matched')
        if p['fee_known']:
            if h['facts']['fee_kind'] != 'confirmed' or p['fee'] is None or p['fee'] != h['fee']: err('fee_not_confirmed')
        elif p['fee'] is not None:
            err('unknown_fee_not_null')
        if p['fee_known'] != (p['fee'] is not None): err('fee_pair')
        # All v1 consumer writes remain disabled, even a completed tracking report.
        if any(x['next_skill_hint'] == 'aftercare-interact' for x in p['next_steps']): err('v1_handoff_not_ready')
        if any(i['retryable'] for i in r['issues']): err('no_automatic_retry')
        if s['paused'] and (p['next_steps'] or p['user_todos']): err('paused_has_steps')
        walk(p)
        for issue in r['issues']:
            for ref in issue['evidence_refs']: object_ref(ref, 'evidence')
    except (KeyError, TypeError, ValueError) as ex:
        err('invalid_context:' + type(ex).__name__)
    return finish()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('result', type=Path)
    parser.add_argument('context', type=Path)
    args = parser.parse_args()
    report = check(*(json.loads(p.read_text(encoding='utf-8-sig')) for p in (args.request, args.result, args.context)))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(bool(report['errors']))
