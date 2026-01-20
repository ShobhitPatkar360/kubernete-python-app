# EKS Kubernetes Operations API - Deployment Guide

## Quick Start

### 1. Prerequisites

- EC2 instance running (preferred) or local machine with AWS credentials
- Python 3.9 or higher
- pip package manager
- Access to an AWS EKS cluster
- IAM permissions: `eks:DescribeCluster`, `sts:GetCallerIdentity`

### 2. Local Development Setup

```bash
# Clone or navigate to the project directory
cd kubernete-python-app

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r app/requirements.txt
```

### 3. Configure Environment

Create `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your EKS cluster information:

```
EKS_CLUSTER_NAME=your-eks-cluster-name
EKS_REGION=us-east-1
LOG_LEVEL=INFO
```

**Important:** 
- AWS credentials are automatically resolved from EC2 IAM role (if running on EC2)
- Or set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` environment variables
- Or configure `~/.aws/credentials` file

### 4. Run the Application

```bash
# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be accessible at:
- API: `http://localhost:8000`
- Interactive Docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Deployment Scenarios

### Scenario 1: EC2 Instance (Recommended)

**Step 1: Prepare EC2 Instance**

1. Launch EC2 instance (Amazon Linux 2 or Ubuntu)
2. Attach IAM role with EKS permissions

**Step 2: Install Python**

```bash
# Amazon Linux 2
sudo yum update -y
sudo yum install python3 python3-pip -y

# Ubuntu
sudo apt update
sudo apt install python3 python3-pip -y
```

**Step 3: Deploy Application**

```bash
# Clone repository
git clone <repo-url> /opt/eks-api
cd /opt/eks-api

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r app/requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your cluster details
nano .env
```

**Step 4: Run with Systemd (Recommended)**

Create `/etc/systemd/system/eks-api.service`:

```ini
[Unit]
Description=EKS Kubernetes Operations API
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/opt/eks-api
Environment="PATH=/opt/eks-api/venv/bin"
ExecStart=/opt/eks-api/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable eks-api
sudo systemctl start eks-api

# Check status
sudo systemctl status eks-api

# View logs
sudo journalctl -u eks-api -f
```

### Scenario 2: Docker Container

**Step 1: Build Docker Image**

Create `Dockerfile` in project root:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
# Build image
docker build -t eks-api:latest .

# Run container
docker run -d \
  --name eks-api \
  -p 8000:8000 \
  -e EKS_CLUSTER_NAME=your-cluster \
  -e EKS_REGION=us-east-1 \
  eks-api:latest

# View logs
docker logs -f eks-api
```

### Scenario 3: Kubernetes Deployment (EKS Cluster Itself)

Deploy the API as a pod inside the EKS cluster:

```yaml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: eks-api
  namespace: default

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: eks-api
rules:
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["create", "delete", "get", "list", "watch"]
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["create", "delete", "get", "list"]
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: eks-api
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: eks-api
subjects:
- kind: ServiceAccount
  name: eks-api
  namespace: default

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: eks-api
  namespace: default
  labels:
    app: eks-api
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
        imagePullPolicy: Always
        ports:
        - name: http
          containerPort: 8000
          protocol: TCP
        env:
        - name: EKS_CLUSTER_NAME
          valueFrom:
            configMapKeyRef:
              name: eks-api-config
              key: cluster-name
        - name: EKS_REGION
          valueFrom:
            configMapKeyRef:
              name: eks-api-config
              key: region
        - name: LOG_LEVEL
          value: "INFO"
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: eks-api-config
  namespace: default
data:
  cluster-name: "your-cluster-name"
  region: "us-east-1"

---
apiVersion: v1
kind: Service
metadata:
  name: eks-api
  namespace: default
  labels:
    app: eks-api
spec:
  type: LoadBalancer
  ports:
  - name: http
    port: 80
    targetPort: 8000
    protocol: TCP
  selector:
    app: eks-api
```

Deploy:

```bash
kubectl apply -f deployment.yaml

# Check deployment
kubectl get deployment eks-api
kubectl get pods -l app=eks-api
kubectl get svc eks-api

# View logs
kubectl logs -l app=eks-api -f
```

## Verifying Deployment

### Health Check

```bash
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","cluster":"your-cluster-name","region":"us-east-1"}
```

### Create a Job

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
    "namespace": "default"
  }'
```

### Get Job Status

```bash
curl http://localhost:8000/api/eks-get-job-status?job_name=job-name&namespace=default
```

### Interactive API Testing

Open browser and navigate to: `http://localhost:8000/docs`

This opens Swagger UI where you can test all endpoints interactively.

## Troubleshooting

### Issue: "EKS_CLUSTER_NAME environment variable is required"

**Solution:** Ensure `.env` file is created and loaded with correct values

```bash
cat .env
export $(cat .env | xargs)
echo $EKS_CLUSTER_NAME
```

### Issue: "Failed to fetch cluster info"

**Solutions:**
1. Verify cluster name and region are correct
2. Check IAM permissions: `aws eks describe-cluster --name your-cluster --region us-east-1`
3. Ensure network connectivity from EC2 to EKS API endpoint
4. Check security group rules allow HTTPS (port 443)

### Issue: "Kubernetes API error: [401 Unauthorized]"

**Solutions:**
1. Verify EC2 IAM role has EKS permissions
2. Check AWS credentials if using environment variables
3. Ensure `sts:GetCallerIdentity` permission is granted

### Issue: "Job creation fails with manifest error"

**Solutions:**
1. Validate job manifest structure against Kubernetes Job API
2. Ensure container image is accessible
3. Check namespace exists or auto-creation is enabled
4. Verify image pull secrets if using private registries

## Security Best Practices

1. **IAM Roles**: Always use EC2 IAM roles instead of hardcoded credentials
2. **Network**: Restrict security group access to the API
3. **CORS**: Configure CORS headers based on your requirements
4. **RBAC**: Apply Kubernetes RBAC policies to limit job creation
5. **Logging**: Enable CloudWatch logs for audit trail
6. **TLS/HTTPS**: Deploy behind ALB/NLB with TLS termination in production
7. **Rate Limiting**: Consider adding rate limiting middleware for production

## Monitoring

### CloudWatch Metrics (If running on EC2 with CloudWatch agent)

1. CPU usage
2. Memory usage
3. Network I/O
4. Custom metrics from logs

### Application Logs

Logs are output to console with structured format:

```
2026-01-20 10:30:00 - app.services.eks_operations - INFO - Creating job my-job in namespace default
```

### API Metrics

Consider adding monitoring for:
- Request count
- Response time
- Error rate
- Queue depth

## Performance Tuning

### Increase Worker Processes (Production)

```bash
gunicorn app.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --workers-class uvicorn.workers.UvicornWorker \
  --max-requests 1000 \
  --max-requests-jitter 100
```

### Add Caching

Implement caching for frequently accessed resources (job status, cluster info) to reduce API calls.

### Connection Pooling

The application uses Kubernetes client's default connection pooling which is sufficient for most workloads.

## Scaling

### Horizontal Scaling

Deploy multiple instances behind a load balancer:

```
User --> Load Balancer
           |
           +-- API Instance 1
           +-- API Instance 2
           +-- API Instance 3
```

Each instance maintains its own Kubernetes client connection and token.

### Load Balancing

Use AWS Application Load Balancer (ALB) or Network Load Balancer (NLB):

```bash
# Example: Direct health checks to /health endpoint
# Set target group health check to: /health
# Expected status code: 200
```

## Backup & Recovery

### Configuration Backup

```bash
# Backup environment variables
cp .env .env.backup

# Store in secure location (e.g., AWS Secrets Manager)
aws secretsmanager create-secret --name eks-api-config --secret-string file://.env.backup
```

### Recovery

```bash
# Restore from backup
aws secretsmanager get-secret-value --secret-id eks-api-config --query SecretString --output text > .env
```

## Cleanup

### Stop EC2 Service

```bash
sudo systemctl stop eks-api
sudo systemctl disable eks-api
```

### Stop Docker Container

```bash
docker stop eks-api
docker rm eks-api
docker rmi eks-api:latest
```

### Delete Kubernetes Deployment

```bash
kubectl delete -f deployment.yaml
```

## Support & Documentation

- **API Docs**: http://localhost:8000/docs
- **GitHub**: [Repository URL]
- **Issues**: [Report issues here]

## License

MIT License - See LICENSE file for details
