-- =====================================================================
-- PAINEL DE VISITAS - RODAR UMA VEZ NO SERVIDOR (banco painel_ateg), no pgAdmin.
-- Cria a view public.vw_visitas em cima da tabela que JÁ EXISTE no servidor: public.acompanhamento_mensal_visitas
-- (nada é copiado; quando a tabela é atualizada, o painel já mostra o dado novo).
--
-- Regras (as mesmas do Power BI "Acompanhamento das Visitas"):
--   Total de visitas          = id_visita distinto no período
--   Propriedades assistidas   = id_propriedade distinto
--   Total visitas padrão      = visitas que NÃO são coleta de dados
--   Coleta de dados / Visita retorno / Visita virtual (atendimento remoto) / Visita zero = colunas do SisATeG
--   Status da propriedade (ATIVO/INATIVO) = status_propriedade_oficial; orientações = colunas ori_* (são da VISITA, juntadas por id_visita na origem:
--     o painel conta cada id_visita uma vez, pois a tabela repete linhas)
--   Propriedade desativada = vinculo_dt_fim preenchido (data em que o vínculo terminou) e vinculo_motivo (motivo da desativação)
--   Supervisor                = supervisor_atual da ÚLTIMA visita do técnico (o mais recente do SisATeG); se faltar, cai no ranking_tecnicos.ultimo_supervisor
-- Só entram visitas até hoje (as futuras/agendadas ficam de fora) e a partir de 01/06/2024.
-- =====================================================================
CREATE OR REPLACE VIEW public.vw_visitas AS
WITH v AS (
  SELECT a.id_visita,
         a.id_propriedade,
         a.dt_visita::date                                         AS dt_visita,
         to_char(a.dt_visita, 'YYYY-MM')                           AS mes,
         NULLIF(btrim(a.projeto, E' \t\r\n'), '')                  AS projeto,
         NULLIF(btrim(a.atividade, E' \t\r\n'), '')                AS atividade,
         NULLIF(btrim(a.municipio_propriedade, E' \t\r\n'), '')    AS municipio,
         NULLIF(btrim(a.tecnico_responsavel, E' \t\r\n'), '')      AS tecnico,
         NULLIF(btrim(a.supervisor_atual, E' \t\r\n'), '')         AS supervisor_sisateg,
         COALESCE(a.flg_coleta_dados, '')  ~* '^(s|v)'             AS coleta_dados,
         COALESCE(a.visita_presencial, '') ~* '^(s|v)'             AS presencial,
         COALESCE(a.visita_virtual, '')    ~* '^(s|v)'             AS "virtual",
         COALESCE(a.visita_retorno, '')    ~* '^(s|v)'             AS retorno,
         COALESCE(a.visita_zero, '')       ~* '^(s|v)'             AS visita_zero,
         COALESCE(a.visita_valida, '')     ~* '^(s|v)'             AS valida,
         a.id_produtor::bigint                                     AS id_produtor,
         CASE WHEN replace(btrim(a.latitude_propriedade),  ',', '.') ~ '^-?[0-9]+(\.[0-9]+)?$'
              THEN -abs(replace(btrim(a.latitude_propriedade),  ',', '.')::double precision) END  AS lat0,
         CASE WHEN replace(btrim(a.longitude_propriedade), ',', '.') ~ '^-?[0-9]+(\.[0-9]+)?$'
              THEN -abs(replace(btrim(a.longitude_propriedade), ',', '.')::double precision) END  AS lon0,
         upper(NULLIF(btrim(a.genero, E' \t\r\n'), ''))              AS genero,
         upper(NULLIF(btrim(a.estado_civil, E' \t\r\n'), ''))        AS estado_civil,
         a.idade::int                                              AS idade,
         NULLIF(btrim(a.formacao_academica, E' \t\r\n'), '')         AS formacao_academica,
         NULLIF(btrim(a.perfil_fundiario, E' \t\r\n'), '')           AS perfil_fundiario,
         CASE WHEN COALESCE(a.visita_valida, '') ~* '^validad' THEN 'VALIDADA'
              WHEN COALESCE(a.visita_valida, '') ~* '^(s|v)'   THEN 'VALIDA'
              ELSE 'INVALIDA' END                                  AS situacao_validade,
         upper(NULLIF(btrim(a.status_propriedade, E' \t\r\n'), ''))         AS status_sisateg,
         upper(NULLIF(btrim(a.status_propriedade_oficial, E' \t\r\n'), '')) AS status_oficial,
         COALESCE(a.ori_aberta, 0) AS ori_aberta, COALESCE(a.ori_em_execucao, 0) AS ori_em_execucao,
         COALESCE(a.ori_concluida, 0) AS ori_concluida, COALESCE(a.ori_cancelada, 0) AS ori_cancelada,
         COALESCE(a.ori_nao_realizada, 0) AS ori_nao_realizada, COALESCE(a.ori_total_geral, 0) AS ori_total,
         upper(NULLIF(btrim(a.vinculo_status, E' \t\r\n'), ''))  AS vinculo_status,
         a.vinculo_dt_fim::date                                    AS vinculo_dt_fim,
         NULLIF(btrim(a.vinculo_motivo, E' \t\r\n'), '')          AS vinculo_motivo
  FROM public.acompanhamento_mensal_visitas a
  WHERE a.id_visita IS NOT NULL
    AND a.dt_visita >= TIMESTAMP '2024-06-01'                      -- início da base: mude aqui se precisar
    AND a.dt_visita <  (CURRENT_DATE + 1)::timestamp               -- só até hoje
)
SELECT v.id_visita, v.id_propriedade, v.dt_visita, v.mes, v.projeto, v.atividade, v.municipio, v.tecnico,
       COALESCE(u.supervisor_atual, v.supervisor_sisateg, k.ultimo_supervisor) AS supervisor, v.supervisor_sisateg,
       v.coleta_dados, v.presencial, v."virtual", v.retorno, v.visita_zero, v.valida,
       v.status_sisateg, v.status_oficial, v.ori_aberta, v.ori_em_execucao, v.ori_concluida,
       v.ori_cancelada, v.ori_nao_realizada, v.ori_total,
       v.vinculo_status, v.vinculo_dt_fim, v.vinculo_motivo,  -- fim do vínculo da propriedade (desativação) e o motivo
       v.situacao_validade,                                   -- VALIDA / VALIDADA / INVALIDA (colunas novas ficam sempre no FIM)
       v.id_produtor, v.genero, v.estado_civil, v.idade, v.formacao_academica, v.perfil_fundiario,   -- perfil do produtor
       -- coordenadas da propriedade (só as que caem dentro do Ceará; o resto fica nulo)
       CASE WHEN v.lat0 BETWEEN -7.95 AND -2.70 AND v.lon0 BETWEEN -41.60 AND -37.10 THEN v.lat0 END AS latitude,
       CASE WHEN v.lat0 BETWEEN -7.95 AND -2.70 AND v.lon0 BETWEEN -41.60 AND -37.10 THEN v.lon0 END AS longitude
FROM v
LEFT JOIN (SELECT DISTINCT ON (tecnico) tecnico, supervisor_sisateg AS supervisor_atual
           FROM v WHERE tecnico IS NOT NULL AND supervisor_sisateg IS NOT NULL
           ORDER BY tecnico, dt_visita DESC, id_visita DESC) u ON u.tecnico = v.tecnico   -- supervisor da ÚLTIMA visita do técnico
LEFT JOIN public.ranking_tecnicos k ON btrim(k.tecnico_responsavel, E' \t\r\n') = v.tecnico;

-- Se existir o usuário somente-leitura do painel, libera a view para ele:
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'painel_leitura') THEN
    GRANT SELECT ON public.vw_visitas TO painel_leitura;
  END IF;
END $$;

-- Conferência (a última consulta mostra o resultado): período 01-08/10/2026 deve dar ~1.938 visitas, 1.872 propriedades, 195 técnicos.
SELECT COUNT(DISTINCT id_visita) AS visitas, COUNT(DISTINCT id_propriedade) AS propriedades,
       COUNT(DISTINCT tecnico) AS tecnicos, COUNT(DISTINCT supervisor) AS supervisores,
       COUNT(*) FILTER (WHERE coleta_dados) AS coleta
FROM public.vw_visitas WHERE dt_visita BETWEEN DATE '2026-10-01' AND DATE '2026-10-08';
