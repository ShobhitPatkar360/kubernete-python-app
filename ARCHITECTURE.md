# Architecture & Design

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│                      (app/main.py)                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────┐
│  API Routes      │ │ Kubernetes Ops   │ │  Configuration
│  (routes.py)     │ │ (eks_operations) │ │  (config.py)
│                  │ │                  │ │
│ - Create Job     │ │ - create_job()   │ │ - EKS_CLUSTER_NAME
│ - Delete Job     │ │ - delete_job()   │ │ - EKS_REGION
│ - Job Status     │ │ - get_job_status │ │ - LOG_LEVEL
│ - Create NS      │ │ - create_ns()    │ │ - AWS credentials
│ - Delete NS      │ │ - delete_ns()    │ │
└──────────────────┘ └──────────────────┘ └──────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
   │ AWS boto3   │   │ Kubernetes   │   │   Logging    │
   │    EKS      │   │   Client     │   │  (logger.py) │
   │  DescribeCluster│ BatchV1Api    │   │              │
   └──────┬──────┘   │ CoreV1Api     │   └──────────────┘
          │          └──────┬───────┘
          │                 │
          └─────────┬───────┘
                    │
        ┌───────────▼───────────┐
        │  IAM Token Generation │
        │   (eks-token lib)     │
        │                       │
        │  AWS STS GetCallerID  │
        └───────────┬───────────┘
                    │
        ┌───────────▼───────────┐
        │  AWS EKS Cluster      │
        │ - Kubernetes API      │
        │ - Batch API           │
        │ - Core API            │
        └───────────────────────┘
```

## Authentication Flow

```
1. Application Startup
   └─> EKSOperationsService._configure_clients()
       └─> Fetch AWS credentials from:
           - EC2 IAM role (preferred)
           - Environment variables
           - AWS CLI config

2. Cluster Discovery
   └─> boto3.client('eks')
       └─> describe_cluster()
           └─> Returns:
               - API endpoint
               - Base64-encoded CA certificate

3. Token Generation
   └─> eks_token.get_token()
       └─> AWS STS GetCallerIdentity
           └─> Generate 15-minute bearer token

4. Kubernetes Client Configuration
   └─> kubernetes.client.Configuration()
       └─> Set:
           - host: cluster endpoint
           - ssl_ca_cert: decoded CA
           - authorization: Bearer token

5. API Calls
   └─> BatchV1Api / CoreV1Api
       └─> All requests include bearer token
```

## Request/Response Flow

### Create Job Request

```
Client
  │
  └─> POST /api/eks-create-job
      │
      ├─> routes.create_job()
      │   ├─> Validate request (JobManifestRequest)
      │   ├─> Get EKS service instance
      │   └─> Call service.create_job()
      │       │
      │       ├─> Check namespace exists
      │       ├─> Build job manifest with labels
      │       └─> BatchV1Api.create_namespaced_job()
      │           │
      │           └─> Kubernetes cluster
      │
      └─> Response: JobCreateResponse
          ├─ job_name
          ├─ namespace
          ├─ creation_timestamp
          └─ status
```

## Key Design Decisions

### 1. **No Kubeconfig Files**
- Mandatory requirement per specification
- Eliminates file I/O and security risks
- Uses IAM-based authentication instead
- Dynamic token generation ensures security

### 2. **Service Layer Architecture**
- Separation of concerns
- API routes → Service layer → Kubernetes API
- Easy to test and maintain
- Reusable service methods

### 3. **Pydantic Models for Validation**
- Automatic request validation
- Type hints for IDE support
- Clear API documentation
- Auto-generated Swagger UI

### 4. **Structured Logging**
- Console output with timestamps
- Configurable log levels
- Trace all API operations
- Easy debugging and monitoring

### 5. **Error Handling Strategy**
- All ApiExceptions caught and logged
- Proper HTTP status codes returned
- User-friendly error messages
- No sensitive information in responses

### 6. **Lazy Service Initialization**
- Service instance created on first use
- Token generation delayed until needed
- Reduces startup time
- Handles configuration errors early

## Security Considerations

### Credentials Management
- No hardcoded credentials
- AWS credentials resolved at runtime
- EC2 IAM role is primary method
- Environment variables as fallback
- AWS CLI config as last resort

### Token Security
- Short-lived tokens (15 minutes)
- Generated fresh on each connection
- No token caching
- Unique token per service instance

### SSL/TLS
- CA certificate verification enabled
- Temporary CA file for SSL verification
- HTTPS for all Kubernetes API calls
- No self-signed certificate bypass

### RBAC
- API doesn't grant Kubernetes RBAC
- Relies on Kubernetes RBAC for fine-grained control
- Service account must have explicit permissions
- Principle of least privilege

## Scalability Considerations

### Stateless Design
- No shared state between instances
- Each instance independent
- Load balancer friendly
- Horizontal scaling possible

### Connection Management
- Kubernetes client connection pooling
- Reuses HTTP connections
- Efficient resource usage
- Handles concurrent requests

### Performance
- Async request handling (FastAPI)
- Non-blocking I/O
- Efficient JSON serialization
- Minimal memory footprint

## Monitoring & Observability

### Application Logs
- Structured logging with timestamps
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Configurable via LOG_LEVEL environment variable
- Easy log aggregation

### Health Checks
- `/health` endpoint always available
- Returns cluster status
- Used for load balancer health checks
- Verifies connectivity to AWS

### Metrics
- Request count (via FastAPI)
- Response time (via middleware)
- Error rates (via exception handling)
- Pod status (via Kubernetes API)

## Testing Strategy

### Unit Tests
- Test service methods in isolation
- Mock Kubernetes API
- Mock AWS boto3 client
- Focus on business logic

### Integration Tests
- Test with actual Kubernetes cluster
- Real AWS credentials
- Temporary namespace for testing
- Clean up resources after tests

### End-to-End Tests
- Full request/response flow
- Test API endpoints
- Verify error handling
- Check response schemas

## Code Organization

### app/main.py
- FastAPI application instance
- Lifespan management (startup/shutdown)
- CORS middleware configuration
- Health check endpoint

### app/api/routes.py
- API endpoint definitions
- Request/response models (Pydantic)
- HTTP error handling
- Route documentation

### app/services/eks_operations.py
- Kubernetes operations
- AWS EKS integration
- Kubernetes client configuration
- Business logic implementation

### app/core/config.py
- Environment configuration
- Settings validation
- Default values

### app/utils/logger.py
- Logging setup
- Structured logging
- Console output formatting

## Dependencies

### Production Dependencies
- **fastapi**: Web framework
- **uvicorn**: ASGI server
- **kubernetes**: Kubernetes Python client
- **boto3**: AWS SDK
- **eks-token**: IAM token generation
- **pydantic**: Data validation

### Development Dependencies
- **pytest**: Testing framework
- **pytest-asyncio**: Async test support
- **gunicorn**: Production WSGI server

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| EKS_CLUSTER_NAME | Yes | - | EKS cluster name |
| EKS_REGION | Yes | us-east-1 | AWS region |
| LOG_LEVEL | No | INFO | Logging level |
| AWS_ACCESS_KEY_ID | No | - | AWS access key |
| AWS_SECRET_ACCESS_KEY | No | - | AWS secret key |

### AWS Credentials Resolution

1. EC2 IAM role (preferred)
2. AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY environment variables
3. ~/.aws/credentials file
4. ~/.aws/config file

## Deployment Models

### EC2 Instance (Recommended)
- Single EC2 instance with IAM role
- Systemd service for process management
- Simple setup and debugging
- Cost-effective for small workloads

### Docker Container
- Container image for easy distribution
- Environment variable configuration
- CI/CD friendly
- Multi-environment deployments

### Kubernetes Deployment
- Deploy inside EKS cluster
- Service account with RBAC
- Load balancer service
- Auto-scaling capabilities
- Multi-replica for HA

## Future Enhancements

1. **Webhook Support**: Real-time job status updates
2. **Caching Layer**: Cache frequently accessed job status
3. **Rate Limiting**: Protect API from abuse
4. **Authentication**: API key or OAuth2
5. **Database**: Store job history
6. **Metrics**: Prometheus metrics endpoint
7. **Batch Operations**: Create multiple jobs in parallel
8. **Job Templates**: Pre-defined job templates
9. **Audit Logging**: Detailed audit trail
10. **Multi-Cluster**: Support multiple EKS clusters

## Troubleshooting Guide

### Common Issues

| Issue | Root Cause | Solution |
|-------|-----------|----------|
| 401 Unauthorized | Invalid IAM credentials | Verify EC2 IAM role or env vars |
| 404 Cluster not found | Wrong cluster name/region | Check EKS_CLUSTER_NAME and EKS_REGION |
| Network timeout | No internet connectivity | Check security group rules |
| Token generation failed | IAM permissions missing | Add sts:GetCallerIdentity permission |
| Job manifest invalid | Malformed manifest | Validate against Kubernetes Job schema |

---

For more details, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) and [README.md](README.md)
