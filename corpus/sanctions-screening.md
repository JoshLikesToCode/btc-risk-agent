# Sanctions screening for virtual currency (analyst notes)

> Analyst notes written for this project as a starter corpus; summaries, not legal advice or
> primary sources. Check current regulator guidance before relying on any point here.

## What the SDN list contains

The US Treasury's Office of Foreign Assets Control (OFAC) publishes the Specially Designated
Nationals and Blocked Persons (SDN) list. For some designated persons, the entry includes
digital currency addresses in the remarks, tagged by asset (for example "XBT" for Bitcoin).
These addresses are identifiers associated with the designated party; they are not an
exhaustive list of everything the party controls.

## Limits of address screening

- A listed address is strong evidence. An unlisted address is not evidence of non-involvement:
  designated parties can and do use addresses that are not listed.
- Sanctions obligations attach to dealings with designated parties and blocked property, not
  only to listed addresses. Screening should also cover names, jurisdictions and counterparties.
- Regulators describe a risk-based approach: identify, assess and mitigate sanctions risk
  proportionate to a firm's products, customers and geography.

## Exposure is not culpability

Receiving funds that trace back to a sanctioned address, directly or through several hops, shows
exposure, not intent or knowledge. Direct dealings with a listed address carry the most
concern. Indirect exposure through high-volume services, CoinJoin transactions or many hops is
weaker and produces false positives, so it should be reviewed by a person with the context
rather than treated as an automatic conclusion.

## Evasion patterns

Common evasion patterns include using unlisted addresses and intermediaries, splitting transfers
into small amounts, routing through mixers or privacy tools, converting to other assets, and
using services in jurisdictions with weaker controls.
