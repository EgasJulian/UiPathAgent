import requests
import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class UiPathManager:
    """
    Manager for UiPath Orchestrator integration to trigger RPA workflows.
    Handles authentication and job execution for automated processes.
    """

    def __init__(self):
        # Load configuration from environment variables
        self.organization = os.getenv("UIPATH_ORGANIZATION", "minsacsvndlb")
        self.tenant = os.getenv("UIPATH_TENANT", "CO_DEMO")
        self.pat = os.getenv("UIPATH_PAT", "rt_BA202D4B901AD1687937668565CEE96EBDCCAA9B0A73021A69FB2AFFF59CA5FB-1")
        self.process_name = os.getenv("UIPATH_PROCESS_NAME", "RPA.Workflow")

        if not all([self.organization, self.tenant, self.pat, self.process_name]):
            raise ValueError("Missing required UiPath environment variables")

        # Build Orchestrator Cloud base URL
        self.base_url = f'https://cloud.uipath.com/{self.organization}/{self.tenant}/orchestrator_/odata/'

        # Headers with PAT token for general operations
        self.headers = {
            'Authorization': f'Bearer {self.pat}',
            'Content-Type': 'application/json'
        }

        # Headers with PAT token and OrganizationUnitId for robot/job operations
        self.robot_headers = {
            'Authorization': f'Bearer {self.pat}',
            'Content-Type': 'application/json',
            'X-UIPATH-OrganizationUnitId': '421017'
        }

        logger.info(f"UiPathManager initialized for organization: {self.organization}, tenant: {self.tenant}")

    async def trigger_dashboard_workflow(self, user_question: str = None, user_email: str = None, question_case: str = None) -> Dict:
        """
        Triggers the UiPath workflow specifically for dashboard billing inquiries.

        Args:
            user_question: The original user question that triggered this workflow
            user_email: The validated email to pass as input argument to UiPath
            question_case: The specific question case/button text to pass as input argument

        Returns:
            Dict with job execution results and status information
        """
        try:
            logger.info(f"[UIPATH] Triggering dashboard workflow for question: {user_question[:50] if user_question else 'N/A'}...")

            # 1. Get ReleaseKey for the process
            params = {"$filter": f"Name eq '{self.process_name}'"}
            res = requests.get(self.base_url + "Releases", headers=self.headers, params=params)
            res.raise_for_status()

            releases = res.json().get("value", [])
            if not releases:
                raise Exception(f"Process '{self.process_name}' not found in UiPath Orchestrator")

            release_key = releases[0]["Key"]
            logger.info(f"[UIPATH] Found process release key: {release_key}")

            # 2. Prepare input arguments with validated email and question case
            arguments = {}

            if user_email:
                arguments["InCorreo"] = user_email
                logger.info(f"[UIPATH] Using email for InCorreo parameter: {user_email}")
            else:
                logger.warning("[UIPATH] No email provided for InCorreo parameter")

            if question_case:
                arguments["InCaso"] = question_case
                logger.info(f"[UIPATH] Using question case for InCaso parameter: {question_case[:50]}...")
            else:
                logger.warning("[UIPATH] No question case provided for InCaso parameter")

            # Convert to JSON string format required by UiPath
            if arguments:
                import json
                input_arguments = json.dumps(arguments, ensure_ascii=False)
                logger.info(f"[UIPATH] Final InputArguments: {input_arguments}")
            else:
                input_arguments = "{}"
                logger.warning("[UIPATH] Using empty InputArguments as no parameters provided")

            # 3. Start job (following the exact pattern from working script)
            start_job_url = self.base_url + "Jobs/UiPath.Server.Configuration.OData.StartJobs"

            data = {
                "startInfo": {
                    "ReleaseKey": release_key,
                    "Strategy": "ModernJobsCount",
                    "RuntimeType": "Development",
                    "JobsCount": 1,
                    "Source": "Manual",      # Required in Cloud
                    "InputArguments": input_arguments,  # Dynamic input arguments with email
                    "JobPriority": "Normal"
                }
            }

            res = requests.post(start_job_url, headers=self.robot_headers, json=data)
            res.raise_for_status()
            job_info = res.json()

            logger.info(f"[UIPATH] Job started successfully: {job_info}")

            # Extract relevant information for response
            job_data = job_info.get("value", [{}])[0] if job_info.get("value") else {}

            return {
                "status": "success",
                "job_id": job_data.get("Id", "unknown"),
                "job_key": job_data.get("Key", "unknown"),
                "release_name": self.process_name,
                "message": "Proceso UiPath iniciado exitosamente para consulta de facturación",
                "details": {
                    "organization": self.organization,
                    "tenant": self.tenant,
                    "input_question": user_question,
                    "input_email": user_email,
                    "input_question_case": question_case,
                    "input_arguments": input_arguments,
                    "job_priority": "Normal",
                    "execution_strategy": "ModernJobsCount"
                }
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"[UIPATH] Request failed: {e}")
            return {
                "status": "error",
                "error_type": "request_failed",
                "message": f"Error de conexión con UiPath Orchestrator: {str(e)}",
                "details": {"original_error": str(e)}
            }
        except Exception as e:
            logger.error(f"[UIPATH] Unexpected error: {e}")
            return {
                "status": "error",
                "error_type": "general_error",
                "message": f"Error ejecutando workflow UiPath: {str(e)}",
                "details": {"original_error": str(e)}
            }

    async def check_job_status(self, job_id: str) -> Dict:
        """
        Check the status of a running UiPath job.

        Args:
            job_id: The ID of the job to check

        Returns:
            Dict with current job status information
        """
        try:
            job_url = f"{self.base_url}Jobs({job_id})"
            res = requests.get(job_url, headers=self.robot_headers)
            res.raise_for_status()

            job_data = res.json()

            return {
                "status": "success",
                "job_status": job_data.get("State", "Unknown"),
                "job_id": job_id,
                "details": job_data
            }

        except Exception as e:
            logger.error(f"[UIPATH] Error checking job status: {e}")
            return {
                "status": "error",
                "message": f"Error verificando estado del job: {str(e)}"
            }

# Global instance
uipath_manager = None

def get_uipath_manager() -> UiPathManager:
    """
    Get or create the global UiPathManager instance.
    """
    global uipath_manager
    if uipath_manager is None:
        try:
            uipath_manager = UiPathManager()
        except Exception as e:
            logger.error(f"Failed to initialize UiPathManager: {e}")
            raise
    return uipath_manager