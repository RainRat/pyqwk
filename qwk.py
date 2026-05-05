"""Run the pyqwk tool directly from this folder."""

from pyqwk import core as _core
from pyqwk.cli import main

for _name in dir(_core):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_core, _name)

__all__ = [_name for _name in dir(_core) if not _name.startswith("__")] + ["main"]

if __name__ == "__main__":
    main()
