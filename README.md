# Radar de Entregas · Reposição de Mercadorias

MVP do projeto extensionista da disciplina **ARA4769 · Tópicos de Big Data em Python** (Universidade Estácio de Sá).

O sistema importa as planilhas mensais de OTIF com **PySpark**, junta tudo em uma base única, verifica a
qualidade dos dados e mostra, em um painel feito com **Pandas, Plotly e Streamlit**, os índices de OT, IF e
OTIF: por mês, por dia da semana, por causa da falha e por cliente.

Grupo: Aloizio Pita de Castro Júnior, Mariana Oliveira Menzonatto e João Gabriel Moreira de Castro.
Professor Orientador: Anderson Cruz

## Jeito mais fácil (Windows)

Com o Python 3.11 ou 3.12 e o Java 17 instalados, dê dois cliques em **`Iniciar Radar de Entregas.bat`**.
Ele cria o ambiente virtual e instala as bibliotecas na primeira vez, processa os CSVs de `dados\brutos`
só quando há arquivo novo ou alterado e abre o painel no navegador. Para encerrar, feche a janela preta.

Para forçar o processamento de todos os CSVs, use **`Reprocessar os CSVs.bat`**.
Sem Java, o painel abre do mesmo jeito, com os dados já processados.
As bibliotecas ficam em `%LOCALAPPDATA%\RadarDeEntregas\venv`, porque o Spark não funciona no Windows
quando o Python está em uma pasta com espaços.

## Como rodar passo a passo (Windows)

O projeto tem duas partes. O **pipeline** (Spark) roda uma vez e grava os dados processados em Parquet.
O **painel** só lê esses arquivos, por isso funciona em qualquer máquina com Python, sem Java.

1. Instale o **Python 3.11 ou 3.12**. Abra o terminal nesta pasta e crie o ambiente virtual:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Abra o painel (os dados processados já estão em `dados\analiticos\`):
   ```
   streamlit run app.py
   ```
   Depois abra http://localhost:8501 no navegador.
3. Para processar os dados de novo (só quem for rodar o pipeline):
   - instale o **Java 17** (Temurin/OpenJDK);
   - copie os CSVs de OTIF (os arquivos de dentro do `otif.7z`) para `dados\brutos\`;
   - rode `python executar_pipeline.py` (leva menos de 1 minuto com os arquivos de exemplo).
   Só entram os arquivos com o mês no nome (`OTIF_JAN22.CSV`, `OTIF_FEV22.CSV`...); os outros são descartados.
4. Testes: `python -m pytest` (o teste do Spark é pulado se o Java não estiver instalado).

## Como o sistema está organizado

```
dados/
  brutos/       camada bruta: os CSVs como vieram (não versionados)
  tratados/     camada tratada: visitas_tratadas.parquet (não versionada)
  analiticos/   camada analítica: modelo estrela, relatório mensal, resumo dos arquivos e relatório de qualidade
src/otif/
  config.py         caminhos e constantes do layout
  processamento.py  ProcessadorSpark: leitura dos CSVs, transformações e agregação mensal
  ambiente.py       escolhe um Java compatível (11, 17 ou 21) e prepara as variáveis do Spark
  validacao.py      ValidadorQualidade e RelatorioQualidade
  modelo_dados.py   ConstrutorModeloEstrela (fato_visita + dimensões)
  repositorio.py    RepositorioParquet (leitura e gravação das camadas)
  indicadores.py    CalculadoraOTIF (OT, IF, OTIF, causas, ranking de clientes e Pareto)
  pipeline.py       PipelineOTIF (orquestra as etapas)
executar_pipeline.py  roda o pipeline
app.py                painel Streamlit (4 abas)
tests/                testes das regras principais
docs/diagramas.md     modelo de dados e diagrama de classes em Mermaid
```

## O painel

| Aba | O que mostra |
| --- | --- |
| Visão geral | OTIF, OT e IF do período, evolução mensal, falhas por dia da semana e relatório mensal (CSV) |
| Clientes | Concentração das falhas (Pareto) e ranking de clientes por volume de falhas ou por taxa de falha |
| Causas das falhas | Prazo, completude, as duas ou entrega não realizada, no total e por mês |
| Qualidade dos dados | Arquivos importados e descartados, entregas não realizadas, meses sem arquivo e regras verificadas |

## Regras adotadas

- Cada arquivo traz um mês, identificado pelo nome (`OTIF_MMMAA.CSV`).
- Da chave "Visita OTIF" o sistema usa só o código do cliente (2º trecho). Visitas com mapa `000000` no fim
  da chave são tratadas como **entrega não realizada** e contam como falha de OT, IF e OTIF.
- Os índices: OT = % de visitas no prazo, IF = % de visitas completas, OTIF = % de visitas no prazo e completas.