# Quick Reference Card

## File Structure

```
kubernete-python-app/
├── .env.example                 # Environment template
├── .gitignore                   # Git ignore rules
├── README.md                    # Main documentation
├── PROJECT_SUMMARY.md           # Project overview
├── DEPLOYMENT_GUIDE.md          # Deployment instructions
├── ARCHITECTURE.md              # System design
├── TESTING.md                   # Testing guide
├── API_EXAMPLES.md              # API usage examples
│
└── app/
    ├── main.py                  # FastAPI app
    ├── requirements.txt         # Dependencies
    ├── __init__.py
    │
    ├── api/
    │   ├── __init__.py
    │   └── routes.py           # 5 API endpoints
    │
    ├── services/
    │   ├── __init__.py
    │   └── eks_operations.py    # 5 service methods
    │
    ├── core/
    │   ├── __init__.py
    │   └── config.py           # Configuration
    │
    └── utils/
        ├── __init__.py
        └── logger.py           # Structured logging
```

## Dependencies

```
fastapi==0.104.1
uvicorn[standard]==0.24.0
kubernetes==28.1.0
boto3==1.34.7
eks-token==0.0.3
pydantic==2.5.0
pydantic-settings==2.1.0
python-dotenv==1.0.0
```

## Setup Commands

```bash
# Clone and navigate
git clone <repo>
cd kubernete-python-app

# Create virtual environment
python -m venv venv
source venv/bin/activate          # macOS/Linux
# or
venv\Scripts\activate             # Windows

# Install dependencies
pip install -r app/requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your cluster details

# Run application
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable | Required | Example |
|----------|----------|---------|
| EKS_CLUSTER_NAME | ✓ | my-cluster |
| EKS_REGION | ✓ | us-east-1 |
| LOG_LEVEL | - | INFO |

## API Endpoints

### Jobs

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/eks-create-job` | Create job |
| GET | `/api/eks-get-job-status` | Get status |
| DELETE | `/api/eks-delete-job` | Delete job |

**Parameters:**
- `job_name` (query/body)
- `namespace` (query/body, default="default")
- `job_manifest` (body, dict)

### Namespaces

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/eks-create-namespace` | Create namespace |
| DELETE | `/api/eks-delete-namespace` | Delete namespace |

**Parameters:**
- `namespace_name` (body/query)

### Other

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI |

## Quick Start

```bash
# 1. Setup (5 min)
git clone <repo> && cd kubernete-python-app
python -m venv venv && source venv/bin/activate
pip install -r app/requirements.txt
cp .env.example .env
# Edit .env with cluster details

# 2. Run (2 min)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. Test (1 min)
curl http://localhost:8000/health
open http://localhost:8000/docs
```

## cURL Cheat Sheet

```bash
# Health check
curl http://localhost:8000/health

# Create job
curl -X POST http://localhost:8000/api/eks-create-job \
  -H "Content-Type: application/json" \
  -d '{"job_manifest":{"spec":{...}},"namespace":"default"}'

# Get status
curl "http://localhost:8000/api/eks-get-job-status?job_name=NAME&namespace=NS"

# Delete job
curl -X DELETE "http://localhost:8000/api/eks-delete-job?job_name=NAME&namespace=NS"

# Create namespace
curl -X POST http://localhost:8000/api/eks-create-namespace \
  -H "Content-Type: application/json" \
  -d '{"namespace_name":"my-ns"}'

# Delete namespace
curl -X DELETE "http://localhost:8000/api/eks-delete-namespace?namespace_name=my-ns"
```

## Key Features

- ✅ **IAM Authentication** (no kubeconfig files)
- ✅ **Kubernetes Job Management** (create, delete, monitor)
- ✅ **Namespace Management** (create, delete)
- ✅ **Auto-generated API Docs** (Swagger UI)
- ✅ **Structured Logging** (configurable levels)
- ✅ **Error Handling** (proper HTTP status codes)
- ✅ **Pydantic Validation** (type-safe requests)
- ✅ **Health Checks** (/health endpoint)
- ✅ **Production Ready** (scalable, secure)

## Authentication Flow

```
1. AWS Credentials (EC2 role / env vars / config)
   ↓
2. Boto3 describe_cluster() → endpoint + CA cert
   ↓
3. eks-token generate_token() → IAM bearer token
   ↓
4. kubernetes.client.Configuration setup
   ↓
5. Kubernetes API calls (with bearer token)
```

## Deployment Options

### EC2 (Recommended)
```bash
# Install Python, pip
# Attach IAM role
git clone <repo>
pip install -r app/requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Docker
```bash
docker build -t eks-api:latest .
docker run -e EKS_CLUSTER_NAME=cluster -e EKS_REGION=us-east-1 \
  -p 8000:8000 eks-api:latest
```

### Kubernetes
```bash
kubectl apply -f deployment.yaml
kubectl get svc eks-api
```

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| `EKS_CLUSTER_NAME not set` | Set in .env or export |
| `Failed to fetch cluster info` | Check IAM permissions |
| `401 Unauthorized` | Verify AWS credentials |
| `404 Job not found` | Check job name and namespace |
| `Network timeout` | Check security group rules |

## Testing

```bash
# Unit tests
pip install pytest pytest-asyncio
pytest tests/

# With coverage
pip install pytest-cov
pytest tests/ --cov=app

# Interactive testing
open http://localhost:8000/docs
```

## Logging Levels

```
DEBUG     - Detailed diagnostic info
INFO      - General information (default)
WARNING   - Warning messages
ERROR     - Error conditions
CRITICAL  - Critical errors
```

Set via `LOG_LEVEL` environment variable.

## Code Structure

| File | Purpose | Lines |
|------|---------|-------|
| main.py | FastAPI setup | ~100 |
| routes.py | API endpoints | ~400 |
| eks_operations.py | Kubernetes ops | ~500 |
| config.py | Settings | ~60 |
| logger.py | Logging | ~45 |

**Total: ~1100 lines of code + ~1500 lines of docs**

## Documentation Map

| Document | Purpose | Size |
|----------|---------|------|
| README.md | Main docs | 500+ lines |
| PROJECT_SUMMARY.md | Overview | 300+ lines |
| DEPLOYMENT_GUIDE.md | Deploy | 400+ lines |
| ARCHITECTURE.md | Design | 300+ lines |
| TESTING.md | Tests | 300+ lines |
| API_EXAMPLES.md | Examples | 400+ lines |

## Important Notes

1. **No kubeconfig files** - IAM authentication only
2. **Short-lived tokens** - 15 minute expiration
3. **Stateless design** - Horizontally scalable
4. **No hardcoded credentials** - All from secure sources
5. **Full error handling** - Proper HTTP status codes
6. **Structured logging** - Easy debugging and monitoring

## Next Steps

1. **Review**: Read [README.md](README.md)
2. **Deploy**: Follow [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
3. **Understand**: Check [ARCHITECTURE.md](ARCHITECTURE.md)
4. **Test**: See [TESTING.md](TESTING.md)
5. **Use**: Check [API_EXAMPLES.md](API_EXAMPLES.md)

## Production Checklist

- [ ] Set `EKS_CLUSTER_NAME` and `EKS_REGION`
- [ ] Verify IAM role has `eks:DescribeCluster` permission
- [ ] Test health endpoint: `/health`
- [ ] Configure logging level: `LOG_LEVEL=INFO`
- [ ] Test job creation with sample manifest
- [ ] Monitor application logs
- [ ] Set up health checks (load balancer)
- [ ] Configure auto-scaling if needed
- [ ] Enable TLS/HTTPS (reverse proxy/ALB)
- [ ] Set up monitoring and alerting

## Support

- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Logs**: Console output (stdout)
- **Issues**: Check [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) troubleshooting

## License

MIT License

---

**Version**: 1.0.0
**Status**: Production Ready
**Date**: January 20, 2026
