# Release Process

## 1. Environment profiles

Use one profile per environment:

- `env/.env.dev.example`
- `env/.env.stage.example`
- `env/.env.prod.example`

Copy the correct profile to root `.env` and replace secrets.

## 2. Preflight

Run the preflight script before merge/release:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/release_preflight.ps1 -Environment stage
```

The script validates:

- required env vars in `.env`
- frontend production build
- smoke e2e
- smoke enterprise admin

## 3. Branch and release flow

1. Develop on feature branch.
2. Run tests + preflight.
3. Merge into `dev`.
4. Deploy to staging with stage profile.
5. Run UAT.
6. Promote to production with prod profile.

## 4. Rollback

If release fails:

1. Restore previous `.env` profile.
2. Rollback deployment image/tag.
3. Validate with:
   - `scripts/smoke_e2e.ps1`
   - `scripts/smoke_enterprise_admin.ps1`
