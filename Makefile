.PHONY: setup-db refresh inspect test test-vector

PYTHON ?= python

setup-db:
	$(PYTHON) -m cs_agent.db.refresh setup

refresh:
	$(PYTHON) -m cs_agent.db.refresh refresh

inspect:
	$(PYTHON) -m cs_agent.db.refresh inspect

test:
	CS_BACKEND=fixtures $(PYTHON) -m unittest tests.test_framework

test-vector:
	CS_RUN_VECTOR_TESTS=1 CS_BACKEND=postgres $(PYTHON) -m unittest tests.test_vector_retrieval
