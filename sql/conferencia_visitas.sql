-- CONFERÊNCIA com a planilha "Lista de Visitas" do SisATeG (rodar no servidor, depois de criar a view).
-- Troque as datas pelas do filtro da planilha e compare: visitas, propriedades, coleta, técnicos.
SELECT COUNT(DISTINCT id_visita) AS visitas,
       COUNT(DISTINCT id_propriedade) AS propriedades,
       COUNT(DISTINCT id_visita) FILTER (WHERE coleta_dados) AS coleta_dados,
       COUNT(DISTINCT id_visita) FILTER (WHERE NOT coleta_dados) AS visitas_padrao,
       COUNT(DISTINCT tecnico) AS tecnicos,
       COUNT(DISTINCT municipio) AS municipios
FROM public.vw_visitas
WHERE dt_visita BETWEEN DATE '2026-10-01' AND DATE '2026-10-08';

-- por mês (compare com a planilha mês a mês)
SELECT mes, COUNT(DISTINCT id_visita) AS visitas, COUNT(DISTINCT id_propriedade) AS propriedades,
       COUNT(DISTINCT tecnico) AS tecnicos
FROM public.vw_visitas WHERE mes >= '2026-01' GROUP BY 1 ORDER BY 1;
