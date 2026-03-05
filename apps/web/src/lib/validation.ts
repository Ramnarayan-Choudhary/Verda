import { ValidationError } from './errors';

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const MAX_MESSAGE_LENGTH = 10_000;
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

// PDF magic bytes: %PDF
const PDF_MAGIC = [0x25, 0x50, 0x44, 0x46];

export function validateUUID(id: string, fieldName: string = 'id'): void {
    if (!id || !UUID_REGEX.test(id)) {
        throw new ValidationError(`Invalid ${fieldName}: must be a valid UUID`, { [fieldName]: id });
    }
}

export function validateMessage(message: string): void {
    if (!message || typeof message !== 'string') {
        throw new ValidationError('Message is required and must be a string');
    }
    if (message.trim().length === 0) {
        throw new ValidationError('Message cannot be empty');
    }
    if (message.length > MAX_MESSAGE_LENGTH) {
        throw new ValidationError(
            `Message too long: ${message.length} characters (max ${MAX_MESSAGE_LENGTH})`,
            { length: message.length, max: MAX_MESSAGE_LENGTH }
        );
    }
}

export function validateFileUpload(file: File): void {
    if (!file) {
        throw new ValidationError('File is required');
    }
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        throw new ValidationError('Only PDF files are supported', { filename: file.name });
    }
    if (file.size > MAX_FILE_SIZE) {
        throw new ValidationError(
            `File too large: ${(file.size / 1024 / 1024).toFixed(1)}MB (max 50MB)`,
            { size: file.size, max: MAX_FILE_SIZE }
        );
    }
}

export async function validatePDFMagicBytes(buffer: Buffer): Promise<void> {
    if (buffer.length < 4) {
        throw new ValidationError('File too small to be a valid PDF');
    }
    const header = Array.from(buffer.subarray(0, 4));
    const isPDF = PDF_MAGIC.every((byte, i) => header[i] === byte);
    if (!isPDF) {
        throw new ValidationError('File does not appear to be a valid PDF (invalid header)');
    }
}
