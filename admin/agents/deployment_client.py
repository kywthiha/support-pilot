"""Cloud Run deployment client for spinning up agent instances."""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import run_v2

logger = logging.getLogger(__name__)

# Load env variables explicitly for deployment client
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / '.env')

# Usually the default project and location. 
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

# The base agent Docker image (assumes it is pre-built and available in Artifact Registry)
# During the hackathon you might use your GCR or AR URL here.
# Default to a standard name, but ideally set via env var.
BASE_AGENT_IMAGE = os.environ.get(
    "BASE_AGENT_IMAGE",
    f"gcr.io/{PROJECT_ID}/supportpilot-agent:latest"
)


def deploy_agent_service(agent_id: str, agent_key: str) -> str:
    """
    Deploys a Cloud Run service using the predefined agent image,
    injecting the specific AGENT_ID dynamically.
    Returns the service URL.
    """
    # Create the Cloud Run Services client
    client = run_v2.ServicesClient()

    # The parent location
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}"

    # Service name must be lowercase alphanumeric and hyphens only
    # agent_key is already slugified
    service_id = f"agent-{agent_key}"
    service_name = f"{parent}/services/{service_id}"
    
    # We will define the full service definition
    service = run_v2.Service()
    service.template = run_v2.RevisionTemplate()

    # Basic container setup
    container = run_v2.Container()
    container.image = BASE_AGENT_IMAGE

    # Set the crucial environment variables
    env_vars = []
    
    # Core Agent Config
    env_vars.append(run_v2.EnvVar(name="AGENT_ID", value=agent_id))
    env_vars.append(run_v2.EnvVar(name="AGENT_KEY", value=agent_key))
    
    # Models
    env_vars.append(run_v2.EnvVar(name="AGENT_MODEL", value=os.environ.get("AGENT_MODEL", "gemini-live-2.5-flash-native-audio")))
    env_vars.append(run_v2.EnvVar(name="OBSERVE_MODEL", value=os.environ.get("OBSERVE_MODEL", "gemini-3-flash-preview")))
    
    # Vertex / Project config
    env_vars.append(run_v2.EnvVar(name="GOOGLE_GENAI_USE_VERTEXAI", value=os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")))
    env_vars.append(run_v2.EnvVar(name="GOOGLE_CLOUD_PROJECT", value=PROJECT_ID))
    env_vars.append(run_v2.EnvVar(name="GOOGLE_CLOUD_LOCATION", value=LOCATION))

    container.env = env_vars

    service.template.containers = [container]
    
    # Increase the request timeout to 60 minutes (3600 seconds) - maximum allowed by Cloud Run
    import google.protobuf.duration_pb2 as duration_pb2
    service.template.timeout = duration_pb2.Duration(seconds=3600)
    
    # Make it publicly accessible (or require IAM - usually public for websockets)
    # We set ingress to ALL
    service.ingress = run_v2.IngressTraffic.INGRESS_TRAFFIC_ALL

    try:
        # Check if service exists
        try:
            client.get_service(name=service_name)
            exists = True
        except Exception:
            exists = False

        if exists:
            logger.info("Updating existing Cloud Run service: %s", service_name)
            request = run_v2.UpdateServiceRequest(service=service)
            request.service.name = service_name
            operation = client.update_service(request=request)
        else:
            logger.info("Creating new Cloud Run service: %s", service_name)
            request = run_v2.CreateServiceRequest(
                parent=parent,
                service=service,
                service_id=service_id,
            )
            operation = client.create_service(request=request)

        # Wait for the operation to complete
        logger.info("Waiting for deployment operation to complete...")
        response = operation.result(timeout=600) # 10 min timeout
        
        # After creating the service, we must also ensure unauthenticated invocation is allowed 
        # so customer browsers can hit the WebSocket.
        try:
            from google.iam.v1 import iam_policy_pb2, policy_pb2
            policy = client.get_iam_policy(request={"resource": service_name})
            
            # Check if allUsers is already bound
            is_public = any(
                binding.role == "roles/run.invoker" and "allUsers" in binding.members
                for binding in policy.bindings
            )
            
            if not is_public:
                logger.info("Setting IAM policy to allow unauthenticated invocations...")
                binding = policy_pb2.Binding()
                binding.role = "roles/run.invoker"
                binding.members.extend(["allUsers"])
                policy.bindings.extend([binding])
                
                request = iam_policy_pb2.SetIamPolicyRequest(
                    resource=service_name,
                    policy=policy
                )
                client.set_iam_policy(request=request)
                logger.info("IAM policy set successfully.")
        except Exception as iam_exc:
            logger.warning("Failed to set IAM policy (service might not be public): %s", iam_exc)

        logger.info("Deployment successful! URL: %s", response.uri)
        return response.uri

    except Exception as exc:
        logger.error("Failed to deploy agent service %s: %s", service_id, exc)
        raise
