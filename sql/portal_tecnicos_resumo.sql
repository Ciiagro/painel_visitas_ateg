-- Só contagens (sem nome/CPF/contato): o portal lê esta view.
CREATE OR REPLACE VIEW public.vw_tecnicos_resumo AS
SELECT COUNT(*)::int AS total,
       COUNT(*) FILTER (WHERE ativo)::int AS ativos,
       COUNT(*) FILTER (WHERE ultima_visita >= date_trunc('year', CURRENT_DATE))::int AS com_visita_no_ano
FROM public.tecnicos;
GRANT SELECT ON public.vw_tecnicos_resumo TO painel_leitura;
SELECT * FROM public.vw_tecnicos_resumo;
