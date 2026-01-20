"""
FastAPI routes for EKS Kubernetes operations.
All routes wrap service calls in try/except blocks and return structured JSON responses.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from kubernetes.client.rest import ApiException

from app.services.eks_operations import get_eks_service
from app.utils.logger import get_logger
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
async def create_job(request: JobManifestRequest) -> Dict[str, Any]:
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
    """
    try:
        logger.info(
            f"API request: create job with namespace={request.namespace}"
        )
        
        service = get_eks_service()
        
        # Generate job name from manifest or use timestamp-based name
        job_name = request.job_manifest.get("metadata", {}).get("name")
        if not job_name:
            from datetime import datetime
            job_name = f"job-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        result = service.create_job(
            job_name=job_name,
            job_manifest=request.job_manifest,
            namespace=request.namespace
        )
        
        logger.info(f"Successfully created job {job_name}")
        return result
    
    except ApiException as e:
        logger.error(f"Kubernetes API error: {str(e)}")
        raise HTTPException(
            status_code=e.status or 500,
            detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating job: {str(e)}")
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
    """
    try:
        logger.info(
            f"API request: delete job {job_name} from namespace {namespace}"
        )
        
        service = get_eks_service()
        result = service.delete_job(
            job_name=job_name,
            namespace=namespace
        )
        
        logger.info(f"Successfully deleted job {job_name}")
        return result
    
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_name} not found in namespace {namespace}"
            )
        logger.error(f"Kubernetes API error: {str(e)}")
        raise HTTPException(
            status_code=e.status or 500,
            detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting job: {str(e)}")
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
    """
    try:
        logger.info(
            f"API request: get status for job {job_name} in namespace {namespace}"
        )
        
        service = get_eks_service()
        result = service.get_job_status(
            job_name=job_name,
            namespace=namespace
        )
        
        logger.info(f"Successfully retrieved status for job {job_name}")
        return result
    
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_name} not found in namespace {namespace}"
            )
        logger.error(f"Kubernetes API error: {str(e)}")
        raise HTTPException(
            status_code=e.status or 500,
            detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching job status: {str(e)}")
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
    """
    try:
        logger.info(
            f"API request: create namespace {request.namespace_name}"
        )
        
        service = get_eks_service()
        result = service.create_namespace(
            namespace_name=request.namespace_name
        )
        
        logger.info(f"Successfully created namespace {request.namespace_name}")
        return result
    
    except ApiException as e:
        logger.error(f"Kubernetes API error: {str(e)}")
        raise HTTPException(
            status_code=e.status or 500,
            detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating namespace: {str(e)}")
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
    """
    try:
        logger.info(
            f"API request: delete namespace {namespace_name}"
        )
        
        service = get_eks_service()
        result = service.delete_namespace(
            namespace_name=namespace_name
        )
        
        logger.info(f"Successfully deleted namespace {namespace_name}")
        return result
    
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Namespace {namespace_name} not found"
            )
        logger.error(f"Kubernetes API error: {str(e)}")
        raise HTTPException(
            status_code=e.status or 500,
            detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting namespace: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
