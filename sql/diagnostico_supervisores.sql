-- Por que o painel mostra menos supervisores do que o esperado? Rodar no pgAdmin (banco painel_ateg) e me mandar o resultado.
-- Mostra, para cada fonte, os supervisores que aparecem e quantos técnicos/visitas eles têm.
SELECT 'painel (vw_visitas, desde 01/09/2026)' AS fonte, supervisor, COUNT(DISTINCT tecnico) AS tecnicos,
       COUNT(DISTINCT id_visita) AS visitas, MAX(dt_visita) AS ultima_visita
FROM public.vw_visitas WHERE dt_visita >= DATE '2026-09-01' GROUP BY supervisor
UNION ALL
SELECT 'ranking_tecnicos (ultimo_supervisor)', ultimo_supervisor, COUNT(DISTINCT tecnico_responsavel), NULL, NULL
FROM public.ranking_tecnicos GROUP BY ultimo_supervisor
UNION ALL
SELECT 'SisATeG bruto (supervisor_atual, desde 01/01/2026)', btrim(supervisor_atual), COUNT(DISTINCT tecnico_responsavel),
       COUNT(DISTINCT id_visita), MAX(dt_visita)::date
FROM public.acompanhamento_mensal_visitas WHERE dt_visita >= TIMESTAMP '2026-01-01' GROUP BY btrim(supervisor_atual)
ORDER BY 1, 2;
