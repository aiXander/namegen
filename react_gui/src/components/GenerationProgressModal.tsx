import React, { useEffect, useState } from 'react';
import Modal from './Modal';

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

  const progressPercentage = Math.min((currentCount / targetCount) * 100, 100);

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
    onStop();
  };

  useEffect(() => {
    if (isOpen && !isGenerating) {
      startGeneration();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={handleStop} title="Generating Names">
      <div className="space-y-6">
        {/* Progress Info */}
        <div className="text-center">
          <h3 className="text-lg font-semibold mb-2">
            Generated {currentCount} of {targetCount} names
          </h3>
          <p className="text-sm text-muted">
            {isGenerating ? 'Generating names...' : 'Generation complete'}
          </p>
        </div>

        {/* Progress Bar */}
        <div className="w-full">
          <div className="flex justify-between text-sm text-muted mb-2">
            <span>Progress</span>
            <span>{Math.round(progressPercentage)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className="bg-blue-500 h-3 rounded-full transition-all duration-300 ease-out"
              style={{ width: `${progressPercentage}%` }}
            />
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

        {/* Action Button */}
        <div className="flex justify-center pt-4">
          <button
            onClick={handleStop}
            className="px-6 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
            disabled={!isGenerating && currentCount === 0}
          >
            {isGenerating ? 'Stop Generation' : 'Close'}
          </button>
        </div>
      </div>
    </Modal>
  );
};

export default GenerationProgressModal;