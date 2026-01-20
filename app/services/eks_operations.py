"""
Kubernetes operations service layer for EKS cluster management.

Authentication Flow:
1. Use boto3 to call eks.describe_cluster to fetch cluster endpoint and CA cert
2. Generate short-lived IAM bearer token using eks-token package
3. Configure kubernetes.client.Configuration with:
   - host (cluster endpoint)
   - ssl_ca_cert (decoded CA certificate)
   - authorization (Bearer token)
4. All Kubernetes API calls use this authenticated client

No kubeconfig files are used. IAM-based authentication is mandatory.
"""
import base64
import boto3
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from eks_token import get_token
import ssl

from app.utils.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__, settings.log_level)


class EKSOperationsService:
    """
    Service class for managing Kubernetes Jobs and Namespaces in EKS.
    Handles IAM-based authentication and all Kubernetes API operations.
    """
    
    def __init__(self):
        """
        Initialize the EKS operations service.
        Sets up AWS and Kubernetes clients with IAM authentication.
        """
        self.eks_client = None
        self.k8s_batch_api = None
        self.k8s_core_api = None
        self._cluster_endpoint = None
        self._ca_cert_data = None
        self._token = None
        self._configure_clients()
    
    def _get_aws_client(self):
        """
        Get boto3 EKS client.
        AWS credentials are resolved automatically from:
        - EC2 IAM role
        - Environment variables
        - AWS CLI config
        """
        return boto3.client('eks', region_name=settings.eks_region)
    
    def _fetch_cluster_info(self) -> Tuple[str, str]:
        """
        Fetch cluster endpoint and CA certificate from EKS.
        
        Uses boto3 to call eks.describe_cluster which retrieves:
        - Kubernetes API server endpoint
        - Base64-encoded CA certificate
        
        Returns:
            Tuple of (cluster_endpoint, ca_cert_data)
        
        Raises:
            Exception: If cluster not found or API call fails
        """
        try:
            logger.info(f"Fetching cluster info for {settings.eks_cluster_name}")
            response = self.eks_client.describe_cluster(
                name=settings.eks_cluster_name
            )
            
            cluster = response['cluster']
            endpoint = cluster['endpoint']
            ca_data = cluster['certificateAuthority']['data']
            
            logger.info(f"Successfully fetched cluster endpoint: {endpoint}")
            return endpoint, ca_data
        except Exception as e:
            logger.error(f"Failed to fetch cluster info: {str(e)}")
            raise
    
    def _generate_token(self) -> str:
        """
        Generate short-lived IAM bearer token for Kubernetes authentication.
        
        Uses the eks-token package to create a token from AWS STS.
        This token is valid for 15 minutes and is automatically refreshed
        when creating a new client configuration.
        
        Returns:
            Bearer token string for Kubernetes API authentication
        
        Raises:
            Exception: If token generation fails
        """
        try:
            logger.info("Generating IAM bearer token for Kubernetes API")
            token = get_token(
                cluster_name=settings.eks_cluster_name,
                region_name=settings.eks_region
            )
            logger.info("Token generated successfully")
            return token
        except Exception as e:
            logger.error(f"Failed to generate token: {str(e)}")
            raise
    
    def _configure_clients(self) -> None:
        """
        Configure Kubernetes clients with IAM-based authentication.
        
        Process:
        1. Initialize AWS EKS client
        2. Fetch cluster endpoint and CA certificate
        3. Generate short-lived IAM bearer token
        4. Configure kubernetes.client.Configuration manually with:
           - host: Cluster API endpoint
           - ssl_ca_cert: Decoded CA certificate
           - authorization: Bearer token
        5. Create Kubernetes API clients (BatchV1Api, CoreV1Api)
        
        No kubeconfig file is read or written.
        """
        try:
            logger.info("Initializing EKS operations service")
            
            # Get AWS EKS client
            self.eks_client = self._get_aws_client()
            
            # Fetch cluster endpoint and CA certificate
            self._cluster_endpoint, self._ca_cert_data = self._fetch_cluster_info()
            
            # Generate IAM bearer token
            self._token = self._generate_token()
            
            # Decode CA certificate from base64
            ca_cert = base64.b64decode(self._ca_cert_data).decode('utf-8')
            
            # Create temporary CA certificate file for ssl verification
            # Kubernetes client needs this for SSL verification
            import tempfile
            ca_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.crt',
                delete=False
            )
            ca_file.write(ca_cert)
            ca_file.close()
            
            # Configure Kubernetes client with IAM authentication
            k8s_config = client.Configuration()
            k8s_config.host = self._cluster_endpoint
            k8s_config.ssl_ca_cert = ca_file.name
            k8s_config.api_key['authorization'] = f'Bearer {self._token}'
            k8s_config.api_key_prefix['authorization'] = ''
            
            # Create API clients
            api_client = client.ApiClient(k8s_config)
            self.k8s_batch_api = client.BatchV1Api(api_client)
            self.k8s_core_api = client.CoreV1Api(api_client)
            
            logger.info("EKS operations service initialized successfully")
        
        except Exception as e:
            logger.error(f"Failed to configure Kubernetes clients: {str(e)}")
            raise
    
    def create_job(
        self,
        job_name: str,
        job_manifest: Dict[str, Any],
        namespace: str = "default"
    ) -> Dict[str, Any]:
        """
        Create a Kubernetes Job in the EKS cluster.
        
        Args:
            job_name: Name of the job
            job_manifest: Kubernetes Job manifest (dict)
            namespace: Kubernetes namespace (default: "default")
        
        Returns:
            Dict with job_name, namespace, creation_timestamp, and status
        
        Raises:
            ApiException: If Kubernetes API call fails
        """
        try:
            logger.info(f"Creating job {job_name} in namespace {namespace}")
            
            # Ensure namespace exists
            try:
                self.k8s_core_api.read_namespace(namespace)
            except ApiException as e:
                if e.status == 404:
                    logger.warning(f"Namespace {namespace} not found. Creating it.")
                    self.create_namespace(namespace)
            
            # Build job manifest with labels
            job_body = {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "name": job_name,
                    "namespace": namespace,
                    "labels": {
                        "app": "eks-api",
                        "job-id": job_name
                    }
                },
                "spec": job_manifest.get("spec", {})
            }
            
            # Create the job
            response = self.k8s_batch_api.create_namespaced_job(
                namespace=namespace,
                body=job_body
            )
            
            logger.info(f"Job {job_name} created successfully")
            
            return {
                "job_name": response.metadata.name,
                "namespace": response.metadata.namespace,
                "creation_timestamp": response.metadata.creation_timestamp.isoformat() if response.metadata.creation_timestamp else None,
                "status": "created"
            }
        
        except ApiException as e:
            logger.error(f"Kubernetes API error creating job: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating job: {str(e)}")
            raise
    
    def delete_job(
        self,
        job_name: str,
        namespace: str = "default"
    ) -> Dict[str, str]:
        """
        Delete a Kubernetes Job from the EKS cluster.
        
        Args:
            job_name: Name of the job to delete
            namespace: Kubernetes namespace (default: "default")
        
        Returns:
            Dict with success message
        
        Raises:
            ApiException: If job not found or deletion fails
        """
        try:
            logger.info(f"Deleting job {job_name} from namespace {namespace}")
            
            self.k8s_batch_api.delete_namespaced_job(
                name=job_name,
                namespace=namespace,
                body=client.V1DeleteOptions(propagation_policy='Foreground')
            )
            
            logger.info(f"Job {job_name} deleted successfully")
            
            return {
                "message": f"Job {job_name} deleted successfully",
                "status": "success"
            }
        
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Job {job_name} not found in namespace {namespace}")
                raise ApiException(
                    status=404,
                    reason=f"Job {job_name} not found in namespace {namespace}"
                )
            logger.error(f"Kubernetes API error deleting job: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting job: {str(e)}")
            raise
    
    def get_job_status(
        self,
        job_name: str,
        namespace: str = "default"
    ) -> Dict[str, Any]:
        """
        Get the status of a Kubernetes Job.
        
        Args:
            job_name: Name of the job
            namespace: Kubernetes namespace (default: "default")
        
        Returns:
            Dict with job state, active/succeeded/failed counts, and timestamps
        
        Raises:
            ApiException: If job not found
        """
        try:
            logger.info(f"Fetching status for job {job_name} in namespace {namespace}")
            
            job = self.k8s_batch_api.read_namespaced_job(
                name=job_name,
                namespace=namespace
            )
            
            status = job.status
            
            # Determine job state
            if status.succeeded and status.succeeded > 0:
                job_state = "completed"
            elif status.failed and status.failed > 0:
                job_state = "failed"
            elif status.active and status.active > 0:
                job_state = "running"
            else:
                job_state = "unknown"
            
            return {
                "job_name": job.metadata.name,
                "namespace": job.metadata.namespace,
                "state": job_state,
                "active": status.active or 0,
                "succeeded": status.succeeded or 0,
                "failed": status.failed or 0,
                "start_time": status.start_time.isoformat() if status.start_time else None,
                "completion_time": status.completion_time.isoformat() if status.completion_time else None
            }
        
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Job {job_name} not found in namespace {namespace}")
                raise ApiException(
                    status=404,
                    reason=f"Job {job_name} not found in namespace {namespace}"
                )
            logger.error(f"Kubernetes API error fetching job status: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching job status: {str(e)}")
            raise
    
    def create_namespace(self, namespace_name: str) -> Dict[str, Any]:
        """
        Create a Kubernetes Namespace in the EKS cluster.
        
        Args:
            namespace_name: Name of the namespace to create
        
        Returns:
            Dict with namespace_name, creation_timestamp, and status
        
        Raises:
            ApiException: If namespace creation fails
        """
        try:
            logger.info(f"Creating namespace {namespace_name}")
            
            namespace_body = {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": namespace_name
                }
            }
            
            response = self.k8s_core_api.create_namespace(
                body=namespace_body
            )
            
            logger.info(f"Namespace {namespace_name} created successfully")
            
            return {
                "namespace_name": response.metadata.name,
                "creation_timestamp": response.metadata.creation_timestamp.isoformat() if response.metadata.creation_timestamp else None,
                "status": "created"
            }
        
        except ApiException as e:
            logger.error(f"Kubernetes API error creating namespace: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating namespace: {str(e)}")
            raise
    
    def delete_namespace(self, namespace_name: str) -> Dict[str, str]:
        """
        Delete a Kubernetes Namespace from the EKS cluster.
        
        Args:
            namespace_name: Name of the namespace to delete
        
        Returns:
            Dict with success message
        
        Raises:
            ApiException: If namespace not found or deletion fails
        """
        try:
            logger.info(f"Deleting namespace {namespace_name}")
            
            self.k8s_core_api.delete_namespace(
                name=namespace_name,
                body=client.V1DeleteOptions(propagation_policy='Foreground')
            )
            
            logger.info(f"Namespace {namespace_name} deleted successfully")
            
            return {
                "message": f"Namespace {namespace_name} deleted successfully",
                "status": "success"
            }
        
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Namespace {namespace_name} not found")
                raise ApiException(
                    status=404,
                    reason=f"Namespace {namespace_name} not found"
                )
            logger.error(f"Kubernetes API error deleting namespace: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting namespace: {str(e)}")
            raise


# Global service instance
_service_instance: Optional[EKSOperationsService] = None


def get_eks_service() -> EKSOperationsService:
    """
    Get or create the EKS operations service instance.
    Uses lazy initialization on first call.
    
    Returns:
        EKSOperationsService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = EKSOperationsService()
    return _service_instance
