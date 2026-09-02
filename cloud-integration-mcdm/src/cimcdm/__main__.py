"""Allow ``python -m cimcdm``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
