"""
Configuration management for the EKS API application.
Loads configuration from environment variables.
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Required environment variables:
    - EKS_CLUSTER_NAME: Name of the EKS cluster
    - EKS_REGION: AWS region where the EKS cluster is deployed
    
    AWS credentials are automatically resolved from:
    - EC2 IAM role (preferred when running on EC2)
    - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    - AWS CLI configuration (~/.aws/credentials, ~/.aws/config)
    """
    
    eks_cluster_name: str = os.getenv("EKS_CLUSTER_NAME", "")
    eks_region: str = os.getenv("EKS_REGION", "us-east-1")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        case_sensitive = False


# Global settings instance
settings = Settings()


def validate_settings() -> None:
    """
    Validate that required settings are configured.
    Raises ValueError if essential configuration is missing.
    """
    if not settings.eks_cluster_name:
        raise ValueError(
            "EKS_CLUSTER_NAME environment variable is required"
        )
    if not settings.eks_region:
        raise ValueError(
            "EKS_REGION environment variable is required"
        )
