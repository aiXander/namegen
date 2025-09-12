"""LLM wrapper with caching and retry logic."""

import json
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, Union, List, Callable
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI

from ai.utils import get_cache_path, load_json, save_json, ensure_dir
from ai.cost_tracker import get_cost_tracker

# Initialize OpenAI client
openai_client = OpenAI()

# Thread pool for async operations
_executor = ThreadPoolExecutor(max_workers=10)

# Pricing per 1M tokens (input/output) in USD
pricing = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 5.00, "output": 15.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},

    "gpt-5":      {"input": 1.25, "output": 10.0},
    "gpt-5-mini": {"input": 0.25, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "output": 0.40},
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost based on model pricing and token usage."""
    if model not in pricing:
        print(f"⚠️  WARNING: No pricing information for model {model}")
        return 0.0
    
    model_pricing = pricing[model]
    input_cost = (input_tokens / 1_000_000) * model_pricing["input"]
    output_cost = (output_tokens / 1_000_000) * model_pricing["output"]
    
    return input_cost + output_cost


def _sync_openai_response(input_messages: List[Dict[str, str]], model: str, 
                         reasoning_effort: str = "low", **kwargs) -> Any:
    """Synchronous OpenAI response call."""
    # Convert input format from litellm to OpenAI format
    if input_messages and len(input_messages) == 1 and input_messages[0].get("role") == "user":
        input_text = input_messages[0]["content"]
    else:
        # Handle multi-turn conversations by joining them
        input_text = "\n".join([msg.get("content", "") for msg in input_messages if msg.get("content")])
    
    # Build OpenAI API call parameters
    params = {
        "model": model,
        "input": input_text,
        #"reasoning": {"effort": reasoning_effort} #, "summary": 'detailed'}
    }
    
    # Add any additional kwargs that are valid for OpenAI
    for key, value in kwargs.items():
        if key in ["temperature", "max_output_tokens", "stream", "background"]:
            params[key] = value
    
    return openai_client.responses.create(**params)


async def async_openai_response(input_messages: List[Dict[str, str]], model: str, 
                               reasoning_effort: str = "low", **kwargs) -> Any:
    """Async wrapper for OpenAI responses.create()."""
    loop = asyncio.get_event_loop()
    # run_in_executor doesn't accept keyword arguments, so we need to use a wrapper
    def wrapper():
        return _sync_openai_response(input_messages, model, reasoning_effort, **kwargs)
    
    return await loop.run_in_executor(_executor, wrapper)


async def async_gather_responses(tasks: List) -> List:
    """Gather multiple async OpenAI response tasks with proper cleanup."""
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    finally:
        # Ensure all tasks are properly cleaned up
        for task in tasks:
            if not task.done():
                task.cancel()


class LLMWrapper:
    """Wrapper for LLM calls with caching and retries."""
    
    def __init__(self, cache_dir: str, max_retries: int = 3):
        self.cache_dir = ensure_dir(cache_dir) / "llm"
        ensure_dir(self.cache_dir)
        self.max_retries = max_retries
        self.call_count = 0
        self.cost_tracker = get_cost_tracker()
        self.current_component = None  # Will be set by calling code
        
    def set_component(self, component: str):
        """Set the current component for cost tracking."""
        self.current_component = component
    
    def _prepare_json_prompt(self, prompt: str, schema_hint: Optional[str]) -> str:
        """Prepare prompt for JSON output."""
        json_instruction = "Respond with valid JSON only. No additional text or explanations."
        
        if schema_hint:
            json_instruction += f"\nExpected JSON structure: {schema_hint}"
        
        return f"{prompt}\n\n{json_instruction}"
    
    def _extract_json(self, response: str) -> Dict[str, Any]:
        """Extract JSON from response, handling various formats."""
        response = response.strip()
        
        # Try direct JSON parse first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Look for JSON within markdown code blocks
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end > start:
                json_str = response[start:end].strip()
                return json.loads(json_str)
        
        # Look for JSON within regular code blocks
        if "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end > start:
                json_str = response[start:end].strip()
                return json.loads(json_str)
        
        # Look for anything that looks like JSON (starts with { or [)
        for line in response.split('\n'):
            line = line.strip()
            if line.startswith(('{', '[')):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        
        raise ValueError(f"Could not extract valid JSON from response: {response[:200]}...")
    
    def get_stats(self) -> Dict[str, int]:
        """Get usage statistics."""
        return {"total_calls": self.call_count}
    
    def json_complete(
        self,
        prompt: str,
        model: str,
        cache_key: Optional[str] = None,
        schema_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Complete a prompt expecting JSON response.
        
        Args:
            prompt: The prompt to send
            model: Model name (e.g., "gpt-4o-mini")
            cache_key: Cache key (if None, no caching)
            schema_hint: Optional hint about expected JSON structure
            
        Returns:
            Parsed JSON response
        """
        # Check cache first
        if cache_key:
            cache_path = get_cache_path(self.cache_dir, cache_key)
            if cache_path.exists():
                try:
                    return load_json(cache_path)
                except Exception as e:
                    print(f"Warning: Failed to load cache {cache_path}: {e}")
        
        # Enhance prompt for JSON output
        json_prompt = self._prepare_json_prompt(prompt, schema_hint)
        
        # Make LLM call with retries
        response = self._call_with_retries(
            model=model,
            prompt=json_prompt
        )
        
        # Parse JSON response
        try:
            result = self._extract_json(response)
        except Exception as e:
            print(f"Warning: Failed to parse JSON response: {e}")
            print(f"Raw response: {response[:200]}...")
            raise
        
        # Cache result
        if cache_key:
            try:
                save_json(result, cache_path)
            except Exception as e:
                print(f"Warning: Failed to save cache {cache_path}: {e}")
        
        return result
    
    def _call_with_retries(
        self,
        model: str,
        prompt: str,
        verbosity: int = 0
    ) -> str:
        """Make LLM call with retry logic."""
        last_error = None

        if verbosity > 1:
            print('-----------------------------------------------------------')
            print(f"Calling LLM {model} with prompt:\n{prompt}")
            print('-----------------------------------------------------------')
        
        for attempt in range(self.max_retries):
            try:
                self.call_count += 1
                
                # Use OpenAI client
                response = _sync_openai_response(
                    input_messages=[{"role": "user", "content": prompt}],
                    model=model,
                    stream=False,
                    background=False
                )
                
                # Track cost using OpenAI response
                try:
                    # OpenAI response format has usage information
                    usage = getattr(response, 'usage', None)
                    input_tokens = getattr(usage, 'input_tokens', 0) if usage else 0
                    output_tokens = getattr(usage, 'output_tokens', 0) if usage else 0
                    
                    # Calculate cost using our pricing dictionary
                    cost = calculate_cost(model, input_tokens, output_tokens)
                    
                    component = self.current_component if self.current_component else "unknown"
                    self.cost_tracker.record_call(
                        component=component,
                        call_type="completion",
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost=cost
                    )
                except (AttributeError, KeyError) as e:
                    # If cost tracking fails, continue without it
                    print(f"⚠️  WARNING: Could not track cost for completion call with model {model}: {e}")
                
                # Extract content from OpenAI response format
                # Find the message output (skip reasoning items)
                content = None
                for output_item in response.output:
                    if hasattr(output_item, 'type') and output_item.type == 'message':
                        content = output_item.content[0].text
                        break
                
                if content is None:
                    raise ValueError("No message content found in response")

                if verbosity > 1:
                    print('-----------------------------------------------------------')
                    print(f"Response: {content.strip()}")
                    print('-----------------------------------------------------------')
                        
                return content.strip()
                
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # exponential backoff
                    print(f"LLM call failed (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    print(f"LLM call failed after {self.max_retries} attempts: {e}")
        
        raise last_error

    async def batch_json_complete(
        self,
        prompts: List[str],
        model: str,
        cache_keys: Optional[List[Optional[str]]] = None,
        schema_hints: Optional[List[Optional[str]]] = None,
        batch_size: int = 8,
        max_retries: int = 3,
        reasoning_effort: str = "low",
        retry_delay_base: float = 1.0,
        verbosity: int = 0,
        print_reasoning_summary: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Process multiple prompts in parallel batches with rate limit retry handling.
        
        Args:
            prompts: List of prompts to process
            model: Model name (e.g., "gpt-4o-mini")
            cache_keys: Optional list of cache keys (if None, no caching)
            schema_hints: Optional list of schema hints
            batch_size: Maximum number of concurrent requests (default: 16)
            max_retries: Maximum retries for rate limit errors (default: 3)
            retry_delay_base: Base delay for exponential backoff (default: 1.0s)
            
        Returns:
            List of parsed JSON responses in same order as input prompts
        """
        if not prompts:
            return []
        
        n_prompts = len(prompts)
        cache_keys = cache_keys or [None] * n_prompts
        schema_hints = schema_hints or [None] * n_prompts
        
        print(f"Processing {n_prompts} prompts in batches of {batch_size}")
        
        # Check cache first and prepare uncached tasks
        results = [None] * n_prompts
        uncached_indices = []
        
        for i, (prompt, cache_key, schema_hint) in enumerate(zip(prompts, cache_keys, schema_hints)):
            if cache_key:
                cache_path = get_cache_path(self.cache_dir, cache_key)
                if cache_path.exists():
                    try:
                        results[i] = load_json(cache_path)
                        continue
                    except Exception as e:
                        print(f"Warning: Failed to load cache {cache_path}: {e}")
            uncached_indices.append(i)
        
        cached_count = n_prompts - len(uncached_indices)
        if cached_count > 0:
            print(f"Found {cached_count} cached results")
        
        if not uncached_indices:
            return results
        
        # Process uncached prompts in batches
        for batch_start in range(0, len(uncached_indices), batch_size):
            batch_end = min(batch_start + batch_size, len(uncached_indices))
            batch_indices = uncached_indices[batch_start:batch_end]
            
            print(f"Processing batch {batch_start//batch_size + 1}: items {batch_start + 1}-{batch_end} of {len(uncached_indices)} uncached")
            
            # Create tasks for this batch
            tasks = []
            for i in batch_indices:
                prompt = prompts[i]
                cache_key = cache_keys[i]
                schema_hint = schema_hints[i]
                
                task = asyncio.create_task(self._async_json_complete_with_retry(
                    prompt=prompt,
                    model=model,
                    cache_key=cache_key,
                    schema_hint=schema_hint,
                    max_retries=max_retries,
                    retry_delay_base=retry_delay_base,
                    reasoning_effort=reasoning_effort,
                    verbosity=verbosity,
                    print_reasoning_summary=print_reasoning_summary
                ))
                tasks.append(task)
            
            # Execute batch
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Store results, handling exceptions
            for i, result in zip(batch_indices, batch_results):
                if isinstance(result, Exception):
                    print(f"Task failed for prompt {i}: {result}")
                    results[i] = result  # Keep exception in results for caller to handle
                else:
                    results[i] = result
        
        print(f"Completed processing all {n_prompts} prompts")
        await cleanup_background_tasks()
        return results
    
    async def _async_json_complete_with_retry(
        self,
        prompt: str,
        model: str,
        cache_key: Optional[str] = None,
        schema_hint: Optional[str] = None,
        max_retries: int = 3,
        retry_delay_base: float = 1.0,
        reasoning_effort: str = "low",
        verbosity: int = 0,
        print_reasoning_summary: bool = False
    ) -> Dict[str, Any]:
        """Single async JSON completion with retry logic."""
        # Check cache first
        if cache_key:
            cache_path = get_cache_path(self.cache_dir, cache_key)
            if cache_path.exists():
                try:
                    return load_json(cache_path)
                except Exception as e:
                    print(f"Warning: Failed to load cache {cache_path}: {e}")
        
        json_prompt = self._prepare_json_prompt(prompt, schema_hint)
        
        for attempt in range(max_retries + 1):
            try:
                if verbosity > 1:
                    print("-----------------------------------------------------------")
                    print(f"Calling LLM {model} with prompt:\n{json_prompt}")
                    print("-----------------------------------------------------------")

                response = await async_openai_response(
                    input_messages=[{"role": "user", "content": json_prompt}],
                    model=model,
                    stream=False,
                    background=False,
                    reasoning_effort=reasoning_effort
                )
                
                # Track cost using OpenAI response
                try:
                    # OpenAI response format has usage information
                    usage = getattr(response, 'usage', None)
                    input_tokens = getattr(usage, 'input_tokens', 0) if usage else 0
                    output_tokens = getattr(usage, 'output_tokens', 0) if usage else 0
                    
                    # Calculate cost using our pricing dictionary
                    cost = calculate_cost(model, input_tokens, output_tokens)
                    
                    component = self.current_component if self.current_component else "unknown"
                    self.cost_tracker.record_call(
                        component=component,
                        call_type="completion",
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost=cost
                    )
                except (AttributeError, KeyError) as e:
                    print(f"⚠️  WARNING: Could not track cost for async completion call with model {model}: {e}")
                
                if verbosity > 1:
                    print(f"Response: {response}")
                
                # Print reasoning summary if requested
                if print_reasoning_summary and hasattr(response, 'reasoning') and response.reasoning:
                    if hasattr(response.reasoning, 'summary') and response.reasoning.summary:
                        print(f"🧠 Reasoning Summary: {response.reasoning.summary}")
                
                # Extract content from OpenAI response format
                # Find the message output (skip reasoning items)
                content = None
                for output_item in response.output:
                    if hasattr(output_item, 'type') and output_item.type == 'message':
                        content = output_item.content[0].text
                        break
                
                if content is None:
                    raise ValueError("No message content found in response")
                
                # Parse JSON
                result = self._extract_json(content.strip())
                
                # Cache result
                if cache_key:
                    try:
                        cache_path = get_cache_path(self.cache_dir, cache_key)
                        save_json(result, cache_path)
                    except Exception as e:
                        print(f"Warning: Failed to save cache {cache_path}: {e}")
                
                # Update call count (thread-safe increment)
                self.call_count += 1
                
                return result
                
            except Exception as e:
                if attempt < max_retries and self._is_rate_limit_error(e):
                    delay = retry_delay_base * (2 ** attempt)
                    print(f"Rate limit error, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    print(f"Failed after {attempt + 1} attempts: {e}")
                    raise
        
        # Should not reach here
        raise RuntimeError("Unexpected end of retry loop")
    
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if error is related to rate limiting."""
        error_str = str(error).lower()
        rate_limit_indicators = [
            "rate limit", "rate_limit", "429", "too many requests",
            "quota exceeded", "rate exceeded", "throttle", "throttled"
        ]
        return any(indicator in error_str for indicator in rate_limit_indicators)


async def cleanup_background_tasks():
    """Cancel any lingering background tasks to ensure clean exit."""
    pending = asyncio.all_tasks()
    current = asyncio.current_task()
    background_tasks = [task for task in pending if task != current and not task.done()]
    
    if background_tasks:
        print(f"Cleaning up {len(background_tasks)} background tasks")
        for task in background_tasks:
            task.cancel()
        await asyncio.sleep(0.1)  # Give tasks time to cancel