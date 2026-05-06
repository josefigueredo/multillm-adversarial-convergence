"""Tests for src.tool_capabilities."""

from __future__ import annotations

import pytest

from src.policy.tool_capabilities import (
    ToolCapabilities,
    classify_tool,
    classify_allowed_tools,
    coverage_stats,
    check_capability_consistency,
    SHIPPED_TOOLS,
    _TOOL_CAPABILITIES,
)


# ---------------------------------------------------------------------------
# ToolCapabilities dataclass
# ---------------------------------------------------------------------------

class TestToolCapabilities:
    def test_is_immutable(self):
        caps = ToolCapabilities()
        with pytest.raises((AttributeError, TypeError)):
            caps.uses_host_shell = True  # type: ignore[misc]

    def test_default_values_are_all_false_or_none(self):
        caps = ToolCapabilities()
        assert caps.uses_host_shell is False
        assert caps.uses_network is False
        assert caps.destination_type is None
        assert caps.may_write is False

    def test_can_construct_with_all_fields(self):
        caps = ToolCapabilities(
            uses_host_shell=True,
            uses_network=True,
            destination_type="web",
            may_write=True,
        )
        assert caps.uses_host_shell is True
        assert caps.uses_network is True
        assert caps.destination_type == "web"
        assert caps.may_write is True

    def test_equality_by_value(self):
        a = ToolCapabilities(uses_network=True, destination_type="web")
        b = ToolCapabilities(uses_network=True, destination_type="web")
        assert a == b

    def test_inequality_on_different_fields(self):
        a = ToolCapabilities(uses_host_shell=True)
        b = ToolCapabilities(uses_host_shell=False)
        assert a != b


# ---------------------------------------------------------------------------
# classify_tool — known tools
# ---------------------------------------------------------------------------

class TestClassifyKnownTools:
    # -- Bash ----------------------------------------------------------------

    def test_bash_uses_host_shell(self):
        caps = classify_tool("Bash")
        assert caps is not None
        assert caps.uses_host_shell is True

    def test_bash_may_write(self):
        caps = classify_tool("Bash")
        assert caps is not None
        assert caps.may_write is True

    def test_bash_does_not_declare_network(self):
        caps = classify_tool("Bash")
        assert caps is not None
        assert caps.uses_network is False
        assert caps.destination_type is None

    # -- WebSearch -----------------------------------------------------------

    def test_websearch_uses_network(self):
        caps = classify_tool("WebSearch")
        assert caps is not None
        assert caps.uses_network is True

    def test_websearch_destination_type_is_web(self):
        caps = classify_tool("WebSearch")
        assert caps is not None
        assert caps.destination_type == "web"

    def test_websearch_does_not_use_host_shell(self):
        caps = classify_tool("WebSearch")
        assert caps is not None
        assert caps.uses_host_shell is False

    def test_websearch_does_not_declare_write(self):
        caps = classify_tool("WebSearch")
        assert caps is not None
        assert caps.may_write is False

    # -- WebFetch ------------------------------------------------------------

    def test_webfetch_uses_network(self):
        caps = classify_tool("WebFetch")
        assert caps is not None
        assert caps.uses_network is True

    def test_webfetch_destination_type_is_web(self):
        caps = classify_tool("WebFetch")
        assert caps is not None
        assert caps.destination_type == "web"

    def test_webfetch_does_not_use_host_shell(self):
        caps = classify_tool("WebFetch")
        assert caps is not None
        assert caps.uses_host_shell is False

    # -- Read ----------------------------------------------------------------

    def test_read_has_no_special_capabilities(self):
        caps = classify_tool("Read")
        assert caps is not None
        assert caps.uses_host_shell is False
        assert caps.uses_network is False
        assert caps.destination_type is None
        assert caps.may_write is False

    # -- Glob ----------------------------------------------------------------

    def test_glob_has_no_special_capabilities(self):
        caps = classify_tool("Glob")
        assert caps is not None
        assert caps.uses_host_shell is False
        assert caps.uses_network is False
        assert caps.destination_type is None
        assert caps.may_write is False

    # -- Grep ----------------------------------------------------------------

    def test_grep_has_no_special_capabilities(self):
        caps = classify_tool("Grep")
        assert caps is not None
        assert caps.uses_host_shell is False
        assert caps.uses_network is False
        assert caps.destination_type is None
        assert caps.may_write is False

    # -- Write / Edit (common write tools) -----------------------------------

    def test_write_declares_may_write(self):
        caps = classify_tool("Write")
        assert caps is not None
        assert caps.may_write is True
        assert caps.uses_host_shell is False
        assert caps.uses_network is False

    def test_edit_declares_may_write(self):
        caps = classify_tool("Edit")
        assert caps is not None
        assert caps.may_write is True
        assert caps.uses_host_shell is False
        assert caps.uses_network is False


# ---------------------------------------------------------------------------
# classify_tool — unknown tools
# ---------------------------------------------------------------------------

class TestClassifyUnknownTools:
    def test_unknown_tool_returns_none(self):
        assert classify_tool("FancyNewTool") is None

    def test_empty_string_returns_none(self):
        assert classify_tool("") is None

    def test_case_sensitive_name_returns_none(self):
        """Tool names are case-sensitive; 'bash' is not the same as 'Bash'."""
        assert classify_tool("bash") is None
        assert classify_tool("websearch") is None

    def test_tool_with_whitespace_returns_none(self):
        assert classify_tool("Web Search") is None


# ---------------------------------------------------------------------------
# classify_allowed_tools
# ---------------------------------------------------------------------------

class TestClassifyAllowedTools:
    def test_empty_iterable_returns_empty_list(self):
        result = classify_allowed_tools([])
        assert result == []

    def test_single_known_tool(self):
        result = classify_allowed_tools(["Bash"])
        assert len(result) == 1
        name, caps = result[0]
        assert name == "Bash"
        assert caps is not None
        assert caps.uses_host_shell is True

    def test_multiple_known_tools(self):
        result = classify_allowed_tools(["WebSearch", "Read", "Bash"])
        assert len(result) == 3
        by_name = {name: caps for name, caps in result}
        assert by_name["WebSearch"].destination_type == "web"
        assert by_name["Read"].uses_host_shell is False
        assert by_name["Bash"].uses_host_shell is True

    def test_unknown_tool_included_with_none_caps(self):
        result = classify_allowed_tools(["Bash", "MysteryTool"])
        by_name = {name: caps for name, caps in result}
        assert by_name["MysteryTool"] is None

    def test_mixed_known_and_unknown_tools(self):
        result = classify_allowed_tools(["WebFetch", "OtherTool", "Grep"])
        by_name = {name: caps for name, caps in result}
        assert by_name["WebFetch"].uses_network is True
        assert by_name["OtherTool"] is None
        assert by_name["Grep"].uses_network is False

    def test_preserves_input_order(self):
        tools = ["Glob", "Bash", "WebSearch"]
        result = classify_allowed_tools(tools)
        names = [name for name, _ in result]
        assert names == tools

    def test_accepts_generator(self):
        result = classify_allowed_tools(t for t in ["Read", "Bash"])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _TOOL_CAPABILITIES registry — structural checks
# ---------------------------------------------------------------------------

class TestToolCapabilitiesRegistry:
    def test_registry_is_non_empty(self):
        assert len(_TOOL_CAPABILITIES) > 0

    def test_all_default_tools_are_classified(self):
        """Every tool in the default allowed_tools string must be in the registry."""
        default_tools = {"WebSearch", "WebFetch", "Read", "Bash", "Glob", "Grep"}
        for tool in default_tools:
            assert tool in _TOOL_CAPABILITIES, f"{tool!r} not in _TOOL_CAPABILITIES"

    def test_all_registry_values_are_tool_capabilities(self):
        for name, caps in _TOOL_CAPABILITIES.items():
            assert isinstance(caps, ToolCapabilities), (
                f"_TOOL_CAPABILITIES[{name!r}] is not a ToolCapabilities instance"
            )


# ---------------------------------------------------------------------------
# LS classification
# ---------------------------------------------------------------------------

class TestLSClassification:
    def test_ls_is_in_registry(self):
        assert "LS" in _TOOL_CAPABILITIES

    def test_ls_has_no_special_capabilities(self):
        caps = classify_tool("LS")
        assert caps is not None
        assert caps.uses_host_shell is False
        assert caps.uses_network is False
        assert caps.destination_type is None
        assert caps.may_write is False


# ---------------------------------------------------------------------------
# SHIPPED_TOOLS constant
# ---------------------------------------------------------------------------

class TestShippedTools:
    _EXPECTED_TOOLS = {
        # default allowed_tools
        "Bash", "WebSearch", "WebFetch", "Read", "Glob", "Grep",
        # filesystem write
        "Write", "Edit", "MultiEdit",
        # agent / task helpers
        "TodoRead", "TodoWrite", "Task",
        # directory listing
        "LS",
    }

    def test_shipped_tools_is_frozenset(self):
        assert isinstance(SHIPPED_TOOLS, frozenset)

    def test_all_expected_tools_in_shipped_tools(self):
        for name in self._EXPECTED_TOOLS:
            assert name in SHIPPED_TOOLS, f"{name!r} missing from SHIPPED_TOOLS"

    def test_all_shipped_tools_are_in_registry(self):
        for name in SHIPPED_TOOLS:
            assert name in _TOOL_CAPABILITIES, (
                f"{name!r} in SHIPPED_TOOLS but not in _TOOL_CAPABILITIES"
            )


# ---------------------------------------------------------------------------
# coverage_stats
# ---------------------------------------------------------------------------

class TestCoverageStats:
    def test_empty_input_returns_zero_stats(self):
        stats = coverage_stats([])
        assert stats == {
            "total": 0,
            "classified": 0,
            "unclassified": 0,
            "unclassified_names": [],
        }

    def test_all_default_tools_fully_classified(self):
        default_tools = ["WebSearch", "WebFetch", "Read", "Bash", "Glob", "Grep"]
        stats = coverage_stats(default_tools)
        assert stats["total"] == 6
        assert stats["classified"] == 6
        assert stats["unclassified"] == 0
        assert stats["unclassified_names"] == []

    def test_unknown_tool_appears_in_unclassified_names(self):
        stats = coverage_stats(["UnknownThing"])
        assert stats["total"] == 1
        assert stats["classified"] == 0
        assert stats["unclassified"] == 1
        assert stats["unclassified_names"] == ["UnknownThing"]

    def test_mixed_known_and_unknown(self):
        stats = coverage_stats(["Bash", "Ghost", "Read", "Phantom"])
        assert stats["total"] == 4
        assert stats["classified"] == 2
        assert stats["unclassified"] == 2
        assert set(stats["unclassified_names"]) == {"Ghost", "Phantom"}

    def test_unclassified_names_preserves_input_order(self):
        tools = ["Alpha", "Bash", "Beta", "Gamma", "Read"]
        stats = coverage_stats(tools)
        assert stats["unclassified_names"] == ["Alpha", "Beta", "Gamma"]

    def test_accepts_generator_input(self):
        gen = (t for t in ["Bash", "MissingTool"])
        stats = coverage_stats(gen)
        assert stats["total"] == 2
        assert stats["classified"] == 1
        assert stats["unclassified"] == 1

    def test_all_shipped_tools_fully_classified(self):
        stats = coverage_stats(SHIPPED_TOOLS)
        assert stats["unclassified"] == 0, (
            f"Unclassified shipped tools: {stats['unclassified_names']}"
        )


# ---------------------------------------------------------------------------
# check_capability_consistency
# ---------------------------------------------------------------------------

class TestCapabilityConsistency:
    def test_default_caps_are_consistent(self):
        caps = ToolCapabilities()
        assert check_capability_consistency(caps) == []

    def test_valid_web_tool_is_consistent(self):
        caps = ToolCapabilities(uses_network=True, destination_type="web")
        assert check_capability_consistency(caps) == []

    def test_valid_other_destination_is_consistent(self):
        caps = ToolCapabilities(uses_network=True, destination_type="other")
        assert check_capability_consistency(caps) == []

    def test_uses_network_without_destination_type_is_invalid(self):
        caps = ToolCapabilities(uses_network=True, destination_type=None)
        errors = check_capability_consistency(caps)
        assert len(errors) >= 1
        assert any("destination_type" in e for e in errors)

    def test_destination_type_without_uses_network_is_invalid(self):
        caps = ToolCapabilities(uses_network=False, destination_type="web")
        errors = check_capability_consistency(caps)
        assert len(errors) >= 1
        assert any("destination_type" in e for e in errors)

    def test_invalid_destination_type_value_is_invalid(self):
        caps = ToolCapabilities(uses_network=True, destination_type="weeb")
        errors = check_capability_consistency(caps)
        assert len(errors) >= 1
        assert any("destination_type" in e for e in errors)

    def test_another_invalid_destination_type_value(self):
        caps = ToolCapabilities(uses_network=True, destination_type="http")
        errors = check_capability_consistency(caps)
        assert len(errors) >= 1

    def test_all_registry_entries_are_consistent(self):
        """Every entry in _TOOL_CAPABILITIES must pass consistency validation."""
        failures: dict[str, list[str]] = {}
        for name, caps in _TOOL_CAPABILITIES.items():
            errors = check_capability_consistency(caps)
            if errors:
                failures[name] = errors
        assert failures == {}, f"Registry consistency failures: {failures}"
