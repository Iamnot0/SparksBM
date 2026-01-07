"""LLM integration - Gemini only"""
import os
from pathlib import Path
from typing import Dict, Optional, List, Any
from dotenv import load_dotenv

# Load .env from Agentic Framework directory (explicit path)
_agenticFrameworkDir = Path(__file__).parent.parent
_envFile = _agenticFrameworkDir / '.env'
if _envFile.exists():
    load_dotenv(_envFile)
else:
    # Fallback to default behavior
    load_dotenv()

# Try to import Google Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


class LLMTool:
    """Wrapper for Gemini LLM provider"""
    
    def __init__(self, provider='gemini'):
        """
        Args:
            provider: 'gemini' (only supported provider)
        """
        self.provider = 'gemini'
        self.conversationHistory = []
        self.geminiClient = None
        
        # Setup Gemini
        if GEMINI_AVAILABLE:
            apiKey = os.getenv('GEMINI_API_KEY')
            if apiKey:
                try:
                    genai.configure(api_key=apiKey)
                    # Use gemini-2.5-flash as default (latest, most compatible)
                    # Can override with GEMINI_MODEL env var
                    modelName = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
                    self.geminiClient = genai.GenerativeModel(modelName)
                except Exception as e:
                    raise RuntimeError(f"Gemini setup failed: {e}")
            else:
                raise ValueError("GEMINI_API_KEY not found in environment variables")
        else:
            raise RuntimeError("Google Generative AI library not installed. Run: pip install google-generativeai")
    
    def generate(self, prompt: str, systemPrompt: str = "", maxTokens: int = 512, provider: Optional[str] = None, retryOnRateLimit: bool = True) -> str:
        """
        Generate text response from Gemini LLM with retry logic
        
        Args:
            prompt: User prompt
            systemPrompt: System instructions
            maxTokens: Max tokens to generate
            provider: Ignored (always uses Gemini)
            retryOnRateLimit: Whether to retry on 429 rate limit errors (default: True)
            
        Returns:
            Generated text
        """
        import time
        
        def isRateLimitError(error: Exception) -> bool:
            """Check if error is a rate limit error"""
            errorStr = str(error).lower()
            return '429' in errorStr or 'quota' in errorStr or 'rate limit' in errorStr or 'too many requests' in errorStr or 'service limit' in errorStr
        
        maxRetries = 3 if retryOnRateLimit else 1
        for attempt in range(maxRetries):
            try:
                fullPrompt = f"{systemPrompt}\n\n{prompt}" if systemPrompt else prompt
                response = self.geminiClient.generate_content(
                    fullPrompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=maxTokens
                    )
                )
                
                # Handle response properly - check for candidates and parts
                try:
                    result = response.text
                except (AttributeError, ValueError) as textError:
                    # Fallback to manual extraction
                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        finish_reason = getattr(candidate, 'finish_reason', None)
                        if finish_reason == 2:  # SAFETY - content blocked
                            raise RuntimeError("Content was blocked by safety filters. Please rephrase your request.")
                        elif hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                            result = candidate.content.parts[0].text
                        else:
                            raise RuntimeError(f"Gemini response has no valid content. Finish reason: {finish_reason}")
                    else:
                        raise RuntimeError(f"Gemini response has no valid content: {textError}")
                self.conversationHistory.append({
                    'provider': 'gemini',
                    'prompt': prompt,
                    'response': result
                })
                return result
            except Exception as e:
                errorMsg = str(e)
                if isRateLimitError(e) and attempt < maxRetries - 1:
                    waitTime = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    time.sleep(waitTime)
                    continue
                raise RuntimeError(f"Gemini generation failed: {errorMsg}")
        
        raise RuntimeError("Gemini generation failed after retries")
    
    def analyze(self, data: Any, analysisType: str = "summary", provider: Optional[str] = None) -> str:
        """
        Analyze data using Gemini LLM
        
        Args:
            data: Data to analyze (dict, list, str)
            analysisType: Type of analysis (summary, extract, validate, etc.)
            provider: Ignored (always uses Gemini)
            
        Returns:
            Analysis result as string
        """
        prompt = f"Analyze the following data ({analysisType}):\n\n{data}"
        return self.generate(prompt, provider=provider)
    
    def extractEntities(self, text: str, entityTypes: List[str], provider: Optional[str] = None) -> Dict:
        """
        Extract entities from text using Gemini LLM
        
        Args:
            text: Text to extract from
            entityTypes: List of entity types to find (e.g., ['person', 'document', 'risk'])
            provider: Ignored (always uses Gemini)
            
        Returns:
            Dict with extracted entities
        """
        prompt = f"Extract the following entity types from the text: {', '.join(entityTypes)}\n\nText:\n{text}\n\nReturn as JSON."
        response = self.generate(prompt, provider=provider)
        
        # Try to parse JSON from response
        import json
        try:
            # Extract JSON from response if wrapped in markdown
            if '```json' in response:
                jsonStr = response.split('```json')[1].split('```')[0].strip()
            elif '```' in response:
                jsonStr = response.split('```')[1].split('```')[0].strip()
            else:
                jsonStr = response.strip()
            
            return json.loads(jsonStr)
        except (json.JSONDecodeError, ValueError, KeyError, IndexError):
            # Fallback: return raw response
            return {'raw': response, 'entities': []}
    
    def getHistory(self) -> List[Dict]:
        """Get conversation history"""
        return self.conversationHistory.copy()
    
    def getAvailableProviders(self) -> List[str]:
        """Get list of available LLM providers"""
        return ['gemini'] if self.geminiClient else []
