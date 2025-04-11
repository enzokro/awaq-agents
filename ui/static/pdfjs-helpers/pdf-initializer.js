// pdf-initializer.js

/**
 * PDF Initializer Module
 *
 * Handles PDF.js viewer initialization.
 * Ensures PDF.js availability, initializes viewer, and dispatches lifecycle events.
 */

import { PDFViewer } from './pdf-viewer.js';

// Define standard events
const PDF_EVENTS = {
  INITIALIZED: 'pdf-initialized', 
  PAGES_INIT: 'pdf-pages-init',
  PAGE_RENDERED: 'pdf-page-rendered',
  TRANSFORM_CHANGED: 'document-transform-changed',
  CLEANUP: 'pdf-cleanup'
};

/**
 * Track PDF viewer state globally.
 */
const viewerState = {
  isInitialized: false,
  activeFileId: null,
  instance: null
};

/**
 * Ensure PDF.js is globally available.
 */
async function ensurePDFjsLoaded() {
  if (!window.pdfjsLib) {
    throw new Error('PDF.js library is not loaded.');
  }
}

/**
 * Displays an error message in the PDF container.
 */
function showErrorMessage(containerId, message) {
  const container = document.getElementById(containerId);
  if (!container) return;
  
  container.innerHTML = `
    <div class="pdf-error-message" style="padding: 20px; color: #721c24; background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 4px; text-align: center;">
      <h3>Error Loading PDF</h3>
      <p>${message}</p>
    </div>
  `;
  
  const loader = document.getElementById('pdf-loader');
  if (loader) loader.style.display = 'none';
}

/**
 * Clean up all PDF-related resources
 */
function cleanupPDFResources() {
  console.log('📄 Cleaning up PDF resources');

  // 1. Clean up viewer instance
  if (viewerState.instance) {
    console.log('  -> Cleaning up PDFViewer instance');
    viewerState.instance.cleanup(); // This should handle renderer/document cleanup
    viewerState.instance = null;
  }

  // 2. Clean up specific DOM elements inside the container
  const pdfContainer = document.getElementById('pdf-main-container');
  if (pdfContainer) {
    const rendererContainer = pdfContainer.querySelector('#pdf-renderer-container');
    if (rendererContainer) {
        console.log('  -> Clearing PDF renderer container');
        rendererContainer.innerHTML = ''; // Remove all page containers, canvases, etc.
    }
  }
  
  // 3. Ensure the loader is hidden
  const loader = document.getElementById('pdf-loader');
  if (loader) {
    loader.style.display = 'none';
  }

  // 4. Reset viewer state variables
  viewerState.isInitialized = false;
  viewerState.activeFileId = null;
  console.log('  -> Viewer state reset');

  // 5. Dispatch cleanup event so other systems like annotations can respond
  console.log('  -> Dispatching PDF cleanup event');
  document.dispatchEvent(new CustomEvent(PDF_EVENTS.CLEANUP, {
    detail: { timestamp: Date.now() }
  }));
  
  console.log('  -> PDF cleanup finished');
}

/**
 * Get the current PDF viewer instance
 */
function getPDFViewer() {
  return viewerState.instance;
}

/**
 * Ensure annotations are loaded for a PDF
 * @param {string} fileId - The file ID
 * @param {string} containerId - The container ID
 */
function ensureAnnotationsLoaded(fileId, containerId = 'pdf-main-container') {
  setTimeout(() => {
    // Check if annotation manager exists and has the correct file ID
    if (!window.currentAnnotationManager || window.currentAnnotationManager.fileId !== fileId) {
      console.log(`🔄 Ensuring annotations are loaded for PDF ${fileId}`);
      
      // Initialize annotation system if we have it
      if (typeof window.initializeAnnotationSystem === 'function') {
        window.initializeAnnotationSystem({
          fileId,
          fileType: 'pdf',
          containerId
        });
      } else {
        console.warn('Cannot load annotations - annotation system not available');
      }
    } else {
      console.log(`✅ Annotation manager already exists for ${fileId}`);
      // Just refresh annotations in case they need updating
      if (window.currentAnnotationManager.refreshAnnotations) {
        window.currentAnnotationManager.refreshAnnotations();
      }
    }
  }, 500); // Short delay to ensure PDF is fully initialized
}

/**
 * Initializes PDF viewer for the specified PDF file.
 * @param {string} fileId - The ID of the file to view
 * @param {Object} options - Configuration options
 * @param {string} options.containerId - DOM container ID for PDF (default: 'pdf-main-container')
 * @param {number} options.initialScale - Initial scale (default: 1.0)
 * @param {number} options.initialRotation - Initial rotation (default: 0)
 * @param {boolean} options.enableAnnotations - Whether to enable annotations (default: true)
 * @returns {Promise<PDFViewer>} - The initialized PDF viewer instance
 */
async function initPDFViewer(fileId, options = {}) {
  console.log(`🌟 Initializing PDF viewer for file: ${fileId}`);
  
  // Always perform cleanup before initializing a new viewer
  console.log('  -> Performing pre-initialization cleanup...');
  cleanupPDFResources(); // Cleanup PDF resources first
  if (window.cleanupAnnotationSystem) {
      cleanupAnnotationSystem(); // Then cleanup annotations
  }
  // Cleanup transformer if present
  if (window.currentDocumentTransformer && window.currentDocumentTransformer.cleanup) {
      window.currentDocumentTransformer.cleanup();
  }
  console.log('  -> Pre-initialization cleanup complete.');

  const containerId = options.containerId || 'pdf-main-container';
  const initialScale = options.initialScale || 1.0;
  const initialRotation = options.initialRotation || 0;
  const enableAnnotations = options.enableAnnotations !== false;

  // Check if container exists
  let container = document.getElementById(containerId);
  if (!container) {
    console.warn(`⚠️ Container #${containerId} not found immediately, waiting briefly...`);
    
    // Wait up to 500ms for container to appear (common with HTMX)
    await new Promise(resolve => {
      let attempts = 0;
      const checkInterval = setInterval(() => {
        container = document.getElementById(containerId);
        attempts++;
        
        if (container || attempts >= 10) {
          clearInterval(checkInterval);
          resolve();
        }
      }, 50);
    });
    
    // Final check after waiting
    container = document.getElementById(containerId);
    if (!container) {
      const error = `Container #${containerId} not found. PDF viewer cannot initialize.`;
      console.error(`❌ ${error}`);
      // Dispatch event for potential UI feedback
      document.dispatchEvent(new CustomEvent('pdf-init-failed', { 
        detail: { fileId, error }
      }));
      // Don't show a message directly in the container, let the calling code handle UI
      // showErrorMessage(containerId, error);
      throw new Error(error);
    }
  }

  const loader = document.getElementById('pdf-loader');
  if (loader) loader.style.display = 'flex';

  try {
    await ensurePDFjsLoaded();

    // Initialize new viewer
    const viewer = new PDFViewer({
      fileId: fileId,
      scale: initialScale,
      rotation: initialRotation,
      enableAnnotations
    });

    // Track viewer instance globally
    viewerState.instance = viewer;
    viewerState.isInitialized = true;
    viewerState.activeFileId = fileId;

    // Set file ID as a data attribute on the container
    container.dataset.fileId = fileId;
    container.dataset.fileType = 'pdf';

    // Initialize PDF document
    await viewer.initialize(`/files/load/${fileId}`, containerId);

    // Notify system that PDF is fully initialized
    document.dispatchEvent(new CustomEvent(PDF_EVENTS.INITIALIZED, {
      detail: {
        fileId,
        numPages: viewer.document.numPages,
        fileType: 'pdf',
        container: containerId
      }
    }));

    // Hide the loader now that we're fully initialized
    if (loader) loader.style.display = 'none';
    
    console.log(`✅ PDF viewer initialized for file: ${fileId}`);
    
    // Ensure annotations are loaded if enabled
    if (enableAnnotations) {
      ensureAnnotationsLoaded(fileId, containerId);
    }
    
    // Initialize the UnifiedDocumentTransformer for PDF
    // Ensure this happens AFTER PDF viewer and annotations are ready
    setTimeout(() => { // Use timeout to ensure DOM is stable
        if (window.UnifiedDocumentTransformer) {
            console.log('  -> Initializing UnifiedDocumentTransformer for PDF');
            window.currentDocumentTransformer = new window.UnifiedDocumentTransformer({
                fileType: 'pdf',
                fileId: fileId,
                container: container // Pass the main PDF container
            });
        } else {
            console.warn('UnifiedDocumentTransformer not found, controls might not work.');
        }
    }, 100); // Small delay

    return viewer;
  } catch (error) {
    console.error('❌ Error during PDF viewer initialization:', error);
    showErrorMessage(containerId, error.message);
    document.dispatchEvent(new CustomEvent('pdf-init-failed', { 
      detail: { fileId, error: error.message } 
    }));
    
    // Clean up any partial initialization
    cleanupPDFResources();
    
    throw error;
  }
}

/**
 * Handles HTMX afterSwap event to reinitialize PDF viewer dynamically.
 */
document.addEventListener('htmx:afterSwap', (event) => {
  // Check if the swapped content contains a PDF container
  const pdfContainer = event.detail.target.querySelector('#pdf-main-container[data-file-id][data-file-type="pdf"]');
  // Check if the swapped content contains an Image container
  const imageContainer = event.detail.target.querySelector('#image-container[data-file-id][data-file-type="image"]');
  
  if (pdfContainer) {
      const fileId = pdfContainer.dataset.fileId;
      console.log(`📄 HTMX swap detected PDF container for file: ${fileId}. Triggering initialization.`);
      // Use a small timeout to ensure the DOM is fully updated after swap
      setTimeout(() => initPDFViewer(fileId), 50); 
  }
});

/**
 * Sets up observer to cleanup PDF viewer resources when container is removed.
 */
const observer = new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    mutation.removedNodes.forEach(node => {
      if (node.nodeType === Node.ELEMENT_NODE &&
          (node.id === 'pdf-main-container' || node.querySelector('#pdf-main-container'))) {
        cleanupPDFResources();
      }
    });
  }
});

observer.observe(document.body, { childList: true, subtree: true });

// Export functions and constants
export {
  initPDFViewer,
  cleanupPDFResources,
  getPDFViewer,
  ensureAnnotationsLoaded,
  PDF_EVENTS
};

// For backward compatibility
window.initPDFViewer = initPDFViewer;
window.cleanupPDFResources = cleanupPDFResources;
window.getPDFViewer = getPDFViewer;
window.ensureAnnotationsLoaded = ensureAnnotationsLoaded;
window.PDF_EVENTS = PDF_EVENTS;

// --- NEW: Cleanup listener using htmx:afterSettle ---
document.addEventListener('htmx:afterSettle', (event) => {
    console.log('[afterSettle] Checking if cleanup is needed...');
    
    const pdfContainerExists = document.getElementById('pdf-main-container');
    const imageContainerExists = document.getElementById('image-container');
    
    // Check if we WERE showing a PDF but it's now gone
    if (viewerState.activeFileId && !pdfContainerExists) {
        console.log('[afterSettle] PDF container removed. Cleaning up PDF resources.');
        cleanupPDFResources(); // This will dispatch PDF_EVENTS.CLEANUP
        // Annotation cleanup is handled by the PDF_EVENTS.CLEANUP listener
        // Transformer cleanup should ideally also listen to PDF_EVENTS.CLEANUP or be called here
        if (window.currentDocumentTransformer && window.currentDocumentTransformer.fileType === 'pdf') {
             console.log('[afterSettle] Cleaning up PDF transformer.');
             window.currentDocumentTransformer.cleanup();
        }
    }
    
    // Check if we WERE showing an Image but it's now gone
    // We check the annotation manager as a proxy for image view state
    const currentManager = window.currentAnnotationManager;
    if (currentManager && currentManager.fileType === 'image' && !imageContainerExists) {
        console.log('[afterSettle] Image container removed. Cleaning up Image resources.');
        // Cleanup annotations
        if (typeof cleanupAnnotationSystem === 'function') {
             cleanupAnnotationSystem();
        }
        // Cleanup transformer
        if (window.currentDocumentTransformer && window.currentDocumentTransformer.fileType === 'image') {
             console.log('[afterSettle] Cleaning up Image transformer.');
             window.currentDocumentTransformer.cleanup();
        }
    }
});
// --- End cleanup listener ---
