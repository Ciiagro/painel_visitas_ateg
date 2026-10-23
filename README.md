# Painel de visitas: Acompanhamento das Visitas (ATeG)

Mesmo desenho do painel de cadeias (FastAPI + Chart.js na Vercel), no layout do Power BI "Acompanhamento das Visitas".
Lê a view `public.vw_visitas` do banco `painel_ateg`, criada em cima da tabela que já existe lá: `acompanhamento_mensal_visitas`.
Nada é copiado: quando a tabela é atualizada, o painel já mostra o dado novo.

## O que o painel mostra
- Filtros: período (De/Até + atalhos), município, supervisor, técnico responsável, atividade, projeto, coleta de dados, visita presencial, visita válida. Um filtro limita as opções dos outros.
- 10 cartões (como no Power BI): total de visitas, propriedades assistidas, total de visitas padrão, coleta de dados, visita retorno, visitas virtual, visitas zero, total de supervisores, total de técnicos, municípios atendidos. Cada um compara com o período anterior de mesma duração.
- Destaques: atividade, supervisor, técnico e município com mais visitas; média por técnico; visitas por propriedade; % de visitas válidas; média por dia.
- Abas: Visão geral (projeto, tabela por atividade, evolução, tipo de visita, dia da semana, frequência por propriedade), Atividades, Supervisores, Técnicos (busca) e Municípios. Tabelas ordenáveis e com botão CSV.

## Regras
- Visita = `id_visita` distinto da tabela `acompanhamento_mensal_visitas` (a lista de visitas do SisATeG sem as visitas excluídas). Só até hoje, a partir de 01/06/2024.
- Propriedades assistidas = `id_propriedade` distinto. Total visitas padrão = visitas que não são coleta de dados.
- Supervisor = o da ÚLTIMA visita do técnico no SisATeG (`supervisor_atual`); se faltar, usa o do ranking (`ranking_tecnicos.ultimo_supervisor`).
- Técnico = técnico responsável pela visita.

## Conferência com a planilha "Lista de Visitas" do SisATeG
Rodar `sql/conferencia_visitas.sql` no servidor e comparar com a planilha (mesmas datas): visitas, propriedades, técnicos, coleta.
Testado com a planilha de 2026 (01 a 08/10/2026): 1.912 visitas, 1.850 propriedades, 195 técnicos, 15 supervisores, 59 coletas, igual ao filtro da planilha.

## Primeira publicação
1. No servidor (pgAdmin, banco `painel_ateg`): rodar `sql/vw_visitas.sql` (cria a view e mostra a conferência).
2. Copiar o `.env` de outra cadeia (só as variáveis REMOTE_DB_*) e testar: `uvicorn app.main:app --port 8005` e abrir http://localhost:8005
3. Criar repositório no GitHub, `git push`, e criar o projeto na Vercel com as variáveis REMOTE_DB_* (ver `.env.example`).


## Aba "Conferência" (só no seu computador)
Compara a lista de visitas baixada do SisATeG (.xlsx) com os dados da API que o painel mostra e lista só as diferenças:
só no SisATeG, só no painel, validade diferente, data diferente e coleta de dados diferente (CSV com todas).
A planilha é lida no navegador e não é enviada a nenhum servidor. A aba aparece quando o painel roda localmente e fica
desligada na Vercel (versão pública). Para forçar, use a variável CONFERENCIA=1 (liga) ou CONFERENCIA=0 (desliga).


## Publicação (Vercel)
Variáveis de ambiente na Vercel: `REMOTE_DB_USER`, `REMOTE_DB_PASS`, `REMOTE_DB_HOST`, `REMOTE_DB_PORT`, `REMOTE_DB_NAME` (use o usuário somente-leitura `painel_leitura`, ver `sql/usuario_leitura.sql`).
Na versão pública ficam desligados automaticamente: aba Conferência e o mapa de propriedades (localização de propriedades).
Velocidade: rodar `sql/vw_visitas.sql` e depois `sql/mv_visitas.sql` uma vez; o `atualizar_visitas.bat` atualiza a tabela pronta (`mv_visitas`) a cada envio.
