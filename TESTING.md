# Testing Guide

## Unit Testing

### Setup

```bash
pip install pytest pytest-asyncio pytest-mock
```

### Example Unit Tests

Create `tests/test_eks_operations.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from app.services.eks_operations import EKSOperationsService
from kubernetes.client.rest import ApiException


@pytest.fixture
def mock_eks_service():
    """Create a mock EKS service for testing."""
    with patch('app.services.eks_operations.boto3'):
        with patch('app.services.eks_operations.client'):
            service = EKSOperationsService()
            service.k8s_batch_api = MagicMock()
            service.k8s_core_api = MagicMock()
            return service


def test_create_job_success(mock_eks_service):
    """Test successful job creation."""
    # Mock the Kubernetes API response
    mock_response = MagicMock()
    mock_response.metadata.name = "test-job"
    mock_response.metadata.namespace = "default"
    mock_response.metadata.creation_timestamp = MagicMock()
    
    mock_eks_service.k8s_batch_api.create_namespaced_job.return_value = mock_response
    mock_eks_service.k8s_core_api.read_namespace.return_value = MagicMock()
    
    # Call the method
    result = mock_eks_service.create_job(
        job_name="test-job",
        job_manifest={"spec": {}},
        namespace="default"
    )
    
    # Assert
    assert result["job_name"] == "test-job"
    assert result["namespace"] == "default"
    assert result["status"] == "created"
    mock_eks_service.k8s_batch_api.create_namespaced_job.assert_called_once()


def test_create_job_failure(mock_eks_service):
    """Test job creation failure."""
    # Mock API exception
    mock_eks_service.k8s_batch_api.create_namespaced_job.side_effect = \
        ApiException(status=400, reason="Invalid manifest")
    mock_eks_service.k8s_core_api.read_namespace.return_value = MagicMock()
    
    # Assert exception is raised
    with pytest.raises(ApiException):
        mock_eks_service.create_job(
            job_name="test-job",
            job_manifest={"spec": {}},
            namespace="default"
        )


def test_delete_job_not_found(mock_eks_service):
    """Test deleting non-existent job."""
    # Mock 404 response
    mock_eks_service.k8s_batch_api.delete_namespaced_job.side_effect = \
        ApiException(status=404, reason="Job not found")
    
    # Assert exception is raised
    with pytest.raises(ApiException) as exc_info:
        mock_eks_service.delete_job("non-existent", "default")
    
    assert exc_info.value.status == 404


def test_get_job_status(mock_eks_service):
    """Test getting job status."""
    # Mock job response
    mock_job = MagicMock()
    mock_job.metadata.name = "test-job"
    mock_job.metadata.namespace = "default"
    mock_job.status.succeeded = 1
    mock_job.status.active = 0
    mock_job.status.failed = 0
    mock_job.status.start_time = MagicMock()
    mock_job.status.completion_time = MagicMock()
    
    mock_eks_service.k8s_batch_api.read_namespaced_job.return_value = mock_job
    
    # Call method
    result = mock_eks_service.get_job_status("test-job", "default")
    
    # Assert
    assert result["job_name"] == "test-job"
    assert result["state"] == "completed"
    assert result["succeeded"] == 1
```

### Run Unit Tests

```bash
pytest tests/test_eks_operations.py -v

# With coverage
pip install pytest-cov
pytest tests/ --cov=app --cov-report=html
```

## Integration Testing

### Integration Test Example

Create `tests/test_integration.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "cluster" in data
    assert "region" in data


def test_create_job_invalid_manifest(client):
    """Test job creation with invalid manifest."""
    response = client.post("/api/eks-create-job", json={
        "job_manifest": None,
        "namespace": "default"
    })
    # Should fail validation
    assert response.status_code in [400, 422]


def test_create_job_valid_manifest(client):
    """Test job creation with valid manifest."""
    response = client.post("/api/eks-create-job", json={
        "job_manifest": {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "test",
                                "image": "busybox",
                                "command": ["echo", "hello"]
                            }
                        ],
                        "restartPolicy": "Never"
                    }
                }
            }
        },
        "namespace": "default"
    })
    
    # Will depend on actual cluster availability
    assert response.status_code in [200, 500]
```

### Run Integration Tests

```bash
# Set environment variables
export EKS_CLUSTER_NAME=your-cluster
export EKS_REGION=us-east-1

# Run tests
pytest tests/test_integration.py -v -s
```

## End-to-End Testing

### Manual Testing with curl

**1. Health Check**

```bash
curl -X GET http://localhost:8000/health
```

**2. Create Namespace**

```bash
curl -X POST http://localhost:8000/api/eks-create-namespace \
  -H "Content-Type: application/json" \
  -d '{
    "namespace_name": "test-ns"
  }'
```

**3. Create Job**

```bash
curl -X POST http://localhost:8000/api/eks-create-job \
  -H "Content-Type: application/json" \
  -d '{
    "job_manifest": {
      "spec": {
        "template": {
          "spec": {
            "containers": [
              {
                "name": "test-job",
                "image": "busybox",
                "command": ["sh", "-c", "echo Hello World && sleep 10"]
              }
            ],
            "restartPolicy": "Never"
          }
        },
        "backoffLimit": 1
      }
    },
    "namespace": "test-ns"
  }'
```

**4. Get Job Status**

```bash
curl -X GET "http://localhost:8000/api/eks-get-job-status?job_name=job-20260120-103000&namespace=test-ns"
```

**5. Delete Job**

```bash
curl -X DELETE "http://localhost:8000/api/eks-delete-job?job_name=job-20260120-103000&namespace=test-ns"
```

**6. Delete Namespace**

```bash
curl -X DELETE "http://localhost:8000/api/eks-delete-namespace?namespace_name=test-ns"
```

### Using Postman/Insomnia

1. Open Postman or Insomnia
2. Create new HTTP requests for each endpoint
3. Set request body to JSON
4. Add necessary query parameters
5. Execute and verify responses

### Using Swagger UI

1. Start application: `uvicorn app.main:app --reload`
2. Open browser: `http://localhost:8000/docs`
3. Use "Try it out" button on each endpoint
4. Test with sample data

## Test Coverage

### Target Coverage

```
app/main.py              95%+
app/api/routes.py        90%+
app/services/eks_operations.py  85%+
app/core/config.py       100%
app/utils/logger.py      90%+
```

### Generate Coverage Report

```bash
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

# Open coverage report
open htmlcov/index.html
```

## Performance Testing

### Load Testing with Apache Bench

```bash
# Install Apache Bench
# macOS: brew install httpd
# Ubuntu: apt-get install apache2-utils

# Test health endpoint
ab -n 1000 -c 10 http://localhost:8000/health

# Test with POST
ab -n 100 -c 5 -p request.json -T application/json \
  http://localhost:8000/api/eks-create-job
```

### Load Testing with Locust

Create `locustfile.py`:

```python
from locust import HttpUser, task, between


class APIUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def health_check(self):
        self.client.get("/health")
    
    @task(1)
    def get_job_status(self):
        self.client.get("/api/eks-get-job-status?job_name=test&namespace=default")


# Run with: locust -f locustfile.py
```

## Stress Testing

### Test with High Concurrency

```bash
# Using Apache Bench
ab -n 5000 -c 100 http://localhost:8000/health

# Using wrk
pip install wrk
wrk -t 4 -c 100 -d 30s http://localhost:8000/health
```

## Security Testing

### Test for Common Vulnerabilities

```bash
# SQL Injection (not applicable - no database)
# XSS (not applicable - API returns JSON)
# CSRF (check CORS settings)
curl -X OPTIONS http://localhost:8000/api/eks-create-job \
  -H "Origin: http://attacker.com"

# Check if credentials are exposed
grep -r "password\|secret\|key" app/
```

## Automated Testing

### GitHub Actions Workflow

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r app/requirements.txt
        pip install pytest pytest-asyncio pytest-cov
    
    - name: Run tests
      run: pytest tests/ --cov=app
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## Continuous Integration

### Pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
- repo: https://github.com/psf/black
  rev: 23.1.0
  hooks:
  - id: black
    
- repo: https://github.com/PyCQA/flake8
  rev: 6.0.0
  hooks:
  - id: flake8
    
- repo: https://github.com/PyCQA/isort
  rev: 5.12.0
  hooks:
  - id: isort
```

Install and setup:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Test Cleanup

### Remove Test Resources

```bash
# Delete test namespace and jobs
kubectl delete namespace test-ns --ignore-not-found=true

# Clear test data
rm -rf .pytest_cache
rm -rf htmlcov
```

## Best Practices

1. **Isolate Tests**: Use fixtures and mocks
2. **Clear Names**: Test names describe what they test
3. **Arrange-Act-Assert**: Structure tests clearly
4. **Mock External Dependencies**: Don't rely on actual EKS cluster for unit tests
5. **Use Fixtures**: Share common setup between tests
6. **Test Error Paths**: Test both success and failure cases
7. **Clean Up**: Remove resources after tests
8. **Document Tests**: Add docstrings to test functions
9. **Run Frequently**: Run tests before commits
10. **Measure Coverage**: Aim for high code coverage

---

For more details, see [README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md)
