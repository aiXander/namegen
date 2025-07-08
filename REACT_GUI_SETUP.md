# React GUI for Markov Name Generator - Setup Instructions

This is a modern React-based GUI that replicates and enhances the functionality of the original tkinter GUI. It features a beautiful dark theme with purple accents and modern UI components.

## Features

- **Dark Theme**: Modern dark UI with purple accent colors
- **Responsive Design**: Works well on different screen sizes
- **Real-time Updates**: Auto-saves state and provides instant feedback
- **Enhanced UX**: Improved visuals and interactions compared to the tkinter version
- **All Original Features**: Complete feature parity with the tkinter GUI

### Tabs

1. **Training Data**: Select and rate word lists for training
2. **Markov Parameters**: Configure model parameters and generation settings
3. **Results**: View generated names with rating capabilities
4. **Saved Results**: Manage your rated names
5. **AI**: Use AI to score generated names

## Quick Start Guide

### Step 1: Start the Python Backend

From the main namegen directory, run:

```bash
# Install Flask dependencies (if not already installed)
pip install Flask Flask-CORS

# Start the API server
python api_server.py
```

You should see:
```
Starting Markov Name Generator API Server...
React frontend should connect to: http://localhost:5001
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5001
 * Running on http://[::1]:5001
```

### Step 2: Start the React Frontend

Open a new terminal, then:

```bash
# Navigate to the React GUI directory
cd react_gui

# Install dependencies (only needed once)
npm install

# Start the development server
npm start
```

The React app will automatically open in your browser at `http://localhost:3000`.

### Step 3: Use the Application

1. The app will load with a modern dark theme interface
2. Navigate between tabs using the tab buttons
3. Configure your settings in the "Training Data" and "Markov Parameters" tabs
4. Click "Generate Names" to create names
5. Rate names in the "Results" tab
6. Use the "AI" tab to score names with AI models

## Development Mode Features

The React development server includes:

- **Hot Reload**: Automatically reloads when you save changes
- **Auto-rebuild**: Compiles TypeScript and updates the app instantly
- **Error Overlay**: Shows compilation errors in the browser
- **Source Maps**: Debug with original TypeScript source code

To make changes:
1. Edit any file in `react_gui/src/`
2. Save the file
3. The browser will automatically reload with your changes

## Architecture Overview

### Frontend (React + TypeScript)
- Modern React components with TypeScript
- Dark theme with CSS custom properties
- Responsive design with modern UI patterns
- HTTP communication via Axios

### Backend (Flask API)
- Lightweight Flask server providing REST API
- Uses existing namegen Python modules
- CORS enabled for React frontend communication
- Runs on `http://localhost:5000`

### Communication
The React frontend communicates with the Python backend through a REST API:
- Configuration management
- Name generation
- Rating system
- AI scoring
- Word list management

## Comparison with Original Tkinter GUI

### Visual Improvements
- **Dark Theme**: Modern dark background with bright fonts and purple accents
- **Better Typography**: Improved font sizes and spacing
- **Modern Icons**: Using Lucide React icon library
- **Smooth Animations**: CSS transitions for better UX
- **Responsive Design**: Works on different screen sizes

### Functional Enhancements
- **Web-based**: Accessible from any modern browser
- **Better Error Handling**: Clear error messages and loading states
- **Improved Navigation**: Modern tab system
- **Enhanced Feedback**: Progress bars and status indicators

### Feature Parity
All original functionality is preserved:
- Word list selection and rating
- Markov model configuration
- Name generation with constraints
- AI-powered scoring
- Results management and export capabilities

## Troubleshooting

### Common Issues

**Backend not starting:**
- Ensure all Python dependencies are installed
- Check that `config.yaml` exists
- Verify the `word_lists/` directory contains .txt files

**Frontend compilation errors:**
- Run `npm install` to ensure dependencies are installed
- Delete `node_modules/` and `package-lock.json`, then run `npm install`

**Connection issues:**
- Ensure backend is running on port 5000
- Check browser developer console for error messages
- Verify no firewall is blocking the connection

**Word lists not loading:**
- Ensure `word_lists/` directory exists in the main project directory
- Check that word list files have .txt extension
- Verify file permissions allow reading

### Development Tips

1. **Making Changes**: Edit files in `react_gui/src/` and they'll auto-reload
2. **Debugging**: Use browser developer tools to inspect network requests
3. **API Testing**: Backend API endpoints can be tested directly at `http://localhost:5000/api/`
4. **Console Logs**: Check both browser console and terminal running the API server

## File Structure

```
namegen/
├── api_server.py              # Flask API server
├── react_gui/                 # React frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── services/          # API service layer
│   │   ├── App.tsx           # Main application component
│   │   └── index.css         # Dark theme styles
│   ├── package.json          # Node.js dependencies
│   └── public/               # Static assets
├── gui/                      # Original tkinter GUI (preserved)
├── word_lists/               # Training data
└── config.yaml              # Configuration file
```

The React GUI is a complete replacement for the tkinter interface while maintaining full compatibility with the existing Python backend.