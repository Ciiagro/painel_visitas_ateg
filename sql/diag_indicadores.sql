SELECT 'mv_visitas' AS fonte, COUNT(*) AS linhas, COUNT(DISTINCT id_visita) AS visitas, COUNT(DISTINCT id_propriedade) AS propriedades,
       MIN(dt_visita)::text AS primeira, MAX(dt_visita)::text AS ultima FROM public.mv_visitas
UNION ALL
SELECT 'vw_visitas', COUNT(*), COUNT(DISTINCT id_visita), COUNT(DISTINCT id_propriedade), MIN(dt_visita)::text, MAX(dt_visita)::text FROM public.vw_visitas
UNION ALL
SELECT 'ano ' || EXTRACT(year FROM dt_visita)::int, COUNT(*), COUNT(DISTINCT id_visita), COUNT(DISTINCT id_propriedade), MIN(dt_visita)::text, MAX(dt_visita)::text
FROM public.mv_visitas GROUP BY EXTRACT(year FROM dt_visita) ORDER BY 1;
