import { useState, useRef, useCallback } from 'react';
import {
  ArrowUpTrayIcon,
  DocumentArrowDownIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';
import { Modal, ModalFooter } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { usersApi } from '@/services/users';
import type { BulkImportResponse, BulkUserResult } from '@/types/user';

interface BulkImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

type ImportStep = 'upload' | 'processing' | 'results';

export function BulkImportModal({ isOpen, onClose, onSuccess }: BulkImportModalProps) {
  const [step, setStep] = useState<ImportStep>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [skipExisting, setSkipExisting] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<BulkImportResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.name.endsWith('.zip')) {
        setFile(droppedFile);
        setError(null);
      } else {
        setError('Please upload a .zip file');
      }
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      await usersApi.downloadBulkTemplate();
    } catch (err) {
      setError('Failed to download template');
    }
  };

  const handleImport = async () => {
    if (!file) return;

    setIsUploading(true);
    setStep('processing');
    setError(null);

    try {
      const response = await usersApi.bulkImport(file, skipExisting);
      setResults(response);
      setStep('results');
      if (response.successful > 0) {
        onSuccess();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
      setStep('upload');
    } finally {
      setIsUploading(false);
    }
  };

  const resetState = () => {
    setStep('upload');
    setFile(null);
    setError(null);
    setResults(null);
    setSkipExisting(true);
  };

  const handleClose = () => {
    if (!isUploading) {
      resetState();
      onClose();
    }
  };

  const getStatusBadge = (status: BulkUserResult['status']) => {
    switch (status) {
      case 'success':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">Success</span>;
      case 'error':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">Error</span>;
      case 'skipped':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">Skipped</span>;
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Bulk Import Users"
      size={step === 'results' ? 'xl' : 'lg'}
    >
      {step === 'upload' && (
        <div className="space-y-6">
          {/* Instructions */}
          <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
            <h4 className="text-sm font-medium text-gray-900 mb-2">Instructions</h4>
            <p className="text-sm text-gray-600 mb-4">
              Upload a ZIP file containing a CSV file for user data and a folder for photos.
              The structure must be exactly as follows:
            </p>
            <div className="bg-gray-900 rounded-md p-4 overflow-x-auto">
              <pre className="text-xs text-gray-300 font-mono leading-relaxed">
{`bulk_import.zip
├── users.csv          (Required columns: name, email, role, department)
└── photos/            (Folder containing user images)
    ├── john_doe/      (Folder name must match 'folder_name' in CSV)
    │   ├── photo1.jpg
    │   └── photo2.jpg
    └── jane_smith/
        └── photo1.jpg`}
              </pre>
            </div>
            <div className="mt-4">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleDownloadTemplate}
                leftIcon={<DocumentArrowDownIcon className="w-4 h-4" />}
              >
                Download CSV Template
              </Button>
            </div>
          </div>

          {/* Drop Zone */}
          <div
            className={`
              relative border-2 border-dashed rounded-xl p-8 text-center transition-colors
              ${isDragging
                ? 'border-primary-500 bg-primary-50'
                : 'border-gray-300 hover:border-gray-400 bg-white'
              }
            `}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              accept=".zip"
              className="hidden"
            />
            
            {file ? (
              <div className="flex items-center justify-center gap-3">
                <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                  <DocumentArrowDownIcon className="w-6 h-6 text-primary-600" />
                </div>
                <div className="text-left">
                  <p className="text-sm font-medium text-gray-900">{file.name}</p>
                  <p className="text-xs text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
                <button
                  onClick={() => setFile(null)}
                  className="p-1 hover:bg-gray-100 rounded-full text-gray-400 hover:text-gray-600 ml-2"
                >
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-3">
                  <ArrowUpTrayIcon className="w-6 h-6 text-gray-400" />
                </div>
                <p className="text-sm font-medium text-gray-900">
                  Click to upload or drag and drop
                </p>
                <p className="text-xs text-gray-500">ZIP files only (max 500MB)</p>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  className="mt-2"
                >
                  Select File
                </Button>
              </div>
            )}
          </div>

          {/* Options */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="skipExisting"
              checked={skipExisting}
              onChange={(e) => setSkipExisting(e.target.checked)}
              className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
            />
            <label htmlFor="skipExisting" className="text-sm text-gray-700">
              Skip existing users (based on email or external ID)
            </label>
          </div>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-sm text-red-600">
              <XCircleIcon className="w-5 h-5 flex-shrink-0" />
              {error}
            </div>
          )}

          <ModalFooter>
            <Button variant="secondary" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              onClick={handleImport}
              disabled={!file}
              leftIcon={<ArrowUpTrayIcon className="w-4 h-4" />}
            >
              Import Users
            </Button>
          </ModalFooter>
        </div>
      )}

      {step === 'processing' && (
        <div className="py-12 text-center">
          <div className="w-16 h-16 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mx-auto mb-4"></div>
          <h3 className="text-lg font-medium text-gray-900">Importing Users...</h3>
          <p className="text-sm text-gray-500 mt-2">
            This may take a while depending on the number of photos to process.
            Please do not close this window.
          </p>
        </div>
      )}

      {step === 'results' && results && (
        <div className="space-y-6">
          {/* Summary Stats */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
              <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">Total</p>
              <p className="text-2xl font-semibold text-gray-900 mt-1">{results.total_rows}</p>
            </div>
            <div className="bg-green-50 p-4 rounded-xl border border-green-100">
              <p className="text-xs text-green-600 font-medium uppercase tracking-wider">Successful</p>
              <p className="text-2xl font-semibold text-green-700 mt-1">{results.successful}</p>
            </div>
            <div className="bg-red-50 p-4 rounded-xl border border-red-100">
              <p className="text-xs text-red-600 font-medium uppercase tracking-wider">Failed</p>
              <p className="text-2xl font-semibold text-red-700 mt-1">{results.failed}</p>
            </div>
            <div className="bg-yellow-50 p-4 rounded-xl border border-yellow-100">
              <p className="text-xs text-yellow-600 font-medium uppercase tracking-wider">Skipped</p>
              <p className="text-2xl font-semibold text-yellow-700 mt-1">{results.skipped}</p>
            </div>
          </div>

          {/* Results Table */}
          <div className="border border-gray-200 rounded-xl overflow-hidden">
            <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
              <h4 className="text-sm font-medium text-gray-900">Detailed Results</h4>
            </div>
            <div className="max-h-[400px] overflow-y-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Folder
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Details
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {results.results.map((result, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {result.name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono">
                        {result.folder_name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getStatusBadge(result.status)}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {result.error ? (
                          <div className="flex items-center text-red-600">
                            <ExclamationTriangleIcon className="w-4 h-4 mr-1" />
                            {result.error}
                          </div>
                        ) : result.status === 'success' ? (
                          <div className="flex items-center gap-2">
                            <span>{result.images_processed} photos</span>
                            <span className="text-gray-300">|</span>
                            <span>{result.embeddings_created} embeddings</span>
                          </div>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <ModalFooter>
            <Button onClick={handleClose}>
              Close
            </Button>
          </ModalFooter>
        </div>
      )}
    </Modal>
  );
}
