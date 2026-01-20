# EKS Kubernetes Operations API - Request Flow Documentation

This document provides a complete step-by-step explanation of how each API request flows through the application, with example logs showing execution paths and common failure scenarios.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Application Startup Flow](#application-startup-flow)
3. [Authentication & Authorization](#authentication--authorization)
4. [Request Flow Diagram](#request-flow-diagram)
5. [API Endpoint Flows](#api-endpoint-flows)
   - [Create Job](#1-create-job---post-api-eks-create-job)
   - [Get Job Status](#2-get-job-status---get-api-eks-get-job-status)
   - [Delete Job](#3-delete-job---delete-api-eks-delete-job)
   - [Create Namespace](#4-create-namespace---post-api-eks-create-namespace)
   - [Delete Namespace](#5-delete-namespace---delete-api-eks-delete-namespace)
6. [Logging Format & Examples](#logging-format--examples)
7. [Error Handling & Failure Scenarios](#error-handling--failure-scenarios)
8. [Debugging Guide](#debugging-guide)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Client (HTTP Request)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│         FastAPI Application (main.py)                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Lifespan Context Manager                                 │  │
│  │ - Load .env file                                         │  │
│  │ - Validate configuration                                │  │
│  │ - Initialize EKS service                                │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│         API Routes (api/routes.py)                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1. Generate Request ID (UUID)                            │  │
│  │ 2. Log request entry with parameters                     │  │
│  │ 3. Call EKS service method                               │  │
│  │ 4. Log response (success/failure)                        │  │
│  │ 5. Return HTTP response                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│         EKS Operations Service (services/eks_operations.py)     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Kubernetes Client Initialization                         │  │
│  │ 1. Fetch cluster endpoint (boto3)                        │  │
│  │ 2. Fetch CA certificate (boto3)                          │  │
│  │ 3. Generate IAM bearer token (eks-token)                │  │
│  │ 4. Configure Kubernetes client                          │  │
│  │ 5. Create API client objects                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Operation Methods (create/delete/get)                    │  │
│  │ - Log operation entry with parameters                    │  │
│  │ - Call Kubernetes Python client API                      │  │
│  │ - Log operation completion with timing                   │  │
│  │ - Return structured response                             │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Kubernetes API Server (EKS Cluster)                            │
│  - AWS EKS Cluster endpoint                                     │
│  - IAM authentication via bearer token                          │
│  - Job and Namespace management                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Application Startup Flow

### Sequence:
1. **python interpreter** starts uvicorn server
2. **uvicorn** imports app.main:app (FastAPI application)
3. **FastAPI** registers routes and enters lifespan context manager
4. **Lifespan startup** begins:
   - Loads .env file (if exists)
   - Validates configuration (EKS_CLUSTER_NAME, EKS_REGION)
   - Logs startup information
5. **Application** is ready to accept requests
6. **First request** triggers lazy initialization of EKS service:
   - Fetches cluster information from AWS EKS
   - Generates IAM bearer token
   - Configures Kubernetes Python client

### Example Startup Logs:

```
2026-01-20 10:00:00.123 | INFO     | main                 | ================================================================================
2026-01-20 10:00:00.124 | INFO     | main                 | EKS Kubernetes Operations API - Startup
2026-01-20 10:00:00.125 | INFO     | main                 | ================================================================================
2026-01-20 10:00:00.126 | INFO     | main                 | Python version: 3.11.7
2026-01-20 10:00:00.127 | INFO     | main                 | Application version: 1.0.0
2026-01-20 10:00:00.128 | INFO     | main                 | Validating configuration...
2026-01-20 10:00:00.234 | INFO     | main                 | Configuration loaded successfully:
2026-01-20 10:00:00.235 | INFO     | main                 |   - EKS Cluster: my-cluster
2026-01-20 10:00:00.236 | INFO     | main                 |   - AWS Region: us-east-1
2026-01-20 10:00:00.237 | INFO     | main                 |   - Log Level: DEBUG
2026-01-20 10:00:00.238 | INFO     | main                 | Starting FastAPI application...
2026-01-20 10:00:00.239 | INFO     | main                 | Application startup completed successfully
2026-01-20 10:00:00.240 | INFO     | main                 | Ready to accept requests
2026-01-20 10:00:00.241 | INFO     | main                 | ================================================================================
```

---

## Authentication & Authorization

### IAM-Based Authentication Model

The application uses **EC2 IAM Role** for authentication, not kubeconfig files:

1. **EC2 Instance** has an IAM role attached with EKS permissions
2. **boto3 SDK** automatically discovers credentials from:
   - EC2 instance metadata service (primary)
   - Environment variables (fallback)
   - ~/.aws/credentials or ~/.aws/config (fallback)
3. **eks-token** package generates temporary bearer tokens using these credentials
4. **Kubernetes API** authenticates requests via IAM webhook

### Required IAM Permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "eks:DescribeCluster",
        "eks:ListClusters"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sts:AssumeRole"
      ],
      "Resource": "arn:aws:iam::*:role/*"
    }
  ]
}
```

### No kubeconfig Required:
- Cluster endpoint discovered via AWS EKS API
- CA certificate fetched from cluster metadata
- Bearer token generated on-demand (valid for ~15 minutes)

---

## Request Flow Diagram

```
Client Request
      │
      ▼
┌─────────────────────────────────┐
│ FastAPI Route Handler           │
│ (routes.py)                     │
│                                 │
│ 1. Generate Request ID (UUID)   │
│ 2. Log: "API request: ..."      │
│ 3. Get EKS Service Instance     │
│ 4. Call Service Method          │
│ 5. Log: "Successfully ..."      │
│ 6. Return Response              │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│ EKS Service Method              │
│ (eks_operations.py)             │
│                                 │
│ with log_operation():           │
│ - Log: START                    │
│ - Verify prerequisites          │
│ - Call Kubernetes API           │
│ - Log: END (with duration)      │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│ Kubernetes API Client           │
│ - create_namespaced_job()       │
│ - read_namespaced_job()         │
│ - delete_namespaced_job()       │
│ - create_namespace()            │
│ - delete_namespace()            │
└──────────────┬──────────────────┘
               │
               ▼
         HTTP Response
         (JSON)
```

---

## API Endpoint Flows

### 1. Create Job - POST /api/eks-create-job

**Purpose**: Create a Kubernetes Job in the EKS cluster

**Request Body**:
```json
{
  "job_manifest": {
    "spec": {
      "parallelism": 1,
      "template": {
        "spec": {
          "containers": [
            {
              "name": "job-container",
              "image": "my-image:latest",
              "command": ["python", "script.py"]
            }
          ],
          "restartPolicy": "Never"
        }
      }
    }
  },
  "namespace": "default"
}
```

**Complete Request Flow**:

```
1. CLIENT sends HTTP POST /api/eks-create-job with job_manifest
   │
   ▼
2. ROUTE HANDLER (create_job) receives request
   │ Generate request_id = "a1b2c3d4"
   │ Log: INFO "API request: create_job namespace=default"
   │
   ▼
3. GET EKS SERVICE (lazy initialization on first call)
   │ Service.__init__():
   │   a) Call _generate_token()
   │      - Log: DEBUG "Cluster name: my-cluster"
   │      - Call: get_token(cluster_name='my-cluster')
   │      - Log: INFO "Generating IAM bearer token"
   │      - Log: INFO "Successfully generated token length=2048"
   │   b) Call _configure_clients()
   │      - Step 1: Fetch cluster endpoint from AWS EKS API
   │      - Log: INFO "Step 1/5: Fetch cluster endpoint and CA certificate"
   │      - Log: DEBUG "Cluster endpoint: https://abc.eks.amazonaws.com"
   │      - Step 2: Generate IAM bearer token
   │      - Step 3: Decode CA certificate from base64
   │      - Step 4: Configure Kubernetes client with IAM auth
   │      - Step 5: Create BatchV1Api and CoreV1Api clients
   │      - Log: INFO "EKS operations service initialized successfully"
   │
   ▼
4. CALL SERVICE.CREATE_JOB (with context manager)
   │ with log_operation(logger, "create_job", job=job_name, namespace="default"):
   │   a) Log: START "create_job job=my-job namespace=default"
   │   b) Step 1: Verify namespace exists
   │      - Call: k8s_core_api.read_namespace("default")
   │      - Log: DEBUG "Namespace default found"
   │   c) Step 2: Build job manifest
   │      - Add labels and metadata
   │      - Log: DEBUG "Job manifest built with spec keys: ..."
   │   d) Step 3: Create job via Kubernetes API
   │      - Call: k8s_batch_api.create_namespaced_job()
   │      - Log: DEBUG "Sending create_namespaced_job request to Kubernetes API"
   │   e) Step 4: Format response
   │      - Log: END "create_job success=true duration_ms=234.5"
   │
   ▼
5. RETURN RESPONSE to client
   HTTP 200 OK:
   {
     "job_name": "my-job",
     "namespace": "default",
     "creation_timestamp": "2026-01-20T10:30:00.123456+00:00",
     "status": "created"
   }
```

**Complete Example Log Output**:

```
2026-01-20 10:30:00.100 | INFO     | routes                 | API request: create_job namespace=default [a1b2c3d4]
2026-01-20 10:30:00.101 | DEBUG    | routes                 | Generated job name: my-job [a1b2c3d4]
2026-01-20 10:30:00.102 | INFO     | eks_operations         | START create_job job=my-job namespace=default [a1b2c3d4]
2026-01-20 10:30:00.103 | DEBUG    | eks_operations         | Step 1: Verifying namespace default exists [a1b2c3d4]
2026-01-20 10:30:00.125 | DEBUG    | eks_operations         | Namespace default found [a1b2c3d4]
2026-01-20 10:30:00.126 | DEBUG    | eks_operations         | Step 2: Building job manifest for my-job [a1b2c3d4]
2026-01-20 10:30:00.127 | DEBUG    | eks_operations         | Job manifest built with spec keys: ['parallelism', 'template', 'backoffLimit'] [a1b2c3d4]
2026-01-20 10:30:00.128 | DEBUG    | eks_operations         | Step 3: Sending create_namespaced_job request to Kubernetes API [a1b2c3d4]
2026-01-20 10:30:00.234 | DEBUG    | eks_operations         | Kubernetes API returned response with metadata: my-job [a1b2c3d4]
2026-01-20 10:30:00.235 | DEBUG    | eks_operations         | Step 4: Formatting response [a1b2c3d4]
2026-01-20 10:30:00.236 | DEBUG    | eks_operations         | Job creation response ready: {...} [a1b2c3d4]
2026-01-20 10:30:00.237 | INFO     | eks_operations         | END create_job success=true duration_ms=135.2 [a1b2c3d4]
2026-01-20 10:30:00.238 | INFO     | routes                 | Successfully created job my-job in namespace default [a1b2c3d4]
```

---

### 2. Get Job Status - GET /api/eks-get-job-status

**Purpose**: Retrieve current status of a Kubernetes Job

**Query Parameters**:
- `job_name` (required): Name of the job
- `namespace` (optional, default="default"): Kubernetes namespace

**Request Example**:
```
GET /api/eks-get-job-status?job_name=my-job&namespace=default
```

**Response Example (Job Running)**:
```json
{
  "job_name": "my-job",
  "namespace": "default",
  "state": "running",
  "active": 1,
  "succeeded": 0,
  "failed": 0,
  "start_time": "2026-01-20T10:30:00.123456+00:00",
  "completion_time": null
}
```

**Response Example (Job Completed)**:
```json
{
  "job_name": "my-job",
  "namespace": "default",
  "state": "completed",
  "active": 0,
  "succeeded": 1,
  "failed": 0,
  "start_time": "2026-01-20T10:30:00.123456+00:00",
  "completion_time": "2026-01-20T10:35:00.123456+00:00"
}
```

**Complete Request Flow**:

```
1. CLIENT sends HTTP GET /api/eks-get-job-status?job_name=my-job&namespace=default
   │
   ▼
2. ROUTE HANDLER (get_job_status) receives request
   │ Generate request_id = "e5f6g7h8"
   │ Log: INFO "API request: get_job_status job=my-job namespace=default"
   │
   ▼
3. CALL SERVICE.GET_JOB_STATUS (with context manager)
   │ with log_operation(logger, "get_job_status", job="my-job", namespace="default"):
   │   a) Log: START "get_job_status job=my-job namespace=default"
   │   b) Step 1: Send read_namespaced_job request
   │      - Call: k8s_batch_api.read_namespaced_job("my-job", "default")
   │      - Log: DEBUG "Sending read_namespaced_job request to Kubernetes API"
   │   c) Step 2: Analyze job status
   │      - Check: succeeded count
   │      - Check: failed count
   │      - Check: active count
   │      - Determine state: "running" | "completed" | "failed" | "unknown"
   │      - Log: DEBUG "Job state determined: running (active=1)"
   │   d) Step 3: Extract status fields
   │      - Format timestamps to ISO format
   │      - Log: DEBUG "Status response formatted: state=running, ..."
   │   e) Log: END "get_job_status success=true duration_ms=45.3"
   │
   ▼
4. RETURN RESPONSE to client
   HTTP 200 OK with job status
```

**Example Logs**:

```
2026-01-20 10:35:30.100 | INFO     | routes                 | API request: get_job_status job=my-job namespace=default [e5f6g7h8]
2026-01-20 10:35:30.101 | INFO     | eks_operations         | START get_job_status job=my-job namespace=default [e5f6g7h8]
2026-01-20 10:35:30.102 | DEBUG    | eks_operations         | Step 1: Sending read_namespaced_job request to Kubernetes API [e5f6g7h8]
2026-01-20 10:35:30.125 | DEBUG    | eks_operations         | Kubernetes API returned job object with status field [e5f6g7h8]
2026-01-20 10:35:30.126 | DEBUG    | eks_operations         | Step 2: Analyzing job status to determine state [e5f6g7h8]
2026-01-20 10:35:30.127 | DEBUG    | eks_operations         | Job state determined: running (active=1) [e5f6g7h8]
2026-01-20 10:35:30.128 | DEBUG    | eks_operations         | Step 3: Extracting status fields [e5f6g7h8]
2026-01-20 10:35:30.129 | DEBUG    | eks_operations         | Status response formatted: state=running, active=1, succeeded=0, failed=0 [e5f6g7h8]
2026-01-20 10:35:30.130 | INFO     | eks_operations         | END get_job_status success=true duration_ms=29.8 [e5f6g7h8]
2026-01-20 10:35:30.131 | DEBUG    | routes                 | Job status: running (active=1, succeeded=0, failed=0) [e5f6g7h8]
2026-01-20 10:35:30.132 | INFO     | routes                 | Successfully retrieved status for job my-job [e5f6g7h8]
```

---

### 3. Delete Job - DELETE /api/eks-delete-job

**Purpose**: Delete a Kubernetes Job from the EKS cluster

**Query Parameters**:
- `job_name` (required): Name of the job to delete
- `namespace` (optional, default="default"): Kubernetes namespace

**Request Example**:
```
DELETE /api/eks-delete-job?job_name=my-job&namespace=default
```

**Response Example**:
```json
{
  "message": "Job my-job deleted successfully",
  "status": "success"
}
```

**Complete Request Flow**:

```
1. CLIENT sends HTTP DELETE /api/eks-delete-job?job_name=my-job&namespace=default
   │
   ▼
2. ROUTE HANDLER (delete_job) receives request
   │ Generate request_id = "i9j0k1l2"
   │ Log: INFO "API request: delete_job job=my-job namespace=default"
   │
   ▼
3. CALL SERVICE.DELETE_JOB (with context manager)
   │ with log_operation(logger, "delete_job", job="my-job", namespace="default"):
   │   a) Log: START "delete_job job=my-job namespace=default"
   │   b) Step 1: Send delete_namespaced_job request
   │      - Call: k8s_batch_api.delete_namespaced_job()
   │      - Use propagation_policy='Foreground' for graceful deletion
   │      - Waits for pods to complete before removing job
   │      - Log: DEBUG "Sending delete_namespaced_job request to Kubernetes API"
   │   c) Kubernetes API confirms deletion
   │      - Log: DEBUG "Kubernetes API confirmed job deletion"
   │   d) Log: END "delete_job success=true duration_ms=567.2"
   │
   ▼
4. RETURN RESPONSE to client
   HTTP 200 OK with success message
```

**Example Logs**:

```
2026-01-20 10:40:00.100 | INFO     | routes                 | API request: delete_job job=my-job namespace=default [i9j0k1l2]
2026-01-20 10:40:00.101 | INFO     | eks_operations         | START delete_job job=my-job namespace=default [i9j0k1l2]
2026-01-20 10:40:00.102 | DEBUG    | eks_operations         | Step 1: Sending delete_namespaced_job request to Kubernetes API [i9j0k1l2]
2026-01-20 10:40:00.567 | DEBUG    | eks_operations         | Kubernetes API confirmed job deletion [i9j0k1l2]
2026-01-20 10:40:00.568 | INFO     | eks_operations         | END delete_job success=true duration_ms=467.3 [i9j0k1l2]
2026-01-20 10:40:00.569 | INFO     | routes                 | Successfully deleted job my-job from namespace default [i9j0k1l2]
```

---

### 4. Create Namespace - POST /api/eks-create-namespace

**Purpose**: Create a Kubernetes Namespace in the EKS cluster

**Request Body**:
```json
{
  "namespace_name": "my-namespace"
}
```

**Response Example**:
```json
{
  "namespace_name": "my-namespace",
  "creation_timestamp": "2026-01-20T10:45:00.123456+00:00",
  "status": "created"
}
```

**Complete Request Flow**:

```
1. CLIENT sends HTTP POST /api/eks-create-namespace with namespace_name
   │
   ▼
2. ROUTE HANDLER (create_namespace) receives request
   │ Generate request_id = "m3n4o5p6"
   │ Log: INFO "API request: create_namespace namespace=my-namespace"
   │
   ▼
3. CALL SERVICE.CREATE_NAMESPACE (with context manager)
   │ with log_operation(logger, "create_namespace", namespace="my-namespace"):
   │   a) Log: START "create_namespace namespace=my-namespace"
   │   b) Step 1: Build namespace manifest
   │      - Create V1Namespace object
   │      - Set metadata.name
   │      - Log: DEBUG "Building namespace manifest for my-namespace"
   │   c) Step 2: Create namespace via Kubernetes API
   │      - Call: k8s_core_api.create_namespace()
   │      - Log: DEBUG "Sending create_namespace request to Kubernetes API"
   │   d) Step 3: Format response
   │      - Extract namespace name and creation timestamp
   │      - Log: DEBUG "Namespace creation response ready"
   │   e) Log: END "create_namespace success=true duration_ms=234.1"
   │
   ▼
4. RETURN RESPONSE to client
   HTTP 200 OK with namespace details
```

**Example Logs**:

```
2026-01-20 10:45:00.100 | INFO     | routes                 | API request: create_namespace namespace=my-namespace [m3n4o5p6]
2026-01-20 10:45:00.101 | INFO     | eks_operations         | START create_namespace namespace=my-namespace [m3n4o5p6]
2026-01-20 10:45:00.102 | DEBUG    | eks_operations         | Step 1: Building namespace manifest for my-namespace [m3n4o5p6]
2026-01-20 10:45:00.103 | DEBUG    | eks_operations         | Namespace manifest created with name=my-namespace [m3n4o5p6]
2026-01-20 10:45:00.104 | DEBUG    | eks_operations         | Step 2: Sending create_namespace request to Kubernetes API [m3n4o5p6]
2026-01-20 10:45:00.234 | DEBUG    | eks_operations         | Kubernetes API returned response with metadata: my-namespace [m3n4o5p6]
2026-01-20 10:45:00.235 | DEBUG    | eks_operations         | Step 3: Formatting response [m3n4o5p6]
2026-01-20 10:45:00.236 | DEBUG    | eks_operations         | Namespace creation response ready: {...} [m3n4o5p6]
2026-01-20 10:45:00.237 | INFO     | eks_operations         | END create_namespace success=true duration_ms=136.5 [m3n4o5p6]
2026-01-20 10:45:00.238 | INFO     | routes                 | Successfully created namespace my-namespace [m3n4o5p6]
```

---

### 5. Delete Namespace - DELETE /api/eks-delete-namespace

**Purpose**: Delete a Kubernetes Namespace from the EKS cluster

**Query Parameters**:
- `namespace_name` (required): Name of the namespace to delete

**Request Example**:
```
DELETE /api/eks-delete-namespace?namespace_name=my-namespace
```

**Response Example**:
```json
{
  "message": "Namespace my-namespace deleted successfully",
  "status": "success"
}
```

**Complete Request Flow**:

```
1. CLIENT sends HTTP DELETE /api/eks-delete-namespace?namespace_name=my-namespace
   │
   ▼
2. ROUTE HANDLER (delete_namespace) receives request
   │ Generate request_id = "q7r8s9t0"
   │ Log: INFO "API request: delete_namespace namespace=my-namespace"
   │
   ▼
3. CALL SERVICE.DELETE_NAMESPACE (with context manager)
   │ with log_operation(logger, "delete_namespace", namespace="my-namespace"):
   │   a) Log: START "delete_namespace namespace=my-namespace"
   │   b) Step 1: Send delete_namespace request
   │      - Call: k8s_core_api.delete_namespace()
   │      - Use propagation_policy='Foreground' for graceful deletion
   │      - Waits for all objects in namespace to be deleted first
   │      - Log: DEBUG "Sending delete_namespace request to Kubernetes API"
   │   c) Kubernetes API confirms deletion
   │      - Log: DEBUG "Kubernetes API confirmed namespace deletion"
   │   d) Log: END "delete_namespace success=true duration_ms=789.4"
   │
   ▼
4. RETURN RESPONSE to client
   HTTP 200 OK with success message
```

**Example Logs**:

```
2026-01-20 10:50:00.100 | INFO     | routes                 | API request: delete_namespace namespace=my-namespace [q7r8s9t0]
2026-01-20 10:50:00.101 | INFO     | eks_operations         | START delete_namespace namespace=my-namespace [q7r8s9t0]
2026-01-20 10:50:00.102 | DEBUG    | eks_operations         | Step 1: Sending delete_namespace request to Kubernetes API [q7r8s9t0]
2026-01-20 10:50:00.789 | DEBUG    | eks_operations         | Kubernetes API confirmed namespace deletion [q7r8s9t0]
2026-01-20 10:50:00.790 | INFO     | eks_operations         | END delete_namespace success=true duration_ms=688.9 [q7r8s9t0]
2026-01-20 10:50:00.791 | INFO     | routes                 | Successfully deleted namespace my-namespace [q7r8s9t0]
```

---

## Logging Format & Examples

### Log Format Specification

```
timestamp | level:8s | module:20s | message [request_id]
```

**Components**:
- `timestamp`: ISO format with milliseconds (e.g., `2026-01-20 10:30:00.123`)
- `level`: Log level (DEBUG, INFO, WARNING, ERROR) left-padded to 8 chars
- `module`: Module name left-padded to 20 chars
- `message`: Log message
- `[request_id]`: Optional 8-char request ID in square brackets for request tracing

### Log Levels Guide

| Level | When to Use | Example |
|-------|------------|---------|
| DEBUG | Detailed diagnostic information for developers | "Job manifest built with spec keys: ..." |
| INFO | General informational messages | "Successfully created job my-job" |
| WARNING | Warning conditions that don't stop execution | "Namespace not found. Creating it." |
| ERROR | Error conditions with exceptions | "Kubernetes API error: 403 Forbidden" |

### Example Complete Request/Response Logs

**Successful Job Creation**:
```
2026-01-20 10:30:00.100 | INFO     | routes                 | API request: create_job namespace=default [a1b2c3d4]
2026-01-20 10:30:00.101 | DEBUG    | routes                 | Generated job name: my-job-20260120-103000 [a1b2c3d4]
2026-01-20 10:30:00.102 | INFO     | eks_operations         | START create_job job=my-job-20260120-103000 namespace=default [a1b2c3d4]
2026-01-20 10:30:00.103 | DEBUG    | eks_operations         | Step 1: Verifying namespace default exists [a1b2c3d4]
2026-01-20 10:30:00.125 | DEBUG    | eks_operations         | Namespace default found [a1b2c3d4]
2026-01-20 10:30:00.126 | DEBUG    | eks_operations         | Step 2: Building job manifest for my-job-20260120-103000 [a1b2c3d4]
2026-01-20 10:30:00.127 | DEBUG    | eks_operations         | Job manifest built with spec keys: ['parallelism', 'template'] [a1b2c3d4]
2026-01-20 10:30:00.128 | DEBUG    | eks_operations         | Step 3: Sending create_namespaced_job request to Kubernetes API [a1b2c3d4]
2026-01-20 10:30:00.234 | DEBUG    | eks_operations         | Kubernetes API returned response with metadata: my-job-20260120-103000 [a1b2c3d4]
2026-01-20 10:30:00.235 | DEBUG    | eks_operations         | Step 4: Formatting response [a1b2c3d4]
2026-01-20 10:30:00.236 | INFO     | eks_operations         | END create_job success=true duration_ms=134.8 [a1b2c3d4]
2026-01-20 10:30:00.237 | INFO     | routes                 | Successfully created job my-job-20260120-103000 in namespace default [a1b2c3d4]
```

---

## Error Handling & Failure Scenarios

### Scenario 1: Job Creation Fails - Namespace Not Found and Creation Fails

**Error Sequence**:

```
2026-01-20 10:30:00.100 | INFO     | routes                 | API request: create_job namespace=my-ns [a1b2c3d4]
2026-01-20 10:30:00.101 | INFO     | eks_operations         | START create_job job=my-job namespace=my-ns [a1b2c3d4]
2026-01-20 10:30:00.102 | DEBUG    | eks_operations         | Step 1: Verifying namespace my-ns exists [a1b2c3d4]
2026-01-20 10:30:00.125 | DEBUG    | eks_operations         | Step 2: Building job manifest for my-job [a1b2c3d4]
2026-01-20 10:30:00.126 | WARNING  | eks_operations         | Namespace my-ns not found. Creating it. [a1b2c3d4]
2026-01-20 10:30:00.127 | INFO     | eks_operations         | START create_namespace namespace=my-ns auto_created=true [a1b2c3d4]
2026-01-20 10:30:00.128 | ERROR    | eks_operations         | Kubernetes API error creating namespace: 403 Forbidden [a1b2c3d4]
2026-01-20 10:30:00.129 | ERROR    | eks_operations         | Traceback (most recent call last):
  File "...", line 123, in create_namespace
    response = self.k8s_core_api.create_namespace(body=namespace_body)
kubernetes.client.exceptions.ApiException: (403)
Reason: Forbidden
HTTP response headers: HTTPHeaderDict({'content-type': 'application/json'})
HTTP response body: {"kind":"Status","apiVersion":"v1","metadata":{},"status":"Failure","message":"namespaces is forbidden: User \"arn:aws:iam::123456789:assumed-role/EC2-Role/i-1234567890abcdef0\" cannot create resource \"namespaces\" in API group \"\" at the cluster scope","reason":"Forbidden","details":{"kind":"namespaces"},"code":403} [a1b2c3d4]
2026-01-20 10:30:00.130 | ERROR    | routes                 | Kubernetes API error creating job: (403)
Reason: Forbidden [a1b2c3d4]
```

**HTTP Response**:
```
HTTP/1.1 500 Internal Server Error

{
  "detail": "Kubernetes API error: Forbidden"
}
```

**How to Debug**:
1. Check IAM role permissions - does it have `kubernetes.io/namespaces:create`?
2. Check cluster RBAC - does the IAM role have ServiceAccount bindings?
3. Verify EKS cluster has IAM auth configured

---

### Scenario 2: Token Generation Fails - AWS Credentials Not Available

**Error Sequence**:

```
2026-01-20 10:00:00.100 | INFO     | main                 | Validating configuration...
2026-01-20 10:00:00.101 | INFO     | main                 | Configuration loaded successfully:
2026-01-20 10:00:00.102 | INFO     | main                 | Application startup completed successfully
(First API request triggers EKS service initialization)
2026-01-20 10:00:05.100 | INFO     | routes                 | API request: create_job namespace=default [a1b2c3d4]
2026-01-20 10:00:05.101 | INFO     | eks_operations         | START _configure_clients cluster=my-cluster [a1b2c3d4]
2026-01-20 10:00:05.102 | DEBUG    | eks_operations         | Step 1: Fetch cluster endpoint and CA certificate [a1b2c3d4]
2026-01-20 10:00:05.234 | DEBUG    | eks_operations         | Cluster endpoint: https://abc.eks.us-east-1.amazonaws.com [a1b2c3d4]
2026-01-20 10:00:05.235 | DEBUG    | eks_operations         | Step 2: Generate IAM bearer token [a1b2c3d4]
2026-01-20 10:00:05.236 | ERROR    | eks_operations         | Traceback (most recent call last):
  File "...", line 156, in _generate_token
    token = get_token(cluster_name=settings.eks_cluster_name)
  File "eks_token/__init__.py", line 123, in get_token
    credentials = session.get_credentials()
botocore.exceptions.NoCredentialsError: Unable to locate credentials. You can configure credentials by running "aws configure" or by setting the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables. [a1b2c3d4]
2026-01-20 10:00:05.237 | ERROR    | eks_operations         | Failed to configure Kubernetes clients: Unable to locate credentials. You can configure credentials by running "aws configure" or by setting the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables. [a1b2c3d4]
2026-01-20 10:00:05.238 | ERROR    | eks_operations         | Initialization context: cluster=my-cluster, region=us-east-1 [a1b2c3d4]
```

**HTTP Response**:
```
HTTP/1.1 500 Internal Server Error

{
  "detail": "Internal server error: Unable to locate credentials..."
}
```

**How to Debug**:
1. Verify EC2 instance has IAM role attached: `aws sts get-caller-identity`
2. Check instance metadata endpoint: `curl http://169.254.169.254/latest/meta-data/iam/security-credentials/`
3. Verify AWS credentials in environment: `env | grep AWS_`
4. Check ~/.aws/credentials file permissions

---

### Scenario 3: Job Not Found - 404 Error

**Error Sequence**:

```
2026-01-20 10:35:30.100 | INFO     | routes                 | API request: get_job_status job=nonexistent-job namespace=default [e5f6g7h8]
2026-01-20 10:35:30.101 | INFO     | eks_operations         | START get_job_status job=nonexistent-job namespace=default [e5f6g7h8]
2026-01-20 10:35:30.102 | DEBUG    | eks_operations         | Step 1: Sending read_namespaced_job request to Kubernetes API [e5f6g7h8]
2026-01-20 10:35:30.125 | WARNING  | eks_operations         | Job nonexistent-job not found in namespace default [e5f6g7h8]
2026-01-20 10:35:30.126 | ERROR    | routes                 | Kubernetes API error fetching job status: (404)
Reason: Not Found
HTTP response body: {"kind":"Status","apiVersion":"v1","metadata":{},"status":"Failure","message":"jobs.batch \"nonexistent-job\" not found","reason":"NotFound","details":{"name":"nonexistent-job","group":"batch","kind":"jobs"},"code":404} [e5f6g7h8]
```

**HTTP Response**:
```
HTTP/1.1 404 Not Found

{
  "detail": "Job nonexistent-job not found in namespace default"
}
```

**How to Debug**:
1. List available jobs: `kubectl get jobs -n default`
2. Check job name spelling and namespace
3. Verify job exists in correct namespace

---

### Scenario 4: Kubernetes Cluster Unreachable

**Error Sequence**:

```
2026-01-20 10:00:05.234 | DEBUG    | eks_operations         | Cluster endpoint: https://invalid-endpoint.amazonaws.com [a1b2c3d4]
2026-01-20 10:00:05.235 | DEBUG    | eks_operations         | Step 2: Generate IAM bearer token [a1b2c3d4]
2026-01-20 10:00:05.500 | DEBUG    | eks_operations         | Successfully generated token length=2048 [a1b2c3d4]
2026-01-20 10:00:05.501 | DEBUG    | eks_operations         | Step 4: Configure Kubernetes client with IAM auth [a1b2c3d4]
2026-01-20 10:00:05.502 | DEBUG    | eks_operations         | Step 5: Create API clients [a1b2c3d4]
(Connection attempt to cluster)
2026-01-20 10:00:25.502 | ERROR    | eks_operations         | Failed to configure Kubernetes clients: HTTPSConnectionPool(host='invalid-endpoint.amazonaws.com', port=443): Max retries exceeded with url: /api/v1/namespaces (Caused by ConnectTimeout()) [a1b2c3d4]
2026-01-20 10:00:25.503 | ERROR    | eks_operations         | Initialization context: cluster=my-cluster, region=us-east-1 [a1b2c3d4]
```

**How to Debug**:
1. Verify cluster endpoint: `aws eks describe-cluster --name my-cluster --query 'cluster.endpoint'`
2. Test connectivity: `curl -v https://cluster-endpoint.amazonaws.com`
3. Check security group allows outbound HTTPS
4. Verify EKS_CLUSTER_NAME environment variable is correct

---

## Debugging Guide

### 1. Enable Debug Logging

Set `LOG_LEVEL` environment variable:

```bash
export LOG_LEVEL=DEBUG
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. Parse Log Files

Extract all logs for a specific request ID:

```bash
grep "\[a1b2c3d4\]" application.log
```

### 3. Common Log Search Patterns

**Find all errors**:
```bash
grep "| ERROR" application.log
```

**Find all API requests**:
```bash
grep "API request:" application.log
```

**Find operation start/end markers**:
```bash
grep "START\|END" application.log
```

**Find specific operation failures**:
```bash
grep "create_job" application.log | grep "ERROR"
```

### 4. Understand Log Timestamps

Log timestamps are in ISO format with millisecond precision:
```
2026-01-20 10:30:00.123
│          │  │   │   └── milliseconds
│          │  │   └────── seconds
│          │  └────────── minutes
│          └──────────────── hours
└─────────────────────────── date
```

Calculate request duration:
- Start: `2026-01-20 10:30:00.100`
- End: `2026-01-20 10:30:00.234`
- Duration: `234 - 100 = 134ms` (should match END log's `duration_ms=134.0`)

### 5. Correlate Requests with Request ID

Every API request has a unique 8-character request ID appended to logs:

```bash
# All logs for one request
grep "\[a1b2c3d4\]" application.log

# Output shows complete request flow:
# - Route entry point
# - Service initialization (if first request)
# - Service method calls
# - Kubernetes API calls
# - Response return
```

### 6. Monitor Real-Time Logs

View logs as they happen:

```bash
# Show last 100 lines
tail -100 application.log

# Follow new logs
tail -f application.log

# Search and follow
tail -f application.log | grep "ERROR"
```

### 7. Check Application Health

Make a health check request:

```bash
curl http://localhost:8000/health
```

Response indicates configuration is loaded:
```json
{
  "status": "healthy",
  "cluster": "my-cluster",
  "region": "us-east-1"
}
```

### 8. Validate Configuration

Check environment variables:

```bash
# Linux/Mac
env | grep EKS_

# Windows PowerShell
Get-Item -Path Env:EKS_*
```

Expected output:
```
EKS_CLUSTER_NAME=my-cluster
EKS_REGION=us-east-1
LOG_LEVEL=DEBUG
```

Check .env file loading (look for startup logs):

```bash
grep "Found environment file" application.log
```

If .env is not being loaded, check:
1. File exists: `ls -la .env`
2. File has correct permissions: `ls -l .env`
3. File is in correct location (project root or app root)

---

## Request ID Propagation

Every request is assigned a unique ID for end-to-end tracing:

```
Client Request A (ID: a1b2c3d4)
    │
    ├─→ FastAPI Route
    │       │
    │       └─→ EKS Service
    │            │
    │            ├─→ AWS boto3 call
    │            │       └─→ Log: [...] [a1b2c3d4]
    │            │
    │            └─→ Kubernetes API call
    │                    └─→ Log: [...] [a1b2c3d4]
    │
    └─→ Response with all logs tagged [a1b2c3d4]

Client Request B (ID: e5f6g7h8) ← Different ID
    ...
    All logs tagged [e5f6g7h8]
```

This allows you to:
- Track a single request through all layers
- Correlate multiple log lines to one request
- Debug concurrent requests simultaneously
- Generate request-specific audit trails

---

## Summary

This request flow documentation provides:

1. **Architecture Overview**: How components interact
2. **Startup Flow**: Application initialization sequence
3. **Authentication Details**: IAM-based Kubernetes authentication
4. **API Endpoint Flows**: Step-by-step execution of each endpoint with example logs
5. **Logging Format**: Standardized structured logging with request IDs
6. **Error Scenarios**: Common failure modes and how to diagnose them
7. **Debugging Guide**: Tools and techniques for troubleshooting

Use this documentation when:
- Implementing monitoring and alerting
- Investigating production issues
- Understanding application behavior
- Training team members on operation
- Implementing automated testing
