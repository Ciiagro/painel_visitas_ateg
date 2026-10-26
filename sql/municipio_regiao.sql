-- Tabela de municípios com região (FAEC, SEBRAE, planejamento) e sindicato.
-- Copiada do Supabase (projeto Avaliacao de Desempenho, schema sindicatos) pelo sincronizar_municipios.py.
-- Pode rodar à mão no pgAdmin (cria vazia); quem preenche é o script.
CREATE TABLE IF NOT EXISTS public.municipio_regiao (
  cod_ibge            text PRIMARY KEY,
  nome                text NOT NULL,
  nome_norm           text NOT NULL UNIQUE,   -- nome sem acento, MAIÚSCULO: é por ele que a view liga com as visitas
  regiao_faec         text,
  regiao_sebrae       text,
  regiao_planejamento text,
  sindicato           text
);
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'painel_leitura') THEN
    GRANT SELECT ON public.municipio_regiao TO painel_leitura;
  END IF;
END $$;
