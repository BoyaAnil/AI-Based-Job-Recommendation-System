# Contributing

## Development Workflow

1. Create a branch from `main`.
2. Implement focused changes.
3. Run relevant tests locally.
4. Open a pull request with clear scope and validation notes.

## Branch Naming

Use descriptive prefixes:

- `feat/<short-description>`
- `fix/<short-description>`
- `docs/<short-description>`
- `chore/<short-description>`

## Code Standards

- Keep changes minimal and scoped.
- Prefer readable, maintainable code over clever shortcuts.
- Follow existing patterns in `web/` and `ai/`.
- Update docs when behavior/config changes.

## Local Validation Before PR

From `ai/`:

```powershell
pytest
```

From `web/`:

```powershell
python manage.py test
```

Manual checks:

1. Upload and parse resume.
2. Match and skill-gap on a job.
3. Recommendations flow.
4. Admin dashboard/job CRUD (if applicable to your change).

## Pull Request Checklist

- [ ] Problem and solution are clearly described.
- [ ] Tests pass locally.
- [ ] New config/env vars are documented.
- [ ] User-facing behavior changes are documented.
- [ ] No secrets committed.

## Commit Message Style

Use imperative, concise subject lines, for example:

- `Add docs scaffold for project architecture and operations`
- `Fix fallback behavior when AI service returns 5xx`
