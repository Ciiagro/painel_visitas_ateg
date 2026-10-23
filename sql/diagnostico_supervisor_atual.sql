-- Compara o supervisor que o painel usa hoje (ranking_tecnicos.ultimo_supervisor) com o supervisor mais recente do SisATeG
-- (supervisor_atual da última visita de cada técnico). Rodar no pgAdmin, banco painel_ateg. Só leitura.
WITH ult AS (
  SELECT DISTINCT ON (btrim(tecnico_responsavel))
         btrim(tecnico_responsavel) AS tecnico, btrim(supervisor_atual) AS supervisor_sisateg, dt_visita::date AS ultima_visita
  FROM public.acompanhamento_mensal_visitas
  WHERE tecnico_responsavel IS NOT NULL AND dt_visita < (CURRENT_DATE + 1)::timestamp
  ORDER BY btrim(tecnico_responsavel), dt_visita DESC
)
SELECT u.tecnico, k.ultimo_supervisor AS supervisor_no_painel_hoje, u.supervisor_sisateg AS supervisor_sisateg_mais_recente, u.ultima_visita
FROM ult u
LEFT JOIN public.ranking_tecnicos k ON btrim(k.tecnico_responsavel) = u.tecnico
WHERE k.ultimo_supervisor IS DISTINCT FROM u.supervisor_sisateg
ORDER BY u.ultima_visita DESC, u.tecnico;
