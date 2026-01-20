"""
FastAPI routes for EKS Kubernetes operations.
All routes wrap service calls in try/except blocks and return structured JSON responses.

Request Flow:
1. Request enters route handler
2. Request parameters validated and logged
3. EKS service called with operation logging
4. Response returned with status code and data
5. Exceptions caught and converted to appropriate HTTP errors
6. All operations logged with timing and result status
"""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from kubernetes.client.rest import ApiException
from uuid import uuid4
import time

from app.services.eks_operations import get_eks_service
from app.utils.logger import get_logger, log_operation, set_request_id, get_request_id
from app.core.config import settings

logger = get_logger(__name__, settings.log_level)
router = APIRouter(prefix="/api", tags=["eks"])


# ============================================================================
# Request/Response Models
# ============================================================================

class JobManifestRequest(BaseModel):
    """Request model for creating a Kubernetes Job."""
    job_manifest: Dict[str, Any] = Field(
        ...,
        description="Kubernetes Job spec (required). Should contain 'spec' key with pod template and parallelism settings."
    )
    namespace: Optional[str] = Field(
        default="default",
        description="Kubernetes namespace where the job will be created"
    )


class NamespaceRequest(BaseModel):
    """Request model for creating a Kubernetes Namespace."""
    namespace_name: str = Field(
        ...,
        description="Name of the namespace to create"
    )


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    job_name: str
    namespace: str
    state: str
    active: int
    succeeded: int
    failed: int
    start_time: Optional[str]
    completion_time: Optional[str]


class JobCreateResponse(BaseModel):
    """Response model for job creation."""
    job_name: str
    namespace: str
    creation_timestamp: Optional[str]
    status: str


class NamespaceCreateResponse(BaseModel):
    """Response model for namespace creation."""
    namespace_name: str
    creation_timestamp: Optional[str]
    status: str


class SuccessResponse(BaseModel):
    """Generic success response."""
    message: str
    status: str


# ============================================================================
# Job Management Routes
# ============================================================================

@router.post(
    "/eks-create-job",
    response_model=JobCreateResponse,
    summary="Create a Kubernetes Job",
    description="Creates a new Kubernetes Job in the specified EKS namespace"
)
async def create_job(request: JobManifestRequest, http_request: Request) -> Dict[str, Any]:
    """
    Create a Kubernetes Job in the EKS cluster.
    
    Request body:
    - job_manifest (dict, required): Kubernetes Job spec
    - namespace (string, optional, default="default"): Target namespace
    
    Returns:
    - job_name: Name of the created job
    - namespace: Namespace where job was created
    - creation_timestamp: ISO timestamp of creation
    - status: "created" on success
    
    Log Output Example:
    - INFO: API request: create_job namespace=default request_id=a1b2c3d4
    - START: Creating Kubernetes job
    - END: Successfully created job=my-job duration=1234ms
    """
    request_id = str(uuid4())[:8]
    set_request_id(request_id)
    
    try:
        logger.info(
            f"API request: create_job namespace={request.namespace}",
            extra={"request_id": request_id}
        )
        
        service = get_eks_service()
        
        # Generate job name from manifest or use timestamp-based name
        job_name = request.job_manifest.get("metadata", {}).get("name")
        if not job_name:
            from datetime import datetime
            job_name = f"job-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        logger.debug(f"Generated job name: {job_name}")
        
        with log_operation(logger, "create_job", job=job_name, namespace=request.namespace):
            result = service.create_job(
                job_name=job_name,
                job_manifest=request.job_manifest,
                namespace=request.namespace
            )
        
        logger.info(f"Successfully created job {job_name} in namespace {request.namespace}")
        return result
    
    except ApiException as e:
        logger.error(
            f"Kubernetes API error creating job: {e.reason} (status={e.status})",
            exc_info=True
        )
        raise HTTPException(
            status_code=e.status or 500,
            detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.delete(
    "/eks-delete-job",
    response_model=SuccessResponse,
    summary="Delete a Kubernetes Job",
    description="Deletes a Kubernetes Job from the EKS cluster"
)
async def delete_job(
    job_name: str = Query(..., description="Name of the job to delete"),
    namespace: str = Query(default="default", description="Kubernetes namespace")
) -> Dict[str, str]:
    """
    Delete a Kubernetes Job from the EKS cluster.
    
    Query parameters:
    - job_name (required): Name of the job to delete
    - namespace (optional, default="default"): Namespace of the job
    
    Returns:
    - message: Confirmation message
    - status: "success" on successful deletion
    
    Log Output Example:
    - INFO: API request: delete_job job=my-job namespace=default
    - START: Deleting Kubernetes job
    - END: Job deleted successfully duration=567ms
    """
    request_id = str(uuid4())[:8]
    set_request_id(request_id)
    
    try:
        logger.info(
            f"API request: delete_job job={job_name} namespace={namespace}",
            extra={"request_id": request_id}
        )
        
        service = get_eks_service()
        
        with log_operation(logger, "delete_job", job=job_name, namespace=namespace):
            result = service.delete_job(
                job_name=job_name,
                namespace=namespace
            )
        
        logger.info(f"Successfully deleted job {job_name} from namespace {namespace}")
        return result
    
    except ApiException as e:
        if e.status == 404:
            logger.warning(f"Job not found: {job_name} in namespace {namespace}")
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_name} not found in namespace {namespace}"
            )
        logger.error(f"Kubernetes API error deleting job: {e.reason}", exc_info=True)
        raise HTTPException(
            status_code=e.status or 500,
            detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/eks-get-job-status",
    response_model=JobStatusResponse,
    summary="Get Kubernetes Job Status",
    description="Retrieves the current status of a Kubernetes Job"
)
async def get_job_status(
    job_name: str = Query(..., description="Name of the job"),
    namespace: str = Query(default="default", description="Kubernetes namespace")
) -> Dict[str, Any]:
    """
    Get the status of a Kubernetes Job.
    
    Query parameters:
    - job_name (required): Name of the job
    - namespace (optional, default="default"): Namespace of the job
    
    Returns:
    - job_name: Name of the job
    - namespace: Namespace
    - state: Job state (running / completed / failed / unknown)
    - active: Number of active pods
    - succeeded: Number of succeeded pods
    - failed: Number of failed pods
    - start_time: ISO timestamp when job started
    - completion_time: ISO timestamp when job completed (if applicable)
    
    Log Output Example:
    - INFO: API request: get_job_status job=my-job namespace=default
    - START: Fetching job status
    - DEBUG: Job status state=Running active=2 succeeded=0 failed=0
    - END: Job status retrieved duration=234ms
    """
    request_id = str(uuid4())[:8]
    set_request_id(request_id)
    
    try:
        logger.info(
            f"API request: get_job_status job={job_name} namespace={namespace}",
            extra={"request_id": request_id}
        )
        
        service = get_eks_service()
        
        with log_operation(logger, "get_job_status", job=job_name, namespace=namespace):
            result = service.get_job_status(
                job_name=job_name,
                namespace=namespace
            )
        
        logger.debug(
            f"Job status: {result.get('state')} "
            f"(active={result.get('active')}, "
            f"succeeded={result.get('succeeded')}, "
            f"failed={result.get('failed')})"
        )
        logger.info(f"Successfully retrieved status for job {job_name}")
        return result
    
    except ApiException as e:
        if e.status == 404:
            logger.warning(f"Job not found: {job_name} in namespace {namespace}")
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_name} not found in namespace {namespace}"
            )
        logger.error(f"Kubernetes API error fetching job status: {e.reason}", exc_info=True)
        raise HTTPException(
            status_code=e.status or 500,
            detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching job status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# ============================================================================
# Namespace Management Routes
# ============================================================================

@router.post(
    "/eks-create-namespace",
    response_model=NamespaceCreateResponse,
    summary="Create a Kubernetes Namespace",
    description="Creates a new Kubernetes Namespace in the EKS cluster"
)
async def create_namespace(request: NamespaceRequest) -> Dict[str, Any]:
    """
    Create a Kubernetes Namespace in the EKS cluster.
    
    Request body:
    - namespace_name (required): Name of the namespace to create
    
    Returns:
    - namespace_name: Name of the created namespace
    - creation_timestamp: ISO timestamp of creation
    - status: "created" on success
    
    Log Output Example:
    - INFO: API request: create_namespace namespace=my-ns
    - START: Creating Kubernetes namespace
    - END: Namespace created successfully duration=345ms
    """
    request_id = str(uuid4())[:8]
    set_request_id(request_id)
    
    try:
        logger.info(
            f"API request: create_namespace namespace={request.namespace_name}",
            extra={"request_id": request_id}
        )
        
        service = get_eks_service()
        
        with log_operation(logger, "create_namespace", namespace=request.namespace_name):
            result = service.create_namespace(
                namespace_name=request.namespace_name
            )
        
        logger.info(f"Successfully created namespace {request.namespace_name}")
        return result
    
    except ApiException as e:
        logger.error(
            f"Kubernetes API error creating namespace: {e.reason}",
            exc_info=True
        )
        raise HTTPException(
            status_code=e.status or 500,
            detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating namespace: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.delete(
    "/eks-delete-namespace",
    response_model=SuccessResponse,
    summary="Delete a Kubernetes Namespace",
    description="Deletes a Kubernetes Namespace from the EKS cluster"
)
async def delete_namespace(
    namespace_name: str = Query(..., description="Name of the namespace to delete")
) -> Dict[str, str]:
    """
    Delete a Kubernetes Namespace from the EKS cluster.
    
    Query parameters:
    - namespace_name (required): Name of the namespace to delete
    
    Returns:
    - message: Confirmation message
    - status: "success" on successful deletion
    
    Log Output Example:
    - INFO: API request: delete_namespace namespace=my-ns
    - START: Deleting Kubernetes namespace
    - END: Namespace deleted successfully duration=789ms
    """
    request_id = str(uuid4())[:8]
    set_request_id(request_id)
    
    try:
        logger.info(
            f"API request: delete_namespace namespace={namespace_name}",
            extra={"request_id": request_id}
        )
        
        service = get_eks_service()
        
        with log_operation(logger, "delete_namespace", namespace=namespace_name):
            result = service.delete_namespace(
                namespace_name=namespace_name
            )
        
        logger.info(f"Successfully deleted namespace {namespace_name}")
        return result
    
    except ApiException as e:
        if e.status == 404:
            logger.warning(f"Namespace not found: {namespace_name}")
            raise HTTPException(
                status_code=404,
                detail=f"Namespace {namespace_name} not found"
            )
        logger.error(f"Kubernetes API error deleting namespace: {e.reason}", exc_info=True)
        raise HTTPException(
            status_code=e.status or 500,
            detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting namespace: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
