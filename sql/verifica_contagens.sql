-- CONFERÊNCIA DAS CONTAGENS (rodar no pgAdmin, banco painel_ateg, depois de recriar a view).
-- Compara visitas e propriedades da TABELA ORIGINAL com a view e com o mv_visitas (o que o painel lê).
-- Para mudar o período, altere as duas datas abaixo. Todas as linhas devem dar confere = SIM.
WITH p AS (SELECT DATE '2026-09-01' AS de, DATE '2026-09-30' AS ate),
orig AS (
  SELECT COUNT(DISTINCT a.id_visita) AS visitas, COUNT(DISTINCT a.id_propriedade) AS propriedades
  FROM public.acompanhamento_mensal_visitas a, p
  WHERE a.id_visita IS NOT NULL AND a.dt_visita::date BETWEEN p.de AND p.ate
    AND a.dt_visita < (CURRENT_DATE + 1)::timestamp AND a.dt_visita >= TIMESTAMP '2024-06-01'),
vw AS (
  SELECT COUNT(DISTINCT v.id_visita) AS visitas, COUNT(DISTINCT v.id_propriedade) AS propriedades
  FROM public.vw_visitas v, p WHERE v.dt_visita BETWEEN p.de AND p.ate),
mv AS (
  SELECT COUNT(DISTINCT v.id_visita) AS visitas, COUNT(DISTINCT v.id_propriedade) AS propriedades
  FROM public.mv_visitas v, p WHERE v.dt_visita BETWEEN p.de AND p.ate),
por_sup AS (
  SELECT COALESCE(SUM(n), 0) AS visitas FROM (
    SELECT COUNT(DISTINCT v.id_visita) AS n FROM public.vw_visitas v, p
    WHERE v.dt_visita BETWEEN p.de AND p.ate GROUP BY v.supervisor) x),
dup AS (
  SELECT COUNT(*) AS visitas_com_mais_de_um_supervisor FROM (
    SELECT v.id_visita FROM public.vw_visitas v, p WHERE v.dt_visita BETWEEN p.de AND p.ate
    GROUP BY v.id_visita HAVING COUNT(DISTINCT v.supervisor) > 1) x)
SELECT 'Visitas: tabela original x view' AS conferencia, orig.visitas AS a, vw.visitas AS b, orig.visitas = vw.visitas AS "confere" FROM orig, vw
UNION ALL SELECT 'Propriedades: tabela original x view', orig.propriedades, vw.propriedades, orig.propriedades = vw.propriedades FROM orig, vw
UNION ALL SELECT 'Visitas: view x mv_visitas (painel)', vw.visitas, mv.visitas, vw.visitas = mv.visitas FROM vw, mv
UNION ALL SELECT 'Propriedades: view x mv_visitas (painel)', vw.propriedades, mv.propriedades, vw.propriedades = mv.propriedades FROM vw, mv
UNION ALL SELECT 'Soma das visitas por supervisor x total', por_sup.visitas, vw.visitas, por_sup.visitas = vw.visitas FROM por_sup, vw
UNION ALL SELECT 'Visitas contadas em mais de um supervisor (deve ser 0)', dup.visitas_com_mais_de_um_supervisor, 0, dup.visitas_com_mais_de_um_supervisor = 0 FROM dup;
