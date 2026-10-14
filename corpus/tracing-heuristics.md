# Transaction tracing heuristics and their limits (analyst notes)

> Analyst notes written for this project as a starter corpus; summaries, not primary sources.

## Common-input-ownership

If one transaction spends several inputs, the addresses are usually controlled by the same
entity, because signing all inputs needs all the keys. Analysts cluster addresses on this
basis. The assumption fails for CoinJoin and PayJoin transactions, where inputs from different
parties are combined on purpose, and clustering across them merges unrelated entities.

## Taint propagation models

Different models answer "how much of this balance came from the flagged source":
- Poison: any link to the source taints everything downstream fully. Simple and prone to false positives.
- Haircut: taint is proportional to the share of value that came from the source.
- FIFO: the oldest received funds are treated as spent first.
None is "correct"; the model chosen should be stated alongside the result.

## Service and exchange addresses

Addresses that belong to exchanges or other high-volume services have enormous counterparty
sets. Almost any address within a few hops of such a service has some indirect link to flagged
funds, so hop-distance exposure through them says little. Recognising a service address (very
high transaction count, many unrelated counterparties) should reduce the weight given to
indirect exposure.

## Coverage limits

Public explorers return recent transactions by default. A bounded graph search only reveals
exposure within the depth and transaction window it inspected, so "no exposure found" means
"none found in the inspected window", not "none exists".
