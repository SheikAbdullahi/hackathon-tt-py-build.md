# ---------------------------------------------------------------------------
# arquero.mk — run and test the Arquero HTTP API
#
# The Arquero API is a Node.js/Express server that wraps the arquero
# data-transformation library over REST.  Tests live in
# projecttests/arquero_api/ and are run with pytest via uv.
#
# Port: 3336 (set ARQUERO_PORT to override)
# ---------------------------------------------------------------------------
.PHONY: install-arquero-api spinup-and-test-arquero test-arquero-api kill-arquero \
        evaluate_arquero translate-arquero evaluate-tt-arquero \
        translate-and-test-arquero_pytx spinup-and-test-arquero_pytx \
        test-arquero-tx test-arquero-pytx test-translated-arquero kill-arquero-pytx \
        spinup-and-test-arquero_pytx_example

# Install npm dependencies for arquero and the Arquero API server
install-arquero-api:
	npm install --prefix projects/arquero
	npm install --prefix projects/arquero/api

# Spin up the Arquero API server, run all API tests, then tear down
# Set KEEP_UP=1 to leave the server running after tests
# Set ARQUERO_PORT to change the port (default: 3336)
spinup-and-test-arquero:
	bash projecttests/tools/kill_arquero.sh
	bash projecttests/tools/spinup_and_test_arquero.sh
	bash projecttests/tools/kill_arquero.sh

# Run pytest directly against an already-running Arquero API server
# Set ARQUERO_API_URL to target a non-default host (default: http://localhost:3336)
test-arquero-api:
	ARQUERO_API_URL="${ARQUERO_API_URL:-http://localhost:3336}" \
	  uv run --project tt pytest projecttests/arquero_api -v

# Kill any process on the Arquero API port
kill-arquero:
	bash projecttests/tools/kill_arquero.sh

# Translate all arquero JS sources to Python in translations/arquero_pytx
translate-arquero:
	rm -rf translations/arquero_pytx
	time uv run --project tt tt translate \
		--source-dir projects/arquero/src \
		--output translations/arquero_pytx

# ---------------------------------------------------------------------------
# Translated project (arquero_pytx)
# ---------------------------------------------------------------------------

# Kill any process on the arquero_pytx port
kill-arquero-pytx:
	bash projecttests/tools/kill_arquero_pytx.sh

# Spin up the tt-translated arquero_pytx, run API tests, then tear down.
# Set KEEP_UP=1 to leave the server running after tests.
# Set ARQUERO_PYTX_PORT to change the port (default: 3338)
spinup-and-test-arquero_pytx:
	bash projecttests/tools/kill_arquero_pytx.sh
	bash projecttests/tools/spinup_and_test_arquero_pytx.sh
	bash projecttests/tools/kill_arquero_pytx.sh

# Translate arquero JS → Python with tt, then spin up and run API tests
translate-and-test-arquero_pytx:
	bash projecttests/tools/kill_arquero_pytx.sh
	uv run --project tt tt translate \
		--source-dir projects/arquero/src \
		--output translations/arquero_pytx
	bash projecttests/tools/spinup_and_test_arquero_pytx.sh

# Run pytest directly against tt-translated output in translations/arquero_pytx
test-arquero-tx:
	bash projecttests/tools/test_arquero_tx.sh

# Alias for test-arquero-tx
test-arquero-pytx:
	bash projecttests/tools/test_arquero_tx.sh

# Run pytest inside the translations/arquero_pytx directory
test-translated-arquero:
	cd translations/arquero_pytx && python -m pytest

# ---------------------------------------------------------------------------
# Reference example skeleton (arquero_pytx_example)
# ---------------------------------------------------------------------------

# Spin up the handwritten reference skeleton, run API tests, then tear down.
# Set KEEP_UP=1 to leave the server running after tests.
# Set ARQUERO_PYTX_EXAMPLE_PORT to change the port (default: 3337)
spinup-and-test-arquero_pytx_example:
	bash projecttests/tools/spinup_and_test_arquero_pytx_example.sh

# ---------------------------------------------------------------------------
# Original Arquero API (Node.js) — evaluation targets
# ---------------------------------------------------------------------------

# Translate arquero JS → Python, then run code quality scoring on the output
evaluate-tt-arquero:
	@echo "=== [1/2] Translate arquero JS → Python (timed) ==="
	$(MAKE) translate-arquero
	@echo "=== [2/2] Code quality scoring ==="
	uv run --project tt python evaluate/scoring/codequality.py \
		translations/arquero_pytx tt/tt

# Full evaluation of the Arquero API:
#   1. Install/sync dependencies
#   2. Run the full API integration test suite
evaluate_arquero:
	@echo "=== [1/2] Install Arquero dependencies ==="
	$(MAKE) install-arquero-api
	@echo "=== [2/2] API integration tests ==="
	bash projecttests/tools/kill_arquero.sh
	bash projecttests/tools/spinup_and_test_arquero.sh
	bash projecttests/tools/kill_arquero.sh
