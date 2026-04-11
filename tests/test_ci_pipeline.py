"""
tests/test_ci_pipeline.py

Validates the GitHub Actions CI/CD workflow configuration at
.github/workflows/ci.yml.

Coverage:
  File existence & validity
    - Workflow file exists at the expected path
    - File is parseable as valid YAML

  Triggers
    - Fires on push events
    - Fires on pull_request events
    - Push trigger includes the 'main' branch

  Jobs structure
    - 'test' job is present
    - 'build' job is present
    - 'build' job declares 'needs: test' (gates Docker build on passing tests)

  test job
    - Runs on ubuntu-latest
    - Has an actions/checkout step
    - Sets up Python 3.11
    - Installs dependencies from requirements.txt via pip
    - Executes pytest
    - Provides a Redis service (required by workers and stats tests)
    - Exposes GOOGLE_API_KEY as an environment variable

  build job
    - Has an actions/checkout step
    - Runs 'docker build'
"""

import os
import pytest

# Path to the workflow file relative to the project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW_PATH = os.path.join(_PROJECT_ROOT, ".github", "workflows", "ci.yml")

yaml = pytest.importorskip("yaml", reason="pyyaml is required to parse workflow files")


@pytest.fixture(scope="module")
def workflow():
    """Parse the CI workflow file once for the whole module."""
    assert os.path.exists(WORKFLOW_PATH), (
        f"CI workflow not found at {WORKFLOW_PATH}. "
        "Create .github/workflows/ci.yml to proceed."
    )
    with open(WORKFLOW_PATH) as f:
        return yaml.safe_load(f)


# ===========================================================================
# 1. File existence & validity
# ===========================================================================

class TestWorkflowFileExists:
    def test_workflow_file_exists(self):
        assert os.path.exists(WORKFLOW_PATH), (
            f"Expected .github/workflows/ci.yml at {WORKFLOW_PATH}"
        )

    def test_workflow_is_valid_yaml(self, workflow):
        assert isinstance(workflow, dict), "Workflow root must be a YAML mapping"


# ===========================================================================
# 2. Triggers
# ===========================================================================

class TestWorkflowTriggers:
    def test_triggers_on_push(self, workflow):
        assert "push" in workflow.get("on", {}), (
            "Workflow must trigger on push events"
        )

    def test_triggers_on_pull_request(self, workflow):
        assert "pull_request" in workflow.get("on", {}), (
            "Workflow must trigger on pull_request events"
        )

    def test_push_includes_main_branch(self, workflow):
        push_cfg = workflow["on"]["push"]
        branches = push_cfg.get("branches", []) if isinstance(push_cfg, dict) else []
        assert "main" in branches, (
            "Push trigger must include 'main' branch"
        )


# ===========================================================================
# 3. Jobs structure
# ===========================================================================

class TestJobsStructure:
    def test_has_test_job(self, workflow):
        assert "test" in workflow.get("jobs", {}), "A 'test' job must be defined"

    def test_has_build_job(self, workflow):
        assert "build" in workflow.get("jobs", {}), "A 'build' job must be defined"

    def test_build_job_needs_test_job(self, workflow):
        """Build must not run unless tests pass."""
        build_job = workflow["jobs"]["build"]
        needs = build_job.get("needs", [])
        if isinstance(needs, str):
            needs = [needs]
        assert "test" in needs, "'build' job must declare 'needs: test'"


# ===========================================================================
# 4. test job details
# ===========================================================================

class TestTestJob:
    @pytest.fixture(autouse=True)
    def _job(self, workflow):
        self.job = workflow["jobs"]["test"]
        self.steps = self.job.get("steps", [])

    def test_runs_on_ubuntu(self):
        assert "ubuntu" in self.job.get("runs-on", ""), (
            "test job must run on ubuntu-latest"
        )

    def test_has_checkout_step(self):
        has_checkout = any(
            "actions/checkout" in str(s.get("uses", ""))
            for s in self.steps
        )
        assert has_checkout, "test job must have an actions/checkout step"

    def test_uses_python_311(self):
        setup_step = next(
            (s for s in self.steps if "setup-python" in str(s.get("uses", ""))),
            None,
        )
        assert setup_step is not None, "test job must have a setup-python step"
        python_version = str(setup_step.get("with", {}).get("python-version", ""))
        assert "3.11" in python_version, (
            f"Python version must be 3.11, got '{python_version}'"
        )

    def test_installs_requirements_txt(self):
        install_step = next(
            (
                s for s in self.steps
                if "pip install" in str(s.get("run", ""))
                and "requirements.txt" in str(s.get("run", ""))
            ),
            None,
        )
        assert install_step is not None, (
            "test job must have a step that runs 'pip install ... requirements.txt'"
        )

    def test_runs_pytest(self):
        pytest_step = next(
            (s for s in self.steps if "pytest" in str(s.get("run", ""))),
            None,
        )
        assert pytest_step is not None, "test job must have a step that runs pytest"

    def test_has_redis_service(self):
        services = self.job.get("services", {})
        assert "redis" in services, (
            "test job must declare a Redis service so worker/stats tests can connect"
        )

    def test_redis_service_uses_redis_image(self):
        redis_service = self.job.get("services", {}).get("redis", {})
        image = redis_service.get("image", "")
        assert "redis" in image, (
            f"Redis service image should be a Redis image, got '{image}'"
        )

    def test_sets_google_api_key_env_var(self):
        """Tests import config.py which calls sys.exit() without this key."""
        # Check both job-level env and step-level env
        job_env = self.job.get("env", {})
        step_envs = [s.get("env", {}) for s in self.steps]
        all_envs = [job_env] + step_envs
        has_key = any("GOOGLE_API_KEY" in env for env in all_envs)
        assert has_key, (
            "test job must set GOOGLE_API_KEY env var "
            "(config.py calls sys.exit() if it is missing)"
        )


# ===========================================================================
# 5. build job details
# ===========================================================================

class TestBuildJob:
    @pytest.fixture(autouse=True)
    def _job(self, workflow):
        self.job = workflow["jobs"]["build"]
        self.steps = self.job.get("steps", [])

    def test_has_checkout_step(self):
        has_checkout = any(
            "actions/checkout" in str(s.get("uses", ""))
            for s in self.steps
        )
        assert has_checkout, "build job must have an actions/checkout step"

    def test_runs_docker_build(self):
        docker_step = next(
            (s for s in self.steps if "docker build" in str(s.get("run", ""))),
            None,
        )
        assert docker_step is not None, (
            "build job must have a step that runs 'docker build'"
        )
