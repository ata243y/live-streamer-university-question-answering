PYTHON = ./venv/bin/python3
VENV_DIR = venv
APP = qa_app/main.py
REQUIREMENTS = qa_app/requirements.txt

all: run

run:
	$(PYTHON) -m qa_app.main

install:
	$(PYTHON) -m pip install -r $(REQUIREMENTS)

test:
	$(PYTHON) -m pytest qa_app/tests/

clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete

.PHONY: all run install test clean