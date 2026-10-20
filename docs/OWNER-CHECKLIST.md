# What still needs the owner by hand

These steps need an account, a key or a person, so they cannot be done from the repository alone.

1. Fund the anchor wallet. The address printed by `python scripts/new_anchor_wallet.py` holds no test ETH. Send Sepolia test ETH to it from any faucet, then run `python scripts/deploy_anchor.py` and commit `docs/evidence/onchain.json`. Put the contract address in `.env` as `ANCHOR_CONTRACT`.
2. Model key. Done for Gemini. Keep `GEMINI_API_KEY` only in `.env`. To refresh the recording, run `python scripts/record_llm.py`.
3. Connect a real sandbox bank. Create a free sandbox account with a payments provider, put its keys in `.env`, and add an adapter behind `helm/bank/service.py`. The Executor does not change.
4. Register for the MyInvois pre production environment through the LHDN portal if a real e invoice call is wanted.
5. Deploy. Create the API from `render.yaml` and the web app on Vercel with root directory `apps/web`, then put the two links in the README.
6. Make the repository public and record the video from `docs/demo-script.md`. Add the video link to the README.
7. Update the slide deck. Use `docs/deck-evidence-slide.md` for the evidence slide and delete any claim that the evidence files do not back.
