-- =====================================================================
-- ACOMPANHAMENTO DAS VISITAS - TRIMESTRE (rodar no pgAdmin, banco painel_ateg)
-- Mesmos números dos cartões do painel, mesmas regras da view public.vw_visitas.
-- Para mudar o período, altere SÓ as duas datas na linha "periodo" abaixo.
-- O período anterior (para a variação) é calculado sozinho: mesmo número de dias, logo antes.
-- =====================================================================
WITH periodo AS (
  SELECT DATE '2026-07-01' AS de, DATE '2026-09-30' AS ate
),
janelas AS (   -- 'atual' e 'anterior' (mesma quantidade de dias, imediatamente antes)
  SELECT 'atual' AS janela, de, ate FROM periodo
  UNION ALL
  SELECT 'anterior', de - ((ate - de) + 1)::int, de - 1 FROM periodo
),
base AS (      -- visitas de cada janela (a view já traz só visitas até hoje e a partir de 01/06/2024)
  SELECT j.janela, v.*
  FROM janelas j
  JOIN public.vw_visitas v ON v.dt_visita BETWEEN j.de AND j.ate
  -- Se precisar tirar o projeto de treinamento, tire o "--" da linha abaixo:
  -- WHERE COALESCE(v.projeto, '') NOT ILIKE 'TREINAMENTO%'
),
visitas AS (   -- cartões de VISITAS
  SELECT janela,
    COUNT(DISTINCT id_visita)                                                       AS total_visitas,
    COUNT(DISTINCT id_visita) FILTER (WHERE valida)                                 AS visitas_validas,
    COUNT(DISTINCT id_visita) FILTER (WHERE situacao_validade = 'VALIDA')           AS so_valida,
    COUNT(DISTINCT id_visita) FILTER (WHERE situacao_validade = 'VALIDADA')         AS validada,
    COUNT(DISTINCT id_visita) FILTER (WHERE NOT valida)                             AS invalida,
    COUNT(DISTINCT id_visita) FILTER (WHERE NOT coleta_dados)                       AS visitas_padrao,
    COUNT(DISTINCT id_visita) FILTER (WHERE coleta_dados)                           AS coleta_de_dados,
    COUNT(DISTINCT id_visita) FILTER (WHERE retorno)                                AS visita_retorno,
    COUNT(DISTINCT id_visita) FILTER (WHERE "virtual")                              AS visita_virtual,
    COUNT(DISTINCT id_visita) FILTER (WHERE visita_zero)                            AS visita_zero,
    COUNT(DISTINCT id_visita) FILTER (WHERE presencial)                             AS visitas_presenciais,
    COUNT(DISTINCT supervisor)                                                      AS supervisores,
    COUNT(DISTINCT tecnico)                                                         AS tecnicos,
    COUNT(DISTINCT atividade)                                                       AS atividades_atendidas,
    COUNT(DISTINCT municipio)                                                       AS municipios_atendidos
  FROM base GROUP BY janela
),
props AS (     -- cartões de PROPRIEDADES: 1 linha por propriedade, com a situação da visita mais recente do período
  SELECT janela,
    COUNT(*)                                                                        AS propriedades_assistidas,
    COUNT(*) FILTER (WHERE status = 'ATIVO')                                        AS propriedades_ativas,
    COUNT(*) FILTER (WHERE status = 'INATIVO')                                      AS propriedades_inativas,
    COUNT(*) FILTER (WHERE status_sisateg = 'ATIVA' AND status_oficial = 'INATIVO') AS divergencias
  FROM (SELECT DISTINCT ON (janela, id_propriedade) janela, id_propriedade,
               COALESCE(status_oficial, status_sisateg) AS status, status_sisateg, status_oficial
        FROM base ORDER BY janela, id_propriedade, dt_visita DESC, id_visita DESC) s
  GROUP BY janela
),
ori AS (       -- cartões de ORIENTAÇÕES: são da visita, então 1 linha por visita
  SELECT janela,
    COALESCE(SUM(ori_total), 0)                          AS orientacoes_total,
    COALESCE(SUM(ori_concluida), 0)                      AS orientacoes_concluidas,
    COALESCE(SUM(ori_total) - SUM(ori_concluida), 0)     AS orientacoes_nao_concluidas,
    COALESCE(SUM(ori_em_execucao), 0)                    AS em_execucao,
    COALESCE(SUM(ori_aberta), 0)                         AS abertas,
    COALESCE(SUM(ori_cancelada), 0)                      AS canceladas,
    COALESCE(SUM(ori_nao_realizada), 0)                  AS nao_realizadas
  FROM (SELECT DISTINCT ON (janela, id_visita) janela, id_visita, ori_total, ori_concluida, ori_em_execucao,
               ori_aberta, ori_cancelada, ori_nao_realizada
        FROM base ORDER BY janela, id_visita, dt_visita DESC) s
  GROUP BY janela
),
tudo AS (
  SELECT v.janela, v.total_visitas, v.visitas_validas, v.so_valida, v.validada, v.invalida, v.visitas_padrao, v.coleta_de_dados,
         v.visita_retorno, v.visita_virtual, v.visita_zero, v.visitas_presenciais,
         p.propriedades_assistidas, p.propriedades_ativas, p.propriedades_inativas, p.divergencias,
         v.supervisores, v.tecnicos, v.atividades_atendidas, v.municipios_atendidos,
         o.orientacoes_total, o.orientacoes_concluidas, o.orientacoes_nao_concluidas, o.em_execucao, o.abertas, o.canceladas, o.nao_realizadas
  FROM visitas v JOIN props p USING (janela) JOIN ori o USING (janela)
),
linhas AS (    -- vira uma linha por indicador
  SELECT janela, 1 AS ordem, 'Total de visitas' AS indicador, total_visitas AS valor FROM tudo
  UNION ALL SELECT janela,  2, 'Visitas válidas',                 visitas_validas FROM tudo
  UNION ALL SELECT janela,  3, 'Visitas validadas',               validada FROM tudo
  UNION ALL SELECT janela,  4, 'Visitas só válidas (não validadas)', so_valida FROM tudo
  UNION ALL SELECT janela,  5, 'Visitas inválidas',               invalida FROM tudo
  UNION ALL SELECT janela,  6, 'Visitas padrão',                  visitas_padrao FROM tudo
  UNION ALL SELECT janela,  7, 'Coleta de dados',                 coleta_de_dados FROM tudo
  UNION ALL SELECT janela,  8, 'Visita retorno',                  visita_retorno FROM tudo
  UNION ALL SELECT janela,  9, 'Visita virtual',                  visita_virtual FROM tudo
  UNION ALL SELECT janela, 10, 'Visita zero',                     visita_zero FROM tudo
  UNION ALL SELECT janela, 11, 'Visitas presenciais',             visitas_presenciais FROM tudo
  UNION ALL SELECT janela, 12, 'Propriedades assistidas',         propriedades_assistidas FROM tudo
  UNION ALL SELECT janela, 13, 'Propriedades ativas',             propriedades_ativas FROM tudo
  UNION ALL SELECT janela, 14, 'Propriedades inativas',           propriedades_inativas FROM tudo
  UNION ALL SELECT janela, 15, 'Divergências (ativa no SisATeG, inativa na oficial)', divergencias FROM tudo
  UNION ALL SELECT janela, 16, 'Supervisores',                    supervisores FROM tudo
  UNION ALL SELECT janela, 17, 'Técnicos',                        tecnicos FROM tudo
  UNION ALL SELECT janela, 18, 'Atividades atendidas',            atividades_atendidas FROM tudo
  UNION ALL SELECT janela, 19, 'Municípios atendidos',            municipios_atendidos FROM tudo
  UNION ALL SELECT janela, 20, 'Orientações - total',             orientacoes_total FROM tudo
  UNION ALL SELECT janela, 21, 'Orientações - concluídas',        orientacoes_concluidas FROM tudo
  UNION ALL SELECT janela, 22, 'Orientações - não concluídas',    orientacoes_nao_concluidas FROM tudo
  UNION ALL SELECT janela, 23, 'Orientações - em execução',       em_execucao FROM tudo
  UNION ALL SELECT janela, 24, 'Orientações - abertas',           abertas FROM tudo
  UNION ALL SELECT janela, 25, 'Orientações - canceladas',        canceladas FROM tudo
  UNION ALL SELECT janela, 26, 'Orientações - não realizadas',    nao_realizadas FROM tudo
)
SELECT a.indicador,
       a.valor                                                      AS "01/07 a 30/09/2026",
       b.valor                                                      AS periodo_anterior,
       CASE WHEN b.valor > 0 THEN round(100.0 * (a.valor - b.valor) / b.valor, 1) END AS "variacao_%"
FROM linhas a
LEFT JOIN linhas b ON b.indicador = a.indicador AND b.janela = 'anterior'
WHERE a.janela = 'atual'
ORDER BY a.ordem;
