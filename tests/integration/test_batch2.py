#!/usr/bin/env python3
"""Full batch add test — needs username+password for multiStorage auth."""

import os
import sys

from service import PortfolioManager

username = os.environ.get('THS_USER')
password = os.environ.get('THS_PASS')

# Stocks guaranteed NOT in the user's list (random test picks)
TEST_MY = ['000595.SZ', '000668.SZ', '000672.SZ']
TEST_GRP = 'batch_test_grp'
TEST_GRP_STOCKS = ['002001.SZ', '002002.SZ', '002003.SZ']


def main() -> None:
    if not username or not password:
        print('Usage: THS_USER=133xxxxxxxx THS_PASS=yourpass python test_batch2.py')
        sys.exit(1)

    with PortfolioManager(username=username, password=password) as pm:
        # Check auth_params are available
        if pm._auth_params:
            sid = pm._auth_params['sessionid'][:8]
            tok = pm._auth_params['token'][:8]
            print(
                f"[OK] auth_params: userid={pm._auth_params['userid']}, "
                f"sessionid={sid}..., token={tok}..."
            )
        else:
            print("[FAIL] auth_params missing — multiStorage won't work")
            sys.exit(1)

        # ── Phase 1: my-stock batch add via v1 ──
        sg_before = pm.get_self_stocks(refresh=True)
        codes_before = {item.code for item in sg_before.items}
        print(f'\n[Phase 1] 我的自选: {len(sg_before.items)} stocks')

        pm.add_item_to_group('我的自选', TEST_MY)
        sg_after = pm.get_self_stocks(refresh=True)
        new_in_self = {item.code for item in sg_after.items} - codes_before
        target_set = {'000595', '000668', '000672'}
        ok = target_set <= new_in_self
        print(f'  after: {len(sg_after.items)} stocks (+{len(new_in_self)})')
        print(f'  added: {new_in_self & target_set}')
        print(f"  {'[OK] v1 batch add works' if ok else '[FAIL]'}")

        # ── Phase 2: custom group batch add via multiStorage ──
        try:
            pm.add_group(TEST_GRP)
            print(f'\n[Phase 2] Created group: {TEST_GRP}')
        except Exception:
            print(f'\n[Phase 2] Group {TEST_GRP} already exists, reusing')

        pm.add_item_to_group(TEST_GRP, TEST_GRP_STOCKS)
        all_groups = pm.get_all_groups(include_self_stocks=True, use_cache=False)
        tg = all_groups.get(TEST_GRP)
        if tg:
            codes = {item.code for item in tg.items}
            expected = {'002001', '002002', '002003'}
            ok2 = codes >= expected
            print(f'  items: {len(tg.items)}, codes: {codes}')
            print(f"  {'[OK] multiStorage batch add works' if ok2 else '[FAIL]'}")
        else:
            print(f'  [FAIL] group {TEST_GRP} not found')

    print('\nDone — no cleanup performed.')


if __name__ == '__main__':
    main()
