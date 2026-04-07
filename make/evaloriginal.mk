# ---------------------------------------------------------------------------
# evaloriginal.mk — run the original Ghostfolio test suite and Python API tests
#
# Targets in this file verify that the original Ghostfolio TypeScript project
# works correctly, and run the Python integration test suite against a live
# Ghostfolio instance (via Docker Compose) to establish a ground-truth baseline.
#
# Prerequisites: cd projects/ghostfolio && npm install
#                Docker must be running for spinup-and-test-ghostfolio
# ---------------------------------------------------------------------------
.PHONY: test-ghostfolio test-ghostfolio-api test-ghostfolio-ui test-ghostfolio-common \
        test-ghostfolio-api-suite spinup-and-test-ghostfolio

# Original ghostfolio tests
test-ghostfolio:
	cd projects/ghostfolio && npm test

test-ghostfolio-api:
	cd projects/ghostfolio && npm run test:api

# Python integration tests against a live Ghostfolio API
# Set GHOSTFOLIO_API_URL to target a non-default host (default: http://localhost:3333)
test-ghostfolio-api-suite:
	bash projecttests/tools/test_ghostfolio_api.sh

# Spin up Ghostfolio via Docker Compose, run API tests, tear down
# Set KEEP_UP=1 to leave containers running after tests
# Set GHOSTFOLIO_PORT to change the host port (default: 3333)
spinup-and-test-ghostfolio:
	bash projecttests/tools/spinup_and_test_ghostfolio.sh
