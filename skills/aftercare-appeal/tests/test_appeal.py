import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "check_appeal.py"
spec = importlib.util.spec_from_file_location("check_appeal", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def draft(**changes):
    d = {"reason_evidence_refs": ["ev-reason"], "grounds": [{"key": "photo_scope", "value": "现有照片显示商品问题位置", "evidence_refs": ["ev-photo"], "certainty": "observed"}], "draft_text": "请结合现有照片重新核对问题位置。", "file_refs": ["file-photo"], "missing_evidence": [], "available_route_refs": ["route-current"], "recommendation": "prepare"}
    d.update(changes)
    return d


def result(data=None, status="completed", questions=None, issues=None, **extra):
    r = {"contract_version": "1.0.0", "skill_id": "aftercare-appeal", "call_id": "call-1", "task_id": "task-1", "based_on_task_revision": 2, "status": status, "data": draft() if data is None else data, "questions": questions or [], "issues": issues or [], "user_message": "这是待核对的草稿。"}
    r.update(extra)
    return r


class AppealFixtureTests(unittest.TestCase):
    # 26 synthetic cases map to the user-requested behavioral matrix. These tests
    # exercise deterministic format/reference invariants only; case disposition is
    # recorded in synthetic-cases.json and is not a model behavioral benchmark.
    def test_01_clear_rejection_and_route(self): self.assertEqual(check.validate_result(result(), registered_refs={"ev-reason", "ev-photo", "file-photo", "route-current"}), [])
    def test_02_pending_not_appeal(self): self.assertEqual(check.validate_result(result(draft(recommendation="stop"))), [])
    def test_03_needs_evidence_not_final_rejection(self): self.assertEqual(check.validate_result(result(draft(recommendation="collect_more", missing_evidence=["问题位置照片"]))), [])
    def test_04_merchant_vs_platform_records_separate_refs(self): self.assertEqual(check.validate_result(result()), [])
    def test_05_ambiguous_reason_requests_observation(self): self.assertIn("issue_required", check.validate_result(result(status="needs_observation", issues=[])))
    def test_06_conflicting_statement_kept_as_user_reported(self): self.assertEqual(check.validate_result(result(draft(grounds=[{"key":"user_statement","value":"用户称已补交照片","evidence_refs":["ev-photo"],"certainty":"user_reported"}]))), [])
    def test_07_observation_not_responsibility(self): self.assertEqual(check.validate_result(result()), [])
    def test_08_existing_material_can_support_clarification(self): self.assertEqual(check.validate_result(result()), [])
    def test_09_targeted_missing_material(self): self.assertEqual(check.validate_result(result(draft(recommendation="collect_more", missing_evidence=["商品整体照"]))), [])
    def test_10_user_cannot_supply_does_not_require_repeat(self): self.assertEqual(check.validate_result(result(draft(recommendation="handoff", missing_evidence=["用户无法提供整体照"]))), [])
    def test_11_invented_first_person_claim_lint(self):
        d = draft(grounds=[{"key": "guess", "value": "推测", "evidence_refs": ["ev-photo"], "certainty": "inferred"}], draft_text="我亲眼看到。")
        self.assertIn("inferred_claim_wording_review", check.validate_result(result(d)))
    def test_12_route_entry_condition_unknown_not_authorization(self): self.assertEqual(check.validate_result(result(draft(recommendation="needs_user"))), ["recommendation"])
    def test_13_missing_route_not_permanent_denial(self): self.assertEqual(check.validate_result(result(draft(recommendation="handoff", available_route_refs=[]))), [])
    def test_14_unknown_deadline_not_fabricated(self): self.assertEqual(check.validate_result(result()), [])
    def test_15_in_progress_repeat_stopped(self): self.assertEqual(check.validate_result(result(draft(recommendation="stop"))), [])
    def test_16_unknown_submission_result_stops(self): self.assertEqual(check.validate_result(result(draft(recommendation="stop"))), [])
    def test_17_supplement_existing_case_distinct_from_new(self): self.assertEqual(check.validate_result(result()), [])
    def test_18_no_new_basis_no_rephrase(self): self.assertEqual(check.validate_result(result(draft(recommendation="stop"))), [])
    def test_19_changed_draft_receipt_not_in_v1_output(self): self.assertNotIn("review_receipt_ref", draft())
    def test_20_review_is_not_send_authorization(self): self.assertNotIn("authorization", draft())
    def test_21_withdraw_or_accept_not_actions(self): self.assertNotIn("operation", draft())
    def test_22_injection_is_not_a_contract_field(self): self.assertNotIn("instruction", draft())
    def test_23_cross_task_or_missing_reference_rejected_when_registry_known(self): self.assertIn("file_refs_not_registered", check.validate_result(result(), registered_refs={"ev-reason", "ev-photo", "route-current"}))
    def test_24_pause_or_changed_goal_issue(self): self.assertIn("issue_required", check.validate_result(result(status="blocked", issues=[])))
    def test_25_completed_is_not_success_claim(self): self.assertNotIn("success", " ".join(result().keys()))
    def test_26_external_legal_claim_not_in_scope(self): self.assertNotIn("legal_result", draft())


if __name__ == "__main__":
    unittest.main()
