import json, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from routing import route
from validate_handoff import check
class ScenarioTests(unittest.TestCase):
 def test_24_synthetic_routes(self):
  rows=json.loads((ROOT/"tests"/"synthetic-scenarios.json").read_text(encoding="utf-8"))
  self.assertEqual(len(rows),24)
  for row in rows:
   with self.subTest(row["id"]): self.assertEqual(route(row["signals"]),row["expected"])
 def test_valid_empty_attachment_draft_and_status_boundaries(self):
  d={"official_channel_ref":None,"summary":"页面显示仍待处理；原因未知。","timeline_evidence_refs":["obs_1"],"unresolved_questions":["当前进度如何？"],"message_draft":"请帮我核实当前进度。","file_refs":[]}
  base={"contract_version":"1.0.0","skill_id":"aftercare-handoff","call_id":"c1","task_id":"t1","based_on_task_revision":2,"status":"completed","data":d,"questions":[],"issues":[],"user_message":"草稿尚未发送。"}
  self.assertEqual(check(base,["obs_1"]),[])
  reviewed=dict(base,status="needs_user",questions=[{"question_id":"q1","text":"重点准确吗？","choices":[]}])
  self.assertEqual(check(reviewed,["obs_1"]),[])
  self.assertTrue(check(base,["other_task_ref"]))
 def test_status_invariants(self):
  b={"contract_version":"1.0.0","skill_id":"aftercare-handoff","call_id":"c","task_id":"t","based_on_task_revision":0,"status":"needs_observation","data":None,"questions":[],"issues":[],"user_message":"需重新观察。"}
  self.assertTrue(check(b))
  b["issues"]=[{"code":"stale_observation","message":"入口过期","retryable":True,"evidence_refs":[]}]
  self.assertEqual(check(b),[])
if __name__=="__main__": unittest.main()
