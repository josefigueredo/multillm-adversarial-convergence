"""MM12 Step 5 — domain architecture diagnostics tests.

TDD tests that verify:
- explain_domain_packages() surfaces the active bounded-context package seams
- Pre-existing packages are also reported
- Backward-compat statement is present
"""
from __future__ import annotations


class TestExplainDomainPackagesExists:
    def test_function_importable(self):
        from src.explain import explain_domain_packages
        assert callable(explain_domain_packages)

    def test_returns_string(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        assert isinstance(result, str)

    def test_non_empty(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        assert len(result) > 0


class TestExplainDomainPackagesHeader:
    def test_contains_header(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        assert "DOMAIN" in result.upper() or "PACKAGE" in result.upper()


class TestExplainDomainPackagesMM12Seams:
    """Verify each MM12 package seam is described."""

    def test_mentions_evidence(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        assert "evidence" in result

    def test_mentions_deliverables(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        assert "deliverables" in result

    def test_mentions_execution(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        assert "execution" in result

    def test_mentions_implement(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        assert "implement" in result

    def test_mentions_policy(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        assert "policy" in result


class TestExplainDomainPackagesPreExisting:
    """Verify pre-existing package seams are acknowledged."""

    def test_mentions_workflows(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        assert "workflows" in result

    def test_mentions_backends(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        assert "backends" in result

    def test_mentions_sandbox(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        assert "sandbox" in result


class TestExplainDomainPackagesBackwardCompat:
    def test_backward_compat_note_present(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        # Should state that flat imports still work
        lower = result.lower()
        assert "backward" in lower or "flat" in lower or "compat" in lower


class TestExplainDomainPackagesResponsibilities:
    """Verify each seam carries a meaningful description."""

    def test_evidence_has_description(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        # evidence seam should mention at least one of its responsibilities
        lower = result.lower()
        after_evidence = lower.split("evidence", 1)[-1][:200]
        assert any(kw in after_evidence for kw in ("citation", "provenance", "reference", "reproducib"))

    def test_deliverables_has_description(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        lower = result.lower()
        after = lower.split("deliverables", 1)[-1][:200]
        assert any(kw in after for kw in ("pipeline", "publication", "export", "class"))

    def test_execution_has_description(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        lower = result.lower()
        after = lower.split("execution", 1)[-1][:200]
        assert any(kw in after for kw in ("plan", "validation", "diagnosis", "repair"))

    def test_policy_has_description(self):
        from src.explain import explain_domain_packages
        result = explain_domain_packages()
        lower = result.lower()
        after = lower.split("policy", 1)[-1][:200]
        assert any(kw in after for kw in ("hitl", "trust", "sandbox", "security", "tool"))
