-- =====================================================================
-- PAINEL DE VISITAS - DEIXAR O PAINEL MAIS RÁPIDO. Rodar UMA vez no SERVIDOR (banco painel_ateg), no pgAdmin.
-- Cria a tabela pronta public.mv_visitas (cópia calculada da view vw_visitas, com índices).
-- Depois de criada, o painel passa a usar essa tabela sozinho (se ela existir; se não existir, usa a vw_visitas).
-- Ela é atualizada a cada envio (sync_visitas_local_to_remoto.py faz o REFRESH). Rode ANTES o vw_visitas.sql, se mudou.
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS public.mv_visitas;
CREATE MATERIALIZED VIEW public.mv_visitas AS SELECT * FROM public.vw_visitas;
CREATE INDEX mv_visitas_dt   ON public.mv_visitas (dt_visita);
CREATE INDEX mv_visitas_vis  ON public.mv_visitas (id_visita);
CREATE INDEX mv_visitas_prop ON public.mv_visitas (id_propriedade, dt_visita DESC);
CREATE INDEX mv_visitas_tec  ON public.mv_visitas (tecnico, dt_visita DESC);
CREATE INDEX mv_visitas_sup  ON public.mv_visitas (supervisor, dt_visita);
CREATE INDEX mv_visitas_mun  ON public.mv_visitas (municipio, dt_visita);
CREATE INDEX mv_visitas_proj ON public.mv_visitas (projeto, dt_visita);
ANALYZE public.mv_visitas;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'painel_leitura') THEN
    GRANT SELECT ON public.mv_visitas TO painel_leitura;
  END IF;
END $$;

-- Conferência: deve dar o mesmo número da vw_visitas.
SELECT (SELECT COUNT(DISTINCT id_visita) FROM public.mv_visitas) AS visitas_mv,
       (SELECT COUNT(DISTINCT id_visita) FROM public.vw_visitas) AS visitas_view;
