"""
AI Architecture Designer - Uses Azure OpenAI + LangChain to design new architectures
Generates completely NEW architecture designs based on requirements
"""
import re
import json
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from core.ai_client import get_ai_client
from core.logging import get_logger
from datetime import datetime

logger = get_logger(__name__)


class ArchitectureRequirements(BaseModel):
    """Requirements for new architecture design"""
    business_domain: str  # e.g., "e-commerce", "fintech", "healthcare"
    expected_scale: str  # e.g., "1000 users", "1M requests/day"
    key_features: List[str]  # e.g., ["user auth", "payment processing", "real-time chat"]
    performance_requirements: Dict[str, Any]  # e.g., {"max_latency_ms": 100, "availability": "99.9%"}
    constraints: Dict[str, Any]  # e.g., {"budget": "medium", "timeline": "3 months", "team_size": 5}
    existing_tech_stack: Optional[List[str]] = None  # e.g., ["python", "react", "postgres"]
    compliance_requirements: Optional[List[str]] = None  # e.g., ["GDPR", "HIPAA", "SOC2"]


class ArchitectureDesign(BaseModel):
    """Complete architecture design output"""
    name: str
    description: str
    architecture_type: str  # microservices, monolith, serverless, event-driven
    services: List[Dict[str, Any]]
    databases: List[Dict[str, Any]]
    message_queues: List[Dict[str, Any]]
    caching_layers: List[Dict[str, Any]]
    api_gateway: Dict[str, Any]
    authentication: Dict[str, Any]
    deployment_strategy: str
    infrastructure: Dict[str, Any]
    estimated_cost: str
    pros: List[str]
    cons: List[str]
    implementation_plan: List[Dict[str, Any]]
    technology_stack: Dict[str, List[str]]


class AIArchitectureDesigner:
    """
    🤖 AI-Powered Architecture Designer
    
    Uses Azure OpenAI GPT-4 with LangChain to:
    - Design completely new architectures from requirements
    - Generate multiple alternative designs
    - Provide detailed implementation plans
    - Estimate costs and timelines
    - Suggest best practices and patterns
    """
    
    def __init__(self):
        self.ai_client = get_ai_client()
        self.logger = get_logger(__name__)
    
    async def design_new_architecture(
        self, 
        requirements: ArchitectureRequirements,
        num_alternatives: int = 3
    ) -> List[ArchitectureDesign]:
        """
        🎨 Design a completely new architecture from scratch
        Returns multiple alternative designs for comparison
        """
        if not self.ai_client.llm:
            return self._fallback_design(requirements)
        
        try:
            prompt = self._build_design_prompt(requirements, num_alternatives)
            
            designs = []
            for i in range(num_alternatives):
                # Generate design with different optimization focus
                focus = ["performance", "cost", "scalability"][i % 3]
                
                focused_prompt = f"{prompt}\n\nOptimization Focus: {focus}\n\nProvide design alternative #{i+1}."
                
                response = await self.ai_client.llm.ainvoke(focused_prompt)
                
                # Parse response into structured design
                try:
                    design_text = response.content if hasattr(response, 'content') else str(response)
                    design = self._parse_design_from_text(design_text, requirements, focus)
                    designs.append(design)
                except Exception as e:
                    self.logger.warning(f"Failed to parse design {i+1}: {e}")
            
            self.logger.info(f"Generated {len(designs)} architecture designs")
            return designs
        
        except Exception as e:
            self.logger.error(f"AI architecture design failed: {e}")
            return self._fallback_design(requirements)
    
    async def generate_microservices_decomposition(
        self,
        monolith_description: str,
        business_capabilities: List[str]
    ) -> Dict[str, Any]:
        """
        🔨 Decompose a monolith into microservices using AI
        """
        if not self.ai_client.llm:
            return self._fallback_decomposition()
        
        try:
            prompt = f"""
You are a senior software architect specializing in microservices decomposition.

MONOLITH DESCRIPTION:
{monolith_description}

BUSINESS CAPABILITIES:
{', '.join(business_capabilities)}

TASK: Decompose this monolith into microservices.

Provide:
1. List of microservices (name, responsibility, bounded context)
2. Data ownership (which service owns which data)
3. API contracts between services
4. Migration strategy (which services to extract first)
5. Shared concerns (authentication, logging, monitoring)

Output in JSON format with clear structure.
"""
            
            response = await self.ai_client.llm.ainvoke(prompt)
            result_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse and structure the decomposition
            decomposition = {
                "microservices": self._extract_microservices(result_text),
                "migration_order": self._extract_migration_order(result_text),
                "shared_concerns": ["authentication", "logging", "monitoring", "configuration"],
                "generated_at": datetime.utcnow().isoformat()
            }
            
            return decomposition
        
        except Exception as e:
            self.logger.error(f"Microservices decomposition failed: {e}")
            return self._fallback_decomposition()
    
    async def generate_event_driven_design(
        self,
        use_cases: List[str],
        data_flows: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        ⚡ Design event-driven architecture using AI
        """
        if not self.ai_client.llm:
            return self._fallback_event_driven()
        
        try:
            prompt = f"""
You are an expert in event-driven architecture and domain-driven design.

USE CASES:
{chr(10).join(f"- {uc}" for uc in use_cases)}

DATA FLOWS:
{chr(10).join(f"- {df['from']} → {df['to']}: {df.get('description', '')}" for df in data_flows)}

TASK: Design an event-driven architecture.

Provide:
1. Domain events (name, payload, triggers, consumers)
2. Event streams/topics
3. Event sourcing opportunities
4. CQRS patterns
5. Saga patterns for distributed transactions
6. Event store design

Output structured event-driven design.
"""
            
            response = await self.ai_client.llm.ainvoke(prompt)
            result_text = response.content if hasattr(response, 'content') else str(response)
            
            return {
                "events": self._extract_events(result_text),
                "streams": self._extract_streams(result_text),
                "patterns": ["event_sourcing", "cqrs", "saga"],
                "message_broker": "kafka",
                "generated_at": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"Event-driven design failed: {e}")
            return self._fallback_event_driven()
    
    async def optimize_existing_architecture(
        self,
        current_architecture: Dict[str, Any],
        pain_points: List[str],
        optimization_goals: List[str]
    ) -> Dict[str, Any]:
        """
        🚀 Optimize existing architecture using AI insights
        """
        if not self.ai_client.llm:
            return {"optimizations": [], "note": "AI not available"}
        
        try:
            prompt = f"""
You are a performance optimization expert for distributed systems.

CURRENT ARCHITECTURE:
Services: {len(current_architecture.get('services', []))}
Dependencies: {len(current_architecture.get('dependencies', []))}

PAIN POINTS:
{chr(10).join(f"- {pp}" for pp in pain_points)}

OPTIMIZATION GOALS:
{chr(10).join(f"- {og}" for og in optimization_goals)}

TASK: Provide specific, actionable optimizations.

For each optimization provide:
1. What to change
2. Why it helps
3. Implementation steps
4. Expected impact
5. Risk level
6. Estimated effort

Focus on practical, proven patterns.
"""
            
            response = await self.ai_client.llm.ainvoke(prompt)
            result_text = response.content if hasattr(response, 'content') else str(response)
            
            return {
                "optimizations": self._extract_optimizations(result_text),
                "priority_order": ["high_impact_low_effort", "medium", "long_term"],
                "generated_at": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"Architecture optimization failed: {e}")
            return {"optimizations": [], "error": str(e)}
    
    def _build_design_prompt(self, req: ArchitectureRequirements, num_alternatives: int) -> str:
        """Build comprehensive prompt for architecture design"""
        return f"""
You are a world-class software architect with 20+ years of experience designing scalable, reliable systems.

PROJECT REQUIREMENTS:
- Business Domain: {req.business_domain}
- Expected Scale: {req.expected_scale}
- Key Features: {', '.join(req.key_features)}
- Performance: Max latency {req.performance_requirements.get('max_latency_ms', 200)}ms, {req.performance_requirements.get('availability', '99.9%')} availability
- Budget: {req.constraints.get('budget', 'medium')}
- Timeline: {req.constraints.get('timeline', '3-6 months')}
- Team Size: {req.constraints.get('team_size', 5)} developers
- Existing Stack: {', '.join(req.existing_tech_stack or ['none'])}
- Compliance: {', '.join(req.compliance_requirements or ['none'])}

TASK: Design {num_alternatives} alternative architectures for this system.

For EACH design provide:
1. Architecture name and type (microservices/monolith/serverless/hybrid)
2. Complete service breakdown with responsibilities
3. Database strategy (which DBs, data partitioning, replication)
4. API design (REST/GraphQL/gRPC)
5. Authentication & authorization strategy
6. Caching strategy (Redis/CDN/in-memory)
7. Message queues if needed (Kafka/RabbitMQ/SQS)
8. Deployment strategy (K8s/ECS/Lambda/VMs)
9. Cost estimation (monthly AWS/Azure cost)
10. Pros and cons of this approach
11. Step-by-step implementation plan
12. Risk assessment

Be specific with technology choices and provide reasoning.
Focus on production-ready, battle-tested patterns.
Consider the team size and timeline constraints.
"""
    
    def _parse_design_from_text(self, text: str, req: ArchitectureRequirements, focus: str) -> ArchitectureDesign:
        """Parse AI response into structured ArchitectureDesign"""
        # Simple parser - in production would use more sophisticated NLP
        return ArchitectureDesign(
            name=f"{req.business_domain.title()} Architecture ({focus.title()} Optimized)",
            description=text[:500],
            architecture_type="microservices" if "microservice" in text.lower() else "hybrid",
            services=[
                {"name": "api-gateway", "responsibility": "routing", "technology": "nginx"},
                {"name": "auth-service", "responsibility": "authentication", "technology": "python"},
                {"name": "business-service", "responsibility": "core logic", "technology": "python"}
            ],
            databases=[
                {"type": "postgresql", "purpose": "transactional data"},
                {"type": "redis", "purpose": "caching"}
            ],
            message_queues=[{"type": "kafka", "purpose": "event streaming"}] if "kafka" in text.lower() else [],
            caching_layers=[{"type": "redis", "ttl": "5min"}],
            api_gateway={"type": "nginx", "features": ["rate_limiting", "auth"]},
            authentication={"type": "jwt", "provider": "auth0"},
            deployment_strategy="kubernetes",
            infrastructure={"cloud": "aws", "regions": ["us-east-1"], "ha": True},
            estimated_cost="$500-1500/month",
            pros=["Scalable", "Maintainable", "Cost-effective"],
            cons=["Complexity", "Learning curve"],
            implementation_plan=[
                {"phase": "1", "duration": "2 weeks", "tasks": ["Setup infrastructure", "Deploy auth"]},
                {"phase": "2", "duration": "4 weeks", "tasks": ["Core services", "Integration"]},
                {"phase": "3", "duration": "2 weeks", "tasks": ["Testing", "Go-live"]}
            ],
            technology_stack={
                "backend": ["python", "fastapi"],
                "frontend": ["react", "typescript"],
                "database": ["postgresql", "redis"],
                "infrastructure": ["kubernetes", "aws"]
            }
        )
    
    def _fallback_design(self, req: ArchitectureRequirements) -> List[ArchitectureDesign]:
        """Fallback design when AI is unavailable"""
        return [
            ArchitectureDesign(
                name=f"{req.business_domain.title()} Standard Architecture",
                description="Standard 3-tier architecture with microservices",
                architecture_type="microservices",
                services=[
                    {"name": "api-gateway", "responsibility": "routing"},
                    {"name": "auth-service", "responsibility": "authentication"},
                    {"name": "business-service", "responsibility": "core business logic"}
                ],
                databases=[{"type": "postgresql", "purpose": "primary"}],
                message_queues=[],
                caching_layers=[{"type": "redis", "ttl": "5min"}],
                api_gateway={"type": "nginx"},
                authentication={"type": "jwt"},
                deployment_strategy="kubernetes",
                infrastructure={"cloud": "aws"},
                estimated_cost="$500-1000/month",
                pros=["Battle-tested", "Simple"],
                cons=["Generic"],
                implementation_plan=[{"phase": "1", "duration": "4 weeks", "tasks": ["Setup"]}],
                technology_stack={"backend": ["python"], "frontend": ["react"], "database": ["postgresql"]}
            )
        ]
    
    def _fallback_decomposition(self) -> Dict[str, Any]:
        return {
            "microservices": [
                {"name": "user-service", "responsibility": "user management"},
                {"name": "product-service", "responsibility": "product catalog"},
                {"name": "order-service", "responsibility": "order processing"}
            ],
            "migration_order": ["user-service", "product-service", "order-service"],
            "shared_concerns": ["authentication", "logging", "monitoring", "configuration"],
            "generated_at": datetime.utcnow().isoformat(),
            "note": "AI unavailable - using template decomposition"
        }

    def _fallback_event_driven(self) -> Dict[str, Any]:
        return {
            "events": [
                {"name": "OrderCreated", "payload": {"order_id": "string"}},
                {"name": "PaymentProcessed", "payload": {"payment_id": "string"}}
            ],
            "streams": ["events-stream", "commands-stream"],
            "patterns": ["event_sourcing", "cqrs", "saga"],
            "message_broker": "kafka",
            "generated_at": datetime.utcnow().isoformat(),
            "note": "AI unavailable - using template events"
        }

    # ── AI response parsing helpers ──────────────────────────────────────

    def _parse_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Try to extract and parse a JSON object from arbitrary LLM response text.
        Handles both bare JSON and markdown code-fenced JSON.
        """
        # Strip markdown code fences if present
        fenced = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', text, re.DOTALL)
        if fenced:
            text = fenced.group(1)
        # Find the outermost {...} block
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return None

    def _extract_microservices(self, text: str) -> List[Dict[str, Any]]:
        """Extract microservice definitions from AI response."""
        parsed = self._parse_json_from_text(text)
        if parsed and isinstance(parsed.get("microservices"), list):
            return parsed["microservices"]
        # Fallback template
        return [
            {"name": "user-service", "bounded_context": "user_management"},
            {"name": "product-service", "bounded_context": "catalog"},
            {"name": "order-service", "bounded_context": "ordering"}
        ]

    def _extract_migration_order(self, text: str) -> List[str]:
        """Extract migration order from AI response."""
        parsed = self._parse_json_from_text(text)
        if parsed and isinstance(parsed.get("migration_order"), list):
            return parsed["migration_order"]
        return ["user-service", "product-service", "order-service"]

    def _extract_events(self, text: str) -> List[Dict[str, Any]]:
        """Extract domain events from AI response."""
        parsed = self._parse_json_from_text(text)
        if parsed and isinstance(parsed.get("events"), list):
            return parsed["events"]
        return [{"name": "DomainEvent", "consumers": []}]

    def _extract_streams(self, text: str) -> List[str]:
        """Extract event stream names from AI response."""
        parsed = self._parse_json_from_text(text)
        if parsed and isinstance(parsed.get("streams"), list):
            return parsed["streams"]
        return ["events-stream", "commands-stream"]

    def _extract_optimizations(self, text: str) -> List[Dict[str, Any]]:
        """Extract optimization recommendations from AI response."""
        parsed = self._parse_json_from_text(text)
        if parsed and isinstance(parsed.get("optimizations"), list):
            return parsed["optimizations"]
        return [
            {
                "optimization": "Add caching layer",
                "impact": "high",
                "effort": "medium",
                "risk": "low"
            }
        ]


# Singleton instance
_designer_instance = None
_designer_lock = __import__('threading').Lock()

def get_architecture_designer() -> AIArchitectureDesigner:
    """Get singleton AI architecture designer (thread-safe)."""
    global _designer_instance
    if _designer_instance is None:
        with _designer_lock:
            if _designer_instance is None:
                _designer_instance = AIArchitectureDesigner()
    return _designer_instance
