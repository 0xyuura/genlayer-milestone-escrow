"""Test harness tweaks for genlayer-test 0.30.0rc2 + GenVM v0.3 (Bradbury).

1. LLM mocks: the rc pre-parses JSON mock responses into a dict, but the v0.3
   SDK's `exec_prompt(..., response_format='json')` decoder expects the host to
   return JSON *text* (which is what real nodes send). Re-serialize so tests
   exercise the same code path as the network.
2. Windows: the rc swaps stdin for a temp file and unlinks it while it is still
   open, which raises PermissionError on Windows. Make that unlink best-effort.
"""
import json
import os
import sys

import gltest.direct.wasi_mock as _wasi_mock

_orig_llm = _wasi_mock._handle_llm_request


def _handle_llm_request(vm, data):
    res = _orig_llm(vm, data)
    if (
        isinstance(res, dict)
        and data.get("response_format") == "json"
        and not isinstance(res.get("ok"), (str, bytes, bytearray, type(None)))
    ):
        res = {"ok": json.dumps(res["ok"])}
    return res


_wasi_mock._handle_llm_request = _handle_llm_request

if sys.platform == "win32":
    import gltest.direct.loader as _loader

    _orig_inject = _loader._inject_message_to_fd0
    _real_unlink = os.unlink

    def _lenient_unlink(path, *a, **kw):
        try:
            _real_unlink(path, *a, **kw)
        except PermissionError:
            pass  # still open as stdin; the OS temp dir reclaims it later

    def _inject_message_to_fd0(vm):
        os.unlink = _lenient_unlink
        try:
            return _orig_inject(vm)
        finally:
            os.unlink = _real_unlink

    _loader._inject_message_to_fd0 = _inject_message_to_fd0
