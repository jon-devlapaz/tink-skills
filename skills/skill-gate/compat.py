"""Harness compatibility evaluation."""

from dataclasses import dataclass
from typing import Dict, List, Set

from features import SkillFeatures

HARNESS_PROFILES: Dict[str, Set[str]] = {
    "pi": {
        "read", "write", "edit", "bash", "bg_start", "bg_status", "bg_list", "bg_kill",
        "fd", "rg", "recall", "typesafe_evaluate", "generate_image",
        "herdr_start_agent", "herdr_send_prompt", "herdr_read_agent", "herdr_wait_agent",
        "herdr_list_agents", "herdr_get_agent", "herdr_stop_agent", "herdr_rename_agent",
        "herdr_focus_agent", "herdr_explain_agent", "herdr_delegate", "herdr_split_pane",
        "herdr_run_command", "herdr_read_pane", "herdr_wait_output", "herdr_send_keys",
        "herdr_close_pane", "herdr_list_panes", "herdr_get_pane", "herdr_resize_pane",
        "herdr_zoom_pane", "herdr_move_pane", "herdr_swap_panes", "herdr_list_tabs",
        "herdr_create_tab", "herdr_get_tab", "herdr_focus_tab", "herdr_rename_tab",
        "herdr_close_tab", "herdr_list_workspaces", "herdr_create_workspace",
        "herdr_get_workspace", "herdr_focus_workspace", "herdr_rename_workspace",
        "herdr_close_workspace", "herdr_worktree_create", "herdr_worktree_open",
        "herdr_worktree_list", "herdr_worktree_remove", "herdr_api_snapshot",
        "herdr_session_list", "herdr_session_stop", "herdr_session_delete",
        "ask_user", "file_search", "dir_list"
    },
    "claude": {
        "read", "write", "edit", "bash", "glob", "grep", "view", "create",
        "str_replace_editor", "bash_command", "file_search", "web_search", "web_fetch"
    },
    "codex": {"read", "write", "edit", "bash", "python", "shell", "exec"},
    "generic": {"read", "write", "bash", "edit"},
}

# ============================================================================
# Compatibility Evaluator
# ============================================================================

@dataclass
class CompatibilityReport:
    target_harness: str
    status: str  # "compatible" or "incompatible"
    missing_tools: List[str]
    declared_tools: List[str]
    supported_tools: List[str]


def evaluate_compatibility(features: SkillFeatures, target_harness: str = "pi") -> CompatibilityReport:
    """Evaluates declared skill tools against harness profiles (pi, claude, codex, generic)."""
    norm_harness = target_harness.lower().strip()
    profile = HARNESS_PROFILES.get(norm_harness, set())

    declared = features.tools
    missing = [t for t in declared if t not in profile]
    status = "compatible" if not missing else "incompatible"

    return CompatibilityReport(
        target_harness=norm_harness,
        status=status,
        missing_tools=sorted(missing),
        declared_tools=sorted(declared),
        supported_tools=sorted(profile),
    )
