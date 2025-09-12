#!/usr/bin/env python3

import asyncio
from typing import List, Dict, Any, Tuple
import json
import re
from ai.llm import LLMWrapper
DEFAULT_SCORE = 0.0

class LLMScorer:
    """
    LLM-based name scoring system using OpenAI client with parallel batch processing
    """
    
    def __init__(self, model: str = "gpt-4o-mini", max_chunk_size: int = 10, cache_dir: str = ".cache"):
        """
        Initialize the LLM scorer
        
        Args:
            model: LLM model name (compatible with OpenAI)
            max_chunk_size: Maximum number of names to score in one API call
            cache_dir: Directory for caching responses
        """
        self.model = model
        self.max_chunk_size = max_chunk_size
        self.llm_wrapper = LLMWrapper(cache_dir=cache_dir)
        self.llm_wrapper.set_component("name_scorer")
        
    def score_names(self, names: List[str], description: str, 
                   scored_examples: List[Tuple[str, float]], 
                   instructions: str,
                   progress_callback=None) -> Tuple[List[Tuple[str, float]], float]:
        """
        Score a list of names using the LLM with parallel batch processing
        
        Args:
            names: List of names to score
            description: Description of what the names are for
            scored_examples: List of (name, score) tuples as examples
            instructions: Instructions for the LLM
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Tuple of (List of (name, score) tuples, total cost in USD)
        """
        if not names:
            return ([], 0.0)
        
        # Get initial cost before scoring
        initial_cost = self.llm_wrapper.cost_tracker.get_total_cost()
        
        # Run async scoring in an event loop
        scores = asyncio.run(self._score_names_async(
            names, description, scored_examples, instructions, progress_callback
        ))
        
        # Calculate cost for this scoring operation
        final_cost = self.llm_wrapper.cost_tracker.get_total_cost()
        operation_cost = final_cost - initial_cost
        
        return (scores, operation_cost)
    
    async def _score_names_async(self, names: List[str], description: str, 
                                scored_examples: List[Tuple[str, float]], 
                                instructions: str,
                                progress_callback=None) -> List[Tuple[str, float]]:
        """Async implementation of score_names with parallel batch processing"""
        # Split names into chunks
        chunks = self._chunk_names(names)
        total_chunks = len(chunks)
        
        # Build prompts for all chunks
        prompts = []
        cache_keys = []
        for i, chunk in enumerate(chunks):
            prompt = self._build_prompt(chunk, description, scored_examples, instructions)
            prompts.append(prompt)
            
            # Generate cache key based on prompt content
            import hashlib
            cache_key = hashlib.md5(prompt.encode()).hexdigest()
            cache_keys.append(cache_key)
        
        # Print first prompt for inspection
        if prompts:
            print("="*80)
            print("LLM PROMPT SENT TO API (first chunk):")
            print("="*80)
            print(prompts[0])
            print("="*80)
        
        # Process all chunks in parallel batches
        try:
            schema_hint = '{"name1": score1, "name2": score2, ...} where scores are integers 0-5'
            
            results = await self.llm_wrapper.batch_json_complete(
                prompts=prompts,
                model=self.model,
                cache_keys=cache_keys,
                schema_hints=[schema_hint] * len(prompts),
                batch_size=8,  # Process up to 8 chunks concurrently
                max_retries=3,
                reasoning_effort="low",
                verbosity=1
            )
            
            # Parse results and combine scores
            all_scores = []
            for i, (chunk, result) in enumerate(zip(chunks, results)):
                if progress_callback:
                    progress_callback((i + 1) / total_chunks)
                
                if isinstance(result, Exception):
                    print(f"Error scoring chunk {i+1}: {str(result)}")
                    chunk_scores = [(name, DEFAULT_SCORE) for name in chunk]
                else:
                    # Print response for inspection (first chunk only)
                    if i == 0:
                        print("="*80)
                        print("LLM RESPONSE RECEIVED (first chunk):")
                        print("="*80)
                        print(json.dumps(result, indent=2))
                        print("="*80)
                    
                    chunk_scores = self._parse_json_scores(result, chunk)
                
                all_scores.extend(chunk_scores)
            
            return all_scores
            
        except Exception as e:
            print(f"Error in batch processing: {str(e)}")
            return [(name, DEFAULT_SCORE) for name in names]
    
    def _chunk_names(self, names: List[str]) -> List[List[str]]:
        """Split names into chunks for processing"""
        chunks = []
        for i in range(0, len(names), self.max_chunk_size):
            chunks.append(names[i:i + self.max_chunk_size])
        return chunks
    
    def _parse_json_scores(self, json_result: Dict[str, Any], names: List[str]) -> List[Tuple[str, float]]:
        """Parse JSON result from LLM to extract scores for names"""
        scores = []
        
        for name in names:
            if name in json_result:
                score = float(json_result[name])
                # Clamp score to valid range
                score = max(0.0, min(5.0, score))
                scores.append((name, score))
            else:
                # Try case-insensitive match
                found = False
                for key, value in json_result.items():
                    if key.lower() == name.lower():
                        score = float(value)
                        score = max(0.0, min(5.0, score))
                        scores.append((name, score))
                        found = True
                        break
                
                if not found:
                    print(f"Warning: No score found for name '{name}', using default score")
                    scores.append((name, DEFAULT_SCORE))
        
        return scores
    
    def _build_prompt(self, names: List[str], description: str, 
                     scored_examples: List[Tuple[str, float]], 
                     instructions: str) -> str:
        """Build the scoring prompt for JSON output"""
        
        prompt_parts = []
        
        # Add description
        if description.strip():
            prompt_parts.append(f"Context: {description}")
        
        # Add scored examples
        if scored_examples:
            examples = [f'"{name}": {score}' for name, score in scored_examples[:10]]
            prompt_parts.append(f"Example scored names: {{{', '.join(examples)}}}")
        
        # Add instructions exactly as provided
        prompt_parts.append(instructions)
        
        # Add names to score with JSON format instruction
        names_list = ', '.join([f'"{name}"' for name in names])
        prompt_parts.append(f"Names to score: [{names_list}]")
        
        # Add JSON format instruction
        prompt_parts.append("Respond with a JSON object where each name is a key and its score (0-5) is the value. Example format: {\"name1\": 4, \"name2\": 1, \"name3\": 2}")
        
        return "\n\n".join(prompt_parts)
    
    
    @staticmethod
    def get_available_models() -> List[str]:
        """Get list of available LLM models"""
        return [
            "gpt-4o-mini",
            "gpt-4.1", 
            "gpt-4o",
            "gpt-5",
            "gpt-5-mini",
            "gpt-5-nano"
        ]