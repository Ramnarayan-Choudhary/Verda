/* eslint-disable @typescript-eslint/no-require-imports */

/**
 * Extract text content from a PDF buffer.
 * 
 * NOTE: We import pdf-parse/lib/pdf-parse.js directly because
 * the default entry point in pdf-parse@1.1.1 tries to load a
 * test fixture file (test/data/05-versions-space.pdf) on require(),
 * causing ENOENT errors in production.
 */
export async function extractTextFromPDF(buffer: Buffer): Promise<string> {
    const pdf = require('pdf-parse/lib/pdf-parse.js');
    const data = await pdf(buffer);
    return sanitizePdfText(data.text);
}

/**
 * Sanitize PDF-extracted text for PostgreSQL storage.
 * Removes null bytes, control characters, and other problematic
 * Unicode escape sequences that PostgreSQL's text type rejects.
 */
function sanitizePdfText(text: string): string {
    return text
        // Remove null bytes (most common PostgreSQL failure)
        .replace(/\0/g, '')
        // Remove other C0 control characters except \t \n \r
        .replace(/[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '')
        // Remove Unicode replacement character and other problematic chars
        .replace(/\uFFFD/g, '')
        // Normalize whitespace (collapse multiple spaces/tabs)
        .replace(/[ \t]+/g, ' ')
        // Collapse 3+ newlines into 2
        .replace(/\n{3,}/g, '\n\n');
}

/**
 * Get PDF metadata
 */
export async function getPDFInfo(buffer: Buffer) {
    const pdf = require('pdf-parse/lib/pdf-parse.js');
    const data = await pdf(buffer);
    return {
        pages: data.numpages,
        title: data.info?.Title || 'Untitled',
        author: data.info?.Author || 'Unknown',
        textLength: data.text.length,
    };
}
