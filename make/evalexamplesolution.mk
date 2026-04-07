# ---------------------------------------------------------------------------
# evalexamplesolution.mk — run the handwritten reference skeleton
#
# ghostfolio_pytx_example is a manually written FastAPI implementation that
# demonstrates the expected shape of a fully translated Ghostfolio API.
# It returns structurally correct (but mostly stub) responses so the test
# suite can run end-to-end.  Use it to understand which tests are reachable
# with a correct API structure, independent of calculation correctness.
#
# Port: 3334 (set PYTX_EXAMPLE_PORT to override)
# ---------------------------------------------------------------------------
.PHONY: spinup-and-test-ghostfolio_pytx_example

# Spin up the ghostfolio_pytx_example reference skeleton, run the API test suite,
# then stop the server. The example shows how a translated API should respond.
# Set KEEP_UP=1 to leave the server running after tests
# Set PYTX_EXAMPLE_PORT to change the port (default: 3334)
spinup-and-test-ghostfolio_pytx_example:
	bash projecttests/tools/spinup_and_test_ghostfolio_pytx_example.sh
