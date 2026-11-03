# MilestoneEscrow — AI-adjudicated escrow on GenLayer

An Intelligent Contract that settles **"was the work actually delivered?"**,
the question ordinary smart-contract escrows cannot answer on their own.

A client locks GEN against a list of explicit acceptance criteria. The provider
submits a public evidence URL. Anyone can then ask the network to adjudicate:
every validator independently fetches the evidence, grades it **criterion by
criterion**, and the contract settles only when validators agree on that
per-criterion outcome.

Targets **GenVM v0.3 / Testnet Bradbury** (`py-genlayer:babwp9t3…`).

## Why it is a reusable primitive

Escrow with subjective release conditions sits underneath freelance
marketplaces, grants and bounties, milestone-based funding, and agent-to-agent
commerce. `MilestoneEscrow` packages the hard part once:

| Concern | How it is handled |
|---|---|
| Subjective judgment | An LLM grades each criterion against the fetched evidence |
| Consensus | Validators **re-fetch and re-grade**, then compare the boolean criterion vector exactly. Prose is stored but never compared |
| Decision | `ACCEPT` iff every criterion is met. It is a pure function of the agreed vector, not an LLM-chosen label |
| Malicious leader | A forged "all criteria met" result is rejected because validators derive their own vector |
| Prompt injection | Evidence is fenced in `<evidence>` and the prompt tells the model to ignore instructions inside it |
| Flaky web / LLM | Errors are tagged `[EXPECTED]` / `[EXTERNAL]` / `[TRANSIENT]` / `[LLM]`. Nodes agree on deterministic failures and force a new leader on LLM failures |
| Unreachable evidence | Agreed `[EXTERNAL]` failure counts as an attempt (`UNREACHABLE`) instead of reverting forever |
| Liveness | Bounded attempts, a deadline, and a 7-day review grace period. Funds can always be reclaimed |
| Fund safety | Pull payments: settlement only credits balances, and `withdraw()` sends funds (state is updated before the transfer) |

## Consensus design

```
adjudicate(deal_id)
  ├─ leader:     render(evidence_url) → LLM grades N criteria → {criteria_met: [bool]*N, reasoning}
  ├─ validator:  render(evidence_url) again → LLM grades again → compare criteria_met == leader's
  │              (leader errored? agree only if we hit the same deterministic error class)
  └─ deterministic: verdict = ACCEPT if all(criteria_met) else REJECT → update state / credit balance
```

This is the *partial field matching* pattern from the GenLayer Equivalence
Principle docs, applied to a vector of facts instead of one label. Two honest
validators can word their reasoning differently, but they must agree on every
criterion.

## Lifecycle

```
create_deal (payable) ──► OPEN ──submit_delivery──► SUBMITTED ──adjudicate──┬─► ACCEPTED  (provider credited)
                           ▲                                                 ├─► OPEN      (REJECT / UNREACHABLE, attempt used)
                           └─────────────────────────────────────────────────┘
OPEN ──cancel (no attempts yet)──► CANCELLED  (client credited)
OPEN ──reclaim (deadline passed or attempts exhausted)──► REFUNDED (client credited)
SUBMITTED ──reclaim (deadline + 7d grace)──► REFUNDED
any credited account ──withdraw──► GEN transferred
```

## Public API

| Method | Kind | Description |
|---|---|---|
| `create_deal(provider, title, criteria, deadline_seconds, max_attempts)` | write, payable | Lock `msg.value`. `criteria` is newline or `;` separated (max 8) |
| `submit_delivery(deal_id, evidence_url)` | write | Provider only. Public `https://` URL |
| `adjudicate(deal_id)` | write | Anyone. Returns `ACCEPT` / `REJECT` / `UNREACHABLE` |
| `cancel(deal_id)` | write | Client only, before any attempt |
| `reclaim(deal_id)` | write | Anyone. Refunds the client when the deal can no longer succeed |
| `withdraw()` | write | Sends everything credited to the caller |
| `get_deal(deal_id)` | view | Full deal state including last verdict, per-criterion result, and reasoning |
| `get_withdrawable(account)`, `get_total_locked()`, `get_deal_count()` | view | Accounting |

## Run the tests

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements-dev.txt
pytest tests -v
```

There are 36 Direct Mode tests covering:
- Input validation and access control
- Accept, reject, retry, and unreachable flows
- Malformed LLM output and prompt-injection fencing
- Validator agreement when only the wording differs
- Validator disagreement when any criterion differs or the leader is forged
- Error-class agreement
- Deadlines, the grace period, and accounting

The first run downloads the GenVM v0.3 SDK (genvm-manager `v0.6.0-rc10`).
`tests/conftest.py` contains two small shims for `genlayer-test 0.30.0rc2`:
- JSON LLM mocks are returned as text, matching real nodes.
- On Windows, a temp-file unlink failure is ignored.

## Preflight against Bradbury (free, read-only)

```bash
python scripts/preflight.py
```

This calls `gen_getContractSchema` on `https://rpc-bradbury.genlayer.com` and
prints the ABI. If the runner pin were wrong, you would see
`runner malformed` here instead of after paying for a deployment.

## Deploy to Testnet Bradbury

```bash
npm install -g genlayer
genlayer network set testnet-bradbury
genlayer account create            # or import an existing testnet key
# fund the printed address: https://testnet-faucet.genlayer.foundation/
genlayer deploy --contract contracts/milestone_escrow.py
```

You can view the deployed contract at
`https://scan.bradbury.genlayer.com/address/<CONTRACT_ADDRESS>`.

## Example session

```bash
C=<CONTRACT_ADDRESS>
# client locks 5 GEN for a provider, 3 criteria, 2-day deadline, 2 attempts
genlayer write $C create_deal --args 0xPROVIDER "Landing page" "Has a dark mode toggle; Responsive on mobile; Has a contact form" 172800 2 --value 5000000000000000000
# provider
genlayer write $C submit_delivery --args 0 https://example.com/my-delivery
# anyone
genlayer write $C adjudicate --args 0
genlayer call  $C get_deal --args 0
# provider pulls funds after ACCEPT
genlayer write $C withdraw
```

## License

MIT
