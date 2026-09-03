# Frontend Agent Instructions

These instructions extend the repository-root [`AGENTS.md`](../../AGENTS.md) for all files under
`apps/web/`. Apply both files. Global security, organization isolation, Git, documentation, and
verification rules remain mandatory.

## Backend Contracts

The UI consumes Backend contracts. Do not invent response fields, statuses, error semantics,
authorization behavior, or metric meaning in frontend types, mocks, services, or components.

Search current contracts and backend schemas before changing a service boundary. If the Backend
contract is missing or insufficient, report the gap and coordinate a canonical contract update.
Mocks must be labeled as mocks and must not silently become a competing contract.

## Type Safety

- Follow the current `tsconfig.json`, Next.js, ESLint, and package-script configuration.
- Preserve strict TypeScript checking and typed service or API boundaries.
- Do not introduce `any`, unsafe assertions, broad lint suppression, or disabled checks merely to
  make code compile.
- Keep frontend types synchronized with approved Backend contracts in the same pull request.

## UI States

Implement the states relevant to the task: loading, empty, processing, success, error,
unauthorized, and retry. Do not present missing, stale, failed, or still-processing data as a
successful result. Preserve accessible and understandable user feedback.

## Frontend Security

Never expose secrets, database credentials, provider tokens, server-only configuration, or private
organization data in browser bundles, logs, mock data, snapshots, or rendered errors. The browser
must not directly access the database or provider secrets. Use approved Backend interfaces and
preserve authenticated organization scope.

## Frontend Verification

Read `package.json` and `.github/workflows/ci.yml` before selecting checks. From `apps/web/`, the
current standard commands are:

```bash
npm run lint
npm run type-check
npm test
npm run build
```

Run the checks applicable to the change and report each result as `PASS`, `FAIL`, or
`NOT RUN — <reason>`. Do not claim a browser flow is verified solely because unit tests pass.
