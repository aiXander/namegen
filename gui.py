#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
import os
import yaml
import json
import hashlib
import random
from typing import Dict, List, Any
from markov_namegen import MarkovNameGenerator
from name_generator import NameGenerator


class MarkovNameGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Markov Name Generator")
        self.root.geometry("800x700")
        
        # Load default config
        self.config = self.load_config()
        
        # Variables for GUI controls
        self.word_list_mapping = []
        self.saved_ratings = {}  # Store ratings for generated names
        self.word_list_ratings = self.config.get('word_list_ratings', {})  # Store ratings for word lists
        self.setup_gui()
        
        # Initialize generator
        self.generator = None
        
        # Cache for markov model
        self.cached_generator = None
        self.cached_word_list_hash = None
        self.cached_model_params_hash = None
        
        # Load saved ratings
        self.load_saved_ratings()
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open("config.yaml", 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            messagebox.showerror("Error", "config.yaml not found!")
            return {}
    
    def save_config(self):
        """Save current configuration to default YAML file"""
        try:
            with open("config.yaml", 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {str(e)}")
    
    def setup_gui(self):
        """Set up the GUI interface"""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Training Data Tab
        self.setup_training_tab(notebook)
        
        # Generation Parameters Tab (now includes model parameters)
        self.setup_generation_tab(notebook)
        
        # Results Tab
        self.setup_results_tab(notebook)
        
        # Saved Results Tab
        self.setup_saved_results_tab(notebook)
        
        # Control buttons
        self.setup_control_buttons()
    
    def setup_training_tab(self, notebook):
        """Set up training data selection tab"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Training Data")
        
        # Word lists selection
        ttk.Label(frame, text="Select Word Lists:", font=('Arial', 12, 'bold')).pack(pady=5)
        
        # Select/Deselect all buttons (moved to top)
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=5)
        
        ttk.Button(button_frame, text="Select All", 
                  command=self.select_all_word_lists).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Deselect All", 
                  command=self.deselect_all_word_lists).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Show Raw Training Data", 
                  command=self.show_raw_training_data).pack(side='left', padx=5)
        
        # Training data view options right next to the button
        ttk.Label(button_frame, text="View:").pack(side='left', padx=(10, 5))
        self.training_view_var = tk.StringVar(value="sorted")
        ttk.Radiobutton(button_frame, text="Sorted", variable=self.training_view_var, 
                       value="sorted").pack(side='left', padx=2)
        ttk.Radiobutton(button_frame, text="Random", variable=self.training_view_var, 
                       value="random").pack(side='left', padx=2)
        
        # Score range selection
        score_frame = ttk.Frame(frame)
        score_frame.pack(pady=10)
        
        ttk.Label(score_frame, text="Select by Score Range:").pack(side='left', padx=5)
        
        # Min score slider
        ttk.Label(score_frame, text="Min:").pack(side='left', padx=(10, 0))
        self.min_score_var = tk.IntVar(value=0)
        min_scale = ttk.Scale(score_frame, from_=0, to=5, variable=self.min_score_var, 
                             orient='horizontal', length=100, command=self.update_min_score_label)
        min_scale.pack(side='left', padx=5)
        self.min_score_label = ttk.Label(score_frame, text="0")
        self.min_score_label.pack(side='left')
        
        # Max score slider
        ttk.Label(score_frame, text="Max:").pack(side='left', padx=(10, 0))
        self.max_score_var = tk.IntVar(value=5)
        max_scale = ttk.Scale(score_frame, from_=0, to=5, variable=self.max_score_var, 
                             orient='horizontal', length=100, command=self.update_max_score_label)
        max_scale.pack(side='left', padx=5)
        self.max_score_label = ttk.Label(score_frame, text="5")
        self.max_score_label.pack(side='left')
        
        # Apply button
        ttk.Button(score_frame, text="Select by Score Range", 
                  command=self.select_by_score_range).pack(side='left', padx=10)
        
        # Simple scrollable listbox-style selection
        # Create a frame for the scrollable area
        scroll_frame = ttk.Frame(frame)
        scroll_frame.pack(fill='both', expand=True, pady=5)
        
        # Create scrollable frame for word lists with ratings
        canvas = tk.Canvas(scroll_frame)
        listbox_scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
        self.word_list_frame = ttk.Frame(canvas)
        
        self.word_list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.word_list_frame, anchor="nw")
        canvas.configure(yscrollcommand=listbox_scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        listbox_scrollbar.pack(side="right", fill="y")
        
        # Enable mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        def unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind("<Enter>", bind_mousewheel)
        canvas.bind("<Leave>", unbind_mousewheel)
        
        # Get all word lists
        word_lists = self.get_word_lists()
        selected_lists = set(self.config.get('training_data', {}).get('sources', []))
        
        # Store the mapping and create checkboxes with ratings
        self.word_list_mapping = word_lists
        self.word_list_vars = []
        self.word_list_widgets = []
        
        for i, word_list in enumerate(word_lists):
            # Format the display name
            display_name = word_list.replace('_', ' ').replace('.txt', '').title()
            
            # Create frame for this word list
            list_frame = ttk.Frame(self.word_list_frame)
            list_frame.pack(fill='x', padx=5, pady=2)
            
            # Checkbox for selection
            var = tk.BooleanVar()
            if word_list in selected_lists:
                var.set(True)
            self.word_list_vars.append(var)
            
            checkbox = ttk.Checkbutton(list_frame, text=display_name, variable=var)
            checkbox.pack(side='left')
            
            # Star rating for this word list
            rating_frame = ttk.Frame(list_frame)
            rating_frame.pack(side='right')
            
            current_rating = self.word_list_ratings.get(word_list, 0)
            
            # Create star buttons (0-5)
            for star in range(6):
                is_filled = star > 0 and star <= current_rating
                star_text = "★" if is_filled else "☆"
                star_button = tk.Button(rating_frame, text=star_text, 
                                      command=lambda wl=word_list, r=star: self.rate_word_list(wl, r),
                                      bg='gold' if is_filled else 'lightgray',
                                      relief='flat', font=('Arial', 12))
                star_button.pack(side='left', padx=1)
                self.word_list_widgets.append(star_button)
            
            # Rating label
            rating_label = ttk.Label(rating_frame, text=f"({current_rating})")
            rating_label.pack(side='left', padx=5)
            
            self.word_list_widgets.extend([list_frame, checkbox, rating_frame, rating_label])
    
    
    def setup_generation_tab(self, notebook):
        """Set up generation parameters tab (simplified layout)"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Generation Parameters")
        
        # Model Parameters Section
        model_frame = ttk.LabelFrame(frame, text="Model Parameters")
        model_frame.pack(pady=10, padx=10, fill='x')
        
        # Model order
        order_label_frame = ttk.Frame(model_frame)
        order_label_frame.pack(pady=5, fill='x')
        ttk.Label(order_label_frame, text="Model Order:", font=('Arial', 10, 'bold')).pack(side='left')
        ttk.Label(order_label_frame, text="(How many letters to look back when predicting the next letter)", 
                 font=('Arial', 8), foreground='gray').pack(side='left', padx=(5, 0))
        
        self.order_var = tk.IntVar(value=self.config.get('model', {}).get('order', 3))
        order_frame = ttk.Frame(model_frame)
        order_frame.pack(pady=5)
        ttk.Scale(order_frame, from_=1, to=6, variable=self.order_var, 
                 orient='horizontal', length=200, command=self.update_order_label).pack(side='left')
        self.order_label = ttk.Label(order_frame, text=str(self.order_var.get()))
        self.order_label.pack(side='left', padx=10)
        
        # Help text for order
        order_help = ttk.Label(model_frame, 
                              text="• Low (1-2): More creative, less realistic  • High (3-5): More realistic, follows training data closely",
                              font=('Arial', 8), foreground='gray')
        order_help.pack(pady=(0, 10))
        
        # Prior (smoothing factor)
        prior_label_frame = ttk.Frame(model_frame)
        prior_label_frame.pack(pady=5, fill='x')
        ttk.Label(prior_label_frame, text="Prior (Creativity Factor):", font=('Arial', 10, 'bold')).pack(side='left')
        ttk.Label(prior_label_frame, text="(Controls randomness vs. following training patterns)", 
                 font=('Arial', 8), foreground='gray').pack(side='left', padx=(5, 0))
        
        self.prior_var = tk.DoubleVar(value=self.config.get('model', {}).get('prior', 0.01))
        prior_frame = ttk.Frame(model_frame)
        prior_frame.pack(pady=5)
        ttk.Scale(prior_frame, from_=0.001, to=0.1, variable=self.prior_var, 
                 orient='horizontal', length=200, command=self.update_prior_label).pack(side='left')
        self.prior_label = ttk.Label(prior_frame, text=f"{self.prior_var.get():.4f}")
        self.prior_label.pack(side='left', padx=10)
        
        # Help text for prior
        prior_help = ttk.Label(model_frame, 
                              text="• Low (0.001-0.01): Stick to training patterns  • High (0.05-0.1): More creative and varied",
                              font=('Arial', 8), foreground='gray')
        prior_help.pack(pady=(0, 10))
        
        # Backoff
        backoff_label_frame = ttk.Frame(model_frame)
        backoff_label_frame.pack(pady=5, fill='x')
        self.backoff_var = tk.BooleanVar(value=self.config.get('model', {}).get('backoff', True))
        ttk.Checkbutton(backoff_label_frame, text="Use Backoff", 
                       variable=self.backoff_var).pack(side='left')
        ttk.Label(backoff_label_frame, text="(Fall back to simpler patterns when complex ones aren't found)", 
                 font=('Arial', 8), foreground='gray').pack(side='left', padx=(5, 0))
        
        # Help text for backoff
        backoff_help = ttk.Label(model_frame, 
                                text="• Enabled: More reliable generation, smoother names  • Disabled: Stricter patterns, may fail occasionally",
                                font=('Arial', 8), foreground='gray')
        backoff_help.pack(pady=(0, 10))
        
        # Generation Parameters Section
        generation_frame = ttk.LabelFrame(frame, text="Generation Settings")
        generation_frame.pack(pady=10, padx=10, fill='x')
        
        # Number of words
        ttk.Label(generation_frame, text="Number of Names:", font=('Arial', 10, 'bold')).pack(pady=5)
        self.n_words_var = tk.IntVar(value=self.config.get('generation', {}).get('n_words', 20))
        ttk.Entry(generation_frame, textvariable=self.n_words_var, width=10).pack(pady=5)
        
        # Length constraints
        length_frame = ttk.LabelFrame(frame, text="Length Constraints")
        length_frame.pack(pady=10, padx=10, fill='x')
        
        ttk.Label(length_frame, text="Min Length:").grid(row=0, column=0, padx=5, pady=5)
        self.min_length_var = tk.IntVar(value=self.config.get('generation', {}).get('min_length', 4))
        ttk.Entry(length_frame, textvariable=self.min_length_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(length_frame, text="Max Length:").grid(row=0, column=2, padx=5, pady=5)
        self.max_length_var = tk.IntVar(value=self.config.get('generation', {}).get('max_length', 12))
        ttk.Entry(length_frame, textvariable=self.max_length_var, width=10).grid(row=0, column=3, padx=5, pady=5)
        
        # Content constraints
        content_frame = ttk.LabelFrame(frame, text="Content Constraints")
        content_frame.pack(pady=10, padx=10, fill='x')
        
        ttk.Label(content_frame, text="Starts with:").grid(row=0, column=0, padx=5, pady=5)
        self.starts_with_var = tk.StringVar(value=self.config.get('generation', {}).get('starts_with', ''))
        ttk.Entry(content_frame, textvariable=self.starts_with_var, width=15).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(content_frame, text="Ends with:").grid(row=0, column=2, padx=5, pady=5)
        self.ends_with_var = tk.StringVar(value=self.config.get('generation', {}).get('ends_with', ''))
        ttk.Entry(content_frame, textvariable=self.ends_with_var, width=15).grid(row=0, column=3, padx=5, pady=5)
        
        ttk.Label(content_frame, text="Includes:").grid(row=1, column=0, padx=5, pady=5)
        self.includes_var = tk.StringVar(value=self.config.get('generation', {}).get('includes', ''))
        ttk.Entry(content_frame, textvariable=self.includes_var, width=15).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(content_frame, text="Excludes:").grid(row=1, column=2, padx=5, pady=5)
        self.excludes_var = tk.StringVar(value=self.config.get('generation', {}).get('excludes', ''))
        ttk.Entry(content_frame, textvariable=self.excludes_var, width=15).grid(row=1, column=3, padx=5, pady=5)
    
    def setup_results_tab(self, notebook):
        """Set up results display tab with star ratings"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Results")
        
        # Create main container frame
        main_frame = ttk.Frame(frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create a scrollable frame for the results
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        self.results_frame = ttk.Frame(canvas)
        
        self.results_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.results_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Enable mouse wheel scrolling for results
        def on_mousewheel_results(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel_results(event):
            canvas.bind_all("<MouseWheel>", on_mousewheel_results)
        
        def unbind_mousewheel_results(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind("<Enter>", bind_mousewheel_results)
        canvas.bind("<Leave>", unbind_mousewheel_results)
        
        
        # Store widgets for ratings
        self.rating_widgets = []
    
    def setup_control_buttons(self):
        """Set up control buttons"""
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Generate Names", 
                  command=self.generate_names).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Save Config", 
                  command=self.save_current_config).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Load Config", 
                  command=self.load_config_file).pack(side='left', padx=5)
    
    def get_word_lists(self) -> List[str]:
        """Get list of available word lists"""
        word_lists = []
        if os.path.exists("word_lists"):
            word_lists = [f for f in os.listdir("word_lists") if f.endswith('.txt')]
        return sorted(word_lists)
    
    def select_all_word_lists(self):
        """Select all word lists"""
        for var in self.word_list_vars:
            var.set(True)
        # Clear cache since word list selection changed
        self.cached_generator = None
    
    def deselect_all_word_lists(self):
        """Deselect all word lists"""
        for var in self.word_list_vars:
            var.set(False)
        # Clear cache since word list selection changed
        self.cached_generator = None
    
    def update_config_from_gui(self):
        """Update config dictionary from GUI values"""
        # Training data
        selected_sources = []
        for i, var in enumerate(self.word_list_vars):
            if var.get():
                selected_sources.append(self.word_list_mapping[i])
        self.config['training_data']['sources'] = selected_sources
        
        # Save word list ratings
        self.config['word_list_ratings'] = self.word_list_ratings
        
        # Model parameters
        self.config['model']['order'] = self.order_var.get()
        self.config['model']['prior'] = self.prior_var.get()
        self.config['model']['backoff'] = self.backoff_var.get()
        
        # Generation parameters
        self.config['generation']['n_words'] = self.n_words_var.get()
        self.config['generation']['min_length'] = self.min_length_var.get()
        self.config['generation']['max_length'] = self.max_length_var.get()
        self.config['generation']['starts_with'] = self.starts_with_var.get()
        self.config['generation']['ends_with'] = self.ends_with_var.get()
        self.config['generation']['includes'] = self.includes_var.get()
        self.config['generation']['excludes'] = self.excludes_var.get()
    
    def _get_word_list_hash(self):
        """Get a hash of the currently selected word lists"""
        selected_sources = []
        for i, var in enumerate(self.word_list_vars):
            if var.get():
                selected_sources.append(self.word_list_mapping[i])
        return hashlib.md5(str(sorted(selected_sources)).encode()).hexdigest()
    
    def _get_model_params_hash(self):
        """Get a hash of the current model parameters"""
        params = {
            'order': self.order_var.get(),
            'prior': self.prior_var.get(),
            'backoff': self.backoff_var.get()
        }
        return hashlib.md5(str(params).encode()).hexdigest()
    
    def generate_names(self):
        """Generate names based on current settings"""
        try:
            # Update config from GUI
            self.update_config_from_gui()
            
            # Check if any word lists are selected
            selected_sources = []
            for i, var in enumerate(self.word_list_vars):
                if var.get():
                    selected_sources.append(self.word_list_mapping[i])
            if not selected_sources:
                messagebox.showwarning("Warning", "Please select at least one word list!")
                return
            
            # Check if we can reuse cached generator
            current_word_list_hash = self._get_word_list_hash()
            current_model_params_hash = self._get_model_params_hash()
            
            if (self.cached_generator is not None and
                self.cached_word_list_hash == current_word_list_hash and
                self.cached_model_params_hash == current_model_params_hash):
                # Use cached generator
                self.generator = self.cached_generator
                print("Using cached markov model")
            else:
                # Create new generator
                print("Creating new markov model")
                self.generator = MarkovNameGenerator()
                self.generator.config = self.config
                
                # Load training data
                self.generator.training_words = self.generator._load_training_data()
                
                # Recreate name generator with new settings
                model_config = self.config['model']
                self.generator.generator = NameGenerator(
                    data=self.generator.training_words,
                    order=model_config['order'],
                    prior=model_config['prior'],
                    backoff=model_config['backoff']
                )
                
                # Cache the generator and hashes
                self.cached_generator = self.generator
                self.cached_word_list_hash = current_word_list_hash
                self.cached_model_params_hash = current_model_params_hash
            
            # Generate names
            names = self.generator.generate_names()
            
            # Display results with star ratings
            self.display_results_with_ratings(names)
            
            # Store results for export
            self.last_results = names
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate names: {str(e)}")
    
    def save_current_config(self):
        """Save current GUI settings to config file with custom name"""
        # Get config name from user
        config_name = simpledialog.askstring(
            "Save Configuration",
            "Enter a name for this configuration:",
            initialvalue="my_config"
        )
        
        if not config_name:
            return
        
        # Ensure saved_configs directory exists
        saved_configs_dir = "saved_configs"
        os.makedirs(saved_configs_dir, exist_ok=True)
        
        # Add .yaml extension if not present
        if not config_name.endswith('.yaml'):
            config_name += '.yaml'
        
        # Save to saved_configs directory
        config_path = os.path.join(saved_configs_dir, config_name)
        
        try:
            self.update_config_from_gui()
            with open(config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
            messagebox.showinfo("Success", f"Configuration saved as '{config_name}'!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {str(e)}")
    
    def load_config_file(self):
        """Load configuration from file"""
        # Default to saved_configs directory if it exists
        initial_dir = "saved_configs" if os.path.exists("saved_configs") else "."
        
        filename = filedialog.askopenfilename(
            title="Select config file",
            initialdir=initial_dir,
            filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r') as f:
                    self.config = yaml.safe_load(f)
                messagebox.showinfo("Success", "Configuration loaded!")
                # TODO: Update GUI controls with loaded config
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load config: {str(e)}")
    
    def export_txt(self):
        """Export results to text file"""
        if not hasattr(self, 'last_results') or not self.last_results:
            messagebox.showwarning("Warning", "No results to export!")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w') as f:
                    for name in self.last_results:
                        f.write(name + "\n")
                messagebox.showinfo("Success", f"Results exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {str(e)}")
    
    def export_json(self):
        """Export results to JSON file"""
        if not hasattr(self, 'last_results') or not self.last_results:
            messagebox.showwarning("Warning", "No results to export!")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(self.last_results, f, indent=2)
                messagebox.showinfo("Success", f"Results exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {str(e)}")
    
    def copy_to_clipboard(self):
        """Copy results to clipboard"""
        if not hasattr(self, 'last_results') or not self.last_results:
            messagebox.showwarning("Warning", "No results to copy!")
            return
        
        try:
            text = "\n".join(self.last_results)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("Success", "Results copied to clipboard!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy: {str(e)}")
    
    def setup_saved_results_tab(self, notebook):
        """Set up saved results tab showing rated names"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Saved Results")
        
        # Header with buttons
        header_frame = ttk.Frame(frame)
        header_frame.pack(pady=10, fill='x')
        
        ttk.Label(header_frame, text="Saved Names (Sorted by Rating)", 
                 font=('Arial', 12, 'bold')).pack(side='left')
        
        # Move refresh/clear buttons next to the title
        ttk.Button(header_frame, text="Refresh", 
                  command=self.refresh_saved_results).pack(side='right', padx=5)
        ttk.Button(header_frame, text="Clear All", 
                  command=self.clear_saved_results).pack(side='right', padx=5)
        
        # Create scrollable frame for saved names with delete buttons
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        self.saved_results_frame = ttk.Frame(canvas)
        
        self.saved_results_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.saved_results_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")
        
        # Enable mouse wheel scrolling for saved results
        def on_mousewheel_saved(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel_saved(event):
            canvas.bind_all("<MouseWheel>", on_mousewheel_saved)
        
        def unbind_mousewheel_saved(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind("<Enter>", bind_mousewheel_saved)
        canvas.bind("<Leave>", unbind_mousewheel_saved)
        
        # Store widgets for saved results
        self.saved_result_widgets = []
        
        
        # Load and display saved results
        self.refresh_saved_results()
    
    def show_raw_training_data(self):
        """Show raw training data in a popup window"""
        # Get selected word lists
        selected_sources = []
        for i, var in enumerate(self.word_list_vars):
            if var.get():
                selected_sources.append(self.word_list_mapping[i])
        
        if not selected_sources:
            messagebox.showwarning("Warning", "Please select at least one word list!")
            return
        
        # Collect all words from selected lists
        all_words = []
        for word_list_file in selected_sources:
            file_path = os.path.join("word_lists", word_list_file)
            try:
                with open(file_path, 'r') as f:
                    words = [line.strip() for line in f if line.strip()]
                    all_words.extend(words)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to read {word_list_file}: {str(e)}")
                return
        
        # Apply sorting/shuffling based on radio button selection
        if self.training_view_var.get() == "sorted":
            all_words.sort()
        else:
            random.shuffle(all_words)
        
        # Create popup window
        popup = tk.Toplevel(self.root)
        popup.title("Raw Training Data")
        popup.geometry("600x400")
        
        # Display words
        text_widget = scrolledtext.ScrolledText(popup, wrap=tk.WORD)
        text_widget.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Enable mouse wheel scrolling for raw training data popup
        def on_mousewheel_popup(event):
            text_widget.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel_popup(event):
            text_widget.bind_all("<MouseWheel>", on_mousewheel_popup)
        
        def unbind_mousewheel_popup(event):
            text_widget.unbind_all("<MouseWheel>")
        
        text_widget.bind("<Enter>", bind_mousewheel_popup)
        text_widget.bind("<Leave>", unbind_mousewheel_popup)
        
        text_widget.insert(tk.END, f"Total words: {len(all_words)}\n\n")
        for word in all_words:
            text_widget.insert(tk.END, word + "\n")
        
        text_widget.config(state=tk.DISABLED)
    
    def display_results_with_ratings(self, names):
        """Display results with star rating controls"""
        # Clear previous results
        for widget in self.rating_widgets:
            widget.destroy()
        self.rating_widgets = []
        
        if not names:
            no_results_label = ttk.Label(self.results_frame, 
                                       text="No names generated. Try adjusting your parameters.")
            no_results_label.pack(pady=20)
            self.rating_widgets.append(no_results_label)
            return
        
        # Header
        header_label = ttk.Label(self.results_frame, 
                               text=f"Generated {len(names)} names:", 
                               font=('Arial', 12, 'bold'))
        header_label.pack(pady=10)
        self.rating_widgets.append(header_label)
        
        # Display each name with star rating
        for i, name in enumerate(names, 1):
            name_frame = ttk.Frame(self.results_frame)
            name_frame.pack(fill='x', padx=20, pady=5)
            
            # Name label
            name_label = ttk.Label(name_frame, text=f"{i:2d}. {name}", 
                                 font=('Arial', 11))
            name_label.pack(side='left')
            
            # Star rating buttons
            rating_frame = ttk.Frame(name_frame)
            rating_frame.pack(side='right')
            
            # Get current rating if exists
            current_rating = self.saved_ratings.get(name, 0)
            
            # Create star buttons (1-5, plus 0 for unrated)
            for star in range(6):
                # Fix the 1-star rating bug by using proper comparison
                is_filled = star > 0 and star <= current_rating
                star_text = "★" if is_filled else "☆"
                star_button = tk.Button(rating_frame, text=star_text, 
                                      command=lambda n=name, r=star: self.rate_name(n, r),
                                      bg='gold' if is_filled else 'lightgray',
                                      relief='flat', font=('Arial', 14))
                star_button.pack(side='left', padx=1)
                self.rating_widgets.append(star_button)
            
            # Rating label
            rating_label = ttk.Label(rating_frame, text=f"({current_rating})")
            rating_label.pack(side='left', padx=5)
            
            self.rating_widgets.extend([name_frame, name_label, rating_frame, rating_label])
    
    def rate_name(self, name, rating):
        """Rate a name with the given number of stars"""
        self.saved_ratings[name] = rating
        self.save_ratings_to_file()
        
        # Refresh the display to update star colors
        if hasattr(self, 'last_results'):
            self.display_results_with_ratings(self.last_results)
        
        # Refresh saved results tab
        self.refresh_saved_results()
    
    def refresh_saved_results(self):
        """Refresh the saved results display with delete buttons"""
        # Clear previous widgets
        for widget in self.saved_result_widgets:
            widget.destroy()
        self.saved_result_widgets = []
        
        if not self.saved_ratings:
            no_results_label = ttk.Label(self.saved_results_frame, 
                                       text="No saved names yet. Rate some names in the Results tab!")
            no_results_label.pack(pady=20)
            self.saved_result_widgets.append(no_results_label)
            return
        
        # Sort by rating (descending)
        sorted_names = sorted(self.saved_ratings.items(), key=lambda x: x[1], reverse=True)
        
        # Header
        header_label = ttk.Label(self.saved_results_frame, 
                               text=f"Saved Names ({len([n for n, r in sorted_names if r > 0])} total):",
                               font=('Arial', 12, 'bold'))
        header_label.pack(pady=10)
        self.saved_result_widgets.append(header_label)
        
        # Display each saved name with rating and delete button
        for name, rating in sorted_names:
            if rating > 0:  # Only show rated names
                name_frame = ttk.Frame(self.saved_results_frame)
                name_frame.pack(fill='x', padx=20, pady=2)
                
                # Name and rating
                stars = "★" * rating + "☆" * (5 - rating)
                name_label = ttk.Label(name_frame, text=f"{name:<20} {stars} ({rating}/5)", 
                                     font=('Arial', 11))
                name_label.pack(side='left')
                
                # Delete button
                delete_button = ttk.Button(name_frame, text="Delete", 
                                         command=lambda n=name: self.delete_saved_name(n))
                delete_button.pack(side='right')
                
                self.saved_result_widgets.extend([name_frame, name_label, delete_button])
    
    def clear_saved_results(self):
        """Clear all saved ratings"""
        if messagebox.askyesno("Confirm", "Are you sure you want to clear all saved ratings?"):
            self.saved_ratings.clear()
            self.save_ratings_to_file()
            self.refresh_saved_results()
            
            # Refresh results display if available
            if hasattr(self, 'last_results'):
                self.display_results_with_ratings(self.last_results)
    
    def delete_saved_name(self, name):
        """Delete a specific name from saved results"""
        if name in self.saved_ratings:
            del self.saved_ratings[name]
            self.save_ratings_to_file()
            self.refresh_saved_results()
            
            # Refresh results display if available to update star colors
            if hasattr(self, 'last_results'):
                self.display_results_with_ratings(self.last_results)
    
    def rate_word_list(self, word_list, rating):
        """Rate a word list with the given number of stars"""
        self.word_list_ratings[word_list] = rating
        self.update_config_from_gui()
        self.save_config()
        
        # Refresh the display to update star colors
        self.refresh_word_list_display()
    
    def refresh_word_list_display(self):
        """Refresh the word list display to update star ratings"""
        # Clear existing widgets
        for widget in self.word_list_widgets:
            widget.destroy()
        self.word_list_widgets = []
        
        # Get current selections
        current_selections = [var.get() for var in self.word_list_vars]
        
        # Recreate the word list display
        for i, word_list in enumerate(self.word_list_mapping):
            # Format the display name
            display_name = word_list.replace('_', ' ').replace('.txt', '').title()
            
            # Create frame for this word list
            list_frame = ttk.Frame(self.word_list_frame)
            list_frame.pack(fill='x', padx=5, pady=2)
            
            # Checkbox for selection - preserve current state
            var = self.word_list_vars[i]
            checkbox = ttk.Checkbutton(list_frame, text=display_name, variable=var)
            checkbox.pack(side='left')
            
            # Star rating for this word list
            rating_frame = ttk.Frame(list_frame)
            rating_frame.pack(side='right')
            
            current_rating = self.word_list_ratings.get(word_list, 0)
            
            # Create star buttons (0-5)
            for star in range(6):
                is_filled = star > 0 and star <= current_rating
                star_text = "\u2605" if is_filled else "\u2606"
                star_button = tk.Button(rating_frame, text=star_text, 
                                      command=lambda wl=word_list, r=star: self.rate_word_list(wl, r),
                                      bg='gold' if is_filled else 'lightgray',
                                      relief='flat', font=('Arial', 12))
                star_button.pack(side='left', padx=1)
                self.word_list_widgets.append(star_button)
            
            # Rating label
            rating_label = ttk.Label(rating_frame, text=f"({current_rating})")
            rating_label.pack(side='left', padx=5)
            
            self.word_list_widgets.extend([list_frame, checkbox, rating_frame, rating_label])
    
    def select_by_score_range(self):
        """Select word lists within the specified score range"""
        min_score = self.min_score_var.get()
        max_score = self.max_score_var.get()
        
        # Ensure min <= max
        if min_score > max_score:
            min_score, max_score = max_score, min_score
            self.min_score_var.set(min_score)
            self.max_score_var.set(max_score)
            self.update_min_score_label(min_score)
            self.update_max_score_label(max_score)
        
        # Select word lists within the score range
        selected_count = 0
        for i, word_list in enumerate(self.word_list_mapping):
            rating = self.word_list_ratings.get(word_list, 0)
            if min_score <= rating <= max_score:
                self.word_list_vars[i].set(True)
                selected_count += 1
            else:
                self.word_list_vars[i].set(False)
        
        # Clear cache since selection changed
        self.cached_generator = None
    
    def update_min_score_label(self, value):
        """Update min score label with integer value"""
        self.min_score_label.config(text=str(int(float(value))))
    
    def update_max_score_label(self, value):
        """Update max score label with integer value"""
        self.max_score_label.config(text=str(int(float(value))))
    
    def update_order_label(self, value):
        """Update order label with integer value"""
        self.order_label.config(text=str(int(float(value))))
    
    def update_prior_label(self, value):
        """Update prior label with 4 decimal places"""
        self.prior_label.config(text=f"{float(value):.4f}")
    
    def load_saved_ratings(self):
        """Load saved ratings from file"""
        try:
            if os.path.exists("saved_ratings.json"):
                with open("saved_ratings.json", 'r') as f:
                    self.saved_ratings = json.load(f)
        except Exception as e:
            print(f"Error loading saved ratings: {e}")
            self.saved_ratings = {}
    
    def save_ratings_to_file(self):
        """Save ratings to file"""
        try:
            with open("saved_ratings.json", 'w') as f:
                json.dump(self.saved_ratings, f, indent=2)
        except Exception as e:
            print(f"Error saving ratings: {e}")


def main():
    """Main function to run the GUI"""
    root = tk.Tk()
    app = MarkovNameGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()