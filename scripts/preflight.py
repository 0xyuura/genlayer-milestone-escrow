"""Ask a GenLayer node to parse the contract and return its ABI schema.

This is read-only (no transaction, no fees). It proves the runner pin in the
contract header is one the target network can load, and that the public API
is what you expect, before you spend GEN on a deployment.

Usage:  python scripts/preflight.py [contract.py] [rpc_url]
"""
import base64
import json
import sys
import urllib.request

contract = sys.argv[1] if len(sys.argv) > 1 else "contracts/milestone_escrow.py"
rpc = sys.argv[2] if len(sys.argv) > 2 else "https://rpc-bradbury.genlayer.com"

src = open(contract, encoding="utf-8").read()
payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "gen_getContractSchema",
    "params": [{"code": base64.b64encode(src.encode()).decode()}],
}
req = urllib.request.Request(
    rpc,
    json.dumps(payload).encode(),
    {"Content-Type": "application/json", "User-Agent": "milestone-escrow-preflight"},
)
res = json.loads(urllib.request.urlopen(req, timeout=60).read())
if "error" in res:
    print("FAIL:", res["error"].get("message"))
    raise SystemExit(1)
methods = res["result"]["methods"]
print(f"OK: {rpc} accepted {contract}")
for name, m in sorted(methods.items()):
    kind = "view" if m.get("readonly") else ("write, payable" if m.get("payable") else "write")
    params = ", ".join(f"{p}: {t}" for p, t in m["params"])
    print(f"  {name}({params}) -> {m['ret']}  [{kind}]")
