#!/usr/bin/env python3
"""
Ollama Cloud API Usage Monitor

Monitors API calls, tracks rate limits, and logs usage statistics.
Run this script to monitor Ollama Cloud API usage and detect rate limit issues.
"""

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import requests

# Add Agentic Framework to path
_currentDir = Path(__file__).parent.parent.parent
_agenticFrameworkPath = _currentDir / "Agentic Framework"
if _agenticFrameworkPath.exists():
    sys.path.insert(0, str(_agenticFrameworkPath))

from orchestrator.reasoningEngine import OllamaReasoningEngine

# Configuration
LOG_DIR = Path(_currentDir) / "dev" / "logs" / "ollama"
LOG_DIR.mkdir(parents=True, exist_ok=True)
USAGE_LOG = LOG_DIR / f"usage_{datetime.now().strftime('%Y%m%d')}.json"


class OllamaUsageMonitor:
    """Monitor Ollama Cloud API usage and rate limits"""
    
    def __init__(self):
        self.engine = None
        self.stats = {
            "date": datetime.now().isoformat(),
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "rate_limit_errors": 0,
            "total_tokens": 0,
            "average_response_time": 0,
            "calls": []
        }
        self._load_stats()
    
    def _load_stats(self):
        """Load existing stats from log file"""
        if USAGE_LOG.exists():
            try:
                with open(USAGE_LOG, 'r') as f:
                    existing = json.load(f)
                    # Only load if same date
                    if existing.get("date", "").startswith(datetime.now().strftime("%Y-%m-%d")):
                        self.stats = existing
            except Exception:
                pass
    
    def _save_stats(self):
        """Save stats to log file"""
        try:
            with open(USAGE_LOG, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception:
            pass
    
    def test_api(self, query: str = "Say hello") -> Dict:
        """Test API call and record statistics"""
        if not self.engine:
            try:
                self.engine = OllamaReasoningEngine()
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to initialize: {e}",
                    "timestamp": datetime.now().isoformat()
                }
        
        start_time = time.time()
        self.stats["total_calls"] += 1
        
        try:
            response = self.engine.reason(query)
            elapsed = time.time() - start_time
            
            call_record = {
                "timestamp": datetime.now().isoformat(),
                "query_length": len(query),
                "response_length": len(response),
                "response_time": round(elapsed, 2),
                "success": True
            }
            
            self.stats["successful_calls"] += 1
            self.stats["calls"].append(call_record)
            
            # Update average response time
            total_time = sum(c.get("response_time", 0) for c in self.stats["calls"])
            self.stats["average_response_time"] = round(total_time / len(self.stats["calls"]), 2)
            
            self._save_stats()
            
            return {
                "success": True,
                "response": response[:100] + "..." if len(response) > 100 else response,
                "response_time": elapsed,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = str(e)
            
            call_record = {
                "timestamp": datetime.now().isoformat(),
                "query_length": len(query),
                "response_time": round(elapsed, 2),
                "success": False,
                "error": error_msg
            }
            
            self.stats["failed_calls"] += 1
            self.stats["calls"].append(call_record)
            
            # Check for rate limit
            if "429" in error_msg or "rate limit" in error_msg.lower():
                self.stats["rate_limit_errors"] += 1
                call_record["rate_limited"] = True
            
            self._save_stats()
            
            return {
                "success": False,
                "error": error_msg,
                "response_time": elapsed,
                "timestamp": datetime.now().isoformat()
            }
    
    def get_stats(self) -> Dict:
        """Get current statistics"""
        recent_calls = self.stats["calls"][-10:] if len(self.stats["calls"]) > 10 else self.stats["calls"]
        
        return {
            "summary": {
                "total_calls": self.stats["total_calls"],
                "successful": self.stats["successful_calls"],
                "failed": self.stats["failed_calls"],
                "rate_limit_errors": self.stats["rate_limit_errors"],
                "success_rate": round(
                    (self.stats["successful_calls"] / self.stats["total_calls"] * 100) 
                    if self.stats["total_calls"] > 0 else 0, 
                    2
                ),
                "average_response_time": self.stats["average_response_time"]
            },
            "recent_calls": recent_calls
        }
    
    def print_stats(self):
        """Print statistics to console"""
        stats = self.get_stats()
        summary = stats["summary"]
        
        print("\n" + "="*60)
        print("Ollama Cloud API Usage Statistics")
        print("="*60)
        print(f"Total Calls: {summary['total_calls']}")
        print(f"Successful: {summary['successful']} ({summary['success_rate']}%)")
        print(f"Failed: {summary['failed']}")
        print(f"Rate Limit Errors: {summary['rate_limit_errors']}")
        print(f"Average Response Time: {summary['average_response_time']}s")
        print("="*60)
        
        if summary["rate_limit_errors"] > 0:
            print("\n⚠️  WARNING: Rate limit errors detected!")
            print("   Consider upgrading to Pro tier ($20/month)")
        
        if stats["recent_calls"]:
            print("\nRecent Calls:")
            for call in stats["recent_calls"][-5:]:
                status = "✅" if call.get("success") else "❌"
                time_str = f"{call.get('response_time', 0):.2f}s"
                print(f"  {status} {call.get('timestamp', '')[:19]} - {time_str}")


def main():
    """Main monitoring function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor Ollama Cloud API usage")
    parser.add_argument("--test", action="store_true", help="Run a test query")
    parser.add_argument("--query", type=str, default="What is ISMS?", help="Test query")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--watch", action="store_true", help="Watch for rate limits")
    
    args = parser.parse_args()
    
    monitor = OllamaUsageMonitor()
    
    if args.test:
        print(f"Testing with query: '{args.query}'")
        result = monitor.test_api(args.query)
        if result["success"]:
            print(f"✅ Success: {result['response']}")
            print(f"   Response time: {result['response_time']:.2f}s")
        else:
            print(f"❌ Failed: {result['error']}")
    
    if args.stats or not any([args.test, args.watch]):
        monitor.print_stats()
    
    if args.watch:
        print("\nWatching for rate limits... (Press Ctrl+C to stop)")
        try:
            while True:
                time.sleep(60)  # Check every minute
                stats = monitor.get_stats()
                if stats["summary"]["rate_limit_errors"] > 0:
                    print(f"\n⚠️  Rate limit error detected at {datetime.now()}")
                    monitor.print_stats()
        except KeyboardInterrupt:
            print("\nStopped monitoring")


if __name__ == "__main__":
    main()
