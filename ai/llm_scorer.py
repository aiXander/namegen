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
        
        # Print the full response to terminal for inspection
        print("="*80)
        print("LLM RESPONSE RECEIVED:")
        print("="*80)
        print(response.choices[0].message.content)
        print("="*80)
        
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
                prompt_parts.append(f"- {name}: {int(score)}")
        
        # Add instructions exactly as provided
        prompt_parts.append(instructions)
        
        # Add names to score
        prompt_parts.append("Names to score:")
        names_section = []
        for i, name in enumerate(names, 1):
            names_section.append(f"{i}. {name}")
        
        # Join everything with double newlines except the names list
        main_parts = prompt_parts[:-1]  # All parts except "Names to score:"
        main_prompt = "\n\n".join(main_parts)
        
        # Add the names section with single newlines
        names_header = prompt_parts[-1]  # "Names to score:"
        names_list = "\n".join(names_section)
        
        return f"{main_prompt}\n\n{names_header}\n{names_list}"
    
    def _parse_scores(self, response: str, names: List[str]) -> List[Tuple[str, float]]:
        """Parse LLM response to extract scores"""
        
        # Try to extract JSON object with string keys first
        json_obj_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
        
        if json_obj_match:
            try:
                scores_dict = json.loads(json_obj_match.group())
                
                # Check if it's a dictionary with string keys
                if isinstance(scores_dict, dict):
                    scores = []
                    for i in range(1, len(names) + 1):  # 1-based indexing
                        key = str(i)
                        if key in scores_dict:
                            score = float(scores_dict[key])
                            scores.append(max(0.0, min(5.0, score)))
                        else:
                            scores.append(2.5)  # Default score if missing
                    
                    if len(scores) == len(names):
                        return list(zip(names, scores))
                        
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Try to extract the index:score format [1:3, 2:4, 3:0, 4:3]
        index_score_match = re.search(r'\[([0-9:,\s]+)\]', response)
        
        if index_score_match:
            try:
                # Parse the index:score pairs
                pairs_str = index_score_match.group(1)
                pairs = [pair.strip() for pair in pairs_str.split(',')]
                
                # Create a dictionary to store index -> score mapping
                score_dict = {}
                for pair in pairs:
                    if ':' in pair:
                        index_str, score_str = pair.split(':')
                        index = int(index_str.strip())
                        score = float(score_str.strip())
                        score_dict[index] = max(0.0, min(5.0, score))
                
                # Convert to list of scores in order
                scores = []
                for i in range(1, len(names) + 1):  # 1-based indexing
                    if i in score_dict:
                        scores.append(score_dict[i])
                    else:
                        scores.append(2.5)  # Default score if missing
                
                if len(scores) == len(names):
                    return list(zip(names, scores))
                    
            except (ValueError, IndexError):
                pass
        
        # Fallback: try to extract regular JSON array from response
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
            "gpt-4o",
            "gpt-4o-mini",
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514"
        ]