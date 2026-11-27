"""Source-only safety guards for Windows GBrain WSL availability helper.

Does not execute PowerShell, schedule tasks or assert Windows runtime PASS.
"""
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "windows_gbrain_keepalive.ps1"


class WindowsGBrainKeepAliveContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_default_is_status_only(self):
        self.assertIn("[string]$Mode = 'Status'", self.source)
        self.assertIn("[ValidateSet('Status', 'Install', 'Remove')]", self.source)
        self.assertIn("switch ($Mode)", self.source)

    def test_isolated_user_task_and_opt_in_install(self):
        self.assertIn("AppFactory-GBrain-WSL-KeepAlive", self.source)
        self.assertIn("-AtLogOn -User $windowsUser", self.source)
        self.assertIn("-LogonType Interactive -RunLevel Limited", self.source)
        self.assertIn("if ($null -ne (Get-KeepAliveTask))", self.source)
        self.assertIn("throw", self.source)
        self.assertIn("Start-ScheduledTask -TaskName $taskName", self.source)
        self.assertIn("Unregister-ScheduledTask -TaskName $taskName", self.source)

    def test_no_privileged_worker_or_gbrain_mutation(self):
        for forbidden in [
            "AppFactoryAutopilot -Enable", "gbrain mcp expose --yes",
            "wsl --shutdown", "wsl --terminate", "tailscale funnel",
            "Start-Process -Verb RunAs", "Set-ExecutionPolicy",
            "Remove-Item", "gbrain auth", "curl -k",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.source)
        self.assertIn("/usr/bin/sleep infinity", self.source)
        self.assertIn("http://127.0.0.1:3131/health", self.source)

    def test_bounded_health_check(self):
        self.assertIn("$attempt -le 6", self.source)
        self.assertIn("--max-time 5", self.source)
        self.assertIn("ConvertFrom-Json", self.source)


if __name__ == "__main__":
    unittest.main()
