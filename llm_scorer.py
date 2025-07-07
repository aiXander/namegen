#!/usr/bin/env python3

import litellm
from typing import List, Dict, Any, Tuple
import json
import re
import time


class LLMScorer:
    """
    LLM-based name scoring system using litellm for model compatibility
    """
    
    def __init__(self, model: str = "gpt-3.5-turbo", max_chunk_size: int = 10):
        """
        Initialize the LLM scorer
        
        Args:
            model: LLM model name (compatible with litellm)
            max_chunk_size: Maximum number of names to score in one API call
        """
        self.model = model
        self.max_chunk_size = max_chunk_size
        
    def score_names(self, names: List[str], description: str, 
                   scored_examples: List[Tuple[str, float]], 
                   instructions: str,
                   progress_callback=None) -> List[Tuple[str, float]]:
        """
        Score a list of names using the LLM
        
        Args:
            names: List of names to score
            description: Description of what the names are for
            scored_examples: List of (name, score) tuples as examples
            instructions: Instructions for the LLM
            progress_callback: Optional callback function for progress updates
            
        Returns:
            List of (name, score) tuples
        """
        if not names:
            return []
            
        # Split names into chunks
        chunks = self._chunk_names(names)
        total_chunks = len(chunks)
        all_scores = []
        
        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(i / total_chunks)
                
            try:
                chunk_scores = self._score_chunk(chunk, description, scored_examples, instructions)
                all_scores.extend(chunk_scores)
            except Exception as e:
                print(f"Error scoring chunk {i+1}: {str(e)}")
                # Assign default score of 0.5 for failed chunks
                chunk_scores = [(name, 0.5) for name in chunk]
                all_scores.extend(chunk_scores)
                
        if progress_callback:
            progress_callback(1.0)
            
        return all_scores
    
    def _chunk_names(self, names: List[str]) -> List[List[str]]:
        """Split names into chunks for processing"""
        chunks = []
        for i in range(0, len(names), self.max_chunk_size):
            chunks.append(names[i:i + self.max_chunk_size])
        return chunks
    
    def _score_chunk(self, names: List[str], description: str, 
                    scored_examples: List[Tuple[str, float]], 
                    instructions: str) -> List[Tuple[str, float]]:
        """Score a single chunk of names"""
        
        # Build the prompt
        prompt = self._build_prompt(names, description, scored_examples, instructions)
        
        # Print the full prompt to terminal for inspection
        print("="*80)
        print("LLM PROMPT SENT TO API:")
        print("="*80)
        print(prompt)
        print("="*80)
        
        # Make API call
        response = litellm.completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,  # Low temperature for consistent scoring
            max_tokens=1000
        )
        
        # Parse response
        return self._parse_scores(response.choices[0].message.content, names)
    
    def _build_prompt(self, names: List[str], description: str, 
                     scored_examples: List[Tuple[str, float]], 
                     instructions: str) -> str:
        """Build the scoring prompt"""
        
        prompt_parts = []
        
        # Add description
        if description.strip():
            prompt_parts.append(f"Context: {description}")
        
        # Add scored examples
        if scored_examples:
            prompt_parts.append("Example scored names:")
            for name, score in scored_examples[:10]:  # Limit to top 10 examples
                prompt_parts.append(f"- {name}: {score:.1f}")
        
        # Add instructions
        prompt_parts.append(instructions)
        
        # Add names to score
        prompt_parts.append("Names to score:")
        for i, name in enumerate(names, 1):
            prompt_parts.append(f"{i}. {name}")
            
        prompt_parts.append("\nPlease provide scores as a JSON array of numbers (0.0 to 5.0), one for each name in order. Example: [4.2, 3.1, 2.8, 4.5]")
        
        return "\n\n".join(prompt_parts)
    
    def _parse_scores(self, response: str, names: List[str]) -> List[Tuple[str, float]]:
        """Parse LLM response to extract scores"""
        
        # Try to extract JSON array from response
        json_match = re.search(r'\[[\d\s,\.]+\]', response)
        
        if json_match:
            try:
                scores_array = json.loads(json_match.group())
                
                # Ensure we have the right number of scores
                if len(scores_array) == len(names):
                    # Clamp scores to valid range
                    clamped_scores = [max(0.0, min(5.0, float(score))) for score in scores_array]
                    return list(zip(names, clamped_scores))
                    
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Fallback: try to parse individual scores from text
        scores = []
        lines = response.split('\n')
        
        for line in lines:
            # Look for patterns like "1. Name: 4.2" or "Name: 4.2"
            score_match = re.search(r'(\d+\.?\d*)\s*(?:\/5|out of 5)?$', line)
            if score_match:
                try:
                    score = float(score_match.group(1))
                    scores.append(max(0.0, min(5.0, score)))
                except ValueError:
                    pass
        
        # If we got the right number of scores, use them
        if len(scores) == len(names):
            return list(zip(names, scores))
        
        # Final fallback: assign default scores
        print(f"Warning: Could not parse scores from LLM response. Using default scores.")
        return [(name, 2.5) for name in names]
    
    @staticmethod
    def get_available_models() -> List[str]:
        """Get list of available LLM models"""
        return [
            "gpt-3.5-turbo",
            "gpt-4",
            "gpt-4-turbo",
            "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229",
            "claude-3-opus-20240229",
            "gemini-pro",
            "ollama/llama2",
            "ollama/mistral",
            "ollama/codellama"
        ]