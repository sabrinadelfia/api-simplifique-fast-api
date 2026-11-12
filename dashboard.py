import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import requests

DB_PATH = os.environ.get('DB_PATH', 'data.db')
TEAMS_WEBHOOK = os.environ.get('TEAMS_WEBHOOK')
WEEK_CRON_DAY = os.environ.get('WEEK_CRON_DAY', 'mon')
WEEK_CRON_HOUR = int(os.environ.get('WEEK_CRON_HOUR', '9'))
WEEK_CRON_MINUTE = int(os.environ.get('WEEK_CRON_MINUTE', '0'))

app = Flask(__name__)


def get_conn():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cnpj TEXT,
        source TEXT,
        status TEXT,
        product_location TEXT,
        is_new INTEGER,
        received_at TEXT,
        processed_at TEXT,
        returned_at TEXT
    )
    ''')
    conn.commit()
    conn.close()


def add_record(data):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''INSERT INTO records
        (cnpj, source, status, product_location, is_new, received_at, processed_at, returned_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('cnpj'),
        data.get('source'),
        data.get('status'),
        data.get('product_location'),
        1 if data.get('is_new') else 0,
        data.get('received_at'),
        data.get('processed_at'),
        data.get('returned_at'),
    ))
    conn.commit()
    conn.close()


def compute_metrics():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) as total FROM records')
    total = cur.fetchone()['total']
    cur.execute("SELECT COUNT(*) as processed FROM records WHERE status='processed'")
    processed = cur.fetchone()['processed']
    cur.execute("SELECT COUNT(*) as returned FROM records WHERE status='returned'")
    returned = cur.fetchone()['returned']
    cur.execute("SELECT COUNT(*) as new_customers FROM records WHERE is_new=1")
    new_customers = cur.fetchone()['new_customers']
    cur.execute("SELECT product_location, COUNT(*) as cnt FROM records GROUP BY product_location")
    by_product = {row['product_location'] if row['product_location'] else 'unknown': row['cnt'] for row in cur.fetchall()}

    # timing details: average durations in seconds
    cur.execute('SELECT AVG((julianday(processed_at)-julianday(received_at))*24*60*60) as avg_receive_to_process FROM records WHERE processed_at IS NOT NULL AND received_at IS NOT NULL')
    avg_rp = cur.fetchone()['avg_receive_to_process'] or 0
    cur.execute('SELECT AVG((julianday(returned_at)-julianday(processed_at))*24*60*60) as avg_process_to_return FROM records WHERE returned_at IS NOT NULL AND processed_at IS NOT NULL')
    avg_pr = cur.fetchone()['avg_process_to_return'] or 0

    conn.close()
    return {
        'total_received': total,
        'total_processed': processed,
        'total_returned': returned,
        'new_customers': new_customers,
        'by_product_location': by_product,
        'avg_receive_to_process_seconds': round(avg_rp, 1),
        'avg_process_to_return_seconds': round(avg_pr, 1),
    }


def send_teams_message(text):
    if not TEAMS_WEBHOOK:
        app.logger.warning('TEAMS_WEBHOOK not configured; skipping notification')
        return False
    payload = {"text": text}
    try:
        resp = requests.post(TEAMS_WEBHOOK, json=payload, timeout=10)
        return resp.status_code in (200, 201)
    except Exception as e:
        app.logger.exception('Failed to send Teams message: %s', e)
        return False


def weekly_job():
    metrics = compute_metrics()
    msg = (f"Relatório semanal - Aceite Fast:\n"
           f"Total recebidos: {metrics['total_received']}\n"
           f"Processados: {metrics['total_processed']}\n"
           f"Retornados ao simplifique: {metrics['total_returned']}\n"
           f"Clientes novos: {metrics['new_customers']}\n"
           f"Por local de produto: {metrics['by_product_location']}\n"
           f"Tempo médio (receb→process): {metrics['avg_receive_to_process_seconds']}s")
    send_teams_message(msg)


@app.route('/records', methods=['POST'])
def api_add_record():
    data = request.get_json()
    if not data or 'cnpj' not in data:
        return jsonify({'error': 'payload must include cnpj and other fields'}), 400
    # normalize timestamps if provided
    for t in ('received_at', 'processed_at', 'returned_at'):
        if t in data and data[t]:
            try:
                parsed = datetime.fromisoformat(data[t])
                data[t] = parsed.isoformat()
            except Exception:
                data[t] = data[t]
    add_record(data)
    return jsonify({'status': 'ok'}), 201


@app.route('/metrics', methods=['GET'])
def api_metrics():
    return jsonify(compute_metrics())


@app.route('/')
def dashboard():
    m = compute_metrics()
    html = f"""
    <html><head><title>Aceite Fast - Dashboard</title></head><body>
    <h1>Relatório Aceite Fast</h1>
    <ul>
      <li>Total recebidos: {m['total_received']}</li>
      <li>Processados: {m['total_processed']}</li>
      <li>Retornados: {m['total_returned']}</li>
      <li>Clientes novos: {m['new_customers']}</li>
      <li>Por local de produto: {m['by_product_location']}</li>
      <li>Tempo médio (receb→proc): {m['avg_receive_to_process_seconds']} s</li>
    </ul>
    </body></html>
    """
    return html


def start_scheduler():
    scheduler = BackgroundScheduler()
    trigger = CronTrigger(day_of_week=WEEK_CRON_DAY, hour=WEEK_CRON_HOUR, minute=WEEK_CRON_MINUTE)
    scheduler.add_job(weekly_job, trigger, id='weekly_report', replace_existing=True)
    scheduler.start()
    return scheduler


if __name__ == '__main__':
    init_db()
    start_scheduler()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
