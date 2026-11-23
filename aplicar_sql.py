"""Executa um arquivo .sql no servidor painel_ateg e mostra o resultado do último SELECT.
Uso (Git Bash, na pasta painel_visitas):   python aplicar_sql.py sql/vw_visitas_anual.sql
Usa REMOTE_DB_HOST/PORT/USER/PASS/NAME do .env da pasta integracao_ateg_painel_servidor (ou desta pasta)."""
import os, sys
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

AQUI = Path(__file__).resolve().parent
for env in (AQUI.parent / "integracao_ateg_painel_servidor" / ".env", AQUI / ".env"):
    if env.exists():
        load_dotenv(env)
if len(sys.argv) < 2:
    sys.exit("Informe o arquivo: python aplicar_sql.py sql/vw_visitas_anual.sql")
sql = Path(sys.argv[1]).read_text(encoding="utf-8")
con = psycopg2.connect(host=os.environ["REMOTE_DB_HOST"], port=os.environ.get("REMOTE_DB_PORT", "5432"),
                       user=os.environ["REMOTE_DB_USER"], password=os.environ["REMOTE_DB_PASS"],
                       dbname=os.environ["REMOTE_DB_NAME"], connect_timeout=20)
cur = con.cursor()
cur.execute(sql)
if cur.description:
    print([d[0] for d in cur.description])
    for r in cur.fetchall():
        print(r)
con.commit()
con.close()
print("\nOK: arquivo executado.")
