/**
 * PDF Viewer System - Main Entry Point
 *
 * Unified exports for the simplified PDF viewer system.
 */

// Import modules
import { PDFCore } from './pdf-core.js';
import { PDFDocument } from './pdf-document.js';
import { PDFViewport } from './pdf-viewport.js';
import { PDFRenderer } from './pdf-renderer.js';
import { PDFViewer } from './pdf-viewer.js';

// Export modules for modern usage
export {
  PDFCore,
  PDFDocument,
  PDFViewport,
  PDFRenderer,
  PDFViewer
};

// Expose globally for easy legacy integration
window.PDFViewerSystem = {
  PDFCore,
  PDFDocument,
  PDFViewport,
  PDFRenderer,
  PDFViewer
};
