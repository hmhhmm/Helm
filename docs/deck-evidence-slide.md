# Evidence slide (text for the deck)

Title: What we ran, not what we hope

- 123 backend tests. 122 passed and 1 skipped on SQLite, 123 passed on Postgres 16, plus 32 browser tests from a fresh clone. Output with date and commit is in docs/evidence.
- A ten case red team suite plus four extra attacks. It found and fixed one real bypass in our own injection detector.
- Audit hash chain. Editing any row makes verification fail and names the row. Shown in the run log.
- On chain anchor. The contract cannot receive funds and only hashes are written. Verified on a real in process EVM. Public test network hashes are added only once the deployment has been run.
- Live exchange rates from a real public API, saved with a timestamp.
- Real Gemini responses recorded for four documents, two of them poisoned, and replayed through the same schema check.
- Not claimed. A real bank, a public network transaction hash, or any independent penetration test.
