SELECT 'tecnicos distintos (visitas)' AS item, COUNT(DISTINCT tecnico)::text AS valor FROM public.vw_visitas_anual
UNION ALL SELECT 'projetos distintos', COUNT(DISTINCT projeto)::text FROM public.vw_visitas_anual
UNION ALL SELECT 'atividades distintas', COUNT(DISTINCT atividade)::text FROM public.vw_visitas_anual
UNION ALL SELECT 'tabelas com tecnic/usuario/supervis: ' || table_name, '' FROM information_schema.tables
  WHERE table_schema='public' AND (table_name ILIKE '%tecnic%' OR table_name ILIKE '%usuario%' OR table_name ILIKE '%supervis%')
UNION ALL SELECT 'atividade: ' || COALESCE(atividade,'(vazio)'), COUNT(DISTINCT id_propriedade)::text FROM public.vw_visitas_anual GROUP BY atividade;
