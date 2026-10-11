"""Compatibility entry for the current partial-input CPU HTTP checks.

Run --help for options. Uses an already-running local worker and packaged data;
does not read a historical report or load a second model.
"""
from validate_subset_http import main


if __name__ == "__main__":
    main()
