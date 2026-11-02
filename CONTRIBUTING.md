# Contributing to Ezhuthu

Thank you for helping more people read Tamil inscriptions. Issues and pull requests are welcome, especially from
epigraphists and native Tamil speakers: reviews of the Tamil strings and of the drawn Vatteluttu letters are some of
the most useful contributions.

## Before you open a pull request

1. Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22.
2. `make setup`, then `make check` (ruff, pytest, design checks). Tests make no live model calls; live tests run only
   with `EZHUTHU_LIVE=1` and your own AWS credentials.
3. For the web app: `cd app/web && npm ci && npm run lint && npm test && npm run build`.
4. Add tests with your change. CI runs both checks on every pull request.

## House rules

- **API contracts first.** The API is specified in [`contracts/`](contracts/). A change to a contract needs the
  `contract-change` label and matching changes on both sides (API and web app).
- **Numbers come from reports.** Any result quoted in the README or the app comes from a file in `eval/reports/` or
  `benchmark/stats.json`; `tests/test_doc_numbers.py` checks the README. Do not estimate a number that was not measured.
- **Wording.** A restoration "matches the editors' restoration" (or differs from it); never call it "correct". "Over
  1,100 years old" applies only to the Pallava collection.
- **Model IDs** come only from [`config/models.yaml`](config/models.yaml).
- **Data.** Never commit `data/raw/`, model weights, `.env` files or secrets. The benchmark is CC BY-SA 4.0 and must
  keep its DHARMA attribution.

By contributing, you agree that your code is licensed under [Apache-2.0](LICENSE) and any data you add to
`benchmark/` under CC BY-SA 4.0.
