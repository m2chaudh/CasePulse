"""Verify every pages_modules/*.py imports without errors. Catches stale
imports left behind by the pages/ → pages_modules/ migration."""

from pathlib import Path
import ast
import pytest

PAGES_DIR = Path(__file__).resolve().parents[2] / "pages_modules"


@pytest.mark.parametrize("path", sorted(PAGES_DIR.glob("*.py")))
def test_page_parses_and_top_imports_resolve(path):
    """Each page module must (a) be syntactically valid Python and
    (b) have its top-level imports resolve. We can't fully exec page
    modules outside Streamlit's runtime, so we exec only the top-level
    Import / ImportFrom AST nodes."""
    src = path.read_text()
    tree = ast.parse(src, str(path))
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = ast.Module(body=[node], type_ignores=[])
            ast.fix_missing_locations(module)
            exec(compile(module, str(path), "exec"), {})
