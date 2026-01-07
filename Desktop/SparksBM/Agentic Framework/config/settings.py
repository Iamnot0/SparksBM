"""Configuration and settings management"""
import os
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv

# Load .env from Agentic Framework directory (explicit path)
_agenticFrameworkDir = Path(__file__).parent.parent
_envFile = _agenticFrameworkDir / '.env'
if _envFile.exists():
    load_dotenv(_envFile)
else:
    # Fallback to default behavior
    load_dotenv()


class Settings:
    """Centralized configuration"""
    
    # LLM Configuration - Gemini only
    LLM_BACKEND = os.getenv('LLM_BACKEND', 'gemini')  # 'gemini' only
    LLM_MODEL = os.getenv('LLM_MODEL', '')
    LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '512'))
    
    # Google Gemini
    # Note: Try gemini-1.5-flash or gemini-1.5-pro (without -002 suffix)
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')  # Latest, most compatible
    
    # Verinice (optional)
    VERINICE_ENABLED = os.getenv('VERINICE_ENABLED', 'true').lower() == 'true'
    VERINICE_API_URL = os.getenv('VERINICE_API_URL', 'http://localhost:8070')
    SPARKSBM_SCRIPTS_PATH = os.getenv('SPARKSBM_SCRIPTS_PATH', '')
    
    # File paths
    UPLOAD_DIR = os.getenv('UPLOAD_DIR', 'uploads')
    OUTPUT_DIR = os.getenv('OUTPUT_DIR', 'output')
    
    # Memory settings
    MAX_MEMORY_HISTORY = int(os.getenv('MAX_MEMORY_HISTORY', '1000'))
    
    @classmethod
    def getAvailableGeminiModels(cls) -> Dict[str, str]:
        """Get list of available Gemini models with descriptions"""
        return {
            'gemini-2.5-flash': 'Latest Flash - Fast, cost-effective, best for document processing (RECOMMENDED)',
            'gemini-2.5-pro': 'Latest Pro - More capable, better for complex reasoning',
            'gemini-1.5-flash': 'Previous Flash version',
            'gemini-1.5-pro': 'Previous Pro version',
        }
    
    @classmethod
    def getLLMConfig(cls) -> Dict:
        """Get LLM configuration dict"""
        return {
            'backend': cls.LLM_BACKEND,
            'model': cls.LLM_MODEL,
            'max_tokens': cls.LLM_MAX_TOKENS,
            'gemini_key': cls.GEMINI_API_KEY,
            'gemini_model': cls.GEMINI_MODEL,
            'gemini_available_models': cls.getAvailableGeminiModels()
        }
    
    @classmethod
    def validate(cls) -> Dict:
        """Validate configuration"""
        errors = []
        warnings = []
        
        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY required")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

