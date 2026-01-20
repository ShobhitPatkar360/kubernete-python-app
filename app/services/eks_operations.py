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
        
        **ROOT CAUSE #1**: eks-token.get_token() returns an ExecCredential DICT, NOT a string!
        
        The response structure is:
        {
            'kind': 'ExecCredential',
            'apiVersion': 'client.authentication.k8s.io/v1beta1',
            'status': {
                'expirationTimestamp': '2026-01-21T10:30:00Z',
                'token': 'k8s-aws4-...actual-bearer-token-here...'
            }
        }
        
        **This is by design** - it's the Kubernetes exec plugin credential format.
        The actual bearer token is extracted from: response['status']['token']
        
        Uses the eks-token package to create a token from AWS STS.
        This token is valid for 15 minutes.
        
        It automatically uses AWS credentials from:
        - EC2 IAM role metadata (primary)
        - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        - AWS CLI config (~/.aws/credentials)
        
        Returns:
            Bearer token string for Kubernetes API authentication
        
        Raises:
            ValueError: If token extraction fails or invalid response format
            Exception: If token generation fails
        """
        try:
            logger.debug(f"Token generation: cluster_name={settings.eks_cluster_name}")
            logger.info("Generating IAM bearer token via eks-token package")
            
            # Call eks-token.get_token() - returns ExecCredential dict
            credential_response = get_token(cluster_name=settings.eks_cluster_name)
            logger.debug(f"eks-token response type: {type(credential_response).__name__}")
            
            # Validate response is dict (ExecCredential format)
            if not isinstance(credential_response, dict):
                raise ValueError(
                    f"Expected dict from get_token(), got {type(credential_response).__name__}. "
                    f"Verify eks-token version: pip show eks-token"
                )
            
            # Extract token from ExecCredential structure
            # Path: response['status']['token']
            try:
                token = credential_response.get('status', {}).get('token')
                if not token:
                    logger.error(f"ExecCredential response: {credential_response}")
                    raise ValueError("No token in ExecCredential.status.token")
            except AttributeError as e:
                logger.error(
                    f"Failed to extract token. Response type: {type(credential_response).__name__}, "
                    f"Keys: {list(credential_response.keys()) if isinstance(credential_response, dict) else 'N/A'}"
                )
                raise ValueError(f"Invalid ExecCredential response format: {str(e)}")
            
            # Validate token is non-empty string
            if not isinstance(token, str) or len(token) == 0:
                raise ValueError(
                    f"Token is not a non-empty string. Type: {type(token).__name__}, "
                    f"Length: {len(token) if isinstance(token, str) else 'N/A'}"
                )
            
            logger.debug(f"Token extracted from ExecCredential.status.token")
            logger.info(f"IAM bearer token generated successfully (length={len(token)} chars, expires ~15 min)")
            logger.debug(f"Token prefix (first 20 chars): {token[:20]}...")
            logger.debug(f"Token format check: starts with 'k8s-aws4' = {token.startswith('k8s-aws4')}")
            
            return token
        
        except ValueError as e:
            logger.error(f"Token extraction failed: {str(e)}")
            logger.error(f"Context: cluster={settings.eks_cluster_name}, region={settings.eks_region}")
            logger.error("Fix: (1) Verify eks-token installed, (2) Check AWS credentials, (3) Check IAM permissions")
            raise
        except Exception as e:
            logger.error(f"Token generation failed: {str(e)}", exc_info=True)
            logger.error(f"Context: cluster={settings.eks_cluster_name}, region={settings.eks_region}")
            raise
    
    def _configure_clients(self) -> None:
        """
        Configure Kubernetes clients with IAM-based authentication.
        
        **ROOT CAUSE #2**: This method MUST be defined as a class method and called in __init__.
        Error "has no attribute '_configure_clients'" means the method wasn't defined properly.
        
        **INITIALIZATION LIFECYCLE**:
        1. Called ONCE during __init__ (service instantiation)
        2. Failure here prevents entire service from working
        3. Kubernetes API clients stored as self.k8s_batch_api, self.k8s_core_api
        
        **No kubeconfig files** - IAM-only authentication.
        
        Process:
        1. Initialize AWS EKS client
        2. Fetch cluster endpoint and CA certificate
        3. Generate short-lived IAM bearer token (extracts from ExecCredential dict)
        4. Configure kubernetes.client.Configuration manually
        5. Create Kubernetes API clients (BatchV1Api, CoreV1Api)
        """
        try:
            logger.info("=" * 80)
            logger.info("Initializing EKS operations service")
            logger.info("=" * 80)
            logger.debug(f"Cluster: {settings.eks_cluster_name}, Region: {settings.eks_region}")
            
            # Validate state before starting
            if self.k8s_batch_api is not None or self.k8s_core_api is not None:
                logger.warning("Kubernetes clients already initialized, reinitializing...")
            
            # STEP 1: Initialize AWS EKS client
            logger.debug(f"Creating boto3 EKS client for region={settings.eks_region}")
            self.eks_client = self._get_aws_client()
            logger.debug("✓ boto3 EKS client created")
            
            # STEP 2: Fetch cluster endpoint and CA certificate
            logger.info("Step 1/5: Fetching cluster endpoint and CA certificate from AWS EKS")
            self._cluster_endpoint, self._ca_cert_data = self._fetch_cluster_info()
            logger.debug(f"✓ Cluster endpoint: {self._cluster_endpoint}")
            logger.debug(f"✓ CA certificate data received (base64, {len(self._ca_cert_data)} chars)")
            
            # STEP 3: Generate IAM bearer token (handles ExecCredential dict extraction)
            logger.info("Step 2/5: Generating IAM bearer token via eks-token")
            self._token = self._generate_token()  # Returns extracted token string
            logger.debug(f"✓ Token extracted from ExecCredential response ({len(self._token)} chars)")
            
            # STEP 4: Decode CA certificate from base64
            logger.info("Step 3/5: Decoding CA certificate from base64")
            try:
                ca_cert = base64.b64decode(self._ca_cert_data).decode('utf-8')
                logger.debug(f"✓ CA certificate decoded ({len(ca_cert)} chars)")
            except Exception as e:
                logger.error(f"Failed to decode CA certificate: {str(e)}")
                raise ValueError(f"Invalid base64 CA certificate: {str(e)}")
            
            # STEP 5: Create temporary CA certificate file
            # Kubernetes client requires this file for SSL verification
            import tempfile
            logger.debug("Creating temporary CA certificate file")
            try:
                ca_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.crt',
                    delete=False,
                    prefix='eks_ca_'
                )
                ca_file.write(ca_cert)
                ca_file.close()
                logger.debug(f"✓ CA certificate file: {ca_file.name} ({len(ca_cert)} bytes)")
            except Exception as e:
                logger.error(f"Failed to create temp CA file: {str(e)}")
                raise ValueError(f"Cannot create CA certificate file: {str(e)}")
            
            # STEP 6: Configure Kubernetes client with IAM authentication
            logger.info("Step 4/5: Configuring Kubernetes client with IAM bearer token")
            try:
                k8s_config = client.Configuration()
                k8s_config.host = self._cluster_endpoint
                k8s_config.ssl_ca_cert = ca_file.name
                k8s_config.api_key['authorization'] = f'Bearer {self._token}'
                k8s_config.api_key_prefix['authorization'] = ''
                logger.debug(f"✓ Host: {self._cluster_endpoint}")
                logger.debug(f"✓ SSL CA cert: {ca_file.name}")
                logger.debug(f"✓ Auth header: Bearer <{len(self._token)}-char token>")
            except Exception as e:
                logger.error(f"Failed to configure Kubernetes client: {str(e)}")
                raise ValueError(f"Kubernetes config error: {str(e)}")
            
            # STEP 7: Create Kubernetes API clients
            logger.info("Step 5/5: Creating Kubernetes API client instances")
            try:
                api_client = client.ApiClient(k8s_config)
                self.k8s_batch_api = client.BatchV1Api(api_client)
                self.k8s_core_api = client.CoreV1Api(api_client)
                logger.debug("✓ BatchV1Api created (Job operations)")
                logger.debug("✓ CoreV1Api created (Namespace operations)")
            except Exception as e:
                logger.error(f"Failed to create API clients: {str(e)}")
                raise ValueError(f"API client creation error: {str(e)}")
            
            # SUCCESS
            logger.info("=" * 80)
            logger.info("✓ EKS operations service initialized successfully")
            logger.info(f"✓ Cluster: {settings.eks_cluster_name}")
            logger.info(f"✓ Region: {settings.eks_region}")
            logger.info(f"✓ Endpoint: {self._cluster_endpoint}")
            logger.info("✓ Ready for Kubernetes operations")
            logger.info("=" * 80)
        
        except Exception as e:
            logger.error("=" * 80)
            logger.error("✗ FAILED to initialize EKS service")
            logger.error("=" * 80)
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Cluster: {settings.eks_cluster_name}")
            logger.error(f"Region: {settings.eks_region}")
            logger.error("Troubleshooting:")
            logger.error("  1. Cluster exists: aws eks describe-cluster --name ... --region ...")
            logger.error("  2. AWS credentials: aws sts get-caller-identity")
            logger.error("  3. IAM permissions: eks:DescribeCluster, sts:AssumeRole")
            logger.error("  4. eks-token package: pip show eks-token")
            logger.error("  5. .env file: EKS_CLUSTER_NAME, EKS_REGION correct")
            logger.error("=" * 80)
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
        
        Implementation Steps:
        1. Check if namespace exists, create if needed
        2. Build job manifest with labels and metadata
        3. Send create_namespaced_job request to Kubernetes API
        4. Return job metadata in structured response
        """
        from app.utils.logger import log_operation
        
        try:
            logger.debug(f"Creating job {job_name} in namespace {namespace}")
            
            with log_operation(logger, "create_job", job=job_name, namespace=namespace):
                # Step 1: Ensure namespace exists
                logger.debug(f"Step 1: Verifying namespace {namespace} exists")
                try:
                    self.k8s_core_api.read_namespace(namespace)
                    logger.debug(f"Namespace {namespace} found")
                except ApiException as e:
                    if e.status == 404:
                        logger.warning(f"Namespace {namespace} not found. Creating it.")
                        with log_operation(logger, "create_namespace", namespace=namespace, auto_created=True):
                            self.create_namespace(namespace)
                    else:
                        raise
                
                # Step 2: Build job manifest
                logger.debug(f"Step 2: Building job manifest for {job_name}")
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
                logger.debug(f"Job manifest built with spec keys: {list(job_body['spec'].keys())}")
                
                # Step 3: Create the job
                logger.debug(f"Step 3: Sending create_namespaced_job request to Kubernetes API")
                response = self.k8s_batch_api.create_namespaced_job(
                    namespace=namespace,
                    body=job_body
                )
                logger.debug(f"Kubernetes API returned response with metadata: {response.metadata.name}")
                
                # Step 4: Format and return response
                logger.debug(f"Step 4: Formatting response")
                result = {
                    "job_name": response.metadata.name,
                    "namespace": response.metadata.namespace,
                    "creation_timestamp": response.metadata.creation_timestamp.isoformat() if response.metadata.creation_timestamp else None,
                    "status": "created"
                }
                logger.debug(f"Job creation response ready: {result}")
                
                return result
        
        except ApiException as e:
            logger.error(f"Kubernetes API error creating job: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating job: {str(e)}", exc_info=True)
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
        
        Implementation Steps:
        1. Send delete_namespaced_job request to Kubernetes API
        2. Use Foreground propagation policy for graceful deletion
        3. Return success confirmation
        """
        from app.utils.logger import log_operation
        
        try:
            logger.debug(f"Deleting job {job_name} from namespace {namespace}")
            
            with log_operation(logger, "delete_job", job=job_name, namespace=namespace):
                logger.debug(f"Step 1: Sending delete_namespaced_job request to Kubernetes API")
                self.k8s_batch_api.delete_namespaced_job(
                    name=job_name,
                    namespace=namespace,
                    body=client.V1DeleteOptions(propagation_policy='Foreground')
                )
                logger.debug(f"Kubernetes API confirmed job deletion")
            
            logger.debug(f"Job {job_name} deletion request accepted")
            
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
            logger.error(f"Kubernetes API error deleting job: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting job: {str(e)}", exc_info=True)
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
        
        Implementation Steps:
        1. Send read_namespaced_job request to Kubernetes API
        2. Analyze job status to determine state (running/completed/failed/unknown)
        3. Extract and format status fields
        4. Return structured status response
        """
        from app.utils.logger import log_operation
        
        try:
            logger.debug(f"Fetching status for job {job_name} in namespace {namespace}")
            
            with log_operation(logger, "get_job_status", job=job_name, namespace=namespace):
                logger.debug(f"Step 1: Sending read_namespaced_job request to Kubernetes API")
                job = self.k8s_batch_api.read_namespaced_job(
                    name=job_name,
                    namespace=namespace
                )
                logger.debug(f"Kubernetes API returned job object with status field")
                
                status = job.status
                
                # Step 2: Determine job state
                logger.debug(f"Step 2: Analyzing job status to determine state")
                if status.succeeded and status.succeeded > 0:
                    job_state = "completed"
                    logger.debug(f"Job state determined: completed (succeeded={status.succeeded})")
                elif status.failed and status.failed > 0:
                    job_state = "failed"
                    logger.debug(f"Job state determined: failed (failed={status.failed})")
                elif status.active and status.active > 0:
                    job_state = "running"
                    logger.debug(f"Job state determined: running (active={status.active})")
                else:
                    job_state = "unknown"
                    logger.debug(f"Job state determined: unknown (active={status.active}, succeeded={status.succeeded}, failed={status.failed})")
                
                # Step 3: Extract status fields
                logger.debug(f"Step 3: Extracting status fields")
                result = {
                    "job_name": job.metadata.name,
                    "namespace": job.metadata.namespace,
                    "state": job_state,
                    "active": status.active or 0,
                    "succeeded": status.succeeded or 0,
                    "failed": status.failed or 0,
                    "start_time": status.start_time.isoformat() if status.start_time else None,
                    "completion_time": status.completion_time.isoformat() if status.completion_time else None
                }
                logger.debug(f"Status response formatted: state={job_state}, active={result['active']}, succeeded={result['succeeded']}, failed={result['failed']}")
                
                return result
        
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Job {job_name} not found in namespace {namespace}")
                raise ApiException(
                    status=404,
                    reason=f"Job {job_name} not found in namespace {namespace}"
                )
            logger.error(f"Kubernetes API error fetching job status: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching job status: {str(e)}", exc_info=True)
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
        
        Implementation Steps:
        1. Build namespace manifest
        2. Send create_namespace request to Kubernetes API
        3. Return namespace metadata in structured response
        """
        from app.utils.logger import log_operation
        
        try:
            logger.debug(f"Creating namespace {namespace_name}")
            
            with log_operation(logger, "create_namespace", namespace=namespace_name):
                logger.debug(f"Step 1: Building namespace manifest for {namespace_name}")
                namespace_body = {
                    "apiVersion": "v1",
                    "kind": "Namespace",
                    "metadata": {
                        "name": namespace_name
                    }
                }
                logger.debug(f"Namespace manifest created with name={namespace_name}")
                
                logger.debug(f"Step 2: Sending create_namespace request to Kubernetes API")
                response = self.k8s_core_api.create_namespace(
                    body=namespace_body
                )
                logger.debug(f"Kubernetes API returned response with metadata: {response.metadata.name}")
                
                logger.debug(f"Step 3: Formatting response")
                result = {
                    "namespace_name": response.metadata.name,
                    "creation_timestamp": response.metadata.creation_timestamp.isoformat() if response.metadata.creation_timestamp else None,
                    "status": "created"
                }
                logger.debug(f"Namespace creation response ready: {result}")
                
                return result
        
        except ApiException as e:
            logger.error(f"Kubernetes API error creating namespace: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating namespace: {str(e)}", exc_info=True)
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
        
        Implementation Steps:
        1. Send delete_namespace request to Kubernetes API
        2. Use Foreground propagation policy for graceful deletion
        3. Return success confirmation
        """
        from app.utils.logger import log_operation
        
        try:
            logger.debug(f"Deleting namespace {namespace_name}")
            
            with log_operation(logger, "delete_namespace", namespace=namespace_name):
                logger.debug(f"Step 1: Sending delete_namespace request to Kubernetes API")
                self.k8s_core_api.delete_namespace(
                    name=namespace_name,
                    body=client.V1DeleteOptions(propagation_policy='Foreground')
                )
                logger.debug(f"Kubernetes API confirmed namespace deletion")
            
            logger.debug(f"Namespace {namespace_name} deletion request accepted")
            
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
            logger.error(f"Kubernetes API error deleting namespace: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting namespace: {str(e)}", exc_info=True)
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
