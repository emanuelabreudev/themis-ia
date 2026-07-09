PYTHON := .venv/bin/python
PIP := .venv/bin/pip
STREAMLIT := .venv/bin/streamlit

.PHONY: setup run test smoke eval eval-baseline seed-db freeze

setup:            ## Cria o venv e instala as dependências (PyTorch CPU)
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install torch --index-url https://download.pytorch.org/whl/cpu
	$(PIP) install -r requirements.txt

run:              ## Sobe a interface Streamlit
	$(STREAMLIT) run app.py

test:             ## Testes unitários rápidos (sem rede/downloads)
	$(PYTHON) -m pytest -m "not slow"

smoke:            ## Smoke test end-to-end (ingestão + recuperação reais)
	$(PYTHON) -m pytest -m slow -v

seed-db:          ## Indexa os documentos de exemplo na base vetorial
	$(PYTHON) scripts/setup_db.py

eval:             ## Avaliação RAG (groundedness via LLM-as-a-judge; requer GOOGLE_API_KEY)
	$(PYTHON) eval/evaluate.py --mode rag --runs 3

eval-baseline:    ## Avaliação do baseline sem RAG (LLM puro)
	$(PYTHON) eval/evaluate.py --mode baseline --runs 3

freeze:           ## Atualiza o requirements.lock com o ambiente atual
	$(PIP) freeze > requirements.lock
