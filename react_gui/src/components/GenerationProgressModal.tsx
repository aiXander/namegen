import React, { useEffect, useRef, useState } from 'react';

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
  const [animatedText, setAnimatedText] = useState('');
  const [generationError, setGenerationError] = useState<string | null>(null);

  // Refs avoid stale closures inside the streaming loop and guarantee
  // onComplete fires exactly once per generation run
  const namesRef = useRef<string[]>([]);
  const completedRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const progressPercentage = (targetCount > 0 && currentCount >= 0) ? Math.min((currentCount / targetCount) * 100, 100) : 0;

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

  // Fires onComplete exactly once per generation run, regardless of how many
  // code paths (target reached, server complete, abort, error) try to finish
  const finishOnce = (finalNames: string[]) => {
    if (completedRef.current) return;
    completedRef.current = true;
    setIsGenerating(false);
    onComplete(finalNames);
  };

  const addName = (name: string) => {
    namesRef.current = [...namesRef.current, name];
    setNames(namesRef.current);
    setCurrentCount(namesRef.current.length);
  };

  const startGeneration = async () => {
    const controller = new AbortController();
    abortControllerRef.current = controller;

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
        throw new Error(`Generation failed (HTTP ${response.status})`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response stream');
      }

      // Buffer partial chunks so SSE events split across reads aren't dropped
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep the (possibly partial) last line

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;

          let data: any;
          try {
            data = JSON.parse(line.slice(6));
          } catch (e) {
            console.error('Error parsing SSE data:', e, line);
            continue;
          }

          if (data.type === 'progress') {
            addName(data.name);
            if (namesRef.current.length >= targetCount) {
              controller.abort(); // No need to keep the stream open
              finishOnce(namesRef.current);
              return;
            }
          } else if (data.type === 'complete') {
            finishOnce(namesRef.current);
            return;
          } else if (data.type === 'error') {
            setGenerationError(data.message || 'Generation failed');
            setIsGenerating(false);
            return;
          }
        }
      }

      // Stream ended without an explicit complete message
      finishOnce(namesRef.current);
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        // Stopped by user (or by reaching the target) — deliver what we have
        finishOnce(namesRef.current);
      } else {
        console.error('Generation error:', error);
        setGenerationError(error instanceof Error ? error.message : 'Generation failed');
        setIsGenerating(false);
      }
    } finally {
      setIsGenerating(false);
      abortControllerRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    } else if (generationError) {
      // Errored run: close the modal without overwriting existing results
      onStop();
    } else {
      // Generation already finished — close with what we have
      finishOnce(namesRef.current);
    }
  };

  // Reset state and start generation when modal opens
  useEffect(() => {
    if (!isOpen) return;

    namesRef.current = [];
    completedRef.current = false;
    setCurrentCount(0);
    setNames([]);
    setGenerationError(null);
    setAnimatedText('');
    setIsGenerating(true);
    startGeneration();

    return () => {
      // Modal unmounted/closed mid-run: abort the stream
      abortControllerRef.current?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={handleStop} style={{ display: isOpen ? 'flex' : 'none' }}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ width: '560px', maxWidth: '90vw' }}>
        <div className="modal-header">
          <h2 className="modal-title">Forging names…</h2>
          <button
            onClick={handleStop}
            className="btn btn-danger btn-small"
          >
            {isGenerating ? 'Stop Generation' : 'Close'}
          </button>
        </div>
        <div className="space-y-6">
        {/* Error Display */}
        {generationError && (
          <div className="error-banner text-center">
            <p className="error-message">{generationError}</p>
          </div>
        )}
        {/* Animated Character Sampling */}
        <div className="text-center">
          <div className="sampling-ticker">
            {isGenerating ? animatedText : ''}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full">
          <div className="progress-meta">
            <span>forging {currentCount}/{targetCount}</span>
            <span>{Math.round(progressPercentage)}%</span>
          </div>
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{
                width: `${progressPercentage}%`,
                minWidth: progressPercentage > 0 ? '4px' : '0px'
              }}
            />
          </div>
        </div>

        {/* Recent Names Preview */}
        {names.length > 0 && (
          <div className="recent-names-panel">
            <div className="panel-label">Fresh from the forge</div>
            <div className="space-y-1 max-h-24 overflow-y-auto">
              {names.slice(-5).reverse().map((name, index) => (
                <div key={index} className="name-display">
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