from __future__ import annotations

import ast
from pathlib import Path
import unittest

from axia.boundary.presentation.cli import build_parser


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "axia"

FORBIDDEN_MODULE_STEMS = frozenset(
    {
        "durable_memory",
        "forgetting_policy",
        "memory_manager",
        "memory_promotion",
        "memory_repository",
        "memory_search",
        "memory_store",
        "preference_memory",
        "user_profile",
    }
)
FORBIDDEN_SYMBOLS = frozenset(
    {
        "durablememory",
        "forgettingpolicy",
        "memorymanager",
        "memorypromoter",
        "memoryrepository",
        "memorysearch",
        "memorystore",
        "preferencememory",
        "userprofile",
    }
)


class MemoryBoundaryTests(unittest.TestCase):
    def test_source_does_not_admit_durable_memory_components(self) -> None:
        violations: list[str] = []
        for source_path in SOURCE_ROOT.rglob("*.py"):
            relative_path = source_path.relative_to(SOURCE_ROOT)
            if relative_path.stem in FORBIDDEN_MODULE_STEMS:
                violations.append(str(relative_path))

            tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(relative_path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    normalized_name = node.name.replace("_", "").lower()
                    if normalized_name in FORBIDDEN_SYMBOLS:
                        violations.append(f"{relative_path}:{node.name}")

        self.assertEqual(
            violations,
            [],
            "Axia may emit memory candidates and consume scoped context, but it must not admit durable-memory components.",
        )

    def test_cli_does_not_expose_memory_as_an_axia_product_surface(self) -> None:
        parser = build_parser()
        subparser_action = next(
            action for action in parser._actions if hasattr(action, "choices") and action.choices
        )

        self.assertNotIn("memory", subparser_action.choices)
        self.assertNotIn("memory-search", subparser_action.choices)

    def test_spec_configuration_keeps_durable_memory_policy_outside_axia(self) -> None:
        specification = (PROJECT_ROOT / "docs" / "axia_spec.md").read_text(encoding="utf-8")
        config_start = specification.index("### 24.1 `config.yaml`")
        config_end = specification.index("### 24.2 `profiles/tiny-default.yaml`")
        config_section = specification[config_start:config_end]

        self.assertNotIn("\nmemory:\n", config_section)
        self.assertNotIn("read_policy:", config_section)
        self.assertNotIn("write_policy:", config_section)


if __name__ == "__main__":
    unittest.main()
