# Rotina do painel de visitas

Não há rotina própria: o painel lê direto a tabela `acompanhamento_mensal_visitas` do servidor `painel_ateg`.
Ele está sempre tão atualizado quanto essa tabela (a mesma que alimenta o painel ATeG).

## Se o dado parecer velho
1. No servidor: `SELECT MAX(dt_visita) FROM public.acompanhamento_mensal_visitas;` (é a última visita carregada).
2. Se estiver atrás do SisATeG, o problema é a carga dessa tabela, não o painel.
3. Abrir o painel e apertar Ctrl+F5.

## Conferência
`sql/conferencia_visitas.sql` compara visitas, propriedades, técnicos e coleta com a planilha "Lista de Visitas" do SisATeG.
