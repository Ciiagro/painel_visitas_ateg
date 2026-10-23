-- RODAR NO SERVIDOR (banco painel_ateg), com o usuário administrador. SÓ se o usuário painel_leitura ainda não existir.
-- Se ele já existe (das outras cadeias), basta o GRANT da última linha (o vw_visitas.sql já faz isso sozinho).
-- Troque TROQUE_ESTA_SENHA por uma senha forte e NOVA antes de rodar.
CREATE ROLE painel_leitura LOGIN PASSWORD 'TROQUE_ESTA_SENHA';
GRANT CONNECT ON DATABASE painel_ateg TO painel_leitura;
GRANT USAGE ON SCHEMA public TO painel_leitura;
GRANT SELECT ON public.vw_visitas TO painel_leitura;
