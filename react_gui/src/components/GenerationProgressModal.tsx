import React, { useEffect, useState } from 'react';

interface GenerationProgressModalProps {
  isOpen: boolean;
  targetCount: number;
  onStop: () => void;
  onComplete: (names: string[]) => void;
  config: any;
}

const GenerationProgressModal: React.FC<GenerationProgressModalProps> = ({
  isOpen,
  targetCount,
  onStop,
  onComplete,
  config
}) => {
  const [currentCount, setCurrentCount] = useState(0);
  const [names, setNames] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [abortController, setAbortController] = useState<AbortController | null>(null);
  const [animatedText, setAnimatedText] = useState('');

  const progressPercentage = (targetCount > 0 && currentCount >= 0) ? Math.min((currentCount / targetCount) * 100, 100) : 0;
  console.log('Progress debug:', { currentCount, targetCount, progressPercentage });
  
  // Get max length from config for animation
  const maxLength = config?.generation?.max_length || 12;
  
  // Character animation effect
  useEffect(() => {
    if (!isGenerating) return;
    
    const chars = 'abcdefghijklmnopqrstuvwxyz';
    const interval = setInterval(() => {
      const randomString = Array.from({ length: maxLength }, () => 
        chars[Math.floor(Math.random() * chars.length)]
      ).join('');
      setAnimatedText(randomString);
    }, 100); // 10 per second
    
    return () => clearInterval(interval);
  }, [isGenerating, maxLength]);

  const startGeneration = async () => {
    if (isGenerating) return;
    
    console.log(`Starting generation with target count: ${targetCount}`);
    setIsGenerating(true);
    setCurrentCount(0);
    setNames([]);
    
    const controller = new AbortController();
    setAbortController(controller);

    try {
      const response = await fetch('http://localhost:5001/api/generate-stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config),
        signal: controller.signal
      });

      if (!response.ok) {
        throw new Error('Generation failed');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      
      if (!reader) {
        throw new Error('No response stream');
      }

      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n').filter(line => line.trim());
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'progress') {
                setNames(prev => {
                  const newNames = [...prev, data.name];
                  setCurrentCount(newNames.length);
                  
                  console.log(`Progress: ${newNames.length}/${targetCount} names generated`);
                  
                  // Auto-complete when target reached
                  if (newNames.length >= targetCount) {
                    console.log('Target reached, completing generation');
                    setTimeout(() => {
                      setIsGenerating(false);
                      onComplete(newNames);
                    }, 100); // Small delay to ensure UI updates
                  }
                  
                  return newNames;
                });
              } else if (data.type === 'complete') {
                console.log('Server sent complete signal');
                setIsGenerating(false);
                setNames(currentNames => {
                  onComplete(currentNames);
                  return currentNames;
                });
                return;
              } else if (data.type === 'error') {
                throw new Error(data.message);
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        // Generation was stopped by user
        onComplete(names);
      } else {
        console.error('Generation error:', error);
        // Still return whatever names we have
        onComplete(names);
      }
    } finally {
      setIsGenerating(false);
      setAbortController(null);
    }
  };

  const handleStop = () => {
    if (abortController) {
      abortController.abort();
    }
    setIsGenerating(false);
    // Pass any generated names to the results
    if (names.length > 0) {
      onComplete(names);
    } else {
      onStop();
    }
  };

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setCurrentCount(0);
      setNames([]);
      setIsGenerating(false);
      setAbortController(null);
      setAnimatedText('');
      
      // Start generation after a small delay to ensure state is reset
      setTimeout(() => {
        if (isOpen) {
          startGeneration();
        }
      }, 100);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={handleStop} style={{ display: isOpen ? 'flex' : 'none' }}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ width: '80%', maxWidth: '80vw', minHeight: '400px', height: 'auto' }}>
        <div className="modal-header">
          <h2 className="modal-title">Generated {currentCount} of {targetCount} names</h2>
          <button 
            onClick={handleStop}
            className="btn btn-danger btn-small"
            disabled={!isGenerating && currentCount === 0}
          >
            {isGenerating ? 'Stop Generation' : 'Close'}
          </button>
        </div>
        <div className="space-y-6">
        {/* Animated Character Sampling */}
        <div className="text-center">
          <div className="text-lg font-mono tracking-wider text-accent-primary mb-4" style={{ minHeight: '2rem' }}>
            {isGenerating ? animatedText : ''}
          </div>
        </div>

        {/* Progress Bar */}
        <div style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px', color: '#888888', marginBottom: '8px' }}>
            <span>Progress ({currentCount}/{targetCount})</span>
            <span>{Math.round(progressPercentage)}%</span>
          </div>
          <div style={{ 
            width: '100%', 
            height: '20px', 
            backgroundColor: '#1a1a1a', 
            borderRadius: '10px',
            border: '2px solid #4a4a4a',
            overflow: 'hidden'
          }}>
            <div style={{ 
              height: '100%', 
              width: `${progressPercentage}%`,
              backgroundColor: '#a855f7', // Bright purple
              borderRadius: '8px',
              transition: 'width 0.3s ease-out',
              minWidth: progressPercentage > 0 ? '4px' : '0px' // Ensure visibility even at low percentages
            }} />
          </div>
        </div>

        {/* Recent Names Preview */}
        {names.length > 0 && (
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="text-sm font-semibold mb-2 text-muted">Recent Names:</h4>
            <div className="text-sm space-y-1 max-h-24 overflow-y-auto">
              {names.slice(-5).map((name, index) => (
                <div key={index} className="text-gray-700">
                  {name}
                </div>
              ))}
            </div>
          </div>
        )}

        </div>
      </div>
    </div>
  );
};

export default GenerationProgressModal;