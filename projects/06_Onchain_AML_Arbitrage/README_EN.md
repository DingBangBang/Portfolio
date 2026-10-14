# 06 · On-chain AML & Arbitrage Path Mining (Onchain_AML_Arbitrage)

> 中文版 → [README.md](./README.md)

**_Two cases on Ethereum data with a Neo4j graph database: AML fund-splitting tracing and Uniswap multi-hop arbitrage path mining._**

- Language: `Cypher` `Python`
- Core file: [neo4j_arbitrage_mining.cypher](./neo4j_arbitrage_mining.cypher)
- Screenshots: [AML graph analysis](./Neo4j_cypher_analysis_AML.png) · [Arbitrage paths](./DeFi%20Arbitrage%20Path%20Discovery%20on%20Neo4j.png)

## 1. Background

On-chain data is naturally a graph: addresses are nodes, transfers are edges. Multi-hop questions like "where does this money end up after being split across layers" are painful in a relational DB but a native fit for a graph DB's variable-length path queries. This project lands two typical risk / trading scenarios in Neo4j:

- **Case 1 · AML**: identify suspicious addresses doing fan-out (splitting) transfers and trace the full fund path;
- **Case 2 · DeFi arbitrage**: read Uniswap V2 pool reserves, compute pair rates, and mine multi-hop cyclic arbitrage paths.

## 2. Stack

| Stage | Tools |
| --- | --- |
| On-chain reads | `web3.py` (Infura RPC / Ethereum mainnet) |
| Data processing | `pandas` (with a `tqdm` progress bar) |
| Graph database | `Neo4j` (`neo4j-admin import` bulk load + Cypher) |
| Python driver | official `neo4j` driver |
| Visualisation | Neo4j Browser |

## 3. Data

Flow: **Ethereum mainnet (Infura RPC) → web3.py → Python computation → CSV → Neo4j bulk import → Cypher analysis**.

| File | Content | Scale (example) |
| --- | --- | --- |
| `nodes_addresses.csv` | Address nodes (`:ID(Address)`) | ~56,286 addresses |
| `transactions.csv` | Native transfers (from → to, value, hash) | ~73,876 edges |
| `usdt_addresses.csv` | USDT(ERC-20) address nodes | ~1,251 addresses |
| `usdt_transfers.csv` | USDT Transfer event edges | ~1,037 edges |
| `assets_core.csv` / `trading_pairs_core.csv` | Core token nodes and pair rates | 10 core pools |
| `*_unified.csv` | Header-unified import files (`value:string` + `block_number:int`) | — |

## 4. Key findings / design notes

**AML fund-splitting tracing**

- Identify intermediary addresses with variable-length paths: from a suspect address, find fan-out structures where one intermediary sends to multiple distinct receivers, ranked by fan-out count;
- Trace the two-hop path "suspect → intermediary → final receiver" to reassemble scattered transfers into a fund chain;
- Wrap the queries in Python (`aml_analysis.py`) to output, for any address, "in/out overview + splitting-risk addresses + final flow" in one shot.

**Uniswap arbitrage mining**

- Read `getReserves()` for core Uniswap V2 pools, compute `rate = reserve1/reserve0`, and write bidirectional `TRADING_PAIR` edges;
- Find closed loops with the same start and end node (2–6 hops), multiplying hop rates via `reduce(acc * rel.rate)` to get `finalAmount`; `> 1` means an arbitrage window;
- Recompute net profit after Uniswap's 0.3% fee (each hop × `0.997`) to avoid paper-only arbitrage;
- Measured: the 3-hop `USDC → WETH → WBTC → USDC` path gives `finalAmount ≈ 1.001377`, i.e. ~`0.1377%` net — small, but exactly what high-frequency bots target;
- Also runs data-quality checks: rate consistency (A→B→A ≈ 1) and detection of one-way pairs.

## 5. Layout

```
06_Onchain_AML_Arbitrage/
├── export_transactions.py       # Case 1: export native transfer CSVs (nodes + edges)
├── export_erc20_to_csv.py       # Case 1: export USDT(ERC-20) transfer event CSVs
├── export_erc20.py              # ERC-20 event reads (incl. ABI-loading debugging)
├── unify_csv_format.py          # Unify CSV headers for neo4j-admin import
├── aml_analysis.py              # Case 1: three-part analysis of a suspect address
├── aml_tracing.py               # Neo4j connection & query skeleton
├── neo4j_aml_fanout_ana.cypher  # Case 1: fund-splitting Cypher
├── fetch_uniswap_rates.py       # Case 2: read Uniswap reserves and compute rates
├── neo4j_arbitrage_mining.cypher    # Case 2: arbitrage path mining Cypher (core code)
└── *.csv / *.png                # Import data and result screenshots
```

## 6. How to run

**Env**: start Neo4j locally or via Docker (default `bolt://localhost:7687`).

1. **Export on-chain data**: replace `RPC_URL` in `export_transactions.py` / `export_erc20_to_csv.py` with your own Infura (or other) node, then run to get the `nodes/transactions/usdt_*` CSVs;
2. **Unify format**: `python unify_csv_format.py` produces `*_unified.csv`;
3. **Bulk import**:
   ```
   neo4j-admin database import full neo4j \
     --nodes=nodes_addresses_fixed.csv \
     --relationships=transactions_unified.csv \
     --nodes=usdt_addresses_fixed.csv \
     --relationships=usdt_transfers_unified.csv
   ```
4. **AML analysis**: run `neo4j_aml_fanout_ana.cypher` in Neo4j Browser, or `python aml_analysis.py` (change `PASSWORD` to yours);
5. **Arbitrage mining**: run `python fetch_uniswap_rates.py` to generate pair rates, import them, then run `neo4j_arbitrage_mining.cypher`.

> ⚠️ The `RPC_URL / API key / password` in the scripts are historical examples. Replace them with your own and keep them safe — never commit real secrets.
