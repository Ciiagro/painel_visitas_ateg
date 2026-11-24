-- O portal só lê login, nome, tipo e o hash (bcrypt) da senha. Não pode alterar nada.
GRANT SELECT (supervisor, login, senha_hash, tipo) ON public.usuarios_supervisores TO painel_leitura;

SELECT column_name, privilege_type
FROM information_schema.column_privileges
WHERE grantee = 'painel_leitura' AND table_name = 'usuarios_supervisores'
ORDER BY 1;
