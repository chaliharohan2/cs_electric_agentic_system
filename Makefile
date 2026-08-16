.PHONY: setup-db refresh inspect test test-vector

PYTHON ?= python

setup-db:
	$(PYTHON) -m cs_agent.db.refresh setup

refresh:
	$(PYTHON) -m cs_agent.db.refresh refresh

inspect:
	$(PYTHON) -m cs_agent.db.refresh inspect

# The framework suite forces the fixtures backend; the SQLite suites read the
# built artifact, so they run in a second pass with the real backend.
test:
	CS_BACKEND=fixtures $(PYTHON) -m unittest tests.test_framework
	CS_BACKEND=sqlite $(PYTHON) -m unittest tests.test_sqlite tests.test_vector_retrieval

test-vector:
	CS_BACKEND=sqlite $(PYTHON) -m unittest tests.test_vector_retrieval
