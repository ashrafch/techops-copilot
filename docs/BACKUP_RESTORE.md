# Backup e Restore Database

## Backup

```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup_db.ps1
```

Opzioni:
- `-ContainerName techops-postgres-app`
- `-DbUser techops`
- `-DbName techops`
- `-OutputPath backups/custom_name.sql`

## Restore

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore_db.ps1 -InputPath backups/techops_YYYYMMDD_HHMMSS.sql
```

## Test procedura consigliata

1. Esegui backup.
2. Crea ticket di prova.
3. Restore da backup.
4. Verifica che il ticket di prova non sia più presente.

## Policy consigliata

- Backup giornaliero automatico.
- Conservazione minima 30 giorni.
- Copia cifrata offsite.
- Test di restore almeno 1 volta al mese.
