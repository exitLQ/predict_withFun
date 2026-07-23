# Contributing to predict_withFun

Thank you for helping improve predict_withFun. Contributions should preserve
the project's safety, source transparency, provider neutrality, and English
user interface.

## Before opening a change

- Search existing issues and pull requests.
- Use a feature request for behavior changes.
- Report vulnerabilities privately according to `SECURITY.md`.
- Keep one focused change per pull request.
- Never include real API keys, session cookies, DSNs, user data, or paid
  provider output in commits, fixtures, screenshots, logs, or issues.

## Development setup

```bash
git clone https://github.com/exitLQ/predict_withFun.git
cd predict_withFun
python -m venv .venv
```

Activate the environment, then install dependencies:

```bash
pip install -r requirements-dev.txt
npm ci
npx playwright install chromium
```

Copy `.env.example` to `.env`. Demo mode works without provider keys. Use only
your own test credentials and never commit `.env`.

## Quality checks

Run all checks relevant to the change:

```bash
ruff check .
python -m pytest -vv
npm run test:e2e
```

Provider tests must mock SDK/network behavior. Tests must not spend API credit
or depend on live Polymarket/provider availability.

For database changes:

- add a new Alembic revision;
- support PostgreSQL and SQLite;
- implement and review both `upgrade()` and `downgrade()`;
- update migration tests and the README.

For UI changes:

- keep visible copy in English;
- use semantic HTML and keyboard-accessible controls;
- verify desktop and mobile layouts;
- avoid inline scripts/styles so the CSP remains strict;
- add or update Playwright coverage for user-visible behavior.

## Pull requests

1. Create a branch from current `main`.
2. Make focused commits with imperative messages.
3. Update documentation in the same change.
4. Complete the pull request checklist.
5. Wait for all CI jobs and maintainer review.

By submitting a contribution, you agree that it is licensed under the MIT
License in this repository.
