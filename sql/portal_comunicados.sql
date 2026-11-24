-- Comunicados da coordenação, mostrados na Área do colaborador do portal.
CREATE TABLE IF NOT EXISTS public.portal_comunicados (
    id         SERIAL PRIMARY KEY,
    titulo     TEXT NOT NULL,
    texto      TEXT NOT NULL,
    criado_por TEXT NOT NULL,
    criado_em  TIMESTAMP NOT NULL DEFAULT NOW(),
    ativo      BOOLEAN NOT NULL DEFAULT TRUE
);

-- O portal só mexe nesta tabela: ler, publicar e desativar (não apaga).
GRANT SELECT, INSERT, UPDATE ON public.portal_comunicados TO painel_leitura;
GRANT USAGE, SELECT ON SEQUENCE public.portal_comunicados_id_seq TO painel_leitura;

SELECT table_name, privilege_type FROM information_schema.role_table_grants
WHERE grantee = 'painel_leitura' AND table_name = 'portal_comunicados' ORDER BY 2;

-- Comunicado destacado (faixa verde no topo da lista)
ALTER TABLE public.portal_comunicados ADD COLUMN IF NOT EXISTS destaque BOOLEAN NOT NULL DEFAULT FALSE;
