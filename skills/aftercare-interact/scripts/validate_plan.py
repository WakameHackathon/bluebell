"""Pure checks only. Host context is trusted input from an adapter, never model data.
No browser, file resolution, authentication, authorization issuance or dispatch.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / 'references/interact.schema.json').read_text(encoding='utf-8'))

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

def schema_errors(value, definition):
    schema = {'$schema': SCHEMA['$schema'], '$defs': SCHEMA['$defs'], '$ref': '#/$defs/' + definition}
    return [f'{definition}:{e.json_path}:{e.message}' for e in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value)]

def validate(request, result, host):
    """Fail closed on malformed host input; diagnostics are not execution permission."""
    errors = schema_errors(request, 'aftercare-interactRequest') + schema_errors(result, 'aftercare-interactResult')
    if errors:
        return errors
    try:
        return _validate(request, result, host)
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        return ['host_context_invalid:' + type(exc).__name__]

def _validate(q, r, h):
    e = []
    def check(ok, code):
        if not ok:
            e.append(code)
    for key in ('contract_version', 'skill_id', 'call_id', 'task_id'):
        check(q[key] == r[key], 'identity:' + key)
    check(q['skill_version'] == '1.0.0', 'skill_version')
    check(r['based_on_task_revision'] == q['expected_task_revision'], 'result_revision')
    p = r['data']
    if p is None:
        return e + ['interaction_plan_required']
    actions = p['actions']
    high = p['highlight_control_ref']
    check(len(actions) <= 1, 'one_minimal_action')
    check(not actions or r['status'] == 'completed', 'noncompleted_action')
    check(not p['refresh_required'] or (not actions and high is None), 'refresh_excludes_targets')
    check((p['presentation'] == 'propose_action') == bool(actions), 'presentation_actions')
    check(p['presentation'] != 'highlight' or high is not None, 'highlight_required')
    check(p['presentation'] != 'explain_only' or high is None, 'explanation_no_highlight')
    if q['mode'] == 'self':
        check(p['presentation'] == 'explain_only' and not actions and high is None, 'self_only_explains')
    if q['mode'] == 'guided':
        check(not actions, 'guided_no_actions')
    active = bool(actions or high)
    check(q['task_id'] == h['task_id'], 'host_task')
    # An explanatory blocked/stale result can be retained, but never drive stale controls.
    if active:
        check(q['expected_task_revision'] == h['task_revision'], 'stale_task')
        check(q['mode'] == h['mode'], 'mode_changed')
        check(not h['paused'], 'paused')
        check(h['remaining_actions'] > 0 and datetime.fromisoformat(h['now']) < datetime.fromisoformat(h['deadline']), 'budget')
        check(h['challenge'] is None, 'user_challenge')
        check(h['page_current'], 'page_changed')

    def ref(ref_id, kind=None, revision=None):
        obj = h['registry'].get(ref_id)
        if obj is None:
            e.append('missing_ref:' + str(ref_id)); return None
        check(obj['task_id'] == q['task_id'], 'cross_task_ref')
        check(obj['accessible'] and obj['current'], 'invalid_ref')
        check(kind is None or obj['kind'] == kind, 'ref_kind')
        check(revision is None or obj['revision'] == revision, 'ref_revision')
        return obj

    refs = [q['task_snapshot'], q['inputs']['platform_view']] + q['inputs']['source_artifacts']
    resolved = {}
    for obj in refs:
        found = ref(obj['artifact_id'], obj['kind'], obj['revision'])
        if found is not None:
            resolved[obj['artifact_id']] = found
            e.extend(schema_errors(found['data'], obj['kind']))
    if any(obj['artifact_id'] not in resolved for obj in refs):
        return e
    snap = resolved[q['task_snapshot']['artifact_id']]['data']
    view = resolved[q['inputs']['platform_view']['artifact_id']]['data']
    check(snap['task_id'] == q['task_id'] and snap['task_revision'] == q['expected_task_revision'] and snap['mode'] == q['mode'], 'snapshot_binding')
    check(view['platform_key'] == h['platform_key'] and view['environment'] == h['environment'], 'platform_identity')
    check(digest(q['inputs']['goal_step']) == h['step']['goal_digest'], 'step_binding')
    for ev in q['inputs']['goal_step']['required_evidence']:
        ref(ev, 'Evidence')
    for issue in r['issues']:
        for ev in issue['evidence_refs']:
            ref(ev, 'Evidence')
    if not active:
        return e
    check(not snap['paused'], 'snapshot_paused')
    check(not snap['pending_execution_refs'] and not h['pending_business'], 'verify_pending_first')

    def control(cid):
        matches = [x for x in view['controls'] if x['control_ref'] == cid]
        check(len(matches) == 1, 'control_not_unique')
        c = h['controls'].get(cid)
        if len(matches) != 1 or c is None:
            e.append('unregistered_control'); return None
        pc = matches[0]
        check(c['visible'] and c['enabled'] and not c['occluded'], 'control_not_operable')
        check(c['source'] in ('structure', 'visual') and bool(c['evidence_refs']), 'control_source')
        check(c['observation_id'] == pc['observation_id'] == h['observation_id'] and c['page_revision'] == pc['page_revision'] == h['page_revision'], 'stale_control')
        check(c['epoch'] == h['epoch'], 'takeover_invalidated')
        check(c['role'] == pc['semantic_role'] and c['label'] == pc['visible_label'], 'semantic_control')
        check(h['step']['control_refs'] == [cid], 'ambiguous_target')
        check(c['item_ref'] == snap['target_item_ref'], 'control_item')
        check(pc['effect'] == c['effect'], 'adapter_effect_conflict')
        for ev in c['evidence_refs'] + pc['evidence_refs']:
            ref(ev, 'Evidence')
        return c

    if high:
        control(high)
        check(h['highlight_clear'], 'highlight_covers_notice')
    for a in actions:
        c = control(a['control_ref'])
        if c is None:
            continue
        check(a['task_id'] == q['task_id'], 'action_task')
        check(a['target_item_ref'] == snap['target_item_ref'], 'action_item')
        check(a['observation_id'] == h['observation_id'] and a['page_revision'] == h['page_revision'], 'action_page')
        check(a['operation'] == h['step']['operation'] == c['operation'], 'operation_mismatch')
        check(a['operation'] in view['supported_operations'] and a['operation'] not in view['unsupported_operations'], 'unsupported')
        check(a['effect'] == c['effect'] and a['effect'] != 'unknown', 'effect_unverified')
        check(c['minimal'] and c['reversible'] if a['operation'] in ('navigate', 'expand') else c['minimal'], 'minimal_or_reversible')
        check(a['value_refs'] == h['step']['value_refs'], 'field_value_binding')
        check(len(a['value_refs']) <= 1, 'one_field_or_file')
        check(a['recipient_ref'] == h['step']['recipient_ref'] and a['material_content_ref'] == h['step']['material_content_ref'], 'content_binding')
        for ev in a['evidence_refs']:
            ref(ev, 'Evidence')
        check(set(c['evidence_refs']).issubset(a['evidence_refs']), 'effect_evidence')
        for value in a['value_refs']:
            obj = ref(value)
            if obj:
                check(obj['kind'] in ('Value', 'File') and obj['digest'] == h['step']['value_digests'][value], 'value_version')
                if obj['kind'] == 'File':
                    check(obj['purpose'] == 'upload' and obj['readable'] and obj['exists'], 'file_unusable')
        for need in h['step']['requirements']:
            check(h['readiness'].get(need) == 'valid', 'missing_business:' + need)
            kind = {'target':'OrderSelection', 'remedy':'RemedyPlan', 'evidence':'EvidenceBundle'}.get(need)
            artifacts = [resolved[x['artifact_id']]['data'] for x in q['inputs']['source_artifacts'] if x['kind'] == kind]
            if kind:
                check(len(artifacts) == 1, 'business_artifact:' + need)
            if len(artifacts) == 1:
                artifact = artifacts[0]
                if need == 'target':
                    check(artifact['selected_item_ref'] == a['target_item_ref'] and bool(artifact['selection_receipt_ref']), 'selection_missing')
                elif need == 'remedy':
                    check(bool(artifact['choice_receipt_ref']) and artifact['chosen_option_id'] in [x['option_id'] for x in artifact['options']], 'choice_missing')
                elif need == 'evidence':
                    check(bool(artifact['review_receipt_ref']) and all(x['state'] == 'met' for x in artifact['requirement_checks']), 'material_unreviewed')
                    if a['operation'] == 'attach':
                        selected = artifact['original_file_refs'] + [x['file_ref'] for x in artifact['derived_files']]
                        check(set(a['value_refs']).issubset(selected), 'file_not_in_bundle')
        if a['target_item_ref'] is None:
            check(h['step']['purpose'] == 'order_lookup' and a['operation'] in ('navigate', 'expand') and a['effect'] == 'read_only', 'target_unconfirmed')
        if a['effect'] == 'external_write':
            check(h['profile'] == 'synthetic-interact-test-v1', 'production_contract_gap')
            check(a['target_item_ref'] is not None, 'external_target')
            content = ref(a['material_content_ref'], 'Content')
            recipient = ref(a['recipient_ref'], 'Recipient')
            if content and recipient:
                detail = content['data']
                check(detail['item_ref'] == a['target_item_ref'] and detail['operation'] == a['operation'], 'critical_identity')
                check(detail['value_refs'] == a['value_refs'], 'critical_values')
                check(detail['recipient_ref'] == a['recipient_ref'] and recipient['endpoint'] == c['recipient_endpoint'], 'actual_recipient')
                check(content['digest'] == digest(detail), 'content_digest')
                check(detail['amount_state'] in ('known', 'not_applicable') and detail['fee_state'] in ('known', 'not_applicable') and bool(detail['consequences']), 'critical_details_missing')
                for name in ('amount', 'fee'):
                    if detail[name + '_state'] == 'known':
                        check(not schema_errors(detail[name], 'Money'), 'invalid_' + name)
                    elif detail[name + '_state'] == 'not_applicable':
                        check(detail[name] is None, 'inapplicable_' + name)
    return sorted(set(e))
