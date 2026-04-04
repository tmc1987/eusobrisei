import unittest

from agent.playbooks import classify_process, playbook_for


class PlaybookTests(unittest.TestCase):
    def test_classify_critical_service(self):
        cfg = {"processes": {"critical_names": ["sqlservr.exe"], "non_throttle_names": []}}
        self.assertEqual(classify_process("sqlservr.exe", cfg), "critical_service")

    def test_classify_protected_process(self):
        cfg = {"processes": {"critical_names": [], "non_throttle_names": ["SystemSettings.exe"]}}
        self.assertEqual(classify_process("SystemSettings.exe", cfg), "protected_process")

    def test_user_app_playbook_allows_restart_with_rollback(self):
        pb = playbook_for("user_app")
        self.assertIn("restart_process", pb["allowed_actions"])
        self.assertIn("Rollback", pb["rollback_by_action"]["throttle_top_cpu_process"])


if __name__ == "__main__":
    unittest.main()
