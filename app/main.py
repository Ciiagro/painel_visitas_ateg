"""Painel "Acompanhamento das Visitas" (ATeG): visitas, propriedades assistidas, técnicos, supervisores, atividades.
Lê SOMENTE a view do servidor público (public.vw_visitas), nunca o banco local."""
import os
import re
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Response, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _db_url():
    """Usa DB_URL se existir; senão monta a conexão com as mesmas variáveis REMOTE_DB_* do script de cópia."""
    if os.environ.get("DB_URL") and "USUARIO_LEITURA" not in os.environ["DB_URL"]:
        return os.environ["DB_URL"]
    from sqlalchemy.engine import URL
    return URL.create(
        "postgresql+psycopg2",
        username=os.environ.get("REMOTE_DB_USER", "postgres"),
        password=os.environ["REMOTE_DB_PASS"],
        host=os.environ["REMOTE_DB_HOST"],
        port=int(os.environ.get("REMOTE_DB_PORT", "5432")),
        database=os.environ["REMOTE_DB_NAME"],
    )


DB_URL = _db_url()
TABLE = os.environ.get("TABLE_NAME", "public.vw_visitas")
if not re.fullmatch(r"[A-Za-z0-9_]+\.[A-Za-z0-9_]+", TABLE):
    raise RuntimeError("TABLE_NAME inválido (use schema.nome)")

# Pool pequeno: na Vercel cada instância é efêmera; evita estourar conexões do banco.
engine = create_engine(DB_URL, pool_pre_ping=True, pool_size=4, max_overflow=2, pool_recycle=300,
                       connect_args={"connect_timeout": 10})
app = FastAPI(title="Acompanhamento das Visitas")

# Usa a tabela pronta public.mv_visitas (bem mais rápida) quando ela existe e está atualizada com as colunas novas;
# senão cai para a view. TABLE_NAME na variável de ambiente sempre vale.
if "TABLE_NAME" not in os.environ:
    try:
        with engine.connect() as _c:
            _ok = _c.execute(text("SELECT to_regclass('public.mv_visitas') IS NOT NULL")).scalar() and _c.execute(text(
                "SELECT count(*) FROM pg_attribute WHERE attrelid = 'public.mv_visitas'::regclass AND attname IN ('latitude','situacao_validade') AND NOT attisdropped")).scalar() == 2
        if _ok:
            TABLE = "public.mv_visitas"
    except Exception:
        pass
print(f"[painel] consultando: {TABLE}")


# Cache de respostas (5 min): o mesmo filtro/período não refaz as consultas pesadas. Limpa sozinho ao reiniciar.
import time as _time
_CACHE: dict = {}
_CACHE_TTL = int(os.environ.get("CACHE_SEGUNDOS", "300"))


@app.middleware("http")
async def _cache_api(request: Request, call_next):
    if request.method != "GET" or not request.url.path.startswith("/api/") or request.url.path.startswith("/api/conferencia") or request.url.path.startswith("/api/desempenho") or _CACHE_TTL <= 0:
        return await call_next(request)
    k = request.url.path + "?" + str(request.url.query)
    hit = _CACHE.get(k)
    if hit and _time.time() - hit[0] < _CACHE_TTL:
        return Response(hit[1], media_type="application/json", headers={"X-Cache": "hit"})
    resp = await call_next(request)
    if resp.status_code == 200:
        corpo = b"".join([c async for c in resp.body_iterator])
        if len(_CACHE) > 300:
            _CACHE.clear()
        _CACHE[k] = (_time.time(), corpo)
        return Response(corpo, media_type="application/json", headers={"X-Cache": "miss"})
    return resp



templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_static = Path(__file__).parent / "static"
if _static.is_dir():
    app.mount("/img", StaticFiles(directory=str(_static)), name="img")

TEXTO = {"supervisor": "supervisor", "tecnico": "tecnico", "projeto": "projeto",
         "atividade": "atividade", "municipio": "municipio"}
# Filtros de Região (FAEC) e Sindicato: só aparecem quando a tabela/view consultada já tem essas colunas
# (rode `python sincronizar_municipios.py --criar-views` uma vez). Antes disso o painel funciona normalmente, sem eles.
try:
    with engine.connect() as _c:
        _cols = {r[0] for r in _c.execute(text(
            "SELECT attname FROM pg_attribute WHERE attrelid = to_regclass(:t) AND attnum > 0 AND NOT attisdropped"), {"t": TABLE})}
    if "regiao_faec" in _cols and "sindicato" in _cols:
        TEXTO["regiao"] = "regiao_faec"
        TEXTO["sindicato"] = "sindicato"
except Exception:
    pass
_MUN_EXTRA = ", MAX(regiao_faec) AS regiao, MAX(sindicato) AS sindicato" if "regiao" in TEXTO else ""

SIMNAO = {"coleta": "coleta_dados", "presencial": "presencial", "valida": "valida"}
# Propriedade ativa/inativa (situação oficial; se não houver, a do SisATeG). "sim" = ativa, "nao" = inativa.
# Situação da visita no SisATeG: VALIDA, VALIDADA ou INVALIDA ("validas" = VALIDA + VALIDADA).
SITUACAO_SQL = {"valida": "(situacao_validade = 'VALIDA')", "validada": "(situacao_validade = 'VALIDADA')",
                "validas": "(situacao_validade IN ('VALIDA','VALIDADA'))", "invalida": "(situacao_validade = 'INVALIDA')"}
ATIVA_SQL = {"sim": "(COALESCE(status_oficial, status_sisateg) ~* '^ativ')",
             "nao": "(COALESCE(status_oficial, status_sisateg) ~* '^inativ')"}

# Mapa de propriedades (pino por propriedade = localização de propriedades de produtores): só no computador local.
# Na Vercel (versão pública) fica DESLIGADO; para ligar: MAPA_PROPRIEDADES=1. O mapa de técnicos continua disponível.
_mp = os.environ.get("MAPA_PROPRIEDADES")
MAPA_PROPRIEDADES = (_mp.strip().lower() in ("1", "true", "sim")) if _mp is not None else not os.environ.get("VERCEL")


@app.get("/api/mapa/config")
def mapa_config():
    return {"propriedades": MAPA_PROPRIEDADES}


# Aba "Conferência" (compara a planilha do SisATeG com o painel). Ferramenta de trabalho: fica LIGADA só
# LIGADA também na Vercel. Para desligar: CONFERENCIA=0.
_conf = os.environ.get("CONFERENCIA")
CONFERENCIA = (_conf.strip().lower() in ("1", "true", "sim")) if _conf is not None else True


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


def _data(s, nome):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        raise HTTPException(400, f"Data inválida em '{nome}' (use AAAA-MM-DD)")


def _where(f, pular=None, de=None, ate=None):
    """WHERE + parâmetros. `pular` = filtro que não deve se aplicar a si mesmo (listas em cascata)."""
    w, p = ["1=1"], {}
    for k, col in TEXTO.items():
        if f.get(k) and k != pular:
            w.append(f"{col} = :{k}"); p[k] = f[k]
    for k, col in SIMNAO.items():
        v = (f.get(k) or "").lower()
        if v in ("sim", "nao") and k != pular:
            w.append(f"{col} IS {'TRUE' if v == 'sim' else 'FALSE'}")
    if (f.get("ativa") or "").lower() in ATIVA_SQL and pular != "ativa":
        w.append(ATIVA_SQL[f["ativa"].lower()])
    if (f.get("situacao") or "").lower() in SITUACAO_SQL and pular != "situacao":
        w.append(SITUACAO_SQL[f["situacao"].lower()])
    if de:
        w.append("dt_visita >= :de"); p["de"] = de
    if ate:
        w.append("dt_visita <= :ate"); p["ate"] = ate
    return " AND ".join(w), p


def _filtros_da_requisicao(request: Request):
    q = request.query_params
    return {k: q.get(k) for k in [*TEXTO, *SIMNAO, "ativa", "situacao"]}, q.get("de"), q.get("ate")


@app.get("/api/filtros")
def filtros(request: Request):
    """Listas dos filtros. Cada lista respeita TODOS os outros filtros e o período (filtros em cascata)."""
    f, de, ate = _filtros_da_requisicao(request)
    de = _data(de, "de") if de else None
    ate = _data(ate, "ate") if ate else None
    with engine.connect() as con:
        out = {}
        for k, col in TEXTO.items():
            w, p = _where(f, pular=k, de=de, ate=ate)
            out[k] = [r[0] for r in con.execute(text(
                f"SELECT DISTINCT {col} FROM {TABLE} WHERE {w} AND {col} IS NOT NULL ORDER BY 1"), p)]
        m = con.execute(text(f"SELECT MIN(dt_visita), MAX(dt_visita) FROM {TABLE}")).one()
    out["data_min"] = m[0].isoformat() if m[0] else None
    out["data_max"] = m[1].isoformat() if m[1] else None
    return out


_CARDS = """COUNT(DISTINCT id_visita) AS visitas,
  COUNT(DISTINCT id_propriedade) AS propriedades,
  COUNT(DISTINCT id_visita) FILTER (WHERE NOT coleta_dados) AS visitas_padrao,
  COUNT(DISTINCT id_visita) FILTER (WHERE coleta_dados) AS coleta_dados,
  COUNT(DISTINCT id_visita) FILTER (WHERE retorno) AS retorno,
  COUNT(DISTINCT id_visita) FILTER (WHERE "virtual") AS virtual,
  COUNT(DISTINCT id_visita) FILTER (WHERE visita_zero) AS zero,
  COUNT(DISTINCT id_visita) FILTER (WHERE valida) AS validas,
  COUNT(DISTINCT id_visita) FILTER (WHERE NOT valida) AS invalidas,
  COUNT(DISTINCT id_visita) FILTER (WHERE situacao_validade = 'VALIDA') AS so_valida,
  COUNT(DISTINCT id_visita) FILTER (WHERE situacao_validade = 'VALIDADA') AS validada,
  COUNT(DISTINCT id_visita) FILTER (WHERE presencial) AS presenciais,
  COUNT(DISTINCT supervisor) AS supervisores,
  COUNT(DISTINCT tecnico) AS tecnicos,
  COUNT(DISTINCT municipio) AS municipios"""


_SNAP = """SELECT DISTINCT ON (id_propriedade) id_propriedade, atividade, supervisor, tecnico,
    COALESCE(status_oficial, status_sisateg) AS status, status_sisateg, status_oficial
    FROM {tabela} WHERE {w} ORDER BY id_propriedade, dt_visita DESC, id_visita DESC"""
# Orientações são da VISITA (a view de origem junta por id_visita); a tabela repete linhas por visita, então 1 linha por id_visita.
_SNAPV = """SELECT DISTINCT ON (id_visita) id_visita, atividade, supervisor, tecnico,
    ori_aberta, ori_em_execucao, ori_concluida, ori_cancelada, ori_nao_realizada, ori_total
    FROM {tabela} WHERE {w} ORDER BY id_visita, dt_visita DESC"""
_SOMA_P = """COUNT(*) AS propriedades,
    COUNT(*) FILTER (WHERE status = 'ATIVO') AS ativas, COUNT(*) FILTER (WHERE status = 'INATIVO') AS inativas,
    COUNT(*) FILTER (WHERE status_sisateg = 'ATIVA' AND status_oficial = 'INATIVO') AS divergentes"""
_SOMA_O = """COALESCE(SUM(ori_total),0) AS ori_total, COALESCE(SUM(ori_concluida),0) AS ori_concluida,
    COALESCE(SUM(ori_em_execucao),0) AS ori_em_execucao, COALESCE(SUM(ori_aberta),0) AS ori_aberta,
    COALESCE(SUM(ori_cancelada),0) AS ori_cancelada, COALESCE(SUM(ori_nao_realizada),0) AS ori_nao_realizada"""


def _carteira(con, tabela, w, p, grupo, limite=""):
    """Propriedades (status) e orientações juntas, por grupo (None = total)."""
    sp, sv = _SNAP.format(tabela=tabela, w=w), _SNAPV.format(tabela=tabela, w=w)
    if grupo is None:
        r = _linhas(con, f"SELECT {_SOMA_P} FROM ({sp}) s", p)[0]
        r.update(_linhas(con, f"SELECT {_SOMA_O} FROM ({sv}) s", p)[0])
        r["visitas"] = con.execute(text(f"SELECT COUNT(DISTINCT id_visita) FROM {tabela} WHERE {w}"), p).scalar()
        return r
    rot = {"atividade": "(sem atividade)", "supervisor": "(sem supervisor)", "tecnico": "(sem técnico)"}[grupo]
    props = _linhas(con, f"SELECT COALESCE({grupo},'{rot}') AS nome, {_SOMA_P} FROM ({sp}) s GROUP BY 1", p)
    oris = {r["nome"]: r for r in _linhas(con, f"SELECT COALESCE({grupo},'{rot}') AS nome, {_SOMA_O} FROM ({sv}) s GROUP BY 1", p)}
    vis = {r["nome"]: r["v"] for r in _linhas(con, f"SELECT COALESCE({grupo},'{rot}') AS nome, COUNT(DISTINCT id_visita) AS v FROM {tabela} WHERE {w} GROUP BY 1", p)}
    for r in props:
        r["visitas"] = vis.get(r["nome"], 0)
    zero = {k: 0 for k in ("ori_total", "ori_concluida", "ori_em_execucao", "ori_aberta", "ori_cancelada", "ori_nao_realizada")}
    out = [{**r, **{k: v for k, v in oris.get(r["nome"], zero).items() if k != "nome"}} for r in props]
    out.sort(key=lambda r: -r["propriedades"])
    return out[:int(limite)] if limite else out


def _linhas(con, sql, p):
    from decimal import Decimal
    return [{k: (int(v) if isinstance(v, Decimal) else v) for k, v in r._mapping.items()}
            for r in con.execute(text(sql), p)]


_SEM = "'Não declarado'"
_FAIXA = """CASE WHEN idade IS NULL THEN 'Não declarado' WHEN idade < 17 THEN 'Até 17 anos' WHEN idade < 25 THEN '18 a 24 anos'
  WHEN idade < 46 THEN '25 a 45 anos' WHEN idade <= 64 THEN '46 a 64 anos' ELSE 'Acima de 64 anos' END"""


_ESC = """CASE WHEN formacao_academica IS NULL OR formacao_academica ~* '(n[aã]o declarada|sem informa)' THEN 'Não declarada'
  WHEN formacao_academica ~* 'sem escolaridade|analfabeto' THEN 'Sem escolaridade'
  WHEN formacao_academica ~* 'superior|p[oó]s|mestrado|doutor|gradua' THEN 'Nível superior'
  WHEN formacao_academica ~* 'm[eé]dio|t[eé]cnico' THEN 'Nível médio'
  WHEN formacao_academica ~* 'fundamental|b[aá]sica' THEN 'Nível fundamental'
  ELSE 'Não declarada' END"""


@app.get("/api/perfil")
def perfil(request: Request):
    """Perfil dos produtores (um registro por produtor, da visita mais recente do período) e das propriedades."""
    f, de, ate = _filtros_da_requisicao(request)
    if not de or not ate:
        raise HTTPException(400, "Informe de e ate (AAAA-MM-DD)")
    de, ate = _data(de, "de"), _data(ate, "ate")
    w, p = _where(f, de=de, ate=ate)
    prod = f"""WITH pr AS (SELECT DISTINCT ON (id_produtor) id_produtor, genero, estado_civil, idade, formacao_academica
        FROM {TABLE} WHERE {w} AND id_produtor IS NOT NULL ORDER BY id_produtor, dt_visita DESC)"""
    prop = f"""WITH pp AS (SELECT DISTINCT ON (id_propriedade) id_propriedade, perfil_fundiario, COALESCE(status_oficial, status_sisateg) AS st
        FROM {TABLE} WHERE {w} ORDER BY id_propriedade, dt_visita DESC)"""

    def grupo(con, cte, expr, de_tab):
        return _linhas(con, f"{cte} SELECT {expr} AS nome, COUNT(*) AS n FROM {de_tab} GROUP BY 1 ORDER BY 2 DESC", p)
    with engine.connect() as con:
        out = {"total_produtores": con.execute(text(f"{prod} SELECT COUNT(*) FROM pr"), p).scalar(),
               "total_propriedades": con.execute(text(f"{prop} SELECT COUNT(*) FROM pp"), p).scalar(),
               "genero": grupo(con, prod, f"COALESCE(genero, {_SEM})", "pr"),
               "estado_civil": grupo(con, prod, f"COALESCE(estado_civil, {_SEM})", "pr"),
               "escolaridade": grupo(con, prod, _ESC, "pr"),
               "faixa_etaria": grupo(con, prod, _FAIXA, "pr"),
               "porte": grupo(con, prop, f"COALESCE(perfil_fundiario, {_SEM})", "pp"),
               "status": grupo(con, prop, f"CASE WHEN st ~* '^ativ' THEN 'ATIVA' WHEN st ~* '^inativ' THEN 'INATIVA' ELSE {_SEM} END", "pp")}
    return out


def _mapa_base(request: Request):
    f, de, ate = _filtros_da_requisicao(request)
    if not de or not ate:
        raise HTTPException(400, "Informe de e ate (AAAA-MM-DD)")
    de, ate = _data(de, "de"), _data(ate, "ate")
    w, p = _where(f, de=de, ate=ate)
    return f"{w} AND latitude IS NOT NULL AND longitude IS NOT NULL", p, _where(f, de=de, ate=ate)[0]


@app.get("/api/mapa/propriedades")
def mapa_propriedades(request: Request):
    """Uma bolinha por propriedade (coordenada da propriedade), com a atividade da visita mais recente do período."""
    if not MAPA_PROPRIEDADES:
        raise HTTPException(404, "Não encontrado")
    w, p, w_todas = _mapa_base(request)
    with engine.connect() as con:
        rows = con.execute(text(f"""SELECT DISTINCT ON (id_propriedade) latitude, longitude,
              COALESCE(atividade, '(sem atividade)') AS atividade, COALESCE(municipio, '') AS municipio,
              COALESCE(tecnico, '') AS tecnico, COALESCE(supervisor, '') AS supervisor, COALESCE(projeto, '') AS projeto, id_propriedade
            FROM {TABLE} WHERE {w} ORDER BY id_propriedade, dt_visita DESC"""), p).all()
        total = con.execute(text(f"SELECT COUNT(DISTINCT id_propriedade) FROM {TABLE} WHERE {w_todas}"), p).scalar()
    ativ = {}
    for r in rows:
        ativ[r[2]] = ativ.get(r[2], 0) + 1
    nomes = sorted(ativ, key=lambda a: -ativ[a])
    muns = sorted({r[3] for r in rows})
    ia, im = {a: i for i, a in enumerate(nomes)}, {m: i for i, m in enumerate(muns)}
    return {"atividades": [{"nome": a, "n": ativ[a]} for a in nomes], "municipios": muns, "total": total, "com_coordenada": len(rows),
            "pts": [[round(r[0], 5), round(r[1], 5), ia[r[2]], im[r[3]], r[4], r[5], r[6], r[7]] for r in rows]}


@app.get("/api/mapa/tecnicos")
def mapa_tecnicos(request: Request):
    """Técnicos em ação: um marcador por técnico x município x atividade, na posição típica das propriedades visitadas."""
    w, p, _ = _mapa_base(request)
    _, _, ate = _filtros_da_requisicao(request)
    ate = _data(ate, "ate")
    with engine.connect() as con:
        rows = _linhas(con, f"""SELECT COALESCE(tecnico, '(sem técnico)') AS tecnico, COALESCE(municipio, '(sem município)') AS municipio,
              COALESCE(atividade, '(sem atividade)') AS atividade,
              mode() WITHIN GROUP (ORDER BY supervisor) AS supervisor, mode() WITHIN GROUP (ORDER BY projeto) AS projeto,
              percentile_cont(0.5) WITHIN GROUP (ORDER BY latitude) AS lat, percentile_cont(0.5) WITHIN GROUP (ORDER BY longitude) AS lon,
              COUNT(DISTINCT id_visita) AS visitas, COUNT(DISTINCT id_propriedade) AS propriedades
            FROM {TABLE} WHERE {w} GROUP BY 1, 2, 3 ORDER BY 8 DESC LIMIT 4000""", p)
        prim = {r[0]: r[1] for r in con.execute(text(f"SELECT tecnico, MIN(dt_visita) FROM {TABLE} WHERE tecnico IS NOT NULL GROUP BY 1")).all()}
    ativ = {}
    for r in rows:
        ativ[r["atividade"]] = ativ.get(r["atividade"], 0) + r["visitas"]
    nomes = sorted(ativ, key=lambda a: -ativ[a])
    ia = {a: i for i, a in enumerate(nomes)}
    def meses(t):
        d = prim.get(t)
        return max(0, round((ate - d).days / 30.44)) if d else None
    return {"atividades": [{"nome": a, "n": ativ[a]} for a in nomes],
            "pts": [[round(r["lat"], 5), round(r["lon"], 5), ia[r["atividade"]], r["tecnico"], r["municipio"], r["supervisor"] or "", r["projeto"] or "",
                     r["visitas"], r["propriedades"], meses(r["tecnico"])] for r in rows]}


# Aba "Desempenho": mostra o resultado final do ranking (public.ranking_resultado, enviada sozinha pelo ranking quando o admin abre um mês encerrado
# "Publicar no painel de visitas" do ranking). Fica ABERTA (inclusive na Vercel). Para desligar: DESEMPENHO=0.
_des = os.environ.get("DESEMPENHO")
DESEMPENHO = (_des.strip().lower() in ("1", "true", "sim")) if _des is not None else True


@app.get("/api/tecnicos-inativos")
def tecnicos_inativos(request: Request, dias: int = 30, seguir: int = 1):
    """Técnicos sem visita há mais de `dias` dias (contados até a última visita da base): última visita e último supervisor.
    A inatividade usa TODAS as visitas do técnico; os filtros (supervisor, região etc.) valem para a última visita dele.
    seguir=0 ignora os filtros."""
    dias = max(1, min(int(dias), 730))
    f = _filtros_da_requisicao(request)[0] if seguir else {}
    w, p = _where(f)  # sem datas: o período não se aplica
    p["dias"] = dias
    sql = f"""WITH ref AS (SELECT MAX(dt_visita) AS d FROM {TABLE}),
        u AS (SELECT DISTINCT ON (tecnico) * FROM {TABLE} WHERE tecnico IS NOT NULL ORDER BY tecnico, dt_visita DESC, id_visita DESC),
        tot AS (SELECT tecnico AS tec_t, COUNT(DISTINCT id_visita) AS visitas, MIN(dt_visita) AS primeira_visita
                FROM {TABLE} WHERE tecnico IS NOT NULL GROUP BY 1)
        SELECT u.tecnico, u.supervisor, u.dt_visita AS ultima_visita, (ref.d - u.dt_visita) AS dias_sem_visita,
               u.municipio, u.projeto, u.atividade, tot.visitas, tot.primeira_visita
        FROM u JOIN tot ON tot.tec_t = u.tecnico CROSS JOIN ref
        WHERE {w} AND (ref.d - u.dt_visita) > :dias
        ORDER BY u.dt_visita DESC, u.tecnico"""
    with engine.connect() as con:
        rows = _linhas(con, sql, p)
        ref = con.execute(text(f"SELECT MAX(dt_visita) FROM {TABLE}")).scalar()
    return {"referencia": ref.isoformat() if ref else None, "dias": dias, "tecnicos": rows}


@app.get("/api/desempenho")
def desempenho(request: Request, periodo: str = ""):
    if not DESEMPENHO:
        return {"ativo": False}
    q = request.query_params
    with engine.connect() as con:
        if not con.execute(text("SELECT to_regclass('public.ranking_resultado') IS NOT NULL")).scalar():
            return {"ativo": True, "tabela": False, "periodos": [], "linhas": []}
        periodos = _linhas(con, """SELECT periodo_inicio::text AS ini, periodo_fim::text AS fim, MAX(publicado_em)::text AS publicado,
            COUNT(*) AS tecnicos, (periodo_fim < CURRENT_DATE) AS encerrado
            FROM public.ranking_resultado GROUP BY periodo_inicio, periodo_fim ORDER BY 1 DESC, 2 DESC""", {})
        if not periodos:
            return {"ativo": True, "tabela": True, "periodos": [], "linhas": []}
        ini, fim = (periodo.split("|") + [""])[:2] if periodo else (next((x for x in periodos if x["encerrado"]), periodos[0])["ini"], next((x for x in periodos if x["encerrado"]), periodos[0])["fim"])
        if not any(x["ini"] == ini and x["fim"] == fim for x in periodos):
            ini, fim = periodos[0]["ini"], periodos[0]["fim"]
        w, p = ["periodo_inicio = :ini", "periodo_fim = :fim"], {"ini": ini, "fim": fim}
        if q.get("supervisor"):
            w.append("upper(btrim(supervisor)) = upper(btrim(:sup))"); p["sup"] = q["supervisor"]
        if q.get("tecnico"):
            w.append("upper(btrim(tecnico)) = upper(btrim(:tec))"); p["tec"] = q["tecnico"]
        linhas = _linhas(con, f"""SELECT posicao_geral, tecnico, supervisor, posicao_supervisor, tecnicos_no_supervisor,
            nota_final::float8 AS nota_final, avaliacao_supervisor::float8 AS avaliacao_supervisor, sem_avaliacao,
            visitas, propriedades_ativas, propriedades_inativas, pct_visitas_validas::float8 AS pct_visitas_validas,
            orientacoes, pct_ori_concluidas::float8 AS pct_ori_concluidas, aviso
            FROM public.ranking_resultado WHERE {' AND '.join(w)} ORDER BY posicao_geral, tecnico""", p)
    return {"ativo": True, "tabela": True, "periodos": periodos, "periodo": {"ini": ini, "fim": fim}, "linhas": linhas}


@app.get("/api/conferencia/ativo")
def conferencia_ativo():
    return {"ativo": CONFERENCIA}


@app.get("/api/conferencia/visitas")
def conferencia_visitas(request: Request):
    """Uma linha por visita (id_visita) no período, para comparar com a planilha do SisATeG no navegador."""
    if not CONFERENCIA:
        raise HTTPException(404, "Não encontrado")
    q = request.query_params
    if not q.get("de") or not q.get("ate"):
        raise HTTPException(400, "Informe de e ate (AAAA-MM-DD)")
    de, ate = _data(q.get("de"), "de"), _data(q.get("ate"), "ate")
    with engine.connect() as con:
        rows = con.execute(text(f"""SELECT DISTINCT ON (id_visita) id_visita, dt_visita, projeto, tecnico, atividade,
                   valida, coleta_dados
            FROM {TABLE} WHERE dt_visita >= :de AND dt_visita <= :ate ORDER BY id_visita"""), {"de": de, "ate": ate}).all()
    return {"visitas": [[int(r[0]), r[1].isoformat(), r[2], r[3], r[4], 1 if r[5] else 0, 1 if r[6] else 0] for r in rows]}


@app.get("/api/resumo")
def resumo(request: Request):
    f, de, ate = _filtros_da_requisicao(request)
    if not de or not ate:
        raise HTTPException(400, "Informe de e ate (AAAA-MM-DD)")
    de, ate = _data(de, "de"), _data(ate, "ate")
    if ate < de:
        raise HTTPException(400, "A data final é anterior à inicial")
    dias = (ate - de).days + 1
    ant_ate = de - timedelta(days=1)
    ant_de = ant_ate - timedelta(days=dias - 1)
    w, p = _where(f, de=de, ate=ate)
    wa, pa = _where(f, de=ant_de, ate=ant_ate)
    por_dia = dias <= 92
    with engine.connect() as con:
        cards = _linhas(con, f"SELECT {_CARDS} FROM {TABLE} WHERE {w}", p)[0]
        anterior = _linhas(con, f"SELECT {_CARDS} FROM {TABLE} WHERE {wa}", pa)[0]
        por_atividade = _linhas(con, f"""SELECT COALESCE(atividade, '(sem atividade)') AS atividade,
            COUNT(DISTINCT municipio) AS municipios, COUNT(DISTINCT supervisor) AS supervisores,
            COUNT(DISTINCT tecnico) AS tecnicos, COUNT(DISTINCT id_propriedade) AS propriedades, COUNT(DISTINCT id_visita) AS visitas
            FROM {TABLE} WHERE {w} GROUP BY 1 ORDER BY 1""", p)
        rel_atv = _linhas(con, f"""SELECT COALESCE(atividade, '(sem atividade)') AS atividade, COUNT(DISTINCT id_visita) AS visitas,
            COUNT(DISTINCT id_visita) FILTER (WHERE valida) AS validas, COUNT(DISTINCT id_propriedade) AS propriedades,
            COUNT(DISTINCT tecnico) AS tecnicos, COUNT(DISTINCT supervisor) AS supervisores, COUNT(DISTINCT municipio) AS municipios,
            COUNT(DISTINCT id_visita) FILTER (WHERE coleta_dados) AS coleta
            FROM {TABLE} WHERE {w} GROUP BY 1 ORDER BY 2 DESC""", p)
        rel_ant = {r["atividade"]: r["visitas"] for r in _linhas(con, f"""SELECT COALESCE(atividade, '(sem atividade)') AS atividade,
            COUNT(DISTINCT id_visita) AS visitas FROM {TABLE} WHERE {wa} GROUP BY 1""", pa)}
        rel_mun = {}
        for r in _linhas(con, f"""SELECT atividade, municipio, v FROM (SELECT COALESCE(atividade, '(sem atividade)') AS atividade, COALESCE(municipio, '') AS municipio,
            COUNT(DISTINCT id_visita) AS v, ROW_NUMBER() OVER (PARTITION BY COALESCE(atividade, '(sem atividade)') ORDER BY COUNT(DISTINCT id_visita) DESC) AS rn
            FROM {TABLE} WHERE {w} GROUP BY 1, 2) x WHERE rn = 1""", p):
            rel_mun[r["atividade"]] = [r["municipio"], r["v"]]
        rel_tec = {}
        for r in _linhas(con, f"""SELECT atividade, tecnico, v FROM (SELECT COALESCE(atividade, '(sem atividade)') AS atividade, COALESCE(tecnico, '') AS tecnico,
            COUNT(DISTINCT id_visita) AS v, ROW_NUMBER() OVER (PARTITION BY COALESCE(atividade, '(sem atividade)') ORDER BY COUNT(DISTINCT id_visita) DESC) AS rn
            FROM {TABLE} WHERE {w} GROUP BY 1, 2) x WHERE rn = 1""", p):
            rel_tec[r["atividade"]] = [r["tecnico"], r["v"]]
        for r in rel_atv:
            r["anterior"] = rel_ant.get(r["atividade"], 0)
            r["top_municipio"], r["top_municipio_v"] = rel_mun.get(r["atividade"], ["", 0])
            r["top_tecnico"], r["top_tecnico_v"] = rel_tec.get(r["atividade"], ["", 0])
        por_projeto = _linhas(con, f"""SELECT COALESCE(projeto, '(sem projeto)') AS projeto,
            COUNT(DISTINCT id_propriedade) AS propriedades, COUNT(DISTINCT id_visita) AS visitas
            FROM {TABLE} WHERE {w} GROUP BY 1 ORDER BY 3 DESC""", p)
        eixo = "to_char(dt_visita, 'YYYY-MM-DD')" if por_dia else "mes"
        evolucao = _linhas(con, f"""SELECT {eixo} AS periodo, COUNT(DISTINCT id_visita) AS visitas,
            COUNT(DISTINCT id_propriedade) AS propriedades,
            COUNT(DISTINCT id_visita) FILTER (WHERE NOT coleta_dados) AS visitas_padrao,
            COUNT(DISTINCT id_visita) FILTER (WHERE coleta_dados) AS coleta_dados,
            COUNT(DISTINCT id_visita) FILTER (WHERE retorno) AS retorno,
            COUNT(DISTINCT id_visita) FILTER (WHERE "virtual") AS virtual,
            COUNT(DISTINCT id_visita) FILTER (WHERE visita_zero) AS zero,
            COUNT(DISTINCT id_visita) FILTER (WHERE valida) AS validas,
            COUNT(DISTINCT id_visita) FILTER (WHERE NOT valida) AS invalidas,
            COUNT(DISTINCT id_visita) FILTER (WHERE situacao_validade = 'VALIDA') AS so_valida,
            COUNT(DISTINCT id_visita) FILTER (WHERE situacao_validade = 'VALIDADA') AS validada,
            COUNT(DISTINCT supervisor) AS supervisores, COUNT(DISTINCT tecnico) AS tecnicos,
            COUNT(DISTINCT municipio) AS municipios
            FROM {TABLE} WHERE {w} GROUP BY 1 ORDER BY 1""", p)
        evolucao_ant = _linhas(con, f"""SELECT {eixo} AS periodo, COUNT(DISTINCT id_visita) AS visitas,
            COUNT(DISTINCT id_visita) FILTER (WHERE valida) AS validas
            FROM {TABLE} WHERE {wa} GROUP BY 1 ORDER BY 1""", pa)
        wbm, pbm = _where(f)
        mun_comp = _linhas(con, f"""SELECT COALESCE(municipio, '(sem município)') AS municipio,
            COUNT(DISTINCT id_visita) FILTER (WHERE dt_visita BETWEEN :de AND :ate) AS visitas,
            COUNT(DISTINCT id_visita) FILTER (WHERE dt_visita BETWEEN :de AND :ate AND valida) AS validas,
            COUNT(DISTINCT id_propriedade) FILTER (WHERE dt_visita BETWEEN :de AND :ate) AS propriedades,
            COUNT(DISTINCT id_visita) FILTER (WHERE dt_visita BETWEEN :ade AND :aate) AS visitas_ant,
            COUNT(DISTINCT id_visita) FILTER (WHERE dt_visita BETWEEN :ade AND :aate AND valida) AS validas_ant,
            COUNT(DISTINCT id_propriedade) FILTER (WHERE dt_visita BETWEEN :ade AND :aate) AS propriedades_ant
            FROM {TABLE} WHERE {wbm} AND dt_visita BETWEEN :ade AND :ate GROUP BY 1""",
            {**pbm, "de": de, "ate": ate, "ade": ant_de, "aate": ant_ate})
        por_supervisor = _linhas(con, f"""SELECT COALESCE(supervisor, '(sem supervisor)') AS supervisor,
            COUNT(DISTINCT tecnico) AS tecnicos, COUNT(DISTINCT id_propriedade) AS propriedades, COUNT(DISTINCT id_visita) AS visitas
            FROM {TABLE} WHERE {w} GROUP BY 1 ORDER BY 4 DESC""", p)
        por_tecnico = _linhas(con, f"""SELECT COALESCE(tecnico, '(sem técnico)') AS tecnico,
            MAX(supervisor) AS supervisor, mode() WITHIN GROUP (ORDER BY projeto) AS projeto,
            COUNT(DISTINCT id_propriedade) AS propriedades, COUNT(DISTINCT id_visita) AS visitas,
            COUNT(DISTINCT id_visita) FILTER (WHERE coleta_dados) AS coleta_dados, COUNT(DISTINCT dt_visita) AS dias_com_visita,
            MAX(dt_visita) AS ultima_visita
            FROM {TABLE} WHERE {w} GROUP BY 1 ORDER BY 4 DESC LIMIT 500""", p)
        por_municipio = _linhas(con, f"""SELECT COALESCE(municipio, '(sem município)') AS municipio,
            COUNT(DISTINCT supervisor) AS supervisores, COUNT(DISTINCT tecnico) AS tecnicos, COUNT(DISTINCT atividade) AS atividades,
            COUNT(DISTINCT id_propriedade) AS propriedades,
            COUNT(DISTINCT id_visita) AS visitas{_MUN_EXTRA} FROM {TABLE} WHERE {w} GROUP BY 1 ORDER BY 6 DESC LIMIT 400""", p)
        # Posição geral e nota do último ranking publicado (aba Desempenho), ao lado de cada técnico
        ranking_periodo = None
        if DESEMPENHO:
            try:
                if con.execute(text("SELECT to_regclass('public.ranking_resultado') IS NOT NULL")).scalar():
                    _per = con.execute(text("SELECT periodo_inicio, periodo_fim FROM public.ranking_resultado "
                                            "ORDER BY (periodo_fim < CURRENT_DATE) DESC, periodo_inicio DESC, periodo_fim DESC LIMIT 1")).first()
                    if _per:
                        _rk = {r[0]: (r[1], r[2]) for r in con.execute(text(
                            "SELECT upper(btrim(tecnico)), posicao_geral, nota_final::float8 FROM public.ranking_resultado "
                            "WHERE periodo_inicio = :i AND periodo_fim = :f"), {"i": _per[0], "f": _per[1]})}
                        for _t in por_tecnico:
                            _x = _rk.get((_t["tecnico"] or "").strip().upper())
                            if _x:
                                _t["pos_geral"], _t["nota_ranking"] = _x
                        ranking_periodo = _per[0].strftime("%m/%Y") if _per[0].strftime("%m%Y") == _per[1].strftime("%m%Y") \
                            else f"{_per[0].strftime('%m/%Y')} a {_per[1].strftime('%m/%Y')}"
            except Exception:
                ranking_periodo = None
        por_regiao, por_sindicato = [], []
        if "regiao" in TEXTO:   # só quando a view já tem região/sindicato
            for _col, _alias in (("regiao_faec", "regiao"), ("sindicato", "sindicato")):
                _l = _linhas(con, f"""SELECT COALESCE({_col}, '(sem {_alias})') AS {_alias}, COUNT(DISTINCT municipio) AS municipios,
                    COUNT(DISTINCT supervisor) AS supervisores, COUNT(DISTINCT tecnico) AS tecnicos,
                    COUNT(DISTINCT id_propriedade) AS propriedades, COUNT(DISTINCT id_visita) AS visitas
                    FROM {TABLE} WHERE {w} GROUP BY 1 ORDER BY 6 DESC LIMIT 400""", p)
                if _alias == "regiao":
                    por_regiao = _l
                else:
                    por_sindicato = _l
        props_mes = _linhas(con, f"""SELECT mes, COUNT(DISTINCT id_propriedade) AS propriedades
            FROM {TABLE} WHERE {w} GROUP BY 1 ORDER BY 1""", p)
        dow = _linhas(con, f"""SELECT EXTRACT(isodow FROM dt_visita)::int AS dia, COUNT(DISTINCT id_visita) AS visitas
            FROM {TABLE} WHERE {w} GROUP BY 1 ORDER BY 1""", p)
        frequencia = _linhas(con, f"""SELECT CASE WHEN n = 1 THEN '1 visita' WHEN n = 2 THEN '2 visitas'
              WHEN n = 3 THEN '3 visitas' ELSE '4 ou mais' END AS faixa, COUNT(*) AS propriedades
            FROM (SELECT id_propriedade, COUNT(DISTINCT id_visita) AS n FROM {TABLE} WHERE {w} GROUP BY 1) x
            GROUP BY 1 ORDER BY MIN(n)""", p)
        carteira = _carteira(con, TABLE, w, p, None)
        cart_ativ = _carteira(con, TABLE, w, p, "atividade")
        cart_sup = _carteira(con, TABLE, w, p, "supervisor")
        cart_tec = _carteira(con, TABLE, w, p, "tecnico", 500)
        # Propriedades desativadas por mês e motivo (vínculo da propriedade encerrado no SisATeG).
        # Se a view ainda não tem as colunas vinculo_* (vw_visitas.sql não foi rodada de novo), o painel segue funcionando.
        desat = {"disponivel": False}
        try:
            with con.begin_nested():
                wd, pdp = _where(f)
                linhas_d = _linhas(con, f"""WITH x AS (SELECT DISTINCT ON (id_propriedade) id_propriedade, vinculo_dt_fim, vinculo_motivo
                      FROM {TABLE} WHERE {wd} AND vinculo_dt_fim IS NOT NULL ORDER BY id_propriedade, dt_visita DESC, id_visita DESC)
                    SELECT to_char(vinculo_dt_fim, 'YYYY-MM') AS mes, COALESCE(vinculo_motivo, 'Sem motivo informado') AS motivo,
                           COUNT(*) AS propriedades FROM x WHERE vinculo_dt_fim BETWEEN :de AND :ate GROUP BY 1, 2 ORDER BY 1, 3 DESC""",
                    {**pdp, "de": de, "ate": ate})
            tot_d = sum(r["propriedades"] for r in linhas_d)
            por_motivo = {}
            for r in linhas_d:
                por_motivo[r["motivo"]] = por_motivo.get(r["motivo"], 0) + r["propriedades"]
            desat = {"disponivel": True, "total": tot_d, "por_mes": linhas_d,
                     "por_motivo": [{"motivo": k, "propriedades": v, "percentual": round(v / tot_d * 100, 1) if tot_d else 0}
                                    for k, v in sorted(por_motivo.items(), key=lambda kv: -kv[1])]}
        except Exception:
            desat = {"disponivel": False}
        wb, pb = _where(f)
        dest = {}
        for chave, col in (("atividade", "atividade"), ("supervisor", "supervisor"),
                           ("tecnico", "tecnico"), ("municipio", "municipio")):
            rows = _linhas(con, f"""SELECT COALESCE({col}, '(sem informação)') AS nome,
                COUNT(DISTINCT id_visita) FILTER (WHERE dt_visita BETWEEN :de AND :ate) AS atual,
                COUNT(DISTINCT id_visita) FILTER (WHERE dt_visita BETWEEN :ade AND :aate) AS anterior
                FROM {TABLE} WHERE {wb} AND dt_visita BETWEEN :ade AND :ate GROUP BY 1""",
                {**pb, "de": de, "ate": ate, "ade": ant_de, "aate": ant_ate})
            for r in rows:
                r["delta"] = r["atual"] - r["anterior"]
            sobem = sorted([r for r in rows if r["delta"] > 0], key=lambda r: -r["delta"])[:5]
            caem = sorted([r for r in rows if r["delta"] < 0], key=lambda r: r["delta"])[:5]
            dest[chave] = {"sobem": sobem, "caem": caem}
    with engine.connect() as _con:   # primeira visita de cada técnico em TODA a base (para o "Tempo no projeto")
        _prim = {r[0]: r[1] for r in _con.execute(text(f"SELECT tecnico, MIN(dt_visita) FROM {TABLE} WHERE tecnico IS NOT NULL GROUP BY 1")).all()}
    for r in por_tecnico:
        r["ultima_visita"] = r["ultima_visita"].isoformat() if r["ultima_visita"] else None
        _d = _prim.get(r["tecnico"])
        r["primeira_visita"] = _d.isoformat() if _d else None
        r["meses_projeto"] = round(max(0, (ate - _d).days) / 30.44, 1) if _d else None   # da 1ª visita até o fim do período filtrado
    return {"periodo": {"de": de.isoformat(), "ate": ate.isoformat(), "dias": dias,
                        "anterior_de": ant_de.isoformat(), "anterior_ate": ant_ate.isoformat()},
            "cards": cards, "anterior": anterior, "por_atividade": por_atividade, "rel_atv": rel_atv, "por_projeto": por_projeto,
            "evolucao": {"por_dia": por_dia, "pontos": evolucao, "anterior": evolucao_ant},
            "municipios_comparacao": mun_comp,
            "desativacoes": desat, "props_mes": props_mes,
            "por_supervisor": por_supervisor, "por_tecnico": por_tecnico,
            "por_municipio": por_municipio, "por_regiao": por_regiao, "por_sindicato": por_sindicato, "ranking_periodo": ranking_periodo, "dia_semana": dow, "frequencia": frequencia, "destaques": dest,
            "carteira": {"total": carteira, "por_atividade": cart_ativ, "por_supervisor": cart_sup, "por_tecnico": cart_tec}}
