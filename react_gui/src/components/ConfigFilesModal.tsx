import React, { useEffect, useState } from 'react';
import { FileText } from 'lucide-react';
import { apiService, Config } from '../services/api';
import Modal from './Modal';

interface ConfigFilesModalProps {
  config: Config;
  onClose: () => void;
  onLoaded: (config: Config, filename: string) => void;
  onSaved: (filename: string) => void;
  onError: (err: any) => void;
}

/** Save the current settings under a name, or load a saved .yaml config. */
const ConfigFilesModal: React.FC<ConfigFilesModalProps> = ({ config, onClose, onLoaded, onSaved, onError }) => {
  const [files, setFiles] = useState<string[]>([]);
  const [saveName, setSaveName] = useState('');

  useEffect(() => {
    apiService.getAvailableConfigs().then(setFiles).catch(onError);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    const filename = saveName.trim().replace(/\.yaml$/, '') + '.yaml';
    try {
      await apiService.saveConfigAs(filename, config);
      onSaved(filename);
      onClose();
    } catch (err) {
      onError(err);
    }
  };

  const load = async (filename: string) => {
    try {
      onLoaded(await apiService.loadConfigFrom(filename), filename);
      onClose();
    } catch (err) {
      onError(err);
    }
  };

  return (
    <Modal isOpen onClose={onClose} title="Configs">
      <div className="space-y-6">
        <div>
          <div className="panel-label mb-2">Save current settings as</div>
          <form className="flex gap-2" onSubmit={e => { e.preventDefault(); if (saveName.trim()) save(); }}>
            <input className="form-input" autoFocus value={saveName} onChange={e => setSaveName(e.target.value)}
              placeholder="e.g. collective-mind-v2" />
            <button className="btn btn-primary" type="submit" disabled={!saveName.trim()}>Save</button>
          </form>
        </div>
        <div>
          <div className="panel-label mb-2">Load</div>
          {files.length === 0 ? (
            <p className="text-muted text-sm">No saved configs yet.</p>
          ) : (
            <div className="file-list">
              {files.map(file => (
                <button key={file} className="file-row" onClick={() => load(file)}>
                  <FileText size={14} />
                  <span>{file}</span>
                  {file === 'config.yaml' && <span className="text-muted text-xs">(live config)</span>}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
};

export default ConfigFilesModal;
