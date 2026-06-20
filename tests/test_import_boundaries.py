from __future__ import annotations

import ast
from pathlib import Path
import unittest


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "axia"


def _imports_from(source_directory: Path) -> list[tuple[Path, str]]:
    imports: list[tuple[Path, str]] = []
    for source_path in source_directory.rglob("*.py"):
        relative_path = source_path.relative_to(SOURCE_ROOT)
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(relative_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend((relative_path, alias.name) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
                imports.append((relative_path, node.module))
    return imports


class ImportBoundaryTests(unittest.TestCase):
    def test_source_and_shared_do_not_import_boundary_mechanisms(self) -> None:
        violations = [
            f"{source_path}: {module}"
            for directory_name in ("source", "shared", "formation")
            for source_path, module in _imports_from(SOURCE_ROOT / directory_name)
            if module == "axia.boundary" or module.startswith("axia.boundary.")
        ]

        self.assertEqual(violations, [], "Source, shared, and formation layers must not depend on boundary mechanisms.")

    def test_operations_depend_on_ports_not_adapters_or_presentation(self) -> None:
        violations = [
            f"{source_path}: {module}"
            for source_path, module in _imports_from(SOURCE_ROOT / "operation")
            if module.startswith("axia.boundary.adapters")
            or module.startswith("axia.boundary.presentation")
        ]

        self.assertEqual(violations, [], "Operations may depend on ports but not concrete adapters or presentation.")

    def test_ports_do_not_import_adapters_or_presentation(self) -> None:
        violations = [
            f"{source_path}: {module}"
            for source_path, module in _imports_from(SOURCE_ROOT / "boundary" / "ports")
            if module.startswith("axia.boundary.adapters")
            or module.startswith("axia.boundary.presentation")
        ]

        self.assertEqual(violations, [], "Boundary ports must not depend on concrete adapters or presentation.")

    def test_adapters_do_not_import_presentation(self) -> None:
        violations = [
            f"{source_path}: {module}"
            for source_path, module in _imports_from(SOURCE_ROOT / "boundary" / "adapters")
            if module.startswith("axia.boundary.presentation")
        ]

        self.assertEqual(violations, [], "Concrete adapters must not depend on presentation.")


if __name__ == "__main__":
    unittest.main()
