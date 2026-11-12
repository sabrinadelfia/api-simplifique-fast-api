"""
Script para autenticar na API Simplifique e processar os dados.

Principais adaptações:
- Usa cloudscraper para realizar as requisições (contorno de Cloudflare).
- Remove emojis e caracteres especiais nas mensagens de log.
"""

import os
import logging
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import cloudscraper
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from urllib.parse import quote_plus

# Configurações
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
scraper = cloudscraper.create_scraper()

URL_BASE = os.getenv("SIMPLIFIQUE_URL_BASE", "https://book3.simplifiquevivoemp.com.br").rstrip("/")
URL_AUTH = f"{URL_BASE}/ApiSeguranca/Autenticacao/GetAutenticacao"
URL_DADOS = f"{URL_BASE}/AceiteFastApi/GetSimulacoesInvasaoAFast"

# Credenciais
CREDENCIAIS_API = {
    "loginRede": os.getenv("API_LOGIN", "API1234"),
    "senha": os.getenv("API_SENHA", "Api@Externa#71"),
}

# Conexão com SQL Server
SQL_SERVER = os.getenv("SQL_SERVER", "172.20.12.84") # 10.243.253.12
SQL_DATABASE = os.getenv("SQL_DATABASE", "DB_HISTORICO")
SQL_USER = os.getenv("SQL_USER", "Romulo.Ferreira")  #  10.243.253.12	DB_CARTEIRA	Romulo.Ferreira	Vivo@15
SQL_PASSWORD = os.getenv("SQL_PASSWORD", "Vivo@15")

# SQLs
SQL = """
-- Limpeza de tabelas temporárias
IF OBJECT_ID('tempdb..#FDV_CARTEIRA') IS NOT NULL DROP TABLE #FDV_CARTEIRA;
IF OBJECT_ID('tempdb..#CLIENTE_B2B') IS NOT NULL DROP TABLE #CLIENTE_B2B;
IF OBJECT_ID('tempdb..#SIMPLIFIQUE') IS NOT NULL DROP TABLE #SIMPLIFIQUE;
IF OBJECT_ID('tempdb..#ADABAS_SIMPLIFIQUE') IS NOT NULL DROP TABLE #ADABAS_SIMPLIFIQUE;
IF OBJECT_ID('tempdb..#PRE_CARGA') IS NOT NULL DROP TABLE #PRE_CARGA;
IF OBJECT_ID('tempdb..#CARGA_DESPIVOTADA') IS NOT NULL DROP TABLE #CARGA_DESPIVOTADA;
IF OBJECT_ID('tempdb..##CARGA_DESPIVOTADA_DISTINTA') IS NOT NULL DROP TABLE ##CARGA_DESPIVOTADA_DISTINTA;
IF OBJECT_ID('tempdb..#CARGA') IS NOT NULL DROP TABLE #CARGA;

------------------------------------------------------------
SELECT DISTINCT [ADABAS_MOVEL] AS [ADABAS], [REGIONAL], [DIVISAO], 'BasicFixed__c;Mobile__c' AS [MODELO]
INTO #FDV_CARTEIRA
FROM [DB_FDV].[dbo].[TB_INFO_B2B_HIERARQUIA_PARCEIRO]

UNION ALL

SELECT DISTINCT [ADABAS_FIXA], [REGIONAL], [DIVISAO], 'Equipment__c;AdvancedFixed__c;BasicFixed__c;ManagementServices__c;DigitalSolutions__c;Security__c;VivoTech__c' AS [MODELO]
FROM [DB_FDV].[dbo].[TB_INFO_B2B_HIERARQUIA_PARCEIRO];

------------------------------------------------------------

SELECT 
     [ID],
     [BI_NO_IDENTIFICADOR_FISCAL__c],
     [Equipment__c],
     [AdvancedFixed__c],
     [BasicFixed__c],
     [Mobile__c],
     [ManagementServices__c],
     [DigitalSolutions__c],
     [BigData__c],
     [Security__c],
     [Cloud__c],
     [IOTM2M__c],
     [VivoTech__c]

INTO #CLIENTE_B2B
FROM [DB_CARTEIRA_SALESFORCE].[dbo].[TB_CLIENTEB2B] 
WHERE [BI_NO_IDENTIFICADOR_FISCAL__c] IN (
    SELECT DISTINCT [DOCUMENTO] FROM [DB_HISTORICO].[dbo].[BASE_SAIDA_API_FAST_SIMPLIFIQUE_HIST]
        WHERE [DT_PROCESSAMENTO] = (SELECT MAX([DT_PROCESSAMENTO]) FROM [DB_HISTORICO].[dbo].[BASE_SAIDA_API_FAST_SIMPLIFIQUE_HIST])
);

------------------------------------------------------------

SELECT 
     C.[ID],
     A.[DOCUMENTO],
     A.[ADABAS_SOLICITANTE],
     B.[MODELO]
INTO #SIMPLIFIQUE
FROM [DB_HISTORICO].[dbo].[BASE_SAIDA_API_FAST_SIMPLIFIQUE_HIST] A
INNER JOIN #FDV_CARTEIRA B ON A.[ADABAS_SOLICITANTE] = B.[ADABAS]
INNER JOIN #CLIENTE_B2B C ON A.[DOCUMENTO] = C.[BI_NO_IDENTIFICADOR_FISCAL__c];

------------------------------------------------------------

SELECT DISTINCT
      [ID]
     ,[DOCUMENTO]
     ,[ADABAS_SOLICITANTE]
     ,B.VALUE AS [TORRE]
INTO #ADABAS_SIMPLIFIQUE 
FROM #SIMPLIFIQUE
CROSS APPLY STRING_SPLIT([MODELO], ';') B;

------------------------------------------------------------

;WITH TORRES_PIVOTADAS AS 
(
    SELECT 
         [ID],
         [BI_NO_IDENTIFICADOR_FISCAL__c],
         [TORRE],
         [ADABAS]
    FROM #CLIENTE_B2B
    UNPIVOT (
        [ADABAS] FOR [TORRE] IN (
            [Equipment__c], [AdvancedFixed__c], [BasicFixed__c], [Mobile__c], 
            [ManagementServices__c], [DigitalSolutions__c], [BigData__c], 
            [Security__c], [Cloud__c], [IOTM2M__c], [VivoTech__c]
        )
    ) AS TORRES_DESPIVOTADAS
),
ADABAS_POR_LIMNHA AS 
(
    SELECT 
         [ID],
         [BI_NO_IDENTIFICADOR_FISCAL__c],
         [TORRE],
         LTRIM(RTRIM(value)) AS [ADABAS]
    FROM TORRES_PIVOTADAS
    CROSS APPLY STRING_SPLIT([ADABAS], ';')
)

SELECT DISTINCT
     [ID],
     [BI_NO_IDENTIFICADOR_FISCAL__c],
     [ADABAS],
     [TORRE]
INTO #PRE_CARGA
FROM ADABAS_POR_LIMNHA
ORDER BY 
     [BI_NO_IDENTIFICADOR_FISCAL__c],
     [TORRE],
     [ID],
     [ADABAS];

------------------------------------------------------------

SELECT DISTINCT *
INTO #CARGA_DESPIVOTADA
FROM #ADABAS_SIMPLIFIQUE

UNION

SELECT DISTINCT * 
FROM #PRE_CARGA;

------------------------------------------------------------

SELECT DISTINCT * 
INTO ##CARGA_DESPIVOTADA_DISTINTA
FROM #CARGA_DESPIVOTADA;

------------------------------------------------------------

;WITH AGRUPADOS AS 
(
    SELECT
         [ID],
         [DOCUMENTO],
         [Torre],
         STRING_AGG([ADABAS_SOLICITANTE], ';') AS ADABAS_AGRUPADOS
    FROM ##CARGA_DESPIVOTADA_DISTINTA
    GROUP BY [ID], [DOCUMENTO], [Torre]
)

SELECT
     [ID],
     [DOCUMENTO],
     [Equipment__c],
     [AdvancedFixed__c],
     [BasicFixed__c],
     [Mobile__c],
     [ManagementServices__c],
     [DigitalSolutions__c],
     [BigData__c],
     [Security__c],
     [Cloud__c],
     [IOTM2M__c],
     [VivoTech__c]
INTO #CARGA
FROM (
    SELECT 
         [ID],
         [DOCUMENTO],
         [Torre],
         [ADABAS_AGRUPADOS]
    FROM AGRUPADOS
) AS FONTE
PIVOT (
    MAX(ADABAS_AGRUPADOS)
    FOR [Torre] IN (
        [Equipment__c], [AdvancedFixed__c], [BasicFixed__c], [Mobile__c], 
        [ManagementServices__c], [DigitalSolutions__c], [BigData__c], 
        [Security__c], [Cloud__c], [IOTM2M__c], [VivoTech__c]
    )
) AS TABELA;

------------------------------------------------------------

INSERT INTO [DB_HISTORICO].[dbo].[BASE_CARGA_API_FAST_SIMPLIFIQUE_SFA_HIST] (
    [ID],
    [DOCUMENTO],
    [Equipment__c],
    [AdvancedFixed__c],
    [BasicFixed__c],
    [Mobile__c],
    [ManagementServices__c],
    [DigitalSolutions__c],
    [BigData__c],
    [Security__c],
    [Cloud__c],
    [IOTM2M__c],
    [VivoTech__c],
    [DATA_CARGA]
)
SELECT DISTINCT
     [ID],
     [DOCUMENTO],
     COALESCE([Equipment__c], '')            AS [Equipment__c],
     COALESCE([AdvancedFixed__c], '')        AS [AdvancedFixed__c],
     COALESCE([BasicFixed__c], '')           AS [BasicFixed__c],
     COALESCE([Mobile__c], '')            AS [Mobile__c],
     COALESCE([ManagementServices__c], '')    AS [ManagementServices__c],
     COALESCE([DigitalSolutions__c], '')    AS [DigitalSolutions__c],
     COALESCE([BigData__c], '')            AS [BigData__c],
     COALESCE([Security__c], '')            AS [Security__c],
     COALESCE([Cloud__c], '')                AS [Cloud__c],
     COALESCE([IOTM2M__c], '')            AS [IOTM2M__c],
     COALESCE([VivoTech__c], '')            AS [VivoTech__c],
     GETDATE()
FROM #CARGA;

"""

SAIDA = """
SELECT * FROM  [DB_HISTORICO].[dbo].[BASE_CARGA_API_FAST_SIMPLIFIQUE_SFA_HIST]
WHERE [DATA_CARGA] IN (SELECT MAX([DATA_CARGA]) FROM [DB_HISTORICO].[dbo].[BASE_CARGA_API_FAST_SIMPLIFIQUE_SFA_HIST]);
"""

SQL_ATUALIZACAO = SQL
SQL_EXPORTACAO = SAIDA


def autenticar_api(timeout: int = 30):
    try:
        resp = scraper.post(URL_AUTH, json=CREDENCIAIS_API, timeout=timeout)
        resp.raise_for_status()
        token = resp.json().get("retornoToken", {}).get("ds_token")
        if token:
            logging.info("Token JWT obtido com sucesso.")
            return token
        logging.error("Resposta da autenticação não contém token.")
    except Exception as e:
        logging.error(f"Erro na autenticação: {e}")
    return None


def obter_dados_api(token, timeout: int = 30):
    if not token:
        logging.error("Token ausente ao obter dados.")
        return None, None
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = scraper.get(URL_DADOS, headers=headers, timeout=timeout)
        resp.raise_for_status()
        dados = resp.json()
        df = pd.DataFrame([dados] if isinstance(dados, dict) else dados)

        # Limpeza da coluna 'ADABAS_SOLICITANTE'
        if 'ADABAS_SOLICITANTE' in df.columns:
            condicao = (
                df['ADABAS_SOLICITANTE'].astype(str).str.startswith('MPJ', na=False) |
                df['ADABAS_SOLICITANTE'].astype(str).str.startswith('MPF', na=False) |
                df['ADABAS_SOLICITANTE'].isna() |
                (df['ADABAS_SOLICITANTE'].astype(str).str.strip() == '') |
                (df['ADABAS_SOLICITANTE'] == '00000')
            )
            linhas_removidas = condicao.sum()
            if linhas_removidas > 0:
                logging.info(f"Removendo {linhas_removidas} linhas com ADABAS_SOLICITANTE inválido.")
            df = df[~condicao]

        timestamp = datetime.now().strftime("%Y-%m-%d-%Hh%Mm%Ss")
        df["DT_PROCESSAMENTO"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return df, timestamp
    except Exception as e:
        logging.error(f"Erro ao obter dados da API: {e}")
        return None, None


def criar_engine_sql(server, database, user, password):
    # Tenta usar pyodbc; se não estiver disponível, tenta pymssql como fallback.
    try:
        import pyodbc  # type: ignore
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server};DATABASE={database};UID={user};PWD={password}"
        )
        quoted = quote_plus(conn_str)
        return create_engine(f"mssql+pyodbc:///?odbc_connect={quoted}")
    except Exception:
        logging.warning("pyodbc não encontrado; tentando pymssql como alternativa.")
        try:
            import pymssql  # type: ignore
            return create_engine(f"mssql+pymssql://{user}:{password}@{server}/{database}")
        except Exception:
            logging.error(
                "Nenhum driver disponível para conexão com SQL Server. "
                "Instale 'pyodbc' (pip install pyodbc) e o Microsoft ODBC Driver 17 for SQL Server, "
                "ou instale 'pymssql' (pip install pymssql) como alternativa."
            )
            raise


def inserir_dados_sql(df, engine):
    if df is None or df.empty:
        logging.warning("DataFrame vazio. Nenhum dado inserido.")
        return
    try:
        df.to_sql(
            'BASE_SAIDA_API_FAST_SIMPLIFIQUE_HIST',
            engine,
            chunksize=10000,
            method='multi',
            if_exists='append',
            index=False,
            dtype={
                'NR_OPT_SIMULACAO': sqlalchemy.types.VARCHAR(length=13),
                'DOCUMENTO': sqlalchemy.types.VARCHAR(length=14),
                'ADABAS_SOLICITANTE': sqlalchemy.types.VARCHAR(length=55),
                'PRODUTO': sqlalchemy.types.VARCHAR(length=255),
                'STATUS_SIMULACAO': sqlalchemy.types.VARCHAR(length=55),
                'DATA_APROVACAO_ACEITE': sqlalchemy.types.VARCHAR(length=19),
                'DT_PROCESSAMENTO': sqlalchemy.DateTime()
            }
        )
        logging.info("Dados inseridos com sucesso no SQL.")
    except SQLAlchemyError as e:
        logging.error(f"Erro ao inserir dados no SQL: {e}")


def executar_sql(engine, sql):
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                conn.execute(text(sql))
                trans.commit()
                logging.info("SQL executado com sucesso.")
            except Exception as e:
                trans.rollback()
                logging.error(f"Erro durante execução do SQL: {e}")
    except SQLAlchemyError as e:
        logging.error(f"Erro de conexão com o banco: {e}")


def exportar_consulta(engine, sql, timestamp):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            filename = f"INSPECTOR_{timestamp}.csv"
            df.to_csv(filename, index=False)
            logging.info(f"Consulta exportada como '{filename}'.")
    except SQLAlchemyError as e:
        logging.error(f"Erro ao executar consulta: {e}")


if __name__ == "__main__":
    # Remover arquivos CSV no diretório do script antes de rodar
    try:
        script_dir = Path(__file__).resolve().parent
        csv_files = list(script_dir.glob('*.csv'))
        if csv_files:
            logging.info(f"Removendo {len(csv_files)} arquivos CSV em {script_dir}")
            for f in csv_files:
                try:
                    f.unlink()
                except Exception as e:
                    logging.warning(f"Falha ao remover {f}: {e}")
        else:
            logging.info("Nenhum arquivo CSV encontrado para remover.")
    except Exception as e:
        logging.warning(f"Erro ao limpar CSVs: {e}")

    token = autenticar_api()
    if token:
        df_dados, timestamp = obter_dados_api(token)
        if df_dados is not None and not df_dados.empty:
            engine_insert = criar_engine_sql(SQL_SERVER, SQL_DATABASE, SQL_USER, SQL_PASSWORD)
            engine_saida = criar_engine_sql(SQL_SERVER, SQL_DATABASE, SQL_USER, SQL_PASSWORD)
            entrada_filename = f"API_{timestamp}.csv"


            try:
                df_dados.to_csv(entrada_filename, index=False)
                logging.info(f"Arquivo de entrada '{entrada_filename}' salvo com sucesso.")
            except Exception as e:
                logging.error(f"Falha ao salvar arquivo de entrada: {e}")

            inserir_dados_sql(df_dados, engine_insert)
            executar_sql(engine_insert, SQL_ATUALIZACAO)
            exportar_consulta(engine_saida, SQL_EXPORTACAO, timestamp)
        else:
            logging.warning("Nenhum dado retornado da API.")
    else:
        logging.error("Nao foi possivel autenticar na API.")
 