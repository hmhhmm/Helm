# Evidence slide (text for the deck)

Title: What we ran, not what we hope

- 112 backend tests. 111 passed and 1 skipped on SQLite, 112 passed on Postgres 16. Output with date and commit is in docs/evidence.
- A ten case red team suite plus four extra attacks. It found and fixed one real bypass in our own injection detector.
- Audit hash chain. Editing any row makes verification fail and names the row. Shown in the run log.
- On chain anchor. The contract cannot receive funds and only hashes are written. Verified on a real in process EVM. Public test network hashes are added only once the deployment has been run.
- Live exchange rates from a real public API, saved with a timestamp.
- Not claimed. A real bank, a live model result, or any independent penetration test.
