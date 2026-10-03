"""Repeatable product_compare execution; JSON failures exit with status 2."""

from lgax_core.skill_runner import cli_main

if __name__ == "__main__":
    raise SystemExit(cli_main("product_compare"))
