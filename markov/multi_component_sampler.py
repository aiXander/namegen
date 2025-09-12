"""
Multi-component sampling system for Markov name generation.
Provides template-based generation with fixed components and variable segments.
"""

import random
import itertools
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from .markov_model import MarkovModel
from .constraint_sampler import GenerationConstraints


@dataclass
class VariableSegment:
    """Defines a variable segment to be filled by Markov sampling"""
    position: int  # Position in template (0-based)
    length_range: Tuple[int, int]  # Min/max length for this segment
    left_context: str = ""  # Fixed content to the left
    right_context: str = ""  # Fixed content to the right
    constraints: Optional['SegmentConstraints'] = None


@dataclass
class SegmentConstraints:
    """Constraints specific to a variable segment"""
    includes: str = ""
    excludes: str = ""
    starts_with: str = ""
    ends_with: str = ""
    character_set: Optional[Set[str]] = None  # Allowed characters


@dataclass
class ComponentTemplate:
    """Defines a flexible sampling template with fixed and variable segments"""
    fixed_components: List[str]  # Required word components like ["co", "mind"]
    component_positions: List[int]  # Start positions for each component
    variable_segments: List[VariableSegment]  # Segments to be filled by Markov sampling
    total_length: int  # Target word length
    template_string: str = ""  # String representation for debugging
    
    def __post_init__(self):
        """Generate template string representation"""
        if not self.template_string:
            parts = []
            seg_idx = 0
            comp_idx = 0
            pos = 0
            
            while pos < self.total_length:
                # Check if there's a component starting at this position
                if comp_idx < len(self.component_positions) and pos == self.component_positions[comp_idx]:
                    parts.append(f"[{self.fixed_components[comp_idx]}]")
                    pos += len(self.fixed_components[comp_idx])
                    comp_idx += 1
                # Check if there's a variable segment at this position
                elif seg_idx < len(self.variable_segments) and pos == self.variable_segments[seg_idx].position:
                    seg = self.variable_segments[seg_idx]
                    parts.append(f"<VAR{seg_idx}:{seg.length_range[0]}-{seg.length_range[1]}>")
                    pos += seg.length_range[1]  # Use max length for positioning
                    seg_idx += 1
                else:
                    pos += 1
                    
            self.template_string = "".join(parts)


@dataclass
class ComponentConstraints(GenerationConstraints):
    """Extended constraints supporting multi-component generation"""
    components: List[str] = field(default_factory=list)  # Required word components
    component_order: Optional[List[int]] = None  # Specific component ordering (indices)
    allow_component_overlap: bool = False  # Whether components can overlap
    component_separation: Tuple[int, int] = (0, 5)  # Min/max chars between components
    variable_segment_constraints: Dict[int, SegmentConstraints] = field(default_factory=dict)
    max_templates: int = 20  # Maximum number of templates to try
    
    def __post_init__(self):
        super().__post_init__()
        # Ensure all components are lowercase
        self.components = [comp.lower() for comp in self.components]


class TemplateGenerator:
    """Generates sampling templates from component specifications"""
    
    def generate_templates(self, constraints: ComponentConstraints) -> List[ComponentTemplate]:
        """
        Generate possible templates for component arrangement.
        
        Args:
            constraints: Component constraints including components and length range
            
        Returns:
            List of possible templates to try
        """
        if not constraints.components:
            return []
            
        templates = []
        components = constraints.components
        
        # Generate different component orderings
        orderings = self._get_component_orderings(components, constraints.component_order)
        
        # For each ordering, generate templates with different spacing
        for ordering in orderings[:constraints.max_templates // len(orderings) + 1]:
            component_templates = self._generate_spacing_templates(
                ordering, constraints.min_length, constraints.max_length,
                constraints.component_separation
            )
            templates.extend(component_templates)
            
        return templates[:constraints.max_templates]
    
    def _get_component_orderings(self, components: List[str], 
                               forced_order: Optional[List[int]]) -> List[List[str]]:
        """Get possible component orderings"""
        if forced_order:
            return [[components[i] for i in forced_order]]
        else:
            # Generate all permutations
            return list(itertools.permutations(components))
    
    def _generate_spacing_templates(self, components: List[str], min_length: int, 
                                  max_length: int, separation_range: Tuple[int, int]) -> List[ComponentTemplate]:
        """Generate templates with different spacing between components"""
        templates = []
        
        # Calculate fixed component length
        fixed_length = sum(len(comp) for comp in components)
        min_spacing = len(components) + 1  # At least one space before, between, and after
        
        # Check if it's possible to fit components
        if fixed_length + min_spacing > max_length:
            return []
            
        # Try different target lengths
        for target_length in range(max(min_length, fixed_length + min_spacing), max_length + 1):
            available_space = target_length - fixed_length
            
            # Distribute space among variable segments (before, between components, after)
            n_segments = len(components) + 1
            template = self._create_spacing_template(components, target_length, available_space, 
                                                   n_segments, separation_range)
            if template:
                templates.append(template)
                
        return templates
    
    def _create_spacing_template(self, components: List[str], target_length: int,
                               available_space: int, n_segments: int,
                               separation_range: Tuple[int, int]) -> Optional[ComponentTemplate]:
        """Create a specific spacing template"""
        # Simpler approach: just create one template per target length
        min_sep, max_sep = separation_range
        
        # Basic validation
        if available_space < 0:
            return None
            
        # Create simple template with even distribution of space
        segment_lengths = []
        space_per_segment = available_space // n_segments
        remainder = available_space % n_segments
        
        for i in range(n_segments):
            length = space_per_segment + (1 if i < remainder else 0)
            segment_lengths.append(max(0, length))
        
        # Build template
        variable_segments = []
        component_positions = []
        current_pos = 0
        
        for i in range(len(components)):
            # Add variable segment before component
            if segment_lengths[i] > 0:
                var_seg = VariableSegment(
                    position=current_pos,
                    length_range=(0, segment_lengths[i]),
                    left_context="",
                    right_context=""
                )
                variable_segments.append(var_seg)
                current_pos += segment_lengths[i]
            
            # Add fixed component
            component_positions.append(current_pos)
            current_pos += len(components[i])
        
        # Add final variable segment
        if len(segment_lengths) > len(components) and segment_lengths[-1] > 0:
            var_seg = VariableSegment(
                position=current_pos,
                length_range=(0, segment_lengths[-1]),
                left_context="",
                right_context=""
            )
            variable_segments.append(var_seg)
        
        return ComponentTemplate(
            fixed_components=list(components),
            component_positions=component_positions,
            variable_segments=variable_segments,
            total_length=target_length
        )


class SegmentSampler:
    """Handles sampling individual variable segments with context awareness"""
    
    def __init__(self, markov_model: MarkovModel):
        self.model = markov_model
    
    def sample_segment(self, segment: VariableSegment, 
                      constraints: Optional[SegmentConstraints] = None) -> str:
        """
        Sample content for a variable segment with bidirectional context awareness.
        
        Args:
            segment: Variable segment to sample
            constraints: Optional segment-specific constraints
            
        Returns:
            Generated content for the segment
        """
        min_len, max_len = segment.length_range
        if max_len == 0:
            return ""
            
        target_length = random.randint(min_len, max_len)
        if target_length == 0:
            return ""
        
        # Use forward sampling with context awareness
        return self._sample_forward_with_context(segment, target_length, constraints)
    
    def _sample_forward_with_context(self, segment: VariableSegment, 
                                   target_length: int, 
                                   constraints: Optional[SegmentConstraints]) -> str:
        """Sample segment using forward Markov sampling with context"""
        if target_length == 0:
            return ""
            
        # Initialize with left context padding
        left_context = segment.left_context[-self.model.order:] if segment.left_context else ""
        word = "#" * max(0, self.model.order - len(left_context)) + left_context
        
        sampled_content = ""
        attempts = 0
        max_attempts = 1000
        
        while len(sampled_content) < target_length and attempts < max_attempts:
            context = word[-self.model.order:] if len(word) >= self.model.order else word
            
            # Get probabilities for next character
            base_probs = self.model.chains.get(context)
            if not base_probs:
                # Try shorter context
                for i in range(1, len(context)):
                    shorter_context = context[i:]
                    base_probs = self.model.chains.get(shorter_context)
                    if base_probs:
                        break
                        
            if not base_probs:
                break
                
            # Apply constraints
            modified_probs = self._apply_segment_constraints(
                base_probs, sampled_content, constraints, target_length
            )
            
            # Sample next character
            next_char = self._sample_from_probabilities(modified_probs)
            if next_char and next_char != "#":
                sampled_content += next_char
                word += next_char
            else:
                break
                
            attempts += 1
        
        return sampled_content[:target_length]
    
    def _apply_segment_constraints(self, base_probs: List[float], current_content: str,
                                 constraints: Optional[SegmentConstraints],
                                 target_length: int) -> List[float]:
        """Apply segment-specific constraints to probabilities"""
        modified_probs = base_probs.copy()
        
        if not constraints:
            return modified_probs
            
        # Apply character set constraints
        if constraints.character_set:
            for i, char in enumerate(self.model.alphabet):
                if char not in constraints.character_set and char != "#":
                    modified_probs[i] = 0.0
        
        # Apply excludes constraint
        if constraints.excludes:
            for i, char in enumerate(self.model.alphabet):
                if char != "#" and constraints.excludes in (current_content + char):
                    modified_probs[i] = 0.0
        
        # Renormalize
        total = sum(modified_probs)
        if total > 0:
            modified_probs = [p / total for p in modified_probs]
            
        return modified_probs
    
    def _sample_from_probabilities(self, probs: List[float]) -> Optional[str]:
        """Sample a character from probability distribution"""
        total = sum(probs)
        if total <= 0:
            return None
            
        rand = random.random() * total
        accumulator = 0.0
        
        for i, prob in enumerate(probs):
            accumulator += prob
            if rand < accumulator:
                return self.model.alphabet[i]
                
        return None


class MultiComponentSampler:
    """Orchestrates template-based sampling with component constraints"""
    
    def __init__(self, markov_model: MarkovModel):
        self.model = markov_model
        self.template_generator = TemplateGenerator()
        self.segment_sampler = SegmentSampler(markov_model)
    
    def generate_with_components(self, constraints: ComponentConstraints) -> Optional[str]:
        """
        Generate a name with multi-component constraints.
        
        Args:
            constraints: All generation constraints including components
            
        Returns:
            Generated name meeting constraints, or None if impossible
        """
        if not constraints.components:
            return None
            
        # Generate possible templates
        templates = self.template_generator.generate_templates(constraints)
        if not templates:
            return None
            
        # Try each template
        for template in templates:
            result = self._sample_from_template(template, constraints)
            if result and self._validates_all_constraints(result, constraints):
                return result
        
        return None
    
    def _sample_from_template(self, template: ComponentTemplate, 
                            constraints: ComponentConstraints) -> Optional[str]:
        """Sample a word from a specific template"""
        # Sample variable segments
        segment_contents = {}
        for i, segment in enumerate(template.variable_segments):
            seg_constraints = constraints.variable_segment_constraints.get(i)
            content = self.segment_sampler.sample_segment(segment, seg_constraints)
            segment_contents[i] = content
        
        # Assemble final word
        return self._assemble_word_from_template(template, segment_contents)
    
    def _assemble_word_from_template(self, template: ComponentTemplate, 
                                   segment_contents: Dict[int, str]) -> str:
        """Assemble final word from template and sampled segments"""
        # Much simpler assembly - just interleave segments and components
        word_parts = []
        
        # Add segments and components in order
        seg_idx = 0
        for i, comp_pos in enumerate(template.component_positions):
            # Add any variable segment before this component
            while seg_idx < len(template.variable_segments) and template.variable_segments[seg_idx].position <= comp_pos:
                content = segment_contents.get(seg_idx, "")
                if content:
                    word_parts.append(content)
                seg_idx += 1
                
            # Add the component
            word_parts.append(template.fixed_components[i])
        
        # Add any remaining segments
        while seg_idx < len(template.variable_segments):
            content = segment_contents.get(seg_idx, "")
            if content:
                word_parts.append(content)
            seg_idx += 1
        
        return "".join(word_parts)
    
    def _validates_all_constraints(self, word: str, constraints: ComponentConstraints) -> bool:
        """Validate that generated word meets all constraints"""
        # Check basic length constraints
        if not (constraints.min_length <= len(word) <= constraints.max_length):
            return False
            
        # Check that all components are present
        for component in constraints.components:
            if component not in word:
                return False
        
        # Check basic string constraints
        if constraints.starts_with and not word.startswith(constraints.starts_with):
            return False
            
        if constraints.ends_with and not word.endswith(constraints.ends_with):
            return False
            
        if constraints.includes and constraints.includes not in word:
            return False
            
        if constraints.excludes and constraints.excludes in word:
            return False
        
        return True