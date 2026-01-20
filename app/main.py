"""
FastAPI application for managing Kubernetes Jobs and Namespaces in AWS EKS.

Authentication Model:
- IAM-based authentication (no kubeconfig files)
- Uses boto3 to discover cluster endpoint and CA certificate
- Generates short-lived bearer tokens via eks-token package
- Requires EKS_CLUSTER_NAME and EKS_REGION environment variables
- AWS credentials resolved from EC2 IAM role, environment variables, or AWS CLI config

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.routes import router
from app.core.config import settings, validate_settings
from app.utils.logger import get_logger

logger = get_logger(__name__, settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Validates configuration on startup.
    """
    # Startup
    try:
        logger.info("Starting EKS API application")
        validate_settings()
        logger.info(
            f"Configuration: cluster={settings.eks_cluster_name}, "
            f"region={settings.eks_region}"
        )
        logger.info("Application startup completed successfully")
    except ValueError as e:
        logger.error(f"Configuration validation failed: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down EKS API application")


# Create FastAPI application
app = FastAPI(
    title="EKS Kubernetes Operations API",
    description="Production-ready API for managing Kubernetes Jobs and Namespaces in AWS EKS clusters",
    version="1.0.0",
    lifespan=lifespan
)


# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routes
app.include_router(router)


# Health check endpoint
@app.get(
    "/health",
    summary="Health Check",
    description="Simple health check endpoint"
)
async def health_check() -> dict:
    """
    Health check endpoint.
    Returns status and cluster information.
    """
    return {
        "status": "healthy",
        "cluster": settings.eks_cluster_name,
        "region": settings.eks_region
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting uvicorn server")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower()
    )
