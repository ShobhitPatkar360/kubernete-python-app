# EKS Kubernetes Operations API

Production-ready Python FastAPI application for managing Kubernetes Jobs and Namespaces in an AWS EKS cluster, running from a standard EC2 instance.

## Overview

This application provides REST APIs to:
- Create, delete, and monitor Kubernetes Jobs in EKS
- Create and delete Kubernetes Namespaces in EKS
- Use IAM-based authentication (no kubeconfig files required)

### Key Features

✅ **IAM-Based Authentication**
- Uses AWS IAM roles for authentication
- No kubeconfig files required
- Short-lived bearer tokens generated on-the-fly
- Secure credentials from EC2 IAM roles, environment variables, or AWS CLI config

✅ **Kubernetes Management**
- Create and delete Jobs with custom manifests
- Monitor job status and execution metrics
- Create and delete Namespaces
- Automatic labels applied to all resources

✅ **Production-Ready**
- Structured logging with proper error handling
- Comprehensive API documentation with Pydantic models
- Health check endpoint
- CORS support for cross-origin requests
- Proper exception handling and HTTP status codes

## Project Structure

```
app/
├── main.py                  # FastAPI application entry point
├── requirements.txt         # Python dependencies
├── api/
│   └── routes.py           # API endpoint definitions
├── services/
│   └── eks_operations.py    # Kubernetes operations service layer
├── core/
│   └── config.py           # Configuration management
└── utils/
    └── logger.py           # Structured logging
```

## Prerequisites

1. **EC2 Instance** with IAM role attached (or AWS credentials configured)
2. **Python 3.9+**
3. **Access to AWS EKS Cluster** with appropriate IAM permissions
4. **Required IAM Permissions** on the EC2 instance:
   - `eks:DescribeCluster`
   - `sts:GetCallerIdentity` (for token generation)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd kubernete-python-app
```

### 2. Create Virtual Environment

```bash
sudo apt install python3.12-venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r app/requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Edit `.env` with your EKS cluster details:

```
EKS_CLUSTER_NAME=your-cluster-name
EKS_REGION=us-east-1
LOG_LEVEL=INFO
```

**Required Variables:**
- `EKS_CLUSTER_NAME`: Name of your EKS cluster
- `EKS_REGION`: AWS region where the cluster is deployed

**AWS Credentials:**
- Automatically resolved from EC2 IAM role (preferred)
- OR set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
- OR configured in `~/.aws/credentials` or `~/.aws/config`

## Running the Application

### Start the Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at: `http://localhost:8000`
Interactive API documentation: `http://localhost:8000/docs`

### Run in Production

Using Gunicorn with Uvicorn workers:

```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Stop application

Using Gunicorn with Uvicorn workers:

```bash
ps aux | grep uvicorn
sudo kill -9 <pid>
```

## API Documentation

### Interactive Documentation

Visit `http://localhost:8000/docs` for interactive Swagger UI documentation.

### API Endpoints

#### Health Check

```
GET /health
```

Returns cluster information and application health status.

#### Job Management

**Create Job**
```
POST /api/eks-create-job
```

Request body:
```json
{
  "job_manifest": {
    "spec": {
      "template": {
        "spec": {
          "containers": [
            {
              "name": "job-container",
              "image": "my-image:latest",
              "command": ["python", "job.py"]
            }
          ],
          "restartPolicy": "Never"
        }
      },
      "backoffLimit": 3
    }
  },
  "namespace": "default"
}
```

**Delete Job**
```
DELETE /api/eks-delete-job?job_name=my-job&namespace=default
```

**Get Job Status**
```
GET /api/eks-get-job-status?job_name=my-job&namespace=default
```

Response:
```json
{
  "job_name": "my-job",
  "namespace": "default",
  "state": "running",
  "active": 1,
  "succeeded": 0,
  "failed": 0,
  "start_time": "2026-01-20T10:30:00+00:00",
  "completion_time": null
}
```

#### Namespace Management

**Create Namespace**
```
POST /api/eks-create-namespace
```

Request body:
```json
{
  "namespace_name": "my-namespace"
}
```

**Delete Namespace**
```
DELETE /api/eks-delete-namespace?namespace_name=my-namespace
```

## Authentication Flow

The application uses IAM-based authentication without kubeconfig files:

1. **Cluster Discovery**: Uses boto3 to call `eks.describe_cluster`
   - Retrieves Kubernetes API server endpoint
   - Fetches base64-encoded CA certificate

2. **Token Generation**: Uses `eks-token` package
   - Generates short-lived IAM bearer token (valid for 15 minutes)
   - Token is created from AWS STS credentials

3. **Client Configuration**: Manually configures Kubernetes client
   - Sets cluster endpoint
   - Sets decoded CA certificate for SSL verification
   - Sets IAM bearer token for authentication

4. **API Calls**: All Kubernetes API operations use authenticated client

No kubeconfig file (`~/.kube/config`) is read, written, or required.

## Error Handling

The API returns appropriate HTTP status codes:

- `200 OK`: Successful operation
- `400 Bad Request`: Invalid request format
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Unexpected server error

All errors include descriptive messages in the response body.

## Logging

The application uses Python's structured logging module with console output.

Log levels can be configured via the `LOG_LEVEL` environment variable:
- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages
- `WARNING`: Warning messages for unusual situations
- `ERROR`: Error messages for failures
- `CRITICAL`: Critical errors

Example log output:
```
2026-01-20 10:30:00 - app.services.eks_operations - INFO - Creating job my-job in namespace default
2026-01-20 10:30:01 - app.services.eks_operations - INFO - Job my-job created successfully
```

## Security Considerations

1. **IAM Authentication**: Uses AWS IAM for secure credential management
2. **Short-lived Tokens**: Bearer tokens expire after 15 minutes
3. **No Hardcoded Credentials**: All credentials are injected from secure sources
4. **RBAC**: Apply Kubernetes RBAC policies to restrict job creation
5. **SSL Verification**: Uses CA certificate for secure API communication
6. **CORS**: Configured but adjust as needed for your deployment

### Recommended IAM Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "eks:DescribeCluster"
      ],
      "Resource": "arn:aws:eks:*:*:cluster/your-cluster-name"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

## Development

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

### Code Structure

- **`app/main.py`**: FastAPI application with lifespan management
- **`app/api/routes.py`**: API endpoints with request/response models
- **`app/services/eks_operations.py`**: Kubernetes API operations
- **`app/core/config.py`**: Configuration from environment variables
- **`app/utils/logger.py`**: Structured logging setup

### Adding New Endpoints

1. Add the endpoint function in `app/api/routes.py`
2. Use existing Pydantic models or create new ones
3. Call appropriate service methods from `EKSOperationsService`
4. Handle exceptions and return structured responses

## Troubleshooting

### Cluster Connection Issues

```
Failed to fetch cluster info: [error]
```

**Solutions:**
1. Verify `EKS_CLUSTER_NAME` and `EKS_REGION` environment variables
2. Check IAM role permissions (needs `eks:DescribeCluster`)
3. Verify EC2 instance network connectivity to EKS API endpoint
4. Check security group rules allow outbound HTTPS (port 443)

### Authentication Errors

```
Kubernetes API error: [401 Unauthorized]
```

**Solutions:**
1. Verify EC2 IAM role has proper EKS permissions
2. Check AWS credentials are valid (if using environment variables)
3. Ensure `sts:GetCallerIdentity` permission for token generation
4. Token may have expired - application will regenerate on retry

### Job Creation Errors

```
Kubernetes API error: [400 Bad Request]
```

**Solutions:**
1. Validate job manifest structure
2. Ensure container image is accessible
3. Check resource quotas in the namespace
4. Verify image pull secrets if using private registries

## Production Deployment

### Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t eks-api:latest .
docker run -e EKS_CLUSTER_NAME=my-cluster -e EKS_REGION=us-east-1 -p 8000:8000 eks-api:latest
```

### Kubernetes Deployment

Deploy as a Kubernetes Deployment/Pod in the cluster:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: eks-api

---
apiVersion: v1
kind: Role
metadata:
  name: eks-api
rules:
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["create", "delete", "get", "list"]
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["create", "delete", "get", "list"]

---
apiVersion: v1
kind: RoleBinding
metadata:
  name: eks-api
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: eks-api
subjects:
- kind: ServiceAccount
  name: eks-api

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: eks-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: eks-api
  template:
    metadata:
      labels:
        app: eks-api
    spec:
      serviceAccountName: eks-api
      containers:
      - name: eks-api
        image: eks-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: EKS_CLUSTER_NAME
          value: "my-cluster"
        - name: EKS_REGION
          value: "us-east-1"
```

## License

MIT License

## Support

For issues or questions, please open an issue in the repository or contact the team.