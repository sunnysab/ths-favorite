#!/usr/bin/env python3
"""Test batch add for both my-stock and custom groups."""

from service import PortfolioManager

TEST_MY_STOCK = ["513180.SH", "159915.SZ", "159509.SZ"]
TEST_GROUP_NAME = "test_batch"


def main() -> None:
    with PortfolioManager() as pm:
        # ── Before: show what we have ──
        groups_before = pm.get_all_groups(include_self_stocks=True, use_cache=False)
        self_before = pm.get_self_stocks(refresh=True)

        print("══════ 我的自选 (before) ══════")
        print(f"  items: {len(self_before.items)}")
        codes_before = {item.code for item in self_before.items}

        # ── 1. Batch add to 我的自选 ──
        print(f"\n>>> batch add to 我的自选: {TEST_MY_STOCK}")
        pm.add_item_to_group("我的自选", TEST_MY_STOCK)

        # ── 2. Create group + batch add ──
        try:
            pm.add_group(TEST_GROUP_NAME)
            print(f">>> created group: {TEST_GROUP_NAME}")
        except Exception as e:
            if "已存在" in str(e) or "exist" in str(e).lower():
                print(f">>> group {TEST_GROUP_NAME} already exists, reusing")
            else:
                raise

        pm.add_item_to_group(TEST_GROUP_NAME, ["000001.SZ", "000002.SZ", "000858.SZ"])
        print(f">>> batch add to {TEST_GROUP_NAME}: ['000001.SZ', '000002.SZ', '000858.SZ']")

        # ── After: verify ──
        all_groups = pm.get_all_groups(include_self_stocks=True, use_cache=False)
        self_after = pm.get_self_stocks(refresh=True)

        print("\n══════ 我的自选 (after) ══════")
        print(f"  items: {len(self_after.items)}")
        new_in_self = [item.code for item in self_after.items if item.code not in codes_before]
        print(f"  newly added: {new_in_self}")
        test_codes = {"513180", "159915", "159509"}
        found = {item.code for item in self_after.items if item.code in test_codes}
        print(f"  test stocks found: {found}")
        print(f"  SUCCESS: {test_codes == found}")

        tg = all_groups.get(TEST_GROUP_NAME)
        if tg:
            print(f"\n══════ {TEST_GROUP_NAME} ══════")
            print(f"  items: {len(tg.items)}")
            print(f"  codes: {[item.code for item in tg.items]}")
            expected = {"000001", "000002", "000858"}
            actual = {item.code for item in tg.items}
            print(f"  SUCCESS: {expected == actual}")
        else:
            print(f"\n  FAILED: group '{TEST_GROUP_NAME}' not found after add")

    print("\nDone.")


if __name__ == "__main__":
    main()
