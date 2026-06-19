#!/usr/bin/env python3
"""Quick verify: check if batch add to my-stock actually took effect."""

from service import PortfolioManager


def main() -> None:
    with PortfolioManager() as pm:
        sg = pm.get_self_stocks(refresh=True)
        codes = {item.code for item in sg.items}
        targets = {"513180", "159915", "159509"}
        found = codes & targets
        print(f"我的自选 total: {len(sg.items)} stocks")
        print(f"Target stocks: {targets}")
        print(f"Found: {found}")
        print(f"SUCCESS: {targets == found}")


if __name__ == "__main__":
    main()
