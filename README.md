# Aceite Fast - Dashboard

Pequeno serviço Flask que coleta registros de `Aceite Fast`, gera métricas e envia um relatório semanal via Teams.

Instalação:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Como rodar (exemplo):

```powershell
# exporte a webhook do Teams (ou configure via Environment Variables no Windows)
$env:TEAMS_WEBHOOK = 'https://outlook.office.com/webhook/....'
python dashboard.py
```

Endpoints:

- `POST /records` : inserir um registro JSON com campos como `cnpj`, `source`, `status`, `product_location`, `is_new`, `received_at`, `processed_at`, `returned_at`.
- `GET /metrics` : retorna métricas agregadas em JSON.
- `GET /` : dashboard HTML simples.

Configuração:

- `TEAMS_WEBHOOK` : webhook para enviar relatório semanal.
- `DB_PATH` : caminho do arquivo SQLite (padrão `data.db`).
- `WEEK_CRON_DAY`, `WEEK_CRON_HOUR`, `WEEK_CRON_MINUTE` : controlam quando o job semanal roda (padrão segunda-feira 09:00).