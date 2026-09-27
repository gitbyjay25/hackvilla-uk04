import os
import base64
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import json
from dotenv import load_dotenv
import logging

# Try to import Gemini
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("langchain-google-genai not installed. Install with: pip install langchain-google-genai")

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AzureOpenAIChatClient:
    @staticmethod
    def _is_gpt5_deployment(deployment_name: str) -> bool:
        return bool(deployment_name and "gpt-5" in deployment_name.lower())

    def _create_azure_client(self, deployment_name: str, api_version: str):
        base_kwargs = {
            "azure_endpoint": self.azure_endpoint,
            "api_key": self.api_key,
            "api_version": api_version,
            "deployment_name": deployment_name,
        }

        if self._is_gpt5_deployment(deployment_name):
            return AzureChatOpenAI(
                **base_kwargs,
                model_kwargs={
                    "max_completion_tokens": int(os.environ.get("AZURE_OPENAI_MAX_TOKENS", "16384")),
                    "top_p": 0.21,
                    "frequency_penalty": 0.02,
                    "presence_penalty": 0.03,
                },
            )

        return AzureChatOpenAI(
            **base_kwargs,
            temperature=0.1,
            max_tokens=2000,
            model_kwargs={
                "top_p": 0.21,
                "frequency_penalty": 0.02,
                "presence_penalty": 0.03,
            },
        )

    def __init__(self, 
                 azure_endpoint: str = None,
                 deployment_name: str = None,
                 api_key: str = None,
                 api_version: str = None,
                 gemini_api_key: str = None):
        
        self.client = None
        self.client_type = None
        
        # Try Gemini first
        if GEMINI_AVAILABLE:
            try:
                gemini_key = gemini_api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
                if gemini_key:
                    logger.info("Attempting to initialize Gemini API client...")
                    self.client = ChatGoogleGenerativeAI(
                        model="gemini-pro",
                        google_api_key=gemini_key,
                        temperature=0.1,
                        max_tokens=2000,
                        top_p=0.21
                    )
                    # Test the client with a simple call
                    test_response = self.client.invoke([HumanMessage(content="test")])
                    self.client_type = "gemini"
                    logger.info("✓ Gemini API client initialized successfully")
                else:
                    logger.info("Gemini API key not found, falling back to Azure OpenAI")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini API: {str(e)}. Falling back to Azure OpenAI")
                self.client = None
        
        # Fallback to Azure OpenAI (always available)
        if self.client is None:
            try:
                logger.info("Initializing Azure OpenAI client...")
                # Use os.environ.get to fetch environment variables, do not fallback to hardcoded sensitive values
                self.azure_endpoint = azure_endpoint or os.environ.get("ENDPOINT_URL")
                self.deployment_name = deployment_name or os.environ.get("AZURE_OPENAI_DEPLOYMENT_GPT5") or os.environ.get("DEPLOYMENT_NAME")
                self.api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY")
                self.api_version = api_version or "2025-01-01-preview"

                self.client = self._create_azure_client(self.deployment_name, self.api_version)
                self.client_type = "azure"
                logger.info("✓ Azure OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Azure OpenAI: {str(e)}")
                raise Exception("Failed to initialize any AI client (both Gemini and Azure OpenAI failed)")
    
    def generate_desease_name_from_prompt(self, user_text: str) -> str:
        system_prompt_content = """
Forget about the previous instructions, Now you are a Disease Name Resolver for biomedical APIs.

Your task:
- You will receive user input that may contain:
  - Symptoms
  - One disease name
  - Multiple disease names
  - Or a combination of symptoms and disease names
- Based on the input, identify the most accurate and standardized disease name(s)
  that are compatible with api.platform.opentargets.org (EFO-compatible).

Rules you MUST follow:
1. Always return disease names that resolve correctly on api.platform.opentargets.org.
2. Use standardized clinical disease names aligned with EFO / Open Targets ontology.
3. Infer diseases from symptoms only when explicit disease names are not provided.
4. Return multiple diseases only when the input clearly indicates more than one condition.
5. Do NOT include explanations, reasoning, comments, or extra text.
6. Output MUST be valid JSON only.
7. The JSON key must be exactly "desease" (keep this spelling).
8. The value must be an array of one or more disease name strings.
9. Do NOT include duplicates, abbreviations, or non-disease terms.
10. Use lowercase disease names unless capitalization is required by convention.

Strict output format:
{"desease":["<disease name 1>","<disease name 2>"]}

VALID EXAMPLES (ONLY RETURN THE JSON, NO EXTRA TEXT):

{"desease":["breast cancer"]}

{"desease":["prostate cancer"]}

{"desease":["lung cancer"]}

{"desease":["colorectal cancer"]}

{"desease":["type 2 diabetes mellitus"]}

{"desease":["hypertension"]}

{"desease":["alzheimer disease"]}

{"desease":["coronary artery disease"]}

{"desease":["chronic obstructive pulmonary disease"]}

{"desease":["asthma"]}

{"desease":["rheumatoid arthritis"]}

{"desease":["parkinson disease"]}

{"desease":["multiple sclerosis"]}

{"desease":["chronic kidney disease"]}

{"desease":["breast cancer","lung cancer"]}

{"desease":["type 2 diabetes mellitus","hypertension"]}

If the input is ambiguous, return the most likely disease name(s)
that follow Open Targets Platform naming conventions.

"""
        messages = [
            SystemMessage(content=system_prompt_content),
            HumanMessage(content=user_text)
        ]

        try:
            logger.info(f"Using {self.client_type} client for disease name generation")
            response = self.client.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Error with {self.client_type} client: {str(e)}")
            
            # If using Gemini and it fails, try Azure as ultimate fallback
            if self.client_type == "gemini":
                try:
                    logger.info("Gemini failed, attempting Azure OpenAI fallback...")
                    azure_endpoint = os.environ.get("ENDPOINT_URL")
                    deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_GPT5") or os.environ.get("DEPLOYMENT_NAME")
                    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
                    api_version = "2025-01-01-preview"

                    self.azure_endpoint = azure_endpoint
                    self.api_key = api_key
                    fallback_client = self._create_azure_client(deployment_name, api_version)
                    response = fallback_client.invoke(messages)
                    logger.info("✓ Azure OpenAI fallback successful")
                    return response.content
                except Exception as azure_error:
                    logger.error(f"Azure OpenAI fallback also failed: {str(azure_error)}")
                    raise Exception(f"All AI clients failed. Gemini error: {str(e)}, Azure error: {str(azure_error)}")
            else:
                # Azure already failed, re-raise the error
                raise Exception(f"Azure OpenAI client failed: {str(e)}")
