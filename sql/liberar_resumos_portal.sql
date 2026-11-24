GRANT SELECT ON public.resumo_leite_mensal,
                public.resumo_ovino_mensal,
                public.resumo_fruta_mensal,
                public.resumo_api_mensal,
                public.resumo_suino_mensal
TO painel_leitura;

SELECT table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'painel_leitura' AND table_name LIKE 'resumo_%_mensal'
ORDER BY 1;
