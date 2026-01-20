"""
Configuration management for the EKS API application.
Loads configuration from environment variables and .env files.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

# Load .env file if it exists
# Look for .env in the project root and parent directories
env_paths = [
    Path.cwd() / ".env",
    Path(__file__).parent.parent.parent / ".env",
]

for env_path in env_paths:
    if env_path.exists():
        print(f"[CONFIG] Loading environment from: {env_path}")
        load_dotenv(env_path, override=True)
        break
else:
    print("[CONFIG] No .env file found. Using system environment variables.")


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env files.
    Priority order:
    1. Environment variables (loaded from .env)
    2. System environment variables
    3. Default values
    
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
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()


def validate_settings() -> None:
    """
    Validate that required settings are configured.
    Raises ValueError if essential configuration is missing.
    """
    if not settings.eks_cluster_name:
        raise ValueError(
            "EKS_CLUSTER_NAME environment variable is required (set in .env or export)"
        )
    if not settings.eks_region:
        raise ValueError(
            "EKS_REGION environment variable is required (set in .env or export)"
        )
