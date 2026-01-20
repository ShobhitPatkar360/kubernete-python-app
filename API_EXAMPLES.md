# API Usage Examples

## Prerequisites

```bash
# Application running
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Set variables for examples
export API_URL="http://localhost:8000"
export CLUSTER="my-cluster"
export REGION="us-east-1"
```

## cURL Examples

### 1. Health Check

```bash
curl -X GET $API_URL/health
```

Response:
```json
{
  "status": "healthy",
  "cluster": "my-cluster",
  "region": "us-east-1"
}
```

### 2. Create a Job

**Simple Job (Echo)**

```bash
curl -X POST $API_URL/api/eks-create-job \
  -H "Content-Type: application/json" \
  -d '{
    "job_manifest": {
      "spec": {
        "template": {
          "spec": {
            "containers": [
              {
                "name": "echo-job",
                "image": "busybox:latest",
                "command": ["echo"],
                "args": ["Hello from EKS!"]
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

**Python Script Job**

```bash
curl -X POST $API_URL/api/eks-create-job \
  -H "Content-Type: application/json" \
  -d '{
    "job_manifest": {
      "spec": {
        "template": {
          "spec": {
            "containers": [
              {
                "name": "python-job",
                "image": "python:3.11-slim",
                "command": ["python", "-c"],
                "args": ["import time; print(\"Starting...\"); time.sleep(10); print(\"Done\")"]
              }
            ],
            "restartPolicy": "Never"
          }
        },
        "backoffLimit": 3,
        "ttlSecondsAfterFinished": 300
      }
    },
    "namespace": "default"
  }'
```

**Job with Multiple Containers**

```bash
curl -X POST $API_URL/api/eks-create-job \
  -H "Content-Type: application/json" \
  -d '{
    "job_manifest": {
      "spec": {
        "parallelism": 2,
        "completions": 4,
        "template": {
          "spec": {
            "containers": [
              {
                "name": "worker",
                "image": "python:3.11",
                "command": ["python", "-c"],
                "args": ["import os; print(f\"Hostname: {os.environ.get(\"HOSTNAME\")}\")"]
              }
            ],
            "restartPolicy": "Never"
          }
        },
        "backoffLimit": 2
      }
    },
    "namespace": "default"
  }'
```

**Job with Environment Variables**

```bash
curl -X POST $API_URL/api/eks-create-job \
  -H "Content-Type: application/json" \
  -d '{
    "job_manifest": {
      "spec": {
        "template": {
          "spec": {
            "containers": [
              {
                "name": "env-job",
                "image": "busybox",
                "command": ["sh", "-c"],
                "args": ["echo \"API_KEY=$API_KEY, ENV=$ENVIRONMENT\""],
                "env": [
                  {
                    "name": "API_KEY",
                    "value": "secret-key-123"
                  },
                  {
                    "name": "ENVIRONMENT",
                    "value": "production"
                  }
                ]
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

**Job with Resource Limits**

```bash
curl -X POST $API_URL/api/eks-create-job \
  -H "Content-Type: application/json" \
  -d '{
    "job_manifest": {
      "spec": {
        "template": {
          "spec": {
            "containers": [
              {
                "name": "resource-limited",
                "image": "python:3.11",
                "command": ["python", "-c"],
                "args": ["import sys; print(\"Processing...\"); sys.exit(0)"],
                "resources": {
                  "requests": {
                    "memory": "256Mi",
                    "cpu": "250m"
                  },
                  "limits": {
                    "memory": "512Mi",
                    "cpu": "500m"
                  }
                }
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

### 3. Get Job Status

```bash
# Get status of a job
curl -X GET "$API_URL/api/eks-get-job-status?job_name=my-job&namespace=default"
```

Response (Running):
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

Response (Completed):
```json
{
  "job_name": "my-job",
  "namespace": "default",
  "state": "completed",
  "active": 0,
  "succeeded": 1,
  "failed": 0,
  "start_time": "2026-01-20T10:30:00+00:00",
  "completion_time": "2026-01-20T10:30:15+00:00"
}
```

Response (Failed):
```json
{
  "job_name": "my-job",
  "namespace": "default",
  "state": "failed",
  "active": 0,
  "succeeded": 0,
  "failed": 1,
  "start_time": "2026-01-20T10:30:00+00:00",
  "completion_time": "2026-01-20T10:30:20+00:00"
}
```

### 4. Delete a Job

```bash
curl -X DELETE "$API_URL/api/eks-delete-job?job_name=my-job&namespace=default"
```

Response:
```json
{
  "message": "Job my-job deleted successfully",
  "status": "success"
}
```

### 5. Create a Namespace

```bash
curl -X POST $API_URL/api/eks-create-namespace \
  -H "Content-Type: application/json" \
  -d '{
    "namespace_name": "my-namespace"
  }'
```

Response:
```json
{
  "namespace_name": "my-namespace",
  "creation_timestamp": "2026-01-20T10:35:00+00:00",
  "status": "created"
}
```

### 6. Delete a Namespace

```bash
curl -X DELETE "$API_URL/api/eks-delete-namespace?namespace_name=my-namespace"
```

Response:
```json
{
  "message": "Namespace my-namespace deleted successfully",
  "status": "success"
}
```

## Python Client Examples

### Using requests library

```python
import requests
import json

API_URL = "http://localhost:8000"

# Health check
response = requests.get(f"{API_URL}/health")
print(response.json())

# Create job
job_manifest = {
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
}

response = requests.post(
    f"{API_URL}/api/eks-create-job",
    json={
        "job_manifest": job_manifest,
        "namespace": "default"
    }
)
print(response.json())

# Get job status
job_name = response.json()["job_name"]
response = requests.get(
    f"{API_URL}/api/eks-get-job-status",
    params={
        "job_name": job_name,
        "namespace": "default"
    }
)
print(response.json())

# Delete job
response = requests.delete(
    f"{API_URL}/api/eks-delete-job",
    params={
        "job_name": job_name,
        "namespace": "default"
    }
)
print(response.json())
```

### Using httpx async client

```python
import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # Health check
        response = await client.get("http://localhost:8000/health")
        print(response.json())
        
        # Create job
        job_manifest = {
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
        }
        
        response = await client.post(
            "http://localhost:8000/api/eks-create-job",
            json={
                "job_manifest": job_manifest,
                "namespace": "default"
            }
        )
        print(response.json())

asyncio.run(main())
```

## Postman Collection

Import this JSON into Postman:

```json
{
  "info": {
    "name": "EKS API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Health Check",
      "request": {
        "method": "GET",
        "url": {
          "raw": "{{base_url}}/health",
          "host": ["{{base_url}}"],
          "path": ["health"]
        }
      }
    },
    {
      "name": "Create Job",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\"job_manifest\": {\"spec\": {\"template\": {\"spec\": {\"containers\": [{\"name\": \"test\", \"image\": \"busybox\", \"command\": [\"echo\", \"hello\"]}], \"restartPolicy\": \"Never\"}}}}, \"namespace\": \"default\"}"
        },
        "url": {
          "raw": "{{base_url}}/api/eks-create-job",
          "host": ["{{base_url}}"],
          "path": ["api", "eks-create-job"]
        }
      }
    },
    {
      "name": "Get Job Status",
      "request": {
        "method": "GET",
        "url": {
          "raw": "{{base_url}}/api/eks-get-job-status?job_name=test-job&namespace=default",
          "host": ["{{base_url}}"],
          "path": ["api", "eks-get-job-status"],
          "query": [
            {
              "key": "job_name",
              "value": "test-job"
            },
            {
              "key": "namespace",
              "value": "default"
            }
          ]
        }
      }
    },
    {
      "name": "Delete Job",
      "request": {
        "method": "DELETE",
        "url": {
          "raw": "{{base_url}}/api/eks-delete-job?job_name=test-job&namespace=default",
          "host": ["{{base_url}}"],
          "path": ["api", "eks-delete-job"],
          "query": [
            {
              "key": "job_name",
              "value": "test-job"
            },
            {
              "key": "namespace",
              "value": "default"
            }
          ]
        }
      }
    },
    {
      "name": "Create Namespace",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\"namespace_name\": \"test-ns\"}"
        },
        "url": {
          "raw": "{{base_url}}/api/eks-create-namespace",
          "host": ["{{base_url}}"],
          "path": ["api", "eks-create-namespace"]
        }
      }
    },
    {
      "name": "Delete Namespace",
      "request": {
        "method": "DELETE",
        "url": {
          "raw": "{{base_url}}/api/eks-delete-namespace?namespace_name=test-ns",
          "host": ["{{base_url}}"],
          "path": ["api", "eks-delete-namespace"],
          "query": [
            {
              "key": "namespace_name",
              "value": "test-ns"
            }
          ]
        }
      }
    }
  ],
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8000"
    }
  ]
}
```

## Shell Script Examples

### Complete Job Workflow

```bash
#!/bin/bash

API_URL="http://localhost:8000"

echo "1. Creating namespace..."
NS_RESPONSE=$(curl -s -X POST $API_URL/api/eks-create-namespace \
  -H "Content-Type: application/json" \
  -d '{"namespace_name": "workflow-test"}')
echo $NS_RESPONSE | jq .

echo -e "\n2. Creating job..."
JOB_RESPONSE=$(curl -s -X POST $API_URL/api/eks-create-job \
  -H "Content-Type: application/json" \
  -d '{
    "job_manifest": {
      "spec": {
        "template": {
          "spec": {
            "containers": [
              {
                "name": "worker",
                "image": "busybox",
                "command": ["sh", "-c"],
                "args": ["for i in 1 2 3; do echo \"Step $i\"; sleep 1; done"]
              }
            ],
            "restartPolicy": "Never"
          }
        },
        "backoffLimit": 2
      }
    },
    "namespace": "workflow-test"
  }')
echo $JOB_RESPONSE | jq .

JOB_NAME=$(echo $JOB_RESPONSE | jq -r '.job_name')

echo -e "\n3. Monitoring job status..."
for i in {1..30}; do
  STATUS=$(curl -s -X GET "$API_URL/api/eks-get-job-status?job_name=$JOB_NAME&namespace=workflow-test" | jq -r '.state')
  echo "[$i] Status: $STATUS"
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  sleep 2
done

echo -e "\n4. Final job status:"
curl -s -X GET "$API_URL/api/eks-get-job-status?job_name=$JOB_NAME&namespace=workflow-test" | jq .

echo -e "\n5. Cleaning up..."
curl -s -X DELETE "$API_URL/api/eks-delete-job?job_name=$JOB_NAME&namespace=workflow-test" | jq .
curl -s -X DELETE "$API_URL/api/eks-delete-namespace?namespace_name=workflow-test" | jq .

echo -e "\nWorkflow complete!"
```

## Error Responses

### 400 Bad Request

Invalid request format:
```json
{
  "detail": [
    {
      "loc": ["body", "job_manifest"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 404 Not Found

Resource doesn't exist:
```json
{
  "detail": "Job my-job not found in namespace default"
}
```

### 500 Internal Server Error

Server error:
```json
{
  "detail": "Internal server error: [error message]"
}
```

## Performance Testing

### Load Test with Apache Bench

```bash
# Test health endpoint
ab -n 1000 -c 10 http://localhost:8000/health

# Test with custom headers
ab -n 100 -c 5 -H "Content-Type: application/json" \
  -p job.json http://localhost:8000/api/eks-create-job
```

### Load Test with wrk

```bash
# Install: npm install -g wrk

# Simple load test
wrk -t 4 -c 100 -d 30s http://localhost:8000/health

# With script
wrk -t 4 -c 100 -d 30s -s script.lua http://localhost:8000
```

---

For more information, see:
- [README.md](README.md) - Project documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Deployment instructions
