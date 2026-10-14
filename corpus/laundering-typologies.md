# Bitcoin laundering typologies (analyst notes)

> Analyst notes written for this project as a starter corpus. They are summaries from general
> domain knowledge, not primary sources. Ingest published research and regulator guidance
> alongside them and prefer those when citing.

## Peeling chains

A peeling chain is a series of transactions where a large balance is repeatedly spent: each
transaction sends a small amount to a recipient (the "peel") and returns the large remainder to
a fresh change address, which is spent in the next transaction. It is used to move a large sum
in small pieces and to make the balance harder to follow. Peeling chains also describe ordinary
wallet behaviour (paying someone and receiving change), so a chain alone is a weak signal. Longer
chains with consistently small peels to many different recipients are more notable.

## CoinJoin and mixing

CoinJoin combines inputs from several users into one transaction with multiple equal-value
outputs, so an observer cannot tell which input funded which output. Custodial mixers instead
pool deposits and pay out from a separate reserve. Both break simple transaction-graph tracing.
Analysts treat a link that passes through a CoinJoin as weak evidence, because many unrelated
participants share the same transaction. Using a mixer is not by itself unlawful in all
jurisdictions, but it raises risk for the recipient's compliance review, and regulators have
sanctioned some mixing services.

## Chain-hopping

Chain-hopping converts funds between assets or blockchains (for example Bitcoin to a privacy-focused
coin and back) through exchanges, swap services or bridges to interrupt the trail. Bitcoin-only
analysis loses visibility at the swap; the deposit to a swap service or exchange is the last
observable point and should be recorded as an exit.

## Layering through many addresses

Funds are fanned out into many addresses and recombined, or passed through intermediary
addresses with no other purpose, to add distance from the source. Legitimate wallets also
generate many addresses, so context such as timing, amounts and counterparties matters.

## Cash-out points

Illicit proceeds generally have to reach an exchange, OTC desk, payment processor or merchant to
be converted or spent. Exposure of a deposit address at a regulated exchange to flagged sources is
the usual trigger for review and know-your-customer follow-up.
