---
name: regression-tester
description: Run regression tests in the sandbox to verify that a patch does not break existing functionality.
tools:
  - name: run_regression_tests
    description: Run a test suite in the sandbox and compare results.
    states: ["REVIEWER", "VALIDATOR"]
    parameters:
      type: object
      properties:
        test_command: {type: string, description: "Command to execute tests in the sandbox."}
      required: ["test_command"]
---
# Regression Tester Skill

This skill allows you to run test suites in the sandbox to ensure that your security patches do not introduce regressions or break existing functionality.

## Guidelines
- Always use `run_regression_tests` in the REVIEWER state to verify fixes.
- Check the output carefully to ensure all tests pass.
