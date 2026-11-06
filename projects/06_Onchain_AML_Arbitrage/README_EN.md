# 06 · On-chain AML and Arbitrage Path Mining (Onchain_AML_Arbitrage)

> 中文版 → [README.md](./README.md)

**_Addresses are nodes, transfers are edges. Multi-hop queries in SQL are painful; in a graph database they are the point._**

- Language: `Cypher` `Python`
- Core queries: [AML fan-out](./neo4j_aml_fanout_ana.cypher) · [arbitrage mining](./neo4j_arbitrage_mining.cypher)
- Screenshots: [AML graph](./Neo4j_cypher_analysis_AML.png) · [arbitrage path](./DeFi%20Arbitrage%20Path%20Discovery%20on%20Neo4j.png)

---

## 1. Why a graph database

On-chain data is a graph. "Where did this money end up after being split four times" is four self-joins in MySQL (half an hour to write, then you wait), and one variable-length pattern `[:SENT*1..3]` in Neo4j.

Two cases in this project:

- **AML**: find fan-out structures (one address paying many), then reconstruct where funds land two hops later;
- **Arbitrage**: read Uniswap V2 reserves, compute live rates, find closed loops in the graph, and check whether anything is left after the 0.3% fee.

## 2. Data flow

```mermaid
flowchart LR
    A[Ethereum mainnet<br/>RPC node] -->|web3.py get_block / get_logs| B[raw transfers]
    B -->|csv| C[transactions.csv<br/>usdt_transfers.csv]
    C -->|unify_csv_format.py| D[*_unified.csv]
    D -->|neo4j-admin import| E[(Neo4j<br/>Address -[:SENT]-> Transaction -[:TO]-> Address)]
    E --> F[AML: fan-out tracing]
    E --> G[arbitrage: rate loops<br/>reduce multiply]
    H[Uniswap V2 pools] -->|getReserves| I[assets_core.csv<br/>trading_pairs_core.csv]
    I --> E
```

## 3. Data volume (sample batch)

| File | Content | Size |
| --- | --- | --- |
| `nodes_addresses.csv` | address nodes | ~56,286 |
| `transactions.csv` | native transfers | ~73,876 |
| `usdt_addresses.csv` | USDT address nodes | ~1,251 |
| `usdt_transfers.csv` | USDT Transfer events | ~1,037 |
| `assets_core.csv` / `trading_pairs_core.csv` | tokens and rates | 10 pools |

## 4. What the two cases showed

**AML**

- The fan-out query ranks intermediate addresses directly; in this sample one intermediate address paid 17 distinct downstream addresses;
- Two-hop paths let you regroup the split money, and fan-out count plus receiver overlap is usually enough to eyeball whether someone is structuring;
- `aml_analysis.py` chains the three queries so switching address is one config change.

**Arbitrage**

- `USDC → WETH → WBTC → USDC` gives `finalAmount ≈ 1.001377`; after 0.3% per hop the net is about 0.1377%;
- Thin, but that is exactly the MEV bots' hunting range — the honest conclusion is "not a manual trade";
- I also ran a rate consistency check (A→B→A should be ≈ 1), **which is how I found two pool addresses I had copied from a blog were wrong**.

## 5. Performance (local, single machine)

| Step | Volume | Time |
| --- | --- | --- |
| Export 1,000 blocks of native transfers | 73,876 edges | ~7 min (RPC bound) |
| Export 10 blocks of USDT transfers | 1,037 | ~8s |
| `neo4j-admin import` | 50k+ nodes | ~30s |
| Three-hop arbitrage query | 10 pools | < 0.2s |
| Fan-out query | 50k nodes | ~1s |

## 6. Layout

```
06_Onchain_AML_Arbitrage/
├── config_loader.py              # single entry for config + logging
├── config.example.yaml           # block range, output names, pool sleep
├── .env.example                  # RPC_URL / NEO4J_PASSWORD
├── docker-compose.yml            # local Neo4j 5
├── export_transactions.py        # native transfers → CSV
├── export_erc20_to_csv.py        # USDT Transfer events → CSV
├── export_erc20.py               # debug version, kept for reference
├── unify_csv_format.py           # header normalisation for neo4j-admin import
├── aml_analysis.py               # the three AML queries
├── aml_tracing.py                # connection smoke test
├── fetch_uniswap_rates.py        # reserves → rates
└── *.cypher                      # the actual analysis
```

## 7. How to run

```bash
cp .env.example .env && docker compose up -d
pip install -r requirements.txt
python export_transactions.py
python unify_csv_format.py
docker exec -it onchain_neo4j neo4j-admin database import full neo4j \
  --nodes=/import/nodes_addresses_fixed.csv --relationships=/import/transactions_unified.csv
python aml_analysis.py
python fetch_uniswap_rates.py
```

## 8. Things that went wrong (and the compromises)

**1) Infura free tier ran out.**
100k requests/day; trying to scan the whole chain got me 429s within half an hour. Fixes: export narrow block ranges only, and `sleep(0.2)` between RPC calls. Slow, free.

**2) `get_logs` caps at 10,000 results.**
USDT alone blows past that in 10 blocks. The script now prints the actual hint ("shrink the range") so future-me does not debug it again.

**3) `value` as `long` overflowed on import.**
Wei has 18 decimals, large transfers exceed Java long, and the import error message does not say which column. Switched to `value:string`. `unify_csv_format.py` exists because of this — a whole script to patch headers, a bit silly, but cheaper than re-exporting.

**4) The importer is unforgiving about headers.**
Column names, order and type suffixes must match exactly; a mismatch fails the whole batch and the error only names the row. Hence the `*_unified.csv` and `*_fixed.csv` copies — ugly filenames, saved me from regenerating data.

**5) Two pool addresses were wrong.**
`WETH-UNI` and `WETH-LINK` came from an old blog post. Found it by accident: the A→B→A consistency check returned 0.7 instead of 1. After fixing, everything is ≈ 1.0.

**6) `0xSuspicious001` is a made-up address.**
The sample suspect address is synthetic, not a real case. Point `suspect_address` in `config.yaml` at a real address to rerun.

**7) The Infura key used to be hardcoded in five scripts.**
Caught during a pre-push review, rotated, and everything now reads from `.env`. A grep for the old key returns nothing.

## 9. TODO

- [ ] Move to a paid RPC (Alchemy) so full-chain scans stop getting throttled;
- [ ] Incremental import instead of rebuilding the database each time;
- [ ] Fully parameterise Cypher, `--address` on the command line instead of config edits;
- [ ] Only Uniswap V2 so far; V3 concentrated liquidity changes the maths completely, not touching it yet;
- [ ] Add a block timestamp property; estimating time from block height is awkward.

## 10. Credits

The Cypher queries, the two-hop tracing approach and the fee-adjusted arbitrage maths are mine and validated. `config_loader.py`, `docker-compose.yml` and the `unify_csv_format.py` skeleton were drafted with Cline and adapted to the real CSV headers. All keys and passwords are environment variables now; sample addresses are placeholders; data comes from public Ethereum on-chain records.
