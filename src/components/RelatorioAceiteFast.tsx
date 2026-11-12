import React from 'react';
import styles from './RelatorioAceiteFast.module.css';

// Types to mirror expected API structure
type Metric = {
  id: string;
  label: string;
  value: string | number;
};

type FlowStep = {
  name: string;
  quantity: number;
};

type TableRow = {
  stage: string;
  quantity: number;
  avgProcessing: string; // readable string like "2h 10m"
  percent: string;
};

type SLAAlert = {
  cnpj: string;
  reason: string;
  time: string;
};

// Mocked data (replaceable by props / API payload later)
const MOCK_DATA = {
  company: 'Empresa Exemplo S.A.',
  period: 'Últimos 7 dias',
  generatedAt: new Date().toLocaleString('pt-BR'),
  metrics: [
    { id: 'recebidos', label: 'Total CNPJs recebidos do Simplifique', value: 1234 },
    { id: 'enviados', label: 'Total enviados para o SFA', value: 1100 },
    { id: 'fila', label: 'Total em fila / não tratados', value: 134 },
    { id: 'novos', label: 'Clientes novos (não existentes no Salesforce)', value: 42 },
    { id: 'sla', label: 'SLA médio (em horas)', value: 3.6 },
  ] as Metric[],
  flow: [
    { name: 'Recebido do Simplifique', quantity: 1234 },
    { name: 'Tratado', quantity: 1200 },
    { name: 'Enviado para SFA', quantity: 1100 },
    { name: 'Retornado para Simplifique', quantity: 80 },
  ] as FlowStep[],
  table: [
    { stage: 'Recebido', quantity: 1234, avgProcessing: '2h 10m', percent: '100%' },
    { stage: 'Tratado', quantity: 1200, avgProcessing: '1h 50m', percent: '97%' },
    { stage: 'Enviado', quantity: 1100, avgProcessing: '3h 5m', percent: '89%' },
    { stage: 'Retornado', quantity: 80, avgProcessing: '12h 0m', percent: '6%' },
  ] as TableRow[],
  slaAlerts: [
    { cnpj: '12.345.678/0001-00', reason: 'Excedeu SLA (48h)', time: '72h' },
    { cnpj: '98.765.432/0001-99', reason: 'Excedeu SLA (24h)', time: '30h' },
  ] as SLAAlert[],
  footer: {
    disclaimer: 'Este relatório é gerado automaticamente para uso operacional. Valores simulados.',
    source: 'Fonte: API Aceite Fast (mock)',
    version: 'v0.1-mock',
  },
};

// Single-file, presentational component. Ready to accept real data via props in future.
export default function RelatorioAceiteFast({
  data = MOCK_DATA,
}: {
  data?: typeof MOCK_DATA;
}) {
  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <div className={styles.company}>{data.company}</div>
        <div className={styles.meta}>
          <div className={styles.title}>Relatório Aceite Fast</div>
          <div className={styles.subtitle}>Resumo operacional do processo</div>
          <div style={{ marginTop: 6 }}>{data.period}</div>
          <div style={{ marginTop: 4, fontSize: 11 }}>{data.generatedAt}</div>
        </div>
      </header>

      {/* Executive summary cards */}
      <section aria-labelledby="executive-summary">
        <h2 id="executive-summary" style={{ display: 'none' }}>Executive Summary</h2>
        <div className={styles.summaryGrid}>
          {data.metrics.map((m) => (
            <div key={m.id} className={styles.card}>
              <div className={styles.cardLabel}>{m.label}</div>
              <div className={styles.cardValue}>{m.value}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Process flow */}
      <section className={styles.flow} aria-labelledby="process-flow">
        <h3 id="process-flow" style={{ fontSize: 14, marginBottom: 8 }}>Fluxo do processo</h3>
        <div className={styles.flowLine}>
          {data.flow.map((step, idx) => (
            <React.Fragment key={step.name}>
              <div className={styles.flowBox} style={{ minWidth: 160 }}>
                <div style={{ fontWeight: 700 }}>{step.name}</div>
                <div style={{ fontSize: 11, color: '#475569', marginTop: 4 }}>{step.quantity} itens</div>
              </div>
              {idx < data.flow.length - 1 && <div className={styles.arrow}>→</div>}
            </React.Fragment>
          ))}
        </div>
      </section>

      {/* Performance table */}
      <section className={styles.tableWrap} aria-labelledby="performance-table">
        <h3 id="performance-table" style={{ fontSize: 14, marginBottom: 8 }}>Desempenho agregado</h3>
        <table>
          <thead>
            <tr>
              <th>Etapa</th>
              <th>Quantidade</th>
              <th>Tempo médio</th>
              <th>% do total</th>
            </tr>
          </thead>
          <tbody>
            {data.table.map((r) => (
              <tr key={r.stage}>
                <td>{r.stage}</td>
                <td>{r.quantity}</td>
                <td>{r.avgProcessing}</td>
                <td>{r.percent}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* SLA & Alerts */}
      <section className={styles.alerts} aria-labelledby="sla-alerts">
        <h4 id="sla-alerts" style={{ marginTop: 0, fontSize: 13 }}>SLA & Alertas</h4>
        <div>
          <strong>Exemplo de CNPJs com SLA excedido:</strong>
        </div>
        <ul style={{ marginTop: 8, marginBottom: 6 }}>
          {data.slaAlerts.map((a) => (
            <li key={a.cnpj}>
              {a.cnpj} — {a.reason} ({a.time})
            </li>
          ))}
        </ul>
        <div style={{ fontSize: 12, color: '#475569' }}>
          Observação: tom suave para alertas, adequado para impressão e relatórios executivos.
        </div>
      </section>

      <footer className={styles.footer}>
        <div>{data.footer.disclaimer}</div>
        <div style={{ marginTop: 6 }}>{data.footer.source} — {data.footer.version}</div>
      </footer>
    </div>
  );
}
