#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
import os
import yaml
import json
import hashlib
import random
import threading
import atexit
from typing import Dict, List, Any
from markov_namegen import MarkovNameGenerator
from markov.name_generator import NameGenerator
from ai.llm_scorer import LLMScorer


class WordListViewModal:
    def __init__(self, parent, word_list_name, word_list_path):
        self.parent = parent
        self.word_list_name = word_list_name
        self.word_list_path = word_list_path
        self.popup = None
        self.view_var = None
        self.text_widget = None
        
    def show(self):
        """Show the word list view modal"""
        if self.popup:
            return
            
        # Create popup window
        self.popup = tk.Toplevel(self.parent)
        self.popup.title(f"View Word List - {self.word_list_name}")
        self.popup.geometry("600x400")
        self.popup.configure(bg='white')
        
        # Create control frame
        control_frame = ttk.Frame(self.popup)
        control_frame.pack(fill='x', padx=10, pady=5)
        
        # View options
        ttk.Label(control_frame, text="View:").pack(side='left', padx=5)
        self.view_var = tk.StringVar(value="sorted")
        ttk.Radiobutton(control_frame, text="Sorted", variable=self.view_var, 
                       value="sorted", command=self.refresh_view).pack(side='left', padx=2)
        ttk.Radiobutton(control_frame, text="Random", variable=self.view_var, 
                       value="random", command=self.refresh_view).pack(side='left', padx=2)
        
        # Create text widget
        self.text_widget = scrolledtext.ScrolledText(self.popup, wrap=tk.WORD,
                                                    bg='white', fg='black', 
                                                    selectbackground='#4a90e2',
                                                    selectforeground='white')
        self.text_widget.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Load and display content
        self.refresh_view()
        
        # Handle window close
        self.popup.protocol("WM_DELETE_WINDOW", self.close)
        
    def refresh_view(self):
        """Refresh the view based on the selected option"""
        if not self.text_widget:
            return
            
        try:
            # Read words from file
            with open(self.word_list_path, 'r') as f:
                words = [line.strip() for line in f if line.strip()]
            
            # Apply sorting/shuffling
            if self.view_var.get() == "sorted":
                words.sort()
            else:
                random.shuffle(words)
            
            # Clear and populate text widget
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.delete(1.0, tk.END)
            self.text_widget.insert(tk.END, f"Total words: {len(words)}\n\n")
            for word in words:
                self.text_widget.insert(tk.END, word + "\n")
            self.text_widget.config(state=tk.DISABLED)
            
        except Exception as e:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.delete(1.0, tk.END)
            self.text_widget.insert(tk.END, f"Error loading word list: {str(e)}")
            self.text_widget.config(state=tk.DISABLED)
    
    def close(self):
        """Close the modal"""
        if self.popup:
            self.popup.destroy()
            self.popup = None


class MarkovNameGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Markov Name Generator")
        self.root.geometry("800x700")
        
        # Apply dark theme
        self.setup_dark_theme()
        
        # Flag to track if application is being destroyed
        self.is_closing = False
        
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
        
        # Auto-save functionality
        self.auto_save_timer = None
        self.start_auto_save_timer()
        
        # Register shutdown handler
        atexit.register(self.save_state_on_exit)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Load latest state if available
        self.load_latest_state()
        
    def setup_dark_theme(self):
        """Configure light theme for the entire GUI"""
        # Configure root window
        self.root.configure(bg='white')
        
        # Configure ttk style
        style = ttk.Style()
        
        # Configure colors for ttk widgets
        style.theme_use('clam')
        
        # Configure ttk styles
        style.configure('TFrame', background='white')
        style.configure('TLabel', background='white', foreground='black')
        style.configure('TButton', background='#f0f0f0', foreground='black', borderwidth=1, relief='solid')
        style.configure('TCheckbutton', background='white', foreground='black', focuscolor='none')
        style.configure('TRadiobutton', background='white', foreground='black', focuscolor='none')
        style.configure('TScale', background='white', troughcolor='#e0e0e0', borderwidth=0)
        style.configure('TEntry', fieldbackground='white', foreground='black', borderwidth=1, insertcolor='black')
        style.configure('TCombobox', fieldbackground='white', foreground='black', borderwidth=1)
        style.configure('TScrollbar', background='#d0d0d0', troughcolor='white', borderwidth=0)
        style.configure('TNotebook', background='white', borderwidth=0)
        style.configure('TNotebook.Tab', background='#f0f0f0', foreground='black', padding=(12, 8))
        style.configure('TLabelframe', background='white', foreground='black', borderwidth=1, relief='solid')
        style.configure('TLabelframe.Label', background='white', foreground='black')
        style.configure('TProgressbar', background='#4a90e2', troughcolor='#e0e0e0', borderwidth=0)
        
        # Configure hover and active states
        style.map('TButton',
                  background=[('active', '#e0e0e0'), ('pressed', '#d0d0d0')])
        style.map('TCheckbutton',
                  background=[('active', 'white')])
        style.map('TRadiobutton',
                  background=[('active', 'white')])
        style.map('TNotebook.Tab',
                  background=[('selected', '#e0e0e0'), ('active', '#f5f5f5')])
        
        # Configure tk widgets (non-ttk)
        self.root.option_add('*Background', 'white')
        self.root.option_add('*Foreground', 'black')
        self.root.option_add('*selectBackground', '#4a90e2')
        self.root.option_add('*selectForeground', 'white')
        self.root.option_add('*Text.Background', 'white')
        self.root.option_add('*Text.Foreground', 'black')
        self.root.option_add('*Entry.Background', 'white')
        self.root.option_add('*Entry.Foreground', 'black')
        self.root.option_add('*Listbox.Background', 'white')
        self.root.option_add('*Listbox.Foreground', 'black')
        self.root.option_add('*Canvas.Background', 'white')
        
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
        
        # Markov Parameters Tab (now includes model parameters)
        self.setup_generation_tab(notebook)
        
        # Results Tab
        self.setup_results_tab(notebook)
        
        # Saved Results Tab
        self.setup_saved_results_tab(notebook)
        
        # AI Tab
        self.setup_ai_tab(notebook)
        
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
        
        # Enable mouse wheel scrolling - simple approach
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind mousewheel to the entire scroll_frame
        scroll_frame.bind("<MouseWheel>", on_mousewheel)
        canvas.bind("<MouseWheel>", on_mousewheel)
        self.word_list_frame.bind("<MouseWheel>", on_mousewheel)
        
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
            
            # View button for this word list (positioned between checkbox and rating)
            view_button = ttk.Button(list_frame, text="View", 
                                   command=lambda wl=word_list, dn=display_name: self.view_word_list(wl, dn))
            view_button.pack(side='right', padx=5)
            
            current_rating = self.word_list_ratings.get(word_list, 0)
            
            # Create star buttons (0-5)
            for star in range(6):
                is_filled = star > 0 and star <= current_rating
                star_text = "★" if is_filled else "☆"
                star_button = tk.Button(rating_frame, text=star_text, 
                                      command=lambda wl=word_list, r=star: self.rate_word_list(wl, r),
                                      bg='#DAA520' if is_filled else '#f0f0f0',
                                      fg='black', relief='flat', font=('Arial', 12),
                                      activebackground='#e0e0e0', activeforeground='black',
                                      borderwidth=0)
                star_button.pack(side='left', padx=1)
                self.word_list_widgets.append(star_button)
            
            # Rating label
            rating_label = ttk.Label(rating_frame, text=f"({current_rating})")
            rating_label.pack(side='left', padx=5)
            
            self.word_list_widgets.extend([list_frame, checkbox, view_button, rating_frame, rating_label])
    
    def view_word_list(self, word_list_file, display_name):
        """View a specific word list using the modal"""
        word_list_path = os.path.join("word_lists", word_list_file)
        modal = WordListViewModal(self.root, display_name, word_list_path)
        modal.show()
    
    def setup_generation_tab(self, notebook):
        """Set up generation parameters tab (simplified layout)"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Markov Parameters")
        
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
    
    def setup_ai_tab(self, notebook):
        """Set up AI-powered name scoring tab"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="AI")
        
        # Create main container frame
        main_frame = ttk.Frame(frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Description section
        desc_frame = ttk.LabelFrame(main_frame, text="Description")
        desc_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        ttk.Label(desc_frame, text="What are these names for? (e.g., company, website, product)").pack(anchor='e', padx=5, pady=5)
        
        # Create scrolled text widget for description
        self.ai_description_text = scrolledtext.ScrolledText(desc_frame, height=4, width=70,
                                                            bg='white', fg='black', 
                                                            selectbackground='#4a90e2',
                                                            selectforeground='white')
        self.ai_description_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Instructions section
        instructions_frame = ttk.LabelFrame(main_frame, text="Instructions")
        instructions_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Get default instructions from config
        default_instructions = self.config.get('llm', {}).get('default_instructions', 
            "Based on the provided description and scored names, score the following generated name ideas on a scale of 0.0 to 5.0, where 5.0 is excellent and 0.0 is poor.")
        
        self.ai_instructions_text = scrolledtext.ScrolledText(instructions_frame, height=3, width=70,
                                                            bg='white', fg='black', 
                                                            selectbackground='#4a90e2',
                                                            selectforeground='white')
        self.ai_instructions_text.pack(fill='both', expand=True, padx=5, pady=5)
        self.ai_instructions_text.insert('1.0', default_instructions)
        
        # Model and generation settings
        settings_frame = ttk.LabelFrame(main_frame, text="Settings")
        settings_frame.pack(fill='x', padx=5, pady=5)
        
        # Model selection dropdown
        model_frame = ttk.Frame(settings_frame)
        model_frame.pack(fill='x', padx=5, pady=5)
        
        # Left side for label (50% width)
        label_frame = ttk.Frame(model_frame)
        label_frame.pack(side='left', fill='x', expand=True)
        ttk.Label(label_frame, text="LLM Model:").pack(side='right', padx=5)
        
        # Right side for control (50% width)
        control_frame = ttk.Frame(model_frame)
        control_frame.pack(side='right', fill='x', expand=True)
        
        self.ai_model_var = tk.StringVar(value=self.config.get('llm', {}).get('model', 'gpt-3.5-turbo'))
        model_dropdown = ttk.Combobox(control_frame, textvariable=self.ai_model_var, 
                                     values=LLMScorer.get_available_models(), 
                                     state='readonly', width=25)
        model_dropdown.pack(side='left', padx=5)
        
        # Generation count slider
        slider_frame = ttk.Frame(settings_frame)
        slider_frame.pack(fill='x', padx=5, pady=5)
        
        # Left side for label (50% width)
        slider_label_frame = ttk.Frame(slider_frame)
        slider_label_frame.pack(side='left', fill='x', expand=True)
        ttk.Label(slider_label_frame, text="Max names to score:").pack(side='right', padx=5)
        
        # Right side for control (50% width)
        slider_control_frame = ttk.Frame(slider_frame)
        slider_control_frame.pack(side='right', fill='x', expand=True)
        
        self.ai_gen_count_var = tk.IntVar(value=20)
        gen_count_slider = ttk.Scale(slider_control_frame, from_=1, to=100, orient='horizontal',
                                    variable=self.ai_gen_count_var, length=200)
        gen_count_slider.pack(side='left', padx=5)
        
        self.ai_gen_count_label = ttk.Label(slider_control_frame, text="20")
        self.ai_gen_count_label.pack(side='left', padx=5)
        
        # Update label when slider changes
        gen_count_slider.configure(command=lambda v: self.ai_gen_count_label.configure(text=str(int(float(v)))))
        
        # Max chunk size slider
        chunk_frame = ttk.Frame(settings_frame)
        chunk_frame.pack(fill='x', padx=5, pady=5)
        
        # Left side for label (50% width)
        chunk_label_frame = ttk.Frame(chunk_frame)
        chunk_label_frame.pack(side='left', fill='x', expand=True)
        ttk.Label(chunk_label_frame, text="Max chunk size:").pack(side='right', padx=5)
        
        # Right side for control (50% width)
        chunk_control_frame = ttk.Frame(chunk_frame)
        chunk_control_frame.pack(side='right', fill='x', expand=True)
        
        self.ai_chunk_size_var = tk.IntVar(value=self.config.get('llm', {}).get('max_chunk_size', 10))
        chunk_size_slider = ttk.Scale(chunk_control_frame, from_=1, to=50, orient='horizontal',
                                     variable=self.ai_chunk_size_var, length=200)
        chunk_size_slider.pack(side='left', padx=5)
        
        self.ai_chunk_size_label = ttk.Label(chunk_control_frame, text=str(self.ai_chunk_size_var.get()))
        self.ai_chunk_size_label.pack(side='left', padx=5)
        
        # Update label when slider changes
        chunk_size_slider.configure(command=lambda v: self.ai_chunk_size_label.configure(text=str(int(float(v)))))
        
        # Progress bar
        progress_frame = ttk.Frame(settings_frame)
        progress_frame.pack(fill='x', padx=5, pady=5)
        
        # Left side for label (50% width)
        progress_label_frame = ttk.Frame(progress_frame)
        progress_label_frame.pack(side='left', fill='x', expand=True)
        ttk.Label(progress_label_frame, text="Progress:").pack(side='right', padx=5)
        
        # Right side for control (50% width)
        progress_control_frame = ttk.Frame(progress_frame)
        progress_control_frame.pack(side='right', fill='x', expand=True)
        
        self.ai_progress_var = tk.DoubleVar()
        self.ai_progress_bar = ttk.Progressbar(progress_control_frame, variable=self.ai_progress_var, 
                                              maximum=100, length=300)
        self.ai_progress_bar.pack(side='left', padx=5)
        
        self.ai_progress_label = ttk.Label(progress_control_frame, text="Ready")
        self.ai_progress_label.pack(side='left', padx=5)
        
        # Generate button
        button_frame = ttk.Frame(settings_frame)
        button_frame.pack(fill='x', padx=5, pady=10)
        
        self.ai_generate_button = ttk.Button(button_frame, text="AI Score", 
                                           command=self.ai_score_names,
                                           style='Accent.TButton')
        self.ai_generate_button.pack(side='left', padx=5)
        
        # Initialize LLM scorer
        self.llm_scorer = None
        
    def ai_score_names(self):
        """Score existing names in the Results panel with LLM"""
        try:
            # Check if there are existing results to score
            if not hasattr(self, 'last_results') or not self.last_results:
                messagebox.showwarning("Warning", "No existing results to score. Please generate names first in the Results tab.")
                return
            
            # Validate inputs
            description = self.ai_description_text.get('1.0', tk.END).strip()
            instructions = self.ai_instructions_text.get('1.0', tk.END).strip()
            model = self.ai_model_var.get()
            
            if not description:
                messagebox.showwarning("Warning", "Please provide a description for the names.")
                return
            
            if not instructions:
                messagebox.showwarning("Warning", "Please provide instructions for the LLM.")
                return
            
            # Disable score button during processing
            self.ai_generate_button.configure(state='disabled')
            
            # Reset progress
            self.ai_progress_var.set(0)
            self.ai_progress_label.configure(text="Initializing LLM scorer...")
            
            # Step 1: Initialize LLM scorer
            self.update_progress(10, "Initializing LLM scorer...")
            max_chunk_size = self.ai_chunk_size_var.get()
            self.llm_scorer = LLMScorer(model=model, max_chunk_size=max_chunk_size)
            
            # Get scored examples from saved ratings
            scored_examples = self.get_scored_examples()
            
            self.update_progress(20, "Scoring existing names with LLM...")
            
            # Step 2: Score existing names with LLM
            max_names = self.ai_gen_count_var.get()
            names_to_score = self.last_results[:max_names]  # Limit to max names
            
            def progress_callback(progress):
                # Map LLM progress to our overall progress (20-90%)
                overall_progress = 20 + (progress * 70)
                self.ai_progress_var.set(overall_progress)
                self.root.update_idletasks()
            
            scored_names = self.llm_scorer.score_names(
                names=names_to_score,
                description=description,
                scored_examples=scored_examples,
                instructions=instructions,
                progress_callback=progress_callback
            )
            
            self.update_progress(95, "Sorting results...")
            
            # Step 3: Sort by LLM scores (highest first)
            scored_names.sort(key=lambda x: x[1], reverse=True)
            
            self.update_progress(100, "Complete!")
            
            # Display results with LLM scores
            self.display_ai_results(scored_names)
            
            # Store results for export
            self.last_results = [name for name, score in scored_names]
            self.last_ai_results = scored_names
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to score names with AI: {str(e)}")
            print(f"AI scoring error: {str(e)}")
        finally:
            # Re-enable score button
            self.ai_generate_button.configure(state='normal')
    
    def update_progress(self, value, message):
        """Update progress bar and label"""
        self.ai_progress_var.set(value)
        self.ai_progress_label.configure(text=message)
        self.root.update_idletasks()
    
    def get_scored_examples(self):
        """Get scored examples from saved ratings"""
        scored_examples = []
        for name, rating in self.saved_ratings.items():
            if rating > 0:  # Only include rated names
                scored_examples.append((name, rating))
        
        # Sort by rating (highest first) and limit to reasonable number
        scored_examples.sort(key=lambda x: x[1], reverse=True)
        return scored_examples[:20]  # Limit to top 20 examples
    
    def display_ai_results(self, scored_names):
        """Display AI-generated results with scores in the Results tab"""
        # Convert scored tuples to list of names with separate AI scores
        names = [name for name, score in scored_names]
        ai_scores = {name: score for name, score in scored_names}
        
        # Use the unified display function with AI scores
        self.display_results_with_ratings(names, ai_scores=ai_scores, header_text="AI-scored names")
        
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
        
        # Enable mouse wheel scrolling for results - simple approach
        def on_mousewheel_results(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind mousewheel to the entire main_frame
        main_frame.bind("<MouseWheel>", on_mousewheel_results)
        canvas.bind("<MouseWheel>", on_mousewheel_results)
        self.results_frame.bind("<MouseWheel>", on_mousewheel_results)
        
        # Store canvas reference for later use
        self.results_canvas = canvas
        
        
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
        try:
            # Check if application is being closed
            if self.is_closing:
                return
                
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
            
            # AI settings
            if not self.config.get('llm'):
                self.config['llm'] = {}
            self.config['llm']['model'] = self.ai_model_var.get()
            self.config['llm']['max_chunk_size'] = self.ai_chunk_size_var.get()
            try:
                self.config['llm']['default_instructions'] = self.ai_instructions_text.get('1.0', tk.END).strip()
            except (tk.TclError, AttributeError):
                # Widget is no longer valid, skip this update
                pass
            
            # Saved results
            self.config['saved_ratings'] = self.saved_ratings
        except (tk.TclError, AttributeError):
            # Some widgets are no longer valid, skip update
            pass
    
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
                
                # Restore AI settings
                if 'llm' in self.config:
                    if 'model' in self.config['llm']:
                        self.ai_model_var.set(self.config['llm']['model'])
                    if 'max_chunk_size' in self.config['llm']:
                        self.ai_chunk_size_var.set(self.config['llm']['max_chunk_size'])
                        self.ai_chunk_size_label.configure(text=str(self.config['llm']['max_chunk_size']))
                    if 'default_instructions' in self.config['llm']:
                        self.ai_instructions_text.delete('1.0', tk.END)
                        self.ai_instructions_text.insert('1.0', self.config['llm']['default_instructions'])
                
                # Restore saved ratings
                if 'saved_ratings' in self.config:
                    self.saved_ratings = self.config['saved_ratings']
                    self.refresh_saved_results()
                
                # Restore word list ratings
                if 'word_list_ratings' in self.config:
                    self.word_list_ratings = self.config['word_list_ratings']
                    self.refresh_word_list_display()
                
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
        
        # Enable mouse wheel scrolling for saved results - simple approach
        def on_mousewheel_saved(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind mousewheel to the entire frame
        frame.bind("<MouseWheel>", on_mousewheel_saved)
        canvas.bind("<MouseWheel>", on_mousewheel_saved)
        self.saved_results_frame.bind("<MouseWheel>", on_mousewheel_saved)
        
        # Store widgets for saved results
        self.saved_result_widgets = []
        
        
        # Load and display saved results
        self.refresh_saved_results()
    
    def show_raw_training_data(self):
        """Show raw training data in a popup window with sorting options"""
        # Get selected word lists
        selected_sources = []
        for i, var in enumerate(self.word_list_vars):
            if var.get():
                selected_sources.append(self.word_list_mapping[i])
        
        if not selected_sources:
            messagebox.showwarning("Warning", "Please select at least one word list!")
            return
        
        # Create a special modal that shows all selected training data
        class TrainingDataModal:
            def __init__(self, parent, sources):
                self.parent = parent
                self.sources = sources
                self.popup = None
                self.view_var = None
                self.text_widget = None
                
            def show(self):
                if self.popup:
                    return
                    
                # Create popup window
                self.popup = tk.Toplevel(self.parent)
                self.popup.title("Raw Training Data")
                self.popup.geometry("600x400")
                self.popup.configure(bg='white')
                
                # Create control frame
                control_frame = ttk.Frame(self.popup)
                control_frame.pack(fill='x', padx=10, pady=5)
                
                # View options
                ttk.Label(control_frame, text="View:").pack(side='left', padx=5)
                self.view_var = tk.StringVar(value="sorted")
                ttk.Radiobutton(control_frame, text="Sorted", variable=self.view_var, 
                               value="sorted", command=self.refresh_view).pack(side='left', padx=2)
                ttk.Radiobutton(control_frame, text="Random", variable=self.view_var, 
                               value="random", command=self.refresh_view).pack(side='left', padx=2)
                
                # Create text widget
                self.text_widget = scrolledtext.ScrolledText(self.popup, wrap=tk.WORD,
                                                            bg='white', fg='black', 
                                                            selectbackground='#4a90e2',
                                                            selectforeground='white')
                self.text_widget.pack(fill='both', expand=True, padx=10, pady=10)
                
                # Load and display content
                self.refresh_view()
                
                # Handle window close
                self.popup.protocol("WM_DELETE_WINDOW", self.close)
                
            def refresh_view(self):
                if not self.text_widget:
                    return
                    
                # Collect all words from selected lists
                all_words = []
                for word_list_file in self.sources:
                    file_path = os.path.join("word_lists", word_list_file)
                    try:
                        with open(file_path, 'r') as f:
                            words = [line.strip() for line in f if line.strip()]
                            all_words.extend(words)
                    except Exception as e:
                        self.text_widget.config(state=tk.NORMAL)
                        self.text_widget.delete(1.0, tk.END)
                        self.text_widget.insert(tk.END, f"Error loading word list {word_list_file}: {str(e)}")
                        self.text_widget.config(state=tk.DISABLED)
                        return
                
                # Apply sorting/shuffling
                if self.view_var.get() == "sorted":
                    all_words.sort()
                else:
                    random.shuffle(all_words)
                
                # Clear and populate text widget
                self.text_widget.config(state=tk.NORMAL)
                self.text_widget.delete(1.0, tk.END)
                self.text_widget.insert(tk.END, f"Total words: {len(all_words)}\n\n")
                for word in all_words:
                    self.text_widget.insert(tk.END, word + "\n")
                self.text_widget.config(state=tk.DISABLED)
            
            def close(self):
                if self.popup:
                    self.popup.destroy()
                    self.popup = None
        
        # Show the modal
        modal = TrainingDataModal(self.root, selected_sources)
        modal.show()
    
    def display_results_with_ratings(self, names, ai_scores=None, header_text=None):
        """Display results with star rating controls and optional AI scores"""
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
        if header_text:
            header_text = f"Generated {len(names)} {header_text}:"
        else:
            header_text = f"Generated {len(names)} names:"
        
        header_label = ttk.Label(self.results_frame, 
                               text=header_text, 
                               font=('Arial', 12, 'bold'))
        header_label.pack(pady=10)
        self.rating_widgets.append(header_label)
        
        # Column headers if AI scores are present
        if ai_scores:
            headers_frame = ttk.Frame(self.results_frame)
            headers_frame.pack(fill='x', padx=20, pady=5)
            
            # Name column header
            name_header = ttk.Label(headers_frame, text="Name", 
                                  font=('Arial', 11, 'bold'))
            name_header.pack(side='left')
            
            # AI Score column header
            ai_score_header = ttk.Label(headers_frame, text="AI Score", 
                                      font=('Arial', 11, 'bold'))
            ai_score_header.pack(side='left', padx=(200, 0))
            
            # User Rating column header
            user_rating_header = ttk.Label(headers_frame, text="User Rating", 
                                         font=('Arial', 11, 'bold'))
            user_rating_header.pack(side='right')
            
            self.rating_widgets.extend([headers_frame, name_header, ai_score_header, user_rating_header])
        
        # Display each name with star rating
        for i, name in enumerate(names, 1):
            name_frame = ttk.Frame(self.results_frame)
            name_frame.pack(fill='x', padx=20, pady=5)
            
            # Name label
            name_label = ttk.Label(name_frame, text=f"{i:2d}. {name}", 
                                 font=('Arial', 11))
            name_label.pack(side='left')
            
            # AI Score label (if present)
            if ai_scores and name in ai_scores:
                score_val = ai_scores[name]
                # Format as integer if it's a whole number, otherwise single decimal
                if score_val == int(score_val):
                    score_text = f"{int(score_val):>4}"
                else:
                    score_text = f"{score_val:>4.1f}"
                ai_score_label = ttk.Label(name_frame, text=score_text, 
                                         font=('Arial', 11, 'bold'), foreground='blue')
                ai_score_label.pack(side='left', padx=(200, 0))
                self.rating_widgets.append(ai_score_label)
            
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
                                      bg='#DAA520' if is_filled else '#f0f0f0',
                                      fg='black', relief='flat', font=('Arial', 14),
                                      activebackground='#e0e0e0', activeforeground='black',
                                      borderwidth=0)
                star_button.pack(side='left', padx=1)
                self.rating_widgets.append(star_button)
            
            # Rating label
            rating_label = ttk.Label(rating_frame, text=f"({current_rating})")
            rating_label.pack(side='left', padx=5)
            
            self.rating_widgets.extend([name_frame, name_label, rating_frame, rating_label])
        
        # Update canvas scroll region
        self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))
    
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
                name_frame.pack(fill='x', padx=10, pady=2)
                
                # Delete button on the left
                delete_button = ttk.Button(name_frame, text="Delete", 
                                         command=lambda n=name: self.delete_saved_name(n))
                delete_button.pack(side='left', padx=(0, 5))
                
                # Edit button next to delete
                edit_button = ttk.Button(name_frame, text="Edit", 
                                       command=lambda n=name, r=rating: self.edit_saved_score(n, r))
                edit_button.pack(side='left', padx=(0, 10))
                
                # Name in the middle with larger font
                name_label = ttk.Label(name_frame, text=name, 
                                     font=('Arial', 16, 'bold'))
                name_label.pack(side='left')
                
                # Rating on the right
                stars = "★" * rating + "☆" * (5 - rating)
                rating_label = ttk.Label(name_frame, text=f"{stars} ({rating}/5)", 
                                       font=('Arial', 11))
                rating_label.pack(side='right')
                
                self.saved_result_widgets.extend([name_frame, delete_button, edit_button, name_label, rating_label])
    
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
    
    def edit_saved_score(self, name, current_rating):
        """Edit the score for a saved name"""
        new_rating = simpledialog.askinteger(
            "Edit Score", 
            f"Enter new score for '{name}' (1-5):\nCurrent score: {current_rating}",
            minvalue=1, 
            maxvalue=5,
            initialvalue=current_rating
        )
        
        if new_rating is not None and new_rating != current_rating:
            self.saved_ratings[name] = new_rating
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
            
            # View button for this word list (positioned between checkbox and rating)
            view_button = ttk.Button(list_frame, text="View", 
                                   command=lambda wl=word_list, dn=display_name: self.view_word_list(wl, dn))
            view_button.pack(side='right', padx=5)
            
            current_rating = self.word_list_ratings.get(word_list, 0)
            
            # Create star buttons (0-5)
            for star in range(6):
                is_filled = star > 0 and star <= current_rating
                star_text = "\u2605" if is_filled else "\u2606"
                star_button = tk.Button(rating_frame, text=star_text, 
                                      command=lambda wl=word_list, r=star: self.rate_word_list(wl, r),
                                      bg='#DAA520' if is_filled else '#f0f0f0',
                                      fg='black', relief='flat', font=('Arial', 12),
                                      activebackground='#e0e0e0', activeforeground='black',
                                      borderwidth=0)
                star_button.pack(side='left', padx=1)
                self.word_list_widgets.append(star_button)
            
            # Rating label
            rating_label = ttk.Label(rating_frame, text=f"({current_rating})")
            rating_label.pack(side='left', padx=5)
            
            self.word_list_widgets.extend([list_frame, checkbox, view_button, rating_frame, rating_label])
    
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
    
    def save_latest_state(self):
        """Save the complete GUI state to latest_config.yaml"""
        try:
            # Check if application is being closed
            if self.is_closing:
                return
            
            # Update config from current GUI state
            self.update_config_from_gui()
            
            # Create a complete state snapshot, safely accessing widgets
            gui_state = {}
            try:
                gui_state['ai_description'] = self.ai_description_text.get('1.0', tk.END).strip()
                gui_state['ai_instructions'] = self.ai_instructions_text.get('1.0', tk.END).strip()
                gui_state['ai_gen_count'] = self.ai_gen_count_var.get()
                gui_state['ai_chunk_size'] = self.ai_chunk_size_var.get()
                gui_state['min_score'] = self.min_score_var.get()
                gui_state['max_score'] = self.max_score_var.get()
            except (tk.TclError, AttributeError):
                # Widget is no longer valid, skip GUI state saving
                pass
            
            state = {
                'config': self.config,
                'gui_state': gui_state,
                'saved_ratings': self.saved_ratings,
                'word_list_ratings': self.word_list_ratings
            }
            
            # Save to latest_config.yaml
            with open("latest_config.yaml", 'w') as f:
                yaml.dump(state, f, default_flow_style=False)
                
        except Exception as e:
            print(f"Error saving latest state: {e}")
    
    def load_latest_state(self):
        """Load the complete GUI state from latest_config.yaml"""
        try:
            if not os.path.exists("latest_config.yaml"):
                return
            
            with open("latest_config.yaml", 'r') as f:
                state = yaml.safe_load(f)
            
            if not state:
                return
                
            # Load config
            if 'config' in state:
                self.config = state['config']
                
                # Update GUI controls from loaded config
                self.update_gui_from_config()
            
            # Load GUI state
            if 'gui_state' in state:
                gui_state = state['gui_state']
                
                # Update AI tab fields
                if 'ai_description' in gui_state:
                    self.ai_description_text.delete('1.0', tk.END)
                    self.ai_description_text.insert('1.0', gui_state['ai_description'])
                
                if 'ai_instructions' in gui_state:
                    self.ai_instructions_text.delete('1.0', tk.END)
                    self.ai_instructions_text.insert('1.0', gui_state['ai_instructions'])
                
                if 'ai_gen_count' in gui_state:
                    self.ai_gen_count_var.set(gui_state['ai_gen_count'])
                    self.ai_gen_count_label.configure(text=str(gui_state['ai_gen_count']))
                
                if 'ai_chunk_size' in gui_state:
                    self.ai_chunk_size_var.set(gui_state['ai_chunk_size'])
                    self.ai_chunk_size_label.configure(text=str(gui_state['ai_chunk_size']))
                
                if 'min_score' in gui_state:
                    self.min_score_var.set(gui_state['min_score'])
                    self.min_score_label.configure(text=str(gui_state['min_score']))
                
                if 'max_score' in gui_state:
                    self.max_score_var.set(gui_state['max_score'])
                    self.max_score_label.configure(text=str(gui_state['max_score']))
            
            # Load saved ratings
            if 'saved_ratings' in state:
                self.saved_ratings = state['saved_ratings']
                self.refresh_saved_results()
            
            # Load word list ratings
            if 'word_list_ratings' in state:
                self.word_list_ratings = state['word_list_ratings']
                self.refresh_word_list_display()
                
        except Exception as e:
            print(f"Error loading latest state: {e}")
    
    def update_gui_from_config(self):
        """Update GUI controls from the loaded config"""
        try:
            # Update model parameters
            if 'model' in self.config:
                model_config = self.config['model']
                if 'order' in model_config:
                    self.order_var.set(model_config['order'])
                    self.order_label.configure(text=str(model_config['order']))
                if 'prior' in model_config:
                    self.prior_var.set(model_config['prior'])
                    self.prior_label.configure(text=f"{model_config['prior']:.4f}")
                if 'backoff' in model_config:
                    self.backoff_var.set(model_config['backoff'])
            
            # Update generation parameters
            if 'generation' in self.config:
                gen_config = self.config['generation']
                if 'n_words' in gen_config:
                    self.n_words_var.set(gen_config['n_words'])
                if 'min_length' in gen_config:
                    self.min_length_var.set(gen_config['min_length'])
                if 'max_length' in gen_config:
                    self.max_length_var.set(gen_config['max_length'])
                if 'starts_with' in gen_config:
                    self.starts_with_var.set(gen_config['starts_with'])
                if 'ends_with' in gen_config:
                    self.ends_with_var.set(gen_config['ends_with'])
                if 'includes' in gen_config:
                    self.includes_var.set(gen_config['includes'])
                if 'excludes' in gen_config:
                    self.excludes_var.set(gen_config['excludes'])
            
            # Update training data selection
            if 'training_data' in self.config and 'sources' in self.config['training_data']:
                selected_sources = set(self.config['training_data']['sources'])
                for i, word_list in enumerate(self.word_list_mapping):
                    if i < len(self.word_list_vars):
                        self.word_list_vars[i].set(word_list in selected_sources)
            
            # Update AI model selection
            if 'llm' in self.config:
                llm_config = self.config['llm']
                if 'model' in llm_config:
                    self.ai_model_var.set(llm_config['model'])
                if 'max_chunk_size' in llm_config:
                    self.ai_chunk_size_var.set(llm_config['max_chunk_size'])
                    self.ai_chunk_size_label.configure(text=str(llm_config['max_chunk_size']))
                    
        except Exception as e:
            print(f"Error updating GUI from config: {e}")
    
    def start_auto_save_timer(self):
        """Start the auto-save timer"""
        if self.auto_save_timer:
            self.auto_save_timer.cancel()
        
        self.auto_save_timer = threading.Timer(10.0, self.auto_save_callback)
        self.auto_save_timer.daemon = True
        self.auto_save_timer.start()
    
    def auto_save_callback(self):
        """Callback for auto-save timer"""
        try:
            self.save_latest_state()
            print("Auto-saved GUI state to latest_config.yaml")
        except Exception as e:
            print(f"Auto-save failed: {e}")
        finally:
            # Schedule next auto-save
            self.start_auto_save_timer()
    
    def save_state_on_exit(self):
        """Save state when application exits"""
        try:
            if self.auto_save_timer:
                self.auto_save_timer.cancel()
            
            # Only save if not already closing
            if not self.is_closing:
                self.save_latest_state()
                print("Saved GUI state on exit")
        except Exception as e:
            print(f"Error saving state on exit: {e}")
    
    def on_closing(self):
        """Handle window closing event"""
        try:
            self.is_closing = True
            self.save_state_on_exit()
        except Exception as e:
            print(f"Error during shutdown: {e}")
        finally:
            self.root.destroy()


def main():
    """Main function to run the GUI"""
    root = tk.Tk()
    app = MarkovNameGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()