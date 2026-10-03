import os
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path
from typing import List, Optional


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "suggest_today_tasks.py"
FETCH_SCRIPT = ROOT / "scripts" / "gm_daily_memory_fetch_slack.py"
SLACK_SCRIPT = ROOT / "scripts" / "gm_today_slack.sh"


VALID_RESPONSE = """=== today_tasks.md ===
# 今日の優先候補

## 1. 有効候補を処理する
- 候補ID: active-1
- 目的: 承認済み候補を前に進める。
- 具体アクション: 必要な確認だけ行う。
- 完了条件: 確認結果を記録する。
- 所要目安: 30分
- 根拠: current_stateの承認済み候補。
- 今日行う理由: 本日の対象候補であるため。
- リスク注意: 未確定事項を確定扱いしない。



=== rationale.md ===
候補ID active-1 のみを採用した。
不足している前提情報: 特になし

=== deferred_tasks.md ===
候補外は後回し。
"""


def state_with(extra_blocks: str = "") -> str:
    return f"""# current_state

- approval_status: approved
- approved_by: test-human
- approved_at: 2099-01-01

## [active-1] 有効候補
- status: active
- title: 有効候補
- reason_today: 本日の対象候補であるため。
- basis: 架空の承認済み根拠。
- next_action: 架空の次アクション。

{extra_blocks}
"""


def load_fetch_module(tmp: Path):
    spec = importlib.util.spec_from_file_location("fetch_slack", FETCH_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.OUT_DIR = tmp
    module.STATE_FILE = tmp / ".last_progress_checkpoint.json"
    module.EVENTS_FILE = tmp / "progress_events.jsonl"
    module.LAST_SUCCESS_FILE = tmp / ".last_success.json"
    module.LEGACY_STATE_FILE = tmp / ".last_slack_ts"
    module.CHANNEL_ID = "CFAKE"
    module.TOKEN = "xoxb-fake"
    return module


class SuggestTodayTasksTest(unittest.TestCase):
    def run_script(self, tmp: Path, response: str, state: Optional[str], date: str = "2099-01-02", extra_args: Optional[List[str]] = None):
        out_root = tmp / "today_tasks"
        progress_root = tmp / "progress"
        sync_root = tmp / "daily_memory_sync"
        current_state = tmp / "current_state.md"
        mock_response = tmp / "response.md"
        progress_root.mkdir(exist_ok=True)
        sync_root.mkdir(exist_ok=True)
        mock_response.write_text(response, encoding="utf-8")
        if state is not None:
            current_state.write_text(state, encoding="utf-8")
        env = os.environ.copy()
        env.update(
            {
                "GM_TODAY_OUTPUT_ROOT": str(out_root),
                "GM_TODAY_PROGRESS_ROOT": str(progress_root),
                "GM_TODAY_DAILY_SYNC_ROOT": str(sync_root),
                "GM_TODAY_REVISION_ROOT": str(tmp / "revision"),
                "GM_TODAY_REVIEW_ROOT": str(tmp / "context_review"),
                "GM_TODAY_CURRENT_STATE": str(current_state),
            }
        )
        args = [
            sys.executable,
            str(SCRIPT),
            "--date",
            date,
            "--mock-response-file",
            str(mock_response),
        ]
        if extra_args:
            args.extend(extra_args)
        result = subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True)
        return result, out_root / date

    def test_completed_task_is_not_selectable(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            response = VALID_RESPONSE.replace("active-1", "done-1")
            state = state_with("""## [done-1] 完了済み
- status: completed
- title: 完了済み
""")
            result, _ = self.run_script(tmp, response, state)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("done-1", result.stdout)

    def test_stopped_task_is_not_selectable_after_seven_days(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            response = VALID_RESPONSE.replace("active-1", "stopped-1")
            state = state_with("""## [stopped-1] 停止済み
- status: stopped
- title: 停止済み
- stopped_at: 2098-12-01
""")
            result, _ = self.run_script(tmp, response, state, date="2099-01-10")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("stopped-1", result.stdout)

    def test_old_unapproved_proposal_is_not_an_allowed_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            review_dir = tmp / "context_review" / "latest"
            revision_dir = tmp / "revision" / "latest"
            review_dir.mkdir(parents=True)
            revision_dir.mkdir(parents=True)
            (review_dir / "review_notes.md").write_text("## [old-ai-idea]\n- status: active\n", encoding="utf-8")
            (revision_dir / "project_instruction_revised.md").write_text("## [old-ai-idea]\n- status: active\n", encoding="utf-8")
            response = VALID_RESPONSE.replace("active-1", "old-ai-idea")
            result, out_dir = self.run_script(tmp, response, state_with())
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((out_dir / "today_tasks.md").exists())

    def test_new_correction_conflict_blocks_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            response = VALID_RESPONSE.replace("active-1", "blocked-1")
            state = state_with("""## [blocked-1] 要確認候補
- status: active
- title: 要確認候補
- blocked_by: correction-2026-09-09
""")
            result, _ = self.run_script(tmp, response, state)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("blocked-1", result.stdout)

    def test_missing_current_state_is_input_failure(self):
        with tempfile.TemporaryDirectory() as d:
            result, _ = self.run_script(Path(d), VALID_RESPONSE, None)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("current_state is missing", result.stdout)

    def test_single_candidate_outputs_one_task(self):
        with tempfile.TemporaryDirectory() as d:
            result, out_dir = self.run_script(Path(d), VALID_RESPONSE, state_with())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            text = (out_dir / "today_tasks.md").read_text(encoding="utf-8")
            self.assertEqual(text.count("候補ID:"), 1)

    def test_same_day_cache_reuses_existing_output(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            first, out_dir = self.run_script(tmp, VALID_RESPONSE, state_with())
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            before = (out_dir / "today_tasks.md").read_text(encoding="utf-8")
            changed = VALID_RESPONSE.replace("有効候補を処理する", "変更後タイトル")
            second, _ = self.run_script(tmp, changed, state_with())
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            after = (out_dir / "today_tasks.md").read_text(encoding="utf-8")
            self.assertEqual(before, after)
            self.assertIn("cached", second.stdout)

    def test_missing_current_state_with_old_cache_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            out_dir = tmp / "today_tasks" / "2099-01-02"
            out_dir.mkdir(parents=True)
            (out_dir / "today_tasks.md").write_text("old cached task\n", encoding="utf-8")
            result, _ = self.run_script(tmp, VALID_RESPONSE, None)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("current_state is missing", result.stdout)

    def test_unapproved_current_state_with_cache_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            out_dir = tmp / "today_tasks" / "2099-01-02"
            out_dir.mkdir(parents=True)
            (out_dir / "today_tasks.md").write_text("old cached task\n", encoding="utf-8")
            draft = state_with().replace("approval_status: approved", "approval_status: draft")
            result, _ = self.run_script(tmp, VALID_RESPONSE, draft)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("approval_status must be approved", result.stdout)

    def test_valid_cache_requires_matching_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            first, out_dir = self.run_script(tmp, VALID_RESPONSE, state_with())
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            second, _ = self.run_script(tmp, VALID_RESPONSE.replace("有効候補", "別候補"), state_with())
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("cached", second.stdout)
            changed_state = state_with().replace("架空の承認済み根拠", "変更後の架空根拠")
            third, _ = self.run_script(tmp, VALID_RESPONSE, changed_state)
            self.assertNotEqual(third.returncode, 0)
            self.assertIn("Explicit regeneration is required", third.stdout)

    def test_slack_post_not_called_when_upstream_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            home = tmp / "home"
            bin_dir = tmp / "bin"
            home.mkdir()
            bin_dir.mkdir()
            (home / ".env_globalmedical").write_text("SLACK_WEBHOOK_URL=https://example.invalid/webhook\n", encoding="utf-8")
            curl_log = tmp / "curl_calls"
            fake_curl = bin_dir / "curl"
            fake_curl.write_text(f"#!/usr/bin/env bash\necho called >> {curl_log}\nexit 0\n", encoding="utf-8")
            fake_curl.chmod(0o755)
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "PATH": f"{bin_dir}:{env['PATH']}",
                    "GM_TODAY_OUTPUT_ROOT": str(tmp / "today_tasks"),
                    "GM_TODAY_PROGRESS_ROOT": str(tmp / "progress"),
                    "GM_TODAY_DAILY_SYNC_ROOT": str(tmp / "sync"),
                    "GM_TODAY_REVISION_ROOT": str(tmp / "revision"),
                    "GM_TODAY_REVIEW_ROOT": str(tmp / "review"),
                    "GM_TODAY_CURRENT_STATE": str(tmp / "missing_current_state.md"),
                }
            )
            (tmp / "progress").mkdir()
            (tmp / "sync").mkdir()
            result = subprocess.run([str(SLACK_SCRIPT)], cwd=ROOT, env=env, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(curl_log.exists())

    def test_fetch_keeps_three_same_day_progress_events(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            module = load_fetch_module(tmp)
            module.fetch_all_messages = lambda oldest="": (
                [
                    {"ts": "101.0", "text": "[GLMED_PROGRESS]\ndate: 2099-01-02\nwork A"},
                    {"ts": "102.0", "text": "[GLMED_PROGRESS]\ndate: 2099-01-02\nwork B"},
                    {"ts": "103.0", "text": "[GLMED_PROGRESS]\ndate: 2099-01-02\nwork C"},
                ],
                {"page_count": 1, "complete": True},
            )
            self.assertEqual(module.main([]), 0)
            events = (tmp / "progress_events.jsonl").read_text(encoding="utf-8").splitlines()
            daily = (tmp / "2099-01-02.gm_progress.md").read_text(encoding="utf-8")
            self.assertEqual(len(events), 3)
            self.assertIn("work A", daily)
            self.assertIn("work B", daily)
            self.assertIn("work C", daily)

    def test_fetch_deduplicates_retrieved_events(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            module = load_fetch_module(tmp)
            messages = ([{"ts": "101.0", "text": "[GLMED_PROGRESS]\ndate: 2099-01-02\nwork A"}], {"page_count": 1, "complete": True})
            module.fetch_all_messages = lambda oldest="": messages
            self.assertEqual(module.main([]), 0)
            self.assertEqual(module.main([]), 0)
            events = (tmp / "progress_events.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(events), 1)

    def test_fetch_paginates_without_dropping_posts(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            module = load_fetch_module(tmp)
            pages = [
                {"messages": [{"ts": "101.0", "text": "[GLMED_PROGRESS]\ndate: 2099-01-02\npage 1"}], "response_metadata": {"next_cursor": "next"}},
                {"messages": [{"ts": "102.0", "text": "[GLMED_PROGRESS]\ndate: 2099-01-02\npage 2"}], "response_metadata": {"next_cursor": ""}},
            ]

            def page(cursor="", oldest=""):
                return pages[1] if cursor else pages[0]

            module.api_history_page = page
            self.assertEqual(module.main([]), 0)
            events = (tmp / "progress_events.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(events), 2)

    def test_fetch_failure_does_not_advance_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            module = load_fetch_module(tmp)
            module.STATE_FILE.write_text('{"latest_complete_ts":"100.0"}\n', encoding="utf-8")
            module.fetch_all_messages = lambda oldest="": (_ for _ in ()).throw(RuntimeError("boom"))
            self.assertNotEqual(module.main([]), 0)
            data = module.STATE_FILE.read_text(encoding="utf-8")
            self.assertIn("100.0", data)

    def test_fetch_keeps_original_and_correction(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            module = load_fetch_module(tmp)
            module.fetch_all_messages = lambda oldest="": (
                [
                    {"ts": "101.0", "text": "[GLMED_PROGRESS]\ndate: 2099-01-02\noriginal work"},
                    {"ts": "104.0", "text": "[GLMED_PROGRESS]\ndate: 2099-01-03\ncorrection for original work"},
                ],
                {"page_count": 1, "complete": True},
            )
            self.assertEqual(module.main([]), 0)
            events = (tmp / "progress_events.jsonl").read_text(encoding="utf-8")
            self.assertIn("original work", events)
            self.assertIn("correction for original work", events)

    def test_sync_context_missing_only_is_not_business_progress_input(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            state = state_with()
            sync = tmp / "sync"
            sync.mkdir()
            (sync / "2099-01-02.md").write_text("[SYNC_CONTEXT_MISSING]\n", encoding="utf-8")
            result, out_dir = self.run_script(tmp, VALID_RESPONSE, state)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = (out_dir / "generation_manifest.json").read_text(encoding="utf-8")
            self.assertNotIn("2099-01-02.md", manifest)

    def test_valid_progress_mixed_with_missing_notice_is_kept(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            sync = tmp / "daily_memory_sync"
            sync.mkdir()
            (sync / "2099-01-02.md").write_text("[SYNC_CONTEXT_MISSING]\n", encoding="utf-8")
            (sync / "2099-01-02.gm_progress.md").write_text("# GLMED_PROGRESS\n\nvalid work\n", encoding="utf-8")
            result, out_dir = self.run_script(tmp, VALID_RESPONSE, state_with())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            snapshot = (out_dir / "inputs_snapshot.md").read_text(encoding="utf-8")
            self.assertIn("2099-01-02.gm_progress.md", snapshot)

    def test_missing_notice_mention_inside_progress_is_not_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            sync = tmp / "daily_memory_sync"
            sync.mkdir()
            (sync / "2099-01-02.gm_progress.md").write_text("normal progress mentions [SYNC_CONTEXT_MISSING]\n", encoding="utf-8")
            result, out_dir = self.run_script(tmp, VALID_RESPONSE, state_with())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            snapshot = (out_dir / "inputs_snapshot.md").read_text(encoding="utf-8")
            self.assertIn("2099-01-02.gm_progress.md", snapshot)

    def test_rejects_missing_status_unknown_status_and_duplicate_id(self):
        cases = [
            state_with("## [bad-1] statusなし\n- title: statusなし\n- basis: b\n- next_action: n\n"),
            state_with("## [bad-2] unknown\n- status: strange\n- title: unknown\n- basis: b\n- next_action: n\n"),
            state_with("## [active-1] duplicate\n- status: active\n- title: duplicate\n- basis: b\n- next_action: n\n"),
        ]
        for state in cases:
            with self.subTest(state=state):
                with tempfile.TemporaryDirectory() as d:
                    result, _ = self.run_script(Path(d), VALID_RESPONSE, state)
                    self.assertNotEqual(result.returncode, 0)

    def test_draft_template_is_rejected_as_production_input(self):
        with tempfile.TemporaryDirectory() as d:
            template = (ROOT / "outputs/current_state_setup/current_state_template.md").read_text(encoding="utf-8")
            result, _ = self.run_script(Path(d), VALID_RESPONSE, template)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("approval_status must be approved", result.stdout)

    def test_approved_state_with_zero_candidates_does_not_invent_tasks(self):
        with tempfile.TemporaryDirectory() as d:
            state = """# current_state

- approval_status: approved

## [done-1] 完了済み
- status: completed
- title: 完了済み
"""
            result, out_dir = self.run_script(Path(d), VALID_RESPONSE, state)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            text = (out_dir / "today_tasks.md").read_text(encoding="utf-8")
            self.assertIn("今日提示できる承認済み候補はありません", text)
            self.assertNotIn("候補ID:", text)


class CandidateListsTest(unittest.TestCase):
    """Offline end-to-end checks of priority selection and deterministic lists."""

    run_script = SuggestTodayTasksTest.run_script

    def response_for(self, ids):
        detail = VALID_RESPONSE.split("## 1.", 1)[1].split("=== rationale.md ===", 1)[0]
        priorities = "\n".join(f"## {i}." + detail.replace("active-1", task_id)
                                 for i, task_id in enumerate(ids, 1))
        return ("=== today_tasks.md ===\n# 今日の優先候補\n\n" + (priorities or "候補なし\n")
                + "\n=== rationale.md ===\n優先順位の根拠。\n=== deferred_tasks.md ===\n自動生成\n")

    def task(self, task_id, status="active", extra=""):
        return (f"## [{task_id}] {task_id}の作業\n- status: {status}\n"
                f"- basis: 承認済み根拠\n- next_action: 次の行動\n{extra}\n")

    def output(self, tmp, state, ids, date="2099-01-02"):
        result, out = self.run_script(tmp, self.response_for(ids), state, date)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = (out / "today_tasks.md").read_text()
        self.assertIn("上位3件は推奨順位です。すべてを今日完了する前提ではありません。", text)
        self.assertNotIn("今日やらないこと", text)
        return text, out

    def reminders(self, text):
        return text.split("# リマインド候補\n", 1)[1].split("# 状態更新待ち", 1)[0]

    def progress(self, tmp, text, date="2099-01-02"):
        sync = tmp / "daily_memory_sync"
        sync.mkdir(exist_ok=True)
        (sync / f"{date}.gm_progress.md").write_text(text)

    def test_seven_active_keeps_three_plus_four_without_loss(self):
        with tempfile.TemporaryDirectory() as d:
            state = state_with("\n".join(self.task(f"active-{i}") for i in range(2, 8)))
            text, _ = self.output(Path(d), state, ["active-1", "active-2", "active-3"])
            self.assertEqual(text.count("候補ID:"), 3)
            self.assertEqual(self.reminders(text).count("- ["), 4)
            for i in range(4, 8):
                self.assertIn(f"[active-{i}]", self.reminders(text))
            for field in ["目的:", "所要目安:", "リスク注意:"]:
                self.assertNotIn(field, self.reminders(text))

    def test_reminders_capped_at_ten_and_overflow_preserved_locally(self):
        with tempfile.TemporaryDirectory() as d:
            state = state_with("\n".join(self.task(f"active-{i}") for i in range(2, 17)))
            text, out = self.output(Path(d), state, ["active-1", "active-2", "active-3"])
            self.assertEqual(text.count("候補ID:"), 3)
            self.assertEqual(self.reminders(text).count("- ["), 10)
            self.assertIn("ほか3件", text)
            full = (out / "deferred_tasks.md").read_text()
            for i in range(4, 17):
                self.assertIn(f"[active-{i}]", full)

    def test_terminal_aliases_absent_from_all_daily_sections(self):
        statuses = ["completed", "stopped", "superseded", "replaced", "置換済み", "cancelled"]
        with tempfile.TemporaryDirectory() as d:
            state = state_with("\n".join(self.task(f"terminal-{i}", status)
                                         for i, status in enumerate(statuses)))
            text, out = self.output(Path(d), state, ["active-1"])
            self.assertNotIn("terminal-", text)
            self.assertNotIn("terminal-", (out / "deferred_tasks.md").read_text())

    def test_waiting_due_reminded_future_held_never_prioritized(self):
        with tempfile.TemporaryDirectory() as d:
            state = state_with(self.task("due-wait", "waiting", "- next_check: 2099-01-02")
                               + self.task("future-wait", "waiting", "- next_check: 2099-01-03"))
            text, _ = self.output(Path(d), state, ["active-1"])
            self.assertIn("[due-wait]", self.reminders(text))
            self.assertNotIn("future-wait", self.reminders(text))
            self.assertIn("[future-wait]", text.split("# 外部待ち・保留", 1)[1])
            for task_id in ["due-wait", "future-wait"]:
                result, _ = self.run_script(Path(d), self.response_for([task_id]), state, extra_args=["--force"])
                self.assertNotEqual(result.returncode, 0)

    def test_new_progress_conflicts_quarantined_without_state_mutation(self):
        for kind in ["completed", "correction", "waiting"]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as d:
                tmp = Path(d)
                self.progress(tmp, f"[GLMED_PROGRESS]\ndate: 2099-01-02\ntask_id: active-1\n"
                                   f"topic: 任意の名称\ntype: {kind}\nsummary: 最新の報告\nnext: 確認\n")
                state = state_with(self.task("active-2"))
                text, _ = self.output(tmp, state, ["active-2"])
                self.assertNotIn("active-1", text.split("# 状態更新待ち", 1)[0])
                pending = text.split("# 状態更新待ち", 1)[1]
                self.assertIn("task_id: active-1", pending)
                self.assertIn("current_stateの状態: active", pending)
                self.assertIn("最新の報告", pending)
                self.assertIn("推奨される状態変更案:", pending)
                self.assertEqual((tmp / "current_state.md").read_text(), state)

    def test_conflict_survives_context_age_and_long_log_truncation(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self.progress(tmp, "# GLMED_PROGRESS\n## 1. event\ntask_id: active-1\n"
                               "type: completed\nsummary: 終了済み\n\n## 2. other\n" + "長文" * 3000)
            text, _ = self.output(tmp, state_with(), [], date="2099-02-02")
            self.assertIn("task_id: active-1", text.split("# 状態更新待ち", 1)[1])
            self.assertNotIn("候補ID:", text)

    def test_older_progress_does_not_override_approved_state(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self.progress(tmp, "task_id: active-1\ntype: completed\nsummary: 過去\n", date="2099-01-01")
            text, _ = self.output(tmp, state_with(), ["active-1"])
            self.assertNotIn("task_id: active-1", text.split("# 状態更新待ち", 1)[1])

    def test_legacy_topic_exact_match_only_no_guessing(self):
        for topic, conflict in [("有効候補", True), ("有効候補らしい作業", False)]:
            with self.subTest(topic=topic), tempfile.TemporaryDirectory() as d:
                tmp = Path(d)
                self.progress(tmp, f"topic: {topic}\ntype: completed\nsummary: 報告\n")
                text, _ = self.output(tmp, state_with(), [] if conflict else ["active-1"])
                self.assertEqual("task_id: active-1" in text, conflict)

    def test_unknown_explicit_id_never_falls_back_to_topic(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self.progress(tmp, "task_id: unknown\ntopic: 有効候補\ntype: completed\nsummary: 報告\n")
            text, _ = self.output(tmp, state_with(), ["active-1"])
            self.assertNotIn("task_id: active-1", text)

    def test_new_conflict_invalidates_same_day_cache(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self.output(tmp, state_with(), ["active-1"])
            self.progress(tmp, "task_id: active-1\ntype: completed\nsummary: 終了\n")
            result, _ = self.run_script(tmp, VALID_RESPONSE, state_with())
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("state_conflicts mismatch", result.stdout)

    def test_zero_priorities_keeps_active_in_reminders(self):
        with tempfile.TemporaryDirectory() as d:
            text, _ = self.output(Path(d), state_with(), [])
            self.assertNotIn("候補ID:", text)
            self.assertIn("[active-1]", self.reminders(text))

    def test_current_business_state_retires_old_tasks_and_selects_correction(self):
        state = (ROOT / "outputs/current_state/current_state.md").read_text()
        with tempfile.TemporaryDirectory() as d:
            text, _ = self.output(Path(d), state, ["accounting-fy202607-correction"], date="2026-10-04")
            self.assertIn("候補ID: accounting-fy202607-correction", text)
            self.assertNotIn("karte-uat-retest", text)
            self.assertNotIn("accounting-fy202607-freee-import", text)

    def test_fetch_preserves_explicit_task_id_and_legacy_without_inference(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            module = load_fetch_module(tmp)
            module.fetch_all_messages = lambda oldest="": ([
                {"ts": "101.0", "text": "[GLMED_PROGRESS]\ndate: 2099-01-02\n"
                 "task_id: accounting-fy202607-correction\ntopic: 決算修正\ntype: in_progress\nsummary: 確認中"},
                {"ts": "102.0", "text": "[GLMED_PROGRESS]\ndate: 2099-01-02\n"
                 "topic: 決算修正\ntype: in_progress\nsummary: ID不明"},
            ], {"page_count": 1, "complete": True})
            self.assertEqual(module.main([]), 0)
            events = [json.loads(line) for line in module.EVENTS_FILE.read_text().splitlines()]
            self.assertEqual(events[0]["task_id"], "accounting-fy202607-correction")
            self.assertNotIn("task_id", events[1])
            self.assertEqual((tmp / "2099-01-02.gm_progress.md").read_text().count("task_id:"), 1)


if __name__ == "__main__":
    unittest.main()
