# Data Card — Themis.IA

## 1. Visão geral

O Themis.IA opera sobre **dados não estruturados fornecidos pelo usuário em tempo de uso**
(processos, petições, contratos, sentenças) e sobre **metadados públicos** consultados na
API SRU do portal LexML. Não há dataset de treinamento próprio: nenhum modelo é treinado
ou ajustado neste projeto — os dados alimentam exclusivamente o índice vetorial local (RAG).

## 2. Fontes e licenças

| Fonte | Conteúdo | Licença / base legal |
|---|---|---|
| Upload do usuário | PDF/DOCX/TXT/MD de peças e processos | Responsabilidade do usuário; processados apenas localmente + API Gemini |
| LexML (`lexml.gov.br/busca/SRU`) | Metadados Dublin Core de legislação e jurisprudência | Dados públicos governamentais |
| `data/exemplos/` | Contrato e sentença **fictícios**, criados para este projeto | Livres (criados pelo autor, sem dados reais) |
| Google Gemini (API) | Modelo gerador | API comercial (Termos do Google AI Studio) |

## 3. Volume e formato

- Limite por arquivo: **150 MB** (configurável via `MAX_UPLOAD_MB`).
- Formatos aceitos: `.pdf` (PyMuPDF, com OCR opcional), `.docx` (python-docx, incluindo tabelas), `.txt`, `.md`.
- Persistência vetorial: **ChromaDB** local (`chroma_db/`), espaço de similaridade cosseno.

## 4. Schema dos chunks (variáveis)

| Campo | Tipo | Descrição |
|---|---|---|
| `page_content` | texto | Trecho de até `CHUNK_SIZE` caracteres (padrão 1000, overlap 200) |
| `source` | metadado | Nome do arquivo de origem (ex.: `contrato_exemplo.txt`) |
| `page` | metadado | Página (1-indexada) de onde o trecho foi extraído |
| `chunk_index` | metadado | Posição sequencial do chunk no documento |
| `file_sha256` | metadado | Hash SHA-256 do arquivo — deduplicação e rastreabilidade |
| `indexed_at` | metadado | Timestamp UTC da indexação |

## 5. Pré-processamento (reproduzível via código)

Implementado em `src/ingestion/` e coberto por testes unitários:

1. Extração de texto por página (PyMuPDF) ou parágrafo/tabela (python-docx).
2. Remoção de **cabeçalhos/rodapés repetidos** (linhas curtas presentes em ≥ 60% das páginas)
   e de linhas de numeração de página.
3. Normalização de espaços em branco.
4. Chunking recursivo com separadores jurídicos (`\n\n`, `Art.`, `CLÁUSULA`, `§`, …) —
   1000 caracteres, 200 de sobreposição.
5. Deduplicação por SHA-256 antes da indexação (ingestão idempotente).

## 6. Riscos, vieses e privacidade

- **PII / segredo de justiça**: os documentos são enviados à API do Gemini para geração.
  A versão MVP **não deve** ser usada com processos sob sigilo absoluto; recomenda-se
  anonimização prévia e contas corporativas cujos termos vedem uso dos dados para treino.
- **Alucinação**: mitigada por prompts com regras de aterramento rígidas, citação
  obrigatória de fontes (`[arquivo, p. N]` / URN LexML) e avaliação de groundedness
  (`eval/evaluate.py`).
- **Viés de fonte**: a base reflete apenas os documentos carregados; a interface exige o
  aviso permanente de que as respostas não substituem a análise de um(a) advogado(a).
- **Qualidade de PDF**: escaneamentos sem texto selecionável são ignorados (com aviso),
  a menos que o OCR opcional esteja habilitado (`OCR_ENABLED=true`).

## 7. Rastreabilidade

Cada documento indexado registra o SHA-256 na página **📚 Base de Conhecimento**, e cada
consulta gera um evento JSONL em `data/analytics/search_analytics.jsonl` (persona,
latências, nº de trechos usados, uso do LexML), consumido pelo dashboard **📊 Analytics**.
