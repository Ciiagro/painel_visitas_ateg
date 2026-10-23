-- Rodar no SERVIDOR (painel_ateg). Cada bloco mostra um resultado; me mande print dos 4.

-- 1) Quais valores existem de status da propriedade (e quantas propriedades em cada)
SELECT status_propriedade, status_propriedade_oficial, COUNT(DISTINCT id_propriedade) AS propriedades
FROM public.acompanhamento_mensal_visitas
GROUP BY 1,2 ORDER BY 3 DESC;

-- 2) Uma propriedade muda de status entre as visitas? (se sim, usamos o da visita mais recente)
SELECT COUNT(*) AS propriedades_com_mais_de_um_status FROM (
  SELECT id_propriedade FROM public.acompanhamento_mensal_visitas
  GROUP BY 1 HAVING COUNT(DISTINCT status_propriedade_oficial) > 1) x;

-- 3) Orientações: o número repete em todas as visitas da mesma propriedade? (olhe 5 propriedades)
SELECT id_propriedade, id_visita, dt_visita::date, ori_aberta, ori_em_execucao, ori_concluida, ori_cancelada, ori_nao_realizada, ori_total_geral, qtd_orientacao
FROM public.acompanhamento_mensal_visitas
WHERE id_propriedade IN (SELECT id_propriedade FROM public.acompanhamento_mensal_visitas GROUP BY 1 HAVING COUNT(DISTINCT id_visita) >= 3 LIMIT 5)
ORDER BY id_propriedade, dt_visita;

-- 4) Totais brutos (somando linhas) x por propriedade (valor mais recente de cada uma)
SELECT SUM(ori_total_geral) AS soma_bruta_total, SUM(ori_concluida) AS soma_bruta_concluida,
       (SELECT SUM(ori_total_geral) FROM (SELECT DISTINCT ON (id_propriedade) ori_total_geral FROM public.acompanhamento_mensal_visitas ORDER BY id_propriedade, dt_visita DESC) t) AS total_por_propriedade,
       (SELECT SUM(ori_concluida) FROM (SELECT DISTINCT ON (id_propriedade) ori_concluida FROM public.acompanhamento_mensal_visitas ORDER BY id_propriedade, dt_visita DESC) t) AS concluida_por_propriedade
FROM public.acompanhamento_mensal_visitas;
