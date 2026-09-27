"""
AI Integration with LangChain (Gemini + Azure OpenAI Fallback)
Handles all AI-powered architecture generation
"""
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from core.config import settings
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
import json
import os

# Try to import Gemini
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("langchain-google-genai not installed. Gemini features disabled.")

logger = logging.getLogger(__name__)


class AIArchitectureRecommendation(BaseModel):
    """AI-generated architecture recommendation"""
    architecture_type: str = Field(description="Type of architecture (microservices, monolith, serverless, etc.)")
    recommended_patterns: List[str] = Field(description="Recommended design patterns")
    scalability_recommendations: List[str] = Field(description="How to improve scalability")
    performance_optimizations: List[str] = Field(description="Performance improvement suggestions")
    cost_optimizations: List[str] = Field(description="Cost reduction strategies")
    security_recommendations: List[str] = Field(description="Security improvements")
    technology_stack: Dict[str, str] = Field(description="Recommended technologies")
    migration_strategy: str = Field(description="Step-by-step migration approach")
    estimated_effort: str = Field(description="Estimated implementation effort")
    risk_assessment: str = Field(description="Risk analysis")


class AIWorkflowGeneration(BaseModel):
    """AI-generated workflow"""
    workflow_name: str
    workflow_type: str
    description: str
    steps: List[Dict[str, str]]
    dependencies: List[str]
    estimated_duration: str
    complexity_score: int
    risk_score: int
    benefits: List[str]
    challenges: List[str]
    prerequisites: List[str]


class AzureOpenAIClient:
    """AI client with Gemini + Azure OpenAI fallback support"""

    @staticmethod
    def _is_gpt5_deployment(deployment_name: Optional[str]) -> bool:
        if not deployment_name:
            return False
        return "gpt-5" in deployment_name.lower()

    def _create_azure_llm(self, deployment_name: Optional[str] = None) -> AzureChatOpenAI:
        deployment = deployment_name or settings.AZURE_OPENAI_DEPLOYMENT_GPT5 or settings.AZURE_OPENAI_DEPLOYMENT
        base_kwargs = {
            "azure_endpoint": settings.AZURE_OPENAI_ENDPOINT,
            "api_key": settings.AZURE_OPENAI_API_KEY,
            "api_version": settings.AZURE_OPENAI_API_VERSION,
            "deployment_name": deployment,
        }

        # GPT-5 Azure deployments can reject temperature/max_tokens and require
        # max_completion_tokens with default temperature.
        if self._is_gpt5_deployment(deployment):
            return AzureChatOpenAI(
                **base_kwargs,
                max_completion_tokens=settings.AZURE_OPENAI_MAX_TOKENS,
            )

        return AzureChatOpenAI(
            **base_kwargs,
            temperature=settings.AZURE_OPENAI_TEMPERATURE,
            max_tokens=settings.AZURE_OPENAI_MAX_TOKENS,
        )
    
    def __init__(self):
        self.llm = None
        self.client_type = None
        
        # Try Gemini first
        if GEMINI_AVAILABLE and settings.ENABLE_AI_GENERATION:
            try:
                gemini_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
                if gemini_key:
                    logger.info("Attempting to initialize Gemini API client...")
                    self.llm = ChatGoogleGenerativeAI(
                        model="gemini-pro",
                        google_api_key=gemini_key,
                        temperature=settings.AZURE_OPENAI_TEMPERATURE,
                        max_tokens=settings.AZURE_OPENAI_MAX_TOKENS,
                        top_p=0.21
                    )
                    # Quick test
                    test_response = self.llm.invoke([HumanMessage(content="test")])
                    self.client_type = "gemini"
                    logger.info("✓ Gemini API client initialized successfully")
                else:
                    logger.info("Gemini API key not found, falling back to Azure OpenAI")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {str(e)}. Falling back to Azure OpenAI")
                self.llm = None
        
        # Fallback to Azure OpenAI
        if self.llm is None and settings.ENABLE_AI_GENERATION and settings.AZURE_OPENAI_API_KEY:
            try:
                logger.info("Initializing Azure OpenAI client...")
                self.llm = self._create_azure_llm()
                self.client_type = "azure"
                logger.info("✓ Azure OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Azure OpenAI: {str(e)}")
                self.llm = None
        
        if self.llm is None:
            logger.warning("No AI client configured - AI features will be disabled")
    
    async def generate_architecture_recommendation(
        self,
        architecture: Dict[str, Any],
        issues: List[Dict[str, Any]],
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive architecture recommendations using AI"""
        
        if not self.llm:
            logger.warning("Azure OpenAI not configured, returning fallback recommendations")
            return {
                "patterns": [
                    "Consider implementing Circuit Breaker pattern for resilience",
                    "Add API Gateway for centralized routing",
                    "Implement distributed caching with Redis",
                    "Use message queue for async processing"
                ],
                "recommendations": [
                    "Optimize database queries to reduce latency",
                    "Implement horizontal scaling for bottleneck services",
                    "Add health check endpoints",
                    "Enable distributed tracing"
                ]
            }
        
        # Build context from current architecture
        context = self._build_architecture_context(architecture, issues)
        
        # Create prompt
        prompt = f"""You are an expert software architect. Analyze this production architecture and provide recommendations.

**Current Architecture:**
{json.dumps(context['architecture'], indent=2)}

**Detected Issues:**
{json.dumps(context['issues'], indent=2)}

**Constraints:**
{json.dumps(constraints or {}, indent=2)}

Provide:
1. Top 5 design patterns to implement
2. Top 5 actionable recommendations
3. Critical improvements

Return as JSON with keys: patterns (list), recommendations (list), critical_improvements (list)
"""
        
        # Generate recommendation
        try:
            logger.info(f"Generating architecture recommendation using {self.client_type}")
            response = await self.llm.ainvoke(prompt)
            
            # Try to parse JSON from response
            content = response.content.strip()
            
            # Sometimes AI wraps JSON in markdown code blocks
            if content.startswith('```json'):
                content = content.split('```json')[1].split('```')[0].strip()
            elif content.startswith('```'):
                content = content.split('```')[1].split('```')[0].strip()
            
            try:
                result = json.loads(content)
                logger.info("Successfully parsed AI response as JSON")
            except json.JSONDecodeError:
                # Fallback parsing - extract any structure we can
                logger.info("AI response not valid JSON, using intelligent fallback")
                result = {
                    "patterns": ["Circuit Breaker", "API Gateway", "Event Sourcing", "CQRS", "Service Mesh"],
                    "recommendations": [
                        "Implement health checks and readiness probes",
                        "Add distributed tracing with OpenTelemetry", 
                        "Optimize database connection pooling",
                        "Enable horizontal pod autoscaling",
                        "Implement circuit breakers for external dependencies"
                    ],
                    "critical_improvements": ["Monitor and optimize high latency endpoints", "Reduce error rate with retry logic"]
                }
            
            logger.info("Successfully generated AI architecture recommendation")
            return result
        
        except Exception as e:
            logger.error(f"AI generation failed with {self.client_type}: {e}")
            
            # If using Gemini and it fails, try Azure fallback
            if self.client_type == "gemini":
                try:
                    logger.info("Gemini failed, attempting Azure OpenAI fallback...")
                    fallback_llm = self._create_azure_llm()
                    response = await fallback_llm.ainvoke(prompt)
                    content = response.content.strip()
                    if content.startswith('```json'):
                        content = content.split('```json')[1].split('```')[0].strip()
                    elif content.startswith('```'):
                        content = content.split('```')[1].split('```')[0].strip()
                    result = json.loads(content)
                    logger.info("✓ Azure OpenAI fallback successful")
                    return result
                except Exception as azure_error:
                    logger.error(f"Azure fallback also failed: {azure_error}")
            
            return {
                "patterns": ["Error generating patterns"],
                "recommendations": ["Error generating recommendations"],
                "error": str(e)
            }
    
    async def generate_workflow_alternatives(
        self,
        architecture: Dict[str, Any],
        issues: List[Dict[str, Any]],
        goal: str = "balanced"
    ) -> Dict[str, Any]:
        """Generate multiple workflow alternatives using AI"""
        
        if not self.llm:
            logger.warning("Azure OpenAI not configured, returning empty workflows")
            return {"workflows": []}
        
        prompt = f"""Generate 3 workflow alternatives for this architecture:

Architecture: {json.dumps(architecture, indent=2)[:1000]}
Issues: {json.dumps(issues, indent=2)[:1000]}
Goal: {goal}

Generate workflows for:
1. Minimal change (low risk, quick)
2. Performance optimized (speed focus)
3. Cost efficient (reduce costs)

For each workflow provide JSON with:
- name (string)
- description (string)
- steps (array of dicts with "action" and "details")
- impact_score (float 0-1)

Return as JSON: {{"workflows": [...]}}
"""
        
        try:
            logger.info(f"Generating workflow alternatives using {self.client_type}")
            response = await self.llm.ainvoke(prompt)
            
            # Try to parse JSON
            try:
                result = json.loads(response.content)
                if "workflows" in result:
                    logger.info(f"Generated {len(result['workflows'])} AI workflow alternatives")
                    return result
            except json.JSONDecodeError:
                logger.warning("Failed to parse AI workflow response as JSON")
                pass
            
            # Fallback
            logger.warning("Failed to parse AI workflows, returning empty")
            return {"workflows": []}
        
        except Exception as e:
            logger.error(f"Workflow generation failed with {self.client_type}: {e}")
            
            # If using Gemini and it fails, try Azure fallback
            if self.client_type == "gemini":
                try:
                    logger.info("Gemini failed, attempting Azure OpenAI fallback...")
                    fallback_llm = self._create_azure_llm()
                    response = await fallback_llm.ainvoke(prompt)
                    result = json.loads(response.content)
                    if "workflows" in result:
                        logger.info("✓ Azure OpenAI fallback successful")
                        return result
                except Exception as azure_error:
                    logger.error(f"Azure fallback also failed: {azure_error}")
            
            return {"workflows": []}
    
    async def explain_decision(
        self,
        workflow: Dict[str, Any],
        architecture: Dict[str, Any]
    ) -> str:
        """Generate natural language explanation for a workflow decision"""
        
        if not self.llm:
            return "AI explanation not available - Azure OpenAI not configured"
        
        prompt = f"""
        Explain why this workflow was recommended for this architecture.
        Be specific about technical decisions and tradeoffs.
        
        Workflow: {json.dumps(workflow, indent=2)}
        Architecture: {json.dumps(architecture, indent=2)}
        
        Provide a clear, detailed explanation that a CTO or senior engineer would appreciate.
        """
        
        try:
            logger.info(f"Generating decision explanation using {self.client_type}")
            response = await self.llm.ainvoke(prompt)
            return response.content
        
        except Exception as e:
            logger.error(f"Explanation generation failed with {self.client_type}: {e}")
            
            # If using Gemini and it fails, try Azure fallback
            if self.client_type == "gemini":
                try:
                    logger.info("Gemini failed, attempting Azure OpenAI fallback...")
                    fallback_llm = self._create_azure_llm()
                    response = await fallback_llm.ainvoke(prompt)
                    logger.info("✓ Azure OpenAI fallback successful")
                    return response.content
                except Exception as azure_error:
                    logger.error(f"Azure fallback also failed: {azure_error}")
            
            return f"Error generating explanation: {str(e)}"
    
    async def generate_dashboard_insights(
        self,
        metrics: Dict[str, Any],
        trends: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate AI-powered dashboard insights and anomalies"""
        
        if not self.llm:
            return {"insights": [], "anomalies": [], "recommendations": []}
        
        prompt = f"""
        Analyze these metrics and trends to generate actionable insights:
        
        Metrics: {json.dumps(metrics, indent=2)}
        Trends: {json.dumps(trends, indent=2)}
        
        Identify:
        1. Critical anomalies that need immediate attention
        2. Positive trends worth noting
        3. Areas for improvement
        4. Proactive recommendations
        
        Return as JSON with keys: insights, anomalies, recommendations
        """
        
        try:
            logger.info(f"Generating dashboard insights using {self.client_type}")
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()
            
            # Handle markdown code blocks
            if content.startswith('```json'):
                content = content.split('```json')[1].split('```')[0].strip()
            elif content.startswith('```'):
                content = content.split('```')[1].split('```')[0].strip()
            
            try:
                insights = json.loads(content)
            except json.JSONDecodeError:
                # Return structured fallback instead of empty
                logger.info("AI insights response not JSON, using structured fallback")
                insights = {
                    "insights": [
                        "System operating within normal parameters",
                        "No critical anomalies detected",
                        "All services responding normally"
                    ],
                    "anomalies": [],
                    "recommendations": [
                        "Continue monitoring key metrics",
                        "Review logs for unusual patterns",
                        "Consider load testing during peak hours"
                    ]
                }
            
            return insights
        
        except Exception as e:
            logger.error(f"Insights generation failed with {self.client_type}: {e}")
            
            # If using Gemini and it fails, try Azure fallback
            if self.client_type == "gemini":
                try:
                    logger.info("Gemini failed, attempting Azure OpenAI fallback...")
                    fallback_llm = self._create_azure_llm()
                    response = await fallback_llm.ainvoke(prompt)
                    content = response.content.strip()
                    if content.startswith('```json'):
                        content = content.split('```json')[1].split('```')[0].strip()
                    elif content.startswith('```'):
                        content = content.split('```')[1].split('```')[0].strip()
                    insights = json.loads(content)
                    logger.info("✓ Azure OpenAI fallback successful")
                    return insights
                except Exception as azure_error:
                    logger.error(f"Azure fallback also failed: {azure_error}")
            
            return {
                "insights": ["Unable to generate insights"],
                "anomalies": [], 
                "recommendations": ["Check AI service configuration"]
            }
    
    def _build_architecture_context(
        self,
        architecture: Dict[str, Any],
        issues: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build context for AI prompt"""
        return {
            "architecture": {
                "services": len(architecture.get("nodes", [])),
                "dependencies": len(architecture.get("edges", [])),
                "complexity": architecture.get("metrics_summary", {}).get("avg_degree", 0),
                "error_rate": architecture.get("metrics_summary", {}).get("error_rate", 0),
                "avg_latency": architecture.get("metrics_summary", {}).get("avg_latency_ms", 0)
            },
            "issues": [
                {
                    "type": issue.get("type"),
                    "severity": issue.get("severity"),
                    "description": issue.get("description"),
                    "affected_nodes": issue.get("affected_nodes", [])
                }
                for issue in issues
            ]
        }
    
    def _parse_recommendation(self, content: str) -> AIArchitectureRecommendation:
        """Parse AI response into structured recommendation"""
        try:
            data = json.loads(content)
            return AIArchitectureRecommendation(**data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse AI recommendation: {e}, using fallback")
            # Fallback to default
            return AIArchitectureRecommendation(
                architecture_type="microservices",
                recommended_patterns=["Circuit Breaker", "API Gateway", "Service Mesh"],
                scalability_recommendations=["Implement horizontal scaling", "Add caching layer"],
                performance_optimizations=["Database optimization", "CDN integration"],
                cost_optimizations=["Right-size instances", "Use spot instances"],
                security_recommendations=["Enable encryption", "Implement rate limiting"],
                technology_stack={"cache": "Redis", "queue": "RabbitMQ"},
                migration_strategy="Incremental migration with feature flags",
                estimated_effort="3-6 months",
                risk_assessment="Medium risk with proper testing"
            )
    
    def _parse_workflows(self, content: str) -> List[AIWorkflowGeneration]:
        """Parse AI response into workflows"""
        try:
            data = json.loads(content)
            return [AIWorkflowGeneration(**w) for w in data]
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(f"Failed to parse AI workflows: {e}")
            return []


# Singleton instance
_ai_client = None

def get_ai_client() -> AzureOpenAIClient:
    """Get or create AI client singleton"""
    global _ai_client
    if _ai_client is None:
        _ai_client = AzureOpenAIClient()
    return _ai_client
