'use client';

import { useState, useRef, useMemo } from 'react';
import { Send, Paperclip, X, FileText, BookOpen } from 'lucide-react';

// arXiv ID pattern: e.g., 2301.07041 or arxiv:2301.07041v2
const ARXIV_ID_REGEX = /^(?:arxiv:)?(\d{4}\.\d{4,5})(v\d+)?$/i;

interface ChatInputProps {
    onSendMessage: (message: string) => void;
    onUploadFile: (file: File) => void;
    onFetchArxiv?: (arxivId: string) => void;
    disabled?: boolean;
    isProcessing?: boolean;
}

export default function ChatInput({
    onSendMessage,
    onUploadFile,
    onFetchArxiv,
    disabled = false,
    isProcessing = false,
}: ChatInputProps) {
    const [text, setText] = useState('');
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Detect arXiv ID as user types (derived state, no effect needed)
    const detectedArxivId = useMemo(() => {
        const trimmed = text.trim();
        const match = trimmed.match(ARXIV_ID_REGEX);
        if (match && trimmed === match[0]) {
            return match[1];
        }
        return null;
    }, [text]);

    const handleSend = () => {
        if (selectedFile) {
            onUploadFile(selectedFile);
            setSelectedFile(null);
            setText('');
            return;
        }

        if (!text.trim()) return;

        // If arXiv ID detected and handler exists, use fetch flow
        if (detectedArxivId && onFetchArxiv) {
            onFetchArxiv(detectedArxivId);
            setText('');
            return;
        }

        onSendMessage(text.trim());
        setText('');

        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
        }
    };

    const handleFetchArxiv = () => {
        if (detectedArxivId && onFetchArxiv) {
            onFetchArxiv(detectedArxivId);
            setText('');
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        setText(e.target.value);
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height =
                Math.min(textareaRef.current.scrollHeight, 120) + 'px';
        }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file && file.type === 'application/pdf') {
            setSelectedFile(file);
        }
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    return (
        <div className="chat-input-area">
            {selectedFile && (
                <div className="upload-indicator">
                    <FileText size={16} />
                    <span className="filename">{selectedFile.name}</span>
                    <button
                        className="remove-btn"
                        onClick={() => setSelectedFile(null)}
                    >
                        <X size={14} />
                    </button>
                </div>
            )}

            {detectedArxivId && onFetchArxiv && (
                <div className="arxiv-detect-banner">
                    <BookOpen size={14} />
                    <span>arXiv paper detected: <strong>{detectedArxivId}</strong></span>
                    <button
                        className="arxiv-fetch-btn"
                        onClick={handleFetchArxiv}
                        disabled={disabled || isProcessing}
                    >
                        Fetch & Analyze
                    </button>
                </div>
            )}

            <div className="chat-input-wrapper">
                <textarea
                    ref={textareaRef}
                    rows={1}
                    placeholder={
                        isProcessing
                            ? 'Processing your paper...'
                            : selectedFile
                                ? 'Press Enter to upload and analyze...'
                                : 'Ask about research, paste an arXiv ID (e.g. 2301.07041), or upload a PDF...'
                    }
                    value={text}
                    onChange={handleTextChange}
                    onKeyDown={handleKeyDown}
                    disabled={disabled || isProcessing}
                />

                <div className="input-actions">
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf"
                        onChange={handleFileSelect}
                        style={{ display: 'none' }}
                    />
                    <button
                        className="input-btn"
                        type="button"
                        onClick={() => {
                            if (fileInputRef.current) {
                                fileInputRef.current.click();
                            }
                        }}
                        title="Upload PDF"
                        disabled={disabled || isProcessing}
                    >
                        <Paperclip size={18} />
                    </button>
                    <button
                        className="input-btn send"
                        onClick={handleSend}
                        disabled={disabled || isProcessing || (!text.trim() && !selectedFile)}
                        title="Send"
                    >
                        {isProcessing ? (
                            <div className="spinner" />
                        ) : (
                            <Send size={16} />
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
