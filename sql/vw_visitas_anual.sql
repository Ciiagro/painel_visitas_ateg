-- RODAR NO SERVIDOR (banco painel_ateg), com o usuário administrador. Só LEITURA da tabela de origem.
-- View leve (só as colunas que a aba "Por ano" do painel usa) com TODAS as visitas desde o início da base (2016),
-- sem o corte de 01/06/2024 da vw_visitas. Não muda nada nas outras abas.
CREATE OR REPLACE VIEW public.vw_visitas_anual AS
SELECT a.id_visita,
       a.id_propriedade,
       a.dt_visita::date                                       AS dt_visita,
       NULLIF(btrim(a.projeto, E' \t\r\n'), '')                AS projeto,
       NULLIF(btrim(a.atividade, E' \t\r\n'), '')              AS atividade,
       NULLIF(btrim(a.municipio_propriedade, E' \t\r\n'), '')  AS municipio,
       NULLIF(btrim(a.tecnico_responsavel, E' \t\r\n'), '')    AS tecnico,
       COALESCE(a.flg_coleta_dados, '')  ~* '^(s|v)'           AS coleta_dados,
       COALESCE(a.visita_presencial, '') ~* '^(s|v)'           AS presencial,
       COALESCE(a.visita_valida, '')     ~* '^(s|v)'           AS valida
FROM public.acompanhamento_mensal_visitas a
WHERE a.id_visita IS NOT NULL
  AND a.dt_visita < (CURRENT_DATE + 1)::timestamp;            -- só até hoje

GRANT SELECT ON public.vw_visitas_anual TO painel_leitura;

-- Conferência: deve repetir a consulta por ano que você rodou antes.
SELECT EXTRACT(YEAR FROM dt_visita)::int AS ano, COUNT(DISTINCT id_visita) AS visitas,
       COUNT(DISTINCT id_propriedade) AS propriedades, COUNT(DISTINCT municipio) AS municipios
FROM public.vw_visitas_anual GROUP BY 1 ORDER BY 1;
