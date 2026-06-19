#!/usr/bin/env python3
"""Final batch test — cookie-only mode."""

from service import PortfolioManager

TEST_MY_STOCK = ["002082.SZ", "002083.SZ", "002084.SZ"]
TEST_GROUP = "batch_final_v2"
TEST_GROUP_STOCKS = ["300001.SZ", "300002.SZ", "300003.SZ"]


def main() -> None:
    with PortfolioManager() as pm:
        ap = pm._auth_params
        assert ap, "no auth_params"
        print(
            f"[OK] auth_params: userid={ap.get('userid')} sessionid={ap.get('sessionid', '')[:16]}..."
        )

        sg_before = pm.get_self_stocks(refresh=True)
        codes_before = {item.code for item in sg_before.items}
        print(f"\n[我的自选] before: {len(sg_before.items)}")

        pm.add_item_to_group("我的自选", TEST_MY_STOCK)

        sg_after = pm.get_self_stocks(refresh=True)
        new_codes = {item.code for item in sg_after.items} - codes_before
        expected = {"002082", "002083", "002084"}
        ok = expected == new_codes
        print(f"[我的自选] after:  {len(sg_after.items)} (+{len(new_codes)})")
        print(f"  {'[OK]' if ok else '[FAIL]'} v1 batch add ({'3 new' if ok else 'mismatch'})")

        try:
            pm.add_group(TEST_GROUP)
            print(f"\n[分组] created: {TEST_GROUP}")
        except Exception:
            print(f"\n[分组] already exists: {TEST_GROUP}")

        pm.add_item_to_group(TEST_GROUP, TEST_GROUP_STOCKS)

        all_groups = pm.get_all_groups(include_self_stocks=True, use_cache=False)
        tg = all_groups.get(TEST_GROUP)
        if tg:
            codes = {item.code for item in tg.items}
            expected2 = {"300001", "300002", "300003"}
            print(f"[分组] items: {len(tg.items)}, codes: {sorted(codes)}")
            print(f"  {'[OK]' if expected2 <= codes else '[FAIL]'} multiStorage batch add")
        else:
            print("[FAIL] group not found")

    print("\nDone.")


if __name__ == "__main__":
    main()
