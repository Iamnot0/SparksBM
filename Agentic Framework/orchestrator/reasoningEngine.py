"""
Reasoning Engine - Abstract Interface for LLM Integration

This module provides a vendor-independent interface for reasoning engines.
It allows the system to use different LLM providers (Ollama Cloud, OpenAI, Gemini, etc.)
without changing the core application logic.

Architecture:
- ReasoningEngine: Abstract base class defining the interface
- OllamaReasoningEngine: Ollama Cloud API implementation
- FallbackReasoningEngine: Graceful degradation when LLM unavailable

Usage:
    engine = OllamaReasoningEngine()
    response = engine.reason("What is ISMS?", context={...})
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
import requests
import os
import re
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
_agenticFrameworkDir = Path(__file__).parent.parent
_envFile = _agenticFrameworkDir / '.env'
if _envFile.exists():
    load_dotenv(_envFile)
else:
    load_dotenv()


class ReasoningEngine(ABC):
    """
    Abstract base class for reasoning engines.
    
    All reasoning engine implementations must inherit from this class
    and implement the reason() method.
    """
    
    @abstractmethod
    def reason(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Process a query and return a reasoned response.
        
        Args:
            query: The user's question or command
            context: Optional context information (conversation history, documents, etc.)
            
        Returns:
            str: The reasoning engine's response
            
        Raises:
            Exception: If reasoning fails
        """
        pass
    
    @abstractmethod
    def isAvailable(self) -> bool:
        """
        Check if the reasoning engine is available and ready to use.
        
        Returns:
            bool: True if engine is available, False otherwise
        """
        pass


class OllamaReasoningEngine(ReasoningEngine):
    """
    Ollama Cloud API reasoning engine.
    
    This implementation uses Ollama Cloud API (https://ollama.com/api).
    It provides cloud-based reasoning capabilities with API key authentication.
    
    Features:
    - Cloud-based execution (accessible from anywhere)
    - API key authentication
    - Fast response times
    - Free tier available
    - Works on Render and other cloud platforms
    
    Configuration:
    - Default model: mistral
    - Default endpoint: https://ollama.com/api
    - API key: OLLAMA_API_KEY environment variable (required)
    """
    
    def __init__(
        self,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 60,
        temperature: float = 0.7,
        max_tokens: int = 250,
        response_mode: str = "concise"
    ):
        """
        Initialize Ollama Cloud API reasoning engine.
        
        Args:
            model: Ollama model name (default: ministral-3:8b, from env or default)
            endpoint: Ollama API endpoint (default: https://ollama.com)
            api_key: API key for authentication (default: from OLLAMA_API_KEY env)
            timeout: Request timeout in seconds (default: 60)
            temperature: Sampling temperature 0.0-1.0 (default: 0.7)
            max_tokens: Maximum tokens to generate (default: 250 for concise mode)
            response_mode: Response style - "concise" (default), "normal", or "detailed"
        """
        # Default to ministral-3:8b (available on Ollama Cloud, similar to mistral)
        self.model = model or os.getenv('OLLAMA_MODEL', 'ministral-3:8b')
        # Endpoint should be base URL (https://ollama.com), not /api path
        default_endpoint = os.getenv('OLLAMA_ENDPOINT', 'https://ollama.com')
        self.endpoint = (endpoint or default_endpoint).rstrip('/')
        # Remove /api if present (we add it in the request)
        if self.endpoint.endswith('/api'):
            self.endpoint = self.endpoint[:-4]
        self.api_key = api_key or os.getenv('OLLAMA_API_KEY', '')
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.response_mode = response_mode  # concise | normal | detailed
        self._is_available_cache = None
        
        if not self.api_key:
            raise ValueError("OLLAMA_API_KEY is required. Set it in environment variables or pass as api_key parameter.")
    
    def reason(self, query: str, context: Optional[Dict[str, Any]] = None, system_prompt: Optional[str] = None, response_mode: Optional[str] = None) -> str:
        """
        Process a query using Ollama Cloud API and return a response.
        
        Args:
            query: The user's question or command
            context: Optional context (conversation history, documents, etc.)
            system_prompt: Optional system prompt to guide the LLM
            response_mode: Override default response mode ("concise", "normal", "detailed")
            
        Returns:
            str: The model's response (truncated if exceeds limits)
            
        Raises:
            Exception: If Ollama API call fails
        """
        if not self.isAvailable():
            raise Exception("Ollama Cloud API is not available. Please check your API key and network connection.")
        
        # Use provided mode or default
        mode = response_mode or self.response_mode
        
        # DEBUG: Log mode and question type
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[ReasoningEngine] Query: {query[:50]}... | Mode: {mode} | QuestionType: {self._detectQuestionType(query)}")
        
        # Detect question type for appropriate prompt
        question_type = self._detectQuestionType(query)
        
        # Build messages with question-type aware prompts
        messages = self._buildMessages(query, context, system_prompt, mode, question_type)
        
        # Adjust max_tokens based on mode if default is used
        effective_max_tokens = self.max_tokens
        if self.max_tokens == 250:  # Default value
            mode_limits = {
                "concise": 100,  # Reduced to force shorter responses
                "normal": 300,
                "detailed": 600
            }
            effective_max_tokens = mode_limits.get(mode, 250)
        
        # Prepare API request payload
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": effective_max_tokens
            }
        }
        
        # Prepare headers with API key
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            # Call Ollama Cloud API (uses /api/chat endpoint)
            response = requests.post(
                f"{self.endpoint}/api/chat",
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Extract response text from chat API format
            result = response.json()
            message = result.get("message", {})
            response_text = message.get("content", "").strip()
            
            # DEBUG: Log raw response length
            import logging
            logger = logging.getLogger(__name__)
            raw_word_count = len(response_text.split())
            logger.info(f"[ReasoningEngine] Raw response: {raw_word_count} words, Mode: {mode}")
            
            # Apply safety truncation and markdown stripping
            response_text = self._truncateResponse(response_text, mode)
            
            # DEBUG: Log after truncation
            truncated_word_count = len(response_text.split())
            has_md_before = '**' in response_text or '#' in response_text or '•' in response_text
            logger.info(f"[ReasoningEngine] After truncate: {truncated_word_count} words, Has markdown: {has_md_before}")
            
            # Final safety check: ALWAYS strip markdown for concise mode (no exceptions)
            if mode == "concise":
                # Multiple passes of aggressive markdown removal
                for _ in range(3):  # Multiple passes to catch nested/edge cases
                    response_text = response_text.replace('**', '').replace('*', '')
                    response_text = response_text.replace('#', '').replace('•', '-').replace('`', '')
                    response_text = response_text.replace('__', '').replace('_', ' ')
                    # Remove any remaining markdown patterns
                    response_text = re.sub(r'\*\*[^*]*\*\*', '', response_text)
                    response_text = re.sub(r'^#+\s+', '', response_text, flags=re.MULTILINE)
                    response_text = re.sub(r'^\s*[•\-\*]\s+', '', response_text, flags=re.MULTILINE)
                # Clean up whitespace
                response_text = re.sub(r'\s+', ' ', response_text)  # Multiple spaces to single
                response_text = re.sub(r'\n\s*\n+', '\n', response_text)  # Multiple newlines
                response_text = response_text.strip()
                
                # Verify no markdown remains - if it does, strip one more time
                if '**' in response_text or '#' in response_text or '•' in response_text:
                    response_text = response_text.replace('**', '').replace('*', '').replace('#', '').replace('•', '')
                    response_text = re.sub(r'\s+', ' ', response_text).strip()
            
            # DEBUG: Log final response
            final_word_count = len(response_text.split())
            has_md_final = '**' in response_text or '#' in response_text or '•' in response_text
            logger.info(f"[ReasoningEngine] Final response: {final_word_count} words, Has markdown: {has_md_final}")
            
            return response_text
            
        except requests.exceptions.Timeout:
            raise Exception(f"Ollama Cloud API request timed out after {self.timeout} seconds")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise Exception("Ollama Cloud API authentication failed. Please check your API key.")
            elif e.response.status_code == 429:
                raise Exception("Ollama Cloud API rate limit exceeded. Please try again later.")
            else:
                raise Exception(f"Ollama Cloud API error ({e.response.status_code}): {e.response.text}")
        except requests.exceptions.ConnectionError:
            raise Exception("Cannot connect to Ollama Cloud API. Please check your network connection.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ollama Cloud API request failed: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error during reasoning: {str(e)}")
    
    def isAvailable(self) -> bool:
        """
        Check if Ollama Cloud API is available and accessible.
        
        Returns:
            bool: True if Ollama Cloud API is available, False otherwise
        """
        # Basic validation: API key must be present
        if not self.api_key:
            return False
        
        # Use cached result if available (valid for 5 minutes)
        # For cloud API, we assume it's available if API key is set
        # Actual availability will be tested on first request
        return True
    
    def _detectQuestionType(self, query: str) -> str:
        """
        Detect question type to apply appropriate prompt style.
        
        Returns:
            str: Question type - "capabilities", "knowledge", "analysis", "howto", "general"
        """
        query_lower = query.lower().strip()
        
        # Capabilities questions
        if any(phrase in query_lower for phrase in ["what can you", "what do you", "what are your", "your capabilities", "what can", "help me with"]):
            return "capabilities"
        
        # How-to questions
        if any(phrase in query_lower for phrase in ["how do", "how can", "how to", "how should", "steps to", "way to"]):
            return "howto"
        
        # Knowledge questions (what is, what are, explain, define)
        if any(phrase in query_lower for phrase in ["what is", "what are", "what does", "explain", "define", "tell me about", "describe"]):
            return "knowledge"
        
        # Analysis questions
        if any(phrase in query_lower for phrase in ["analyze", "analysis", "summarize", "summary", "main points", "key points"]):
            return "analysis"
        
        # Default
        return "general"
    
    def _getSystemPromptForMode(self, mode: str, question_type: str, base_prompt: Optional[str] = None) -> str:
        """
        Generate appropriate system prompt based on response mode and question type.
        
        Args:
            mode: Response mode ("concise", "normal", "detailed")
            question_type: Question type ("capabilities", "knowledge", "analysis", "howto", "general")
            base_prompt: Optional base prompt to enhance
            
        Returns:
            str: Complete system prompt with constraints
        """
        # CRITICAL: Put response constraints FIRST so they take priority
        prompt_parts = []
        
        # Mode-specific constraints (MUST BE FIRST)
        if mode == "concise":
            prompt_parts.append("=== CRITICAL: YOU MUST FOLLOW THESE RULES ===")
            prompt_parts.append("1. Maximum 80 words. Count your words carefully.")
            prompt_parts.append("2. ABSOLUTELY NO markdown: no **bold**, no # headers, no bullet points (•), no lists, no code blocks.")
            prompt_parts.append("3. Write in plain text sentences only. Use commas and periods, not formatting.")
            prompt_parts.append("4. NO introductions like 'Here is...' or 'Let me explain...'. Start directly with the answer.")
            prompt_parts.append("5. NO conclusions or summaries. Just answer the question.")
            prompt_parts.append("6. If you use formatting, your response is WRONG. Plain text only.")
            prompt_parts.append("=== END RULES ===")
            prompt_parts.append("")
        elif mode == "normal":
            prompt_parts.append("RESPONSE RULES:")
            prompt_parts.append("- Maximum 250 words.")
            prompt_parts.append("- Use minimal formatting.")
        elif mode == "detailed":
            prompt_parts.append("RESPONSE RULES:")
            prompt_parts.append("- Maximum 500 words.")
            prompt_parts.append("- You may use formatting if helpful.")
        
        # Question-type specific guidance
        if question_type == "capabilities":
            prompt_parts.append("- List 3-5 capabilities in one short paragraph (no bullets, no formatting).")
        elif question_type == "knowledge":
            prompt_parts.append("- Answer in 2-3 sentences. Be precise and factual. No formatting.")
        elif question_type == "howto":
            prompt_parts.append("- Provide brief step-by-step instructions in plain text. No numbering unless essential.")
        elif question_type == "analysis":
            prompt_parts.append("- Focus on key insights in 2-3 sentences. Be concise.")
        
        prompt_parts.append("")
        
        # Add base prompt AFTER constraints (so constraints take priority)
        if base_prompt:
            prompt_parts.append(base_prompt)
        
        return "\n".join(prompt_parts)
    
    def _stripMarkdown(self, text: str) -> str:
        """
        Remove markdown formatting from text.
        
        Args:
            text: Text that may contain markdown
            
        Returns:
            str: Plain text with markdown removed
        """
        # Remove bold/italic: **text** or *text* (handle multiline)
        text = re.sub(r'\*\*([^*\n]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*\n]+)\*', r'\1', text)
        text = re.sub(r'__([^_\n]+)__', r'\1', text)
        text = re.sub(r'_([^_\n]+)_', r'\1', text)
        
        # Remove headers: # Header or ## Header (multiline)
        text = re.sub(r'^#+\s+(.+)$', r'\1', text, flags=re.MULTILINE)
        
        # Remove bullet points: • item or - item or * item (multiline, handle indented)
        text = re.sub(r'^[\s]*[•\-\*]\s+', '', text, flags=re.MULTILINE)
        
        # Remove code blocks: `code` or ```code``` (multiline)
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`\n]+)`', r'\1', text)
        
        # Remove numbered lists: 1. item or 1) item (multiline)
        text = re.sub(r'^\d+[\.\)]\s+', '', text, flags=re.MULTILINE)
        
        # Remove section headers like "**Section Name**" on their own line
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            # Remove standalone bold headers
            line = re.sub(r'^\s*\*\*([^*]+)\*\*\s*$', r'\1', line)
            # Remove standalone headers with colons
            if ':' in line and len(line.strip()) < 50:
                line = re.sub(r'^\s*\*\*?([^*:]+):\*\*?\s*$', r'\1:', line)
            cleaned_lines.append(line)
        text = '\n'.join(cleaned_lines)
        
        # Clean up extra whitespace
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines
        text = re.sub(r'  +', ' ', text)  # Multiple spaces
        text = re.sub(r'^\s+', '', text, flags=re.MULTILINE)  # Leading spaces on lines
        text = text.strip()
        
        return text
    
    def _truncateResponse(self, response: str, mode: str) -> str:
        """
        Safety net: Strip markdown and truncate response if it exceeds reasonable limits.
        
        Args:
            response: The response text
            mode: Response mode to determine limit
            
        Returns:
            str: Cleaned and truncated response if needed
        """
        # ALWAYS strip markdown formatting for concise mode (safety net)
        if mode == "concise":
            response = self._stripMarkdown(response)
            # Strip again if markdown still present (more aggressive)
            if '**' in response or '#' in response or '•' in response:
                # More aggressive stripping
                response = response.replace('**', '').replace('*', '').replace('#', '').replace('•', '-').replace('`', '')
                # Clean up any double spaces or formatting artifacts
                response = re.sub(r'\s+', ' ', response)
                response = re.sub(r'\n\s*\n+', '\n', response)
        
        # Word limits by mode (strict)
        word_limits = {
            "concise": 80,  # Strict limit for concise mode
            "normal": 300,
            "detailed": 600
        }
        
        limit = word_limits.get(mode, 300)
        words = response.split()
        
        if len(words) > limit:
            # Truncate at sentence boundary if possible
            truncated = " ".join(words[:limit])
            # Try to end at sentence
            last_period = truncated.rfind('.')
            last_exclamation = truncated.rfind('!')
            last_question = truncated.rfind('?')
            last_sentence = max(last_period, last_exclamation, last_question)
            
            if last_sentence > limit * 0.7:  # If we found a sentence end reasonably close
                return truncated[:last_sentence + 1]
            else:
                return truncated + "..."
        
        return response
    
    def _buildMessages(self, query: str, context: Optional[Dict[str, Any]] = None, system_prompt: Optional[str] = None, mode: str = "concise", question_type: str = "general") -> List[Dict[str, str]]:
        """
        Build messages array for Ollama Cloud API chat endpoint.
        
        Args:
            query: The user's question
            context: Optional context information
            system_prompt: Optional system prompt
            
        Returns:
            List[Dict]: Messages array in format [{"role": "system|user|assistant", "content": "..."}]
        """
        messages = []
        
        # Build enhanced system prompt with mode and question-type awareness
        enhanced_prompt = self._getSystemPromptForMode(mode, question_type, system_prompt)
        
        # Add system prompt
        if enhanced_prompt:
            messages.append({"role": "system", "content": enhanced_prompt})
        elif context and "system" in context:
            # Enhance context system prompt too
            context_system = str(context["system"])
            enhanced_context = self._getSystemPromptForMode(mode, question_type, context_system)
            messages.append({"role": "system", "content": enhanced_context})
        
        # Add conversation history if provided
        if context and "history" in context and context["history"]:
            for msg in context["history"][-5:]:  # Last 5 messages for context
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ["user", "assistant", "system"]:
                    messages.append({"role": role, "content": str(content)})
        
        # Add document context if provided
        if context and "documents" in context and context["documents"]:
            doc_context = "Relevant Documents:\n"
            for doc in context["documents"][:2]:  # Top 2 documents
                doc_context += f"- {doc}\n"
            if messages and messages[-1]["role"] == "system":
                # Append to system message if exists
                messages[-1]["content"] += "\n\n" + doc_context
            else:
                # Add as separate system message
                messages.insert(0, {"role": "system", "content": doc_context})
        
        # Add current user query
        messages.append({"role": "user", "content": query})
        
        return messages
    
    def __repr__(self) -> str:
        """String representation of the engine."""
        endpoint_display = self.endpoint.replace(self.api_key[:8] if self.api_key else "", "***") if "api" in self.endpoint else self.endpoint
        return f"OllamaReasoningEngine(model={self.model}, endpoint={endpoint_display})"


class FallbackReasoningEngine(ReasoningEngine):
    """
    Fallback reasoning engine that returns helpful messages when no LLM is available.
    
    This engine is used when Ollama or other LLM services are not available.
    It provides graceful degradation by returning informative messages instead
    of failing silently.
    """
    
    def reason(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Return a helpful fallback message.
        
        Args:
            query: The user's question
            context: Optional context (ignored)
            
        Returns:
            str: Fallback message
        """
        return (
            "I don't have access to advanced reasoning capabilities right now. "
            "For ISMS operations, please use specific commands like:\n"
            "- 'create scope MyScope'\n"
            "- 'list assets'\n"
            "- 'get scope MyScope'\n"
            "- 'update asset MyAsset description New description'\n"
            "- 'delete scope MyScope'\n\n"
            "For help, type 'help' or ask about specific ISMS concepts."
        )
    
    def isAvailable(self) -> bool:
        """
        Fallback engine is always available.
        
        Returns:
            bool: Always True
        """
        return True
    
    def __repr__(self) -> str:
        """String representation of the engine."""
        return "FallbackReasoningEngine()"


def createReasoningEngine(preferredEngine: str = "ollama") -> ReasoningEngine:
    """
    Factory function to create a reasoning engine.
    
    This function attempts to create the preferred engine and falls back
    to the FallbackReasoningEngine if the preferred engine is not available.
    
    Args:
        preferredEngine: Engine type to create ("ollama", "fallback")
        
    Returns:
        ReasoningEngine: An instance of a reasoning engine
        
    Example:
        engine = createReasoningEngine("ollama")
        if engine.isAvailable():
            response = engine.reason("What is ISMS?")
    """
    if preferredEngine.lower() == "ollama":
        try:
            engine = OllamaReasoningEngine()
            if engine.isAvailable():
                return engine
            else:
                print("⚠️  Ollama Cloud API not available, using fallback engine")
                return FallbackReasoningEngine()
        except ValueError as e:
            # API key missing
            print(f"⚠️  {e}")
            print("⚠️  Using fallback engine")
            return FallbackReasoningEngine()
        except Exception as e:
            print(f"⚠️  Failed to initialize Ollama Cloud API: {e}")
            print("⚠️  Using fallback engine")
            return FallbackReasoningEngine()
    
    elif preferredEngine.lower() == "fallback":
        return FallbackReasoningEngine()
    
    else:
        raise ValueError(f"Unknown reasoning engine: {preferredEngine}")


# Example usage
if __name__ == "__main__":
    print("=== Reasoning Engine Test ===\n")
    
    # Create Ollama engine
    engine = createReasoningEngine("ollama")
    print(f"Engine: {engine}")
    print(f"Available: {engine.isAvailable()}\n")
    
    if engine.isAvailable():
        # Test 1: Simple query
        print("Test 1: Simple Query")
        try:
            response = engine.reason("What is ISMS in one sentence?")
            print(f"Response: {response}\n")
        except Exception as e:
            print(f"Error: {e}\n")
        
        # Test 2: Query with context
        print("Test 2: Query with Context")
        try:
            context = {
                "system": "You are an ISMS expert assistant.",
                "history": [
                    {"role": "user", "content": "What is a scope?"},
                    {"role": "assistant", "content": "A scope defines the boundaries of an ISMS."}
                ]
            }
            response = engine.reason("How do I create one?", context)
            print(f"Response: {response}\n")
        except Exception as e:
            print(f"Error: {e}\n")
    else:
        print("⚠️  Ollama Cloud API not available.")
        print("⚠️  Please set OLLAMA_API_KEY environment variable.")
