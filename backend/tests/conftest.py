# -*- coding: utf-8 -*-
# 临时诊断用：打印每个测试的执行耗时
import time

import pytest


@pytest.fixture(autouse=True)
def _timing():
    t0 = time.perf_counter()
    yield
    print(
        f"\n[conftest-timing] {time.perf_counter() - t0:.2f}s",
        flush=True,
    )
