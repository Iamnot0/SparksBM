"""Error presenter - formats error messages"""
from typing import Any, Dict, Optional
from .base import BasePresenter


class ErrorPresenter(BasePresenter):
    """Presents error messages in user-friendly format"""
    
    def present(self, data: Any, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Present error message
        
        Expected input format:
        - String error message
        - Dict with 'error' key
        - Exception object
        """
        # Extract error message
        if isinstance(data, str):
            error_msg = data
        elif isinstance(data, dict):
            error_msg = data.get('error') or data.get('message') or str(data)
        else:
            error_msg = str(data)
        
        # Clean up technical error messages
        error_msg = self._clean_error(error_msg)
        
        return {
            'type': 'error',
            'content': error_msg
        }
    
    def _clean_error(self, error_msg: str) -> str:
        """Clean up technical error messages for users"""
        error_msg = error_msg.strip()
        
        # Remove common technical prefixes
        error_msg = error_msg.replace('Error:', '').replace('error:', '').strip()
        
        # Handle specific error types
        if 'FileNotFoundError' in error_msg:
            return "The requested file could not be found. Please check the file path."
        
        if 'LLM' in error_msg or 'API' in error_msg:
            if 'quota' in error_msg.lower() or '429' in error_msg:
                return "I've reached a service limit. Please try again in a few moments, or check your API settings.\n\nBasic operations like listing assets and scopes still work."
            if '404' in error_msg or 'not found' in error_msg.lower():
                return "The advanced service is temporarily unavailable.\n\nYou can still:\n• List and view your ISMS objects\n• Create new objects\n• Process files\n\nTry again in a moment."
            return "Some advanced features are temporarily unavailable.\n\nYou can still:\n• List and manage your ISMS objects\n• Create new objects\n• Process files\n\nWhat would you like to do?"
        
        # Truncate long errors
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        
        return error_msg

