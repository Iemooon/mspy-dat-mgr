from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
failed = 0
for test_file in sorted((ROOT / "tests").glob("test_*.py")):
    module_name = test_file.stem
    spec = importlib.util.spec_from_file_location(module_name, test_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {test_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    for name in sorted(n for n in dir(module) if n.startswith("test_")):
        try:
            getattr(module, name)()
            print(f"PASS {module_name}.{name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {module_name}.{name}: {type(exc).__name__}: {exc}")

raise SystemExit(failed)
