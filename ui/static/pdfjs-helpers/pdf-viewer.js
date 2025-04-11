/**
 * PDFViewer - Simplified PDF viewer integrating document loading, rendering, viewport management, and.
 * Provides continuous scrolling, DPI-aware rendering, and stable  positioning.
 */

import { PDFCore } from './pdf-core.js';
import { PDFDocument } from './pdf-document.js';
import { PDFViewport } from './pdf-viewport.js';
import { PDFRenderer } from './pdf-renderer.js';

export class PDFViewer {
  constructor({ scale = 1.0, rotation = 0, enableAnnotations = true, continuousMode = true, fileId = null } = {}) {
    this.container = null;
    this.document = new PDFDocument(new PDFCore());
    this.viewport = new PDFViewport({ scale, rotation: rotation || 0 });
    this.renderer = new PDFRenderer(this.document, this.viewport);
    this.currentPage = 1;
    this.observer = null;
    this.enableAnnotations = enableAnnotations;
    this.annotationReady = false;
    this.initializedEventDispatched = false;
    this.fileId = fileId;
  }

  /**
   * Initialize the viewer and load PDF document.
   * @param {string} source - PDF file URL or binary data.
   * @param {string} containerId - DOM container ID for PDF.
   */
  async initialize(source, containerId = 'pdf-main-container') {
    this.container = document.getElementById(containerId);
    if (!this.container) throw new Error('PDF container not found');

    // Look for the dedicated renderer container
    let rendererContainer = document.getElementById('pdf-renderer-container');
    
    // If it doesn't exist, create it inside the main container
    if (!rendererContainer) {
      rendererContainer = document.createElement('div');
      rendererContainer.id = 'pdf-renderer-container';
      rendererContainer.className = 'relative';
      this.container.innerHTML = ''; // Clear container first
      this.container.appendChild(rendererContainer);
    } else {
      // Clear the existing renderer container
      rendererContainer.innerHTML = '';
    }
    
    this.pagesContainer = rendererContainer;
    this.viewport.setContainer(this.container);

    await this.document.load(source);
    
    // Log document information for debugging
    console.log(`BBOX_DEBUG: PDF Document loaded - pages=${this.document.numPages}, container=${containerId}`);
    
    await this._createPageContainers();

    this._setupIntersectionObserver();

    // Hide PDF loader when initialization is complete
    const loader = document.getElementById('pdf-loader');
    if (loader) loader.style.display = 'none';
    
    // Set ready flag for annotations
    this.annotationReady = true;
    
    // Dispatch event to indicate pages initialized -- MOVED TO OBSERVER
    // this._dispatchPDFEvent('pdf-pages-init', { 
    //   numPages: this.document.numPages,
    //   source
    // });
  }

  /**
   * Creates page container elements.
   */
  async _createPageContainers() {
    // Remove any existing page containers first
    const existingContainers = this.pagesContainer.querySelectorAll('.pdf-page-container');
    if (existingContainers.length > 0) {
      console.log(`BBOX_DEBUG: Removing ${existingContainers.length} existing page containers to prevent duplication`);
      existingContainers.forEach(container => container.remove());
    }
    
    for (let i = 1; i <= this.document.numPages; i++) {
      const container = document.createElement('div');
      container.id = `page-container-${i}`;
      container.className = 'pdf-page-container';
      container.style.position = 'relative';
      container.style.margin = '10px auto';
      container.dataset.pageNum = i;
      this.pagesContainer.appendChild(container);
    }
  }

  /**
   * Intersection observer for rendering pages as they become visible.
   */
  async _setupIntersectionObserver() {
    // Log general page rendering approach
    console.log(`BBOX_DEBUG: Setting up page rendering with intersection observer, container=${this.container?.id}`);
    
    // Disconnect existing observer if it exists to prevent multiple observers
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }
    
    this.observer = new IntersectionObserver(entries => {
      entries.forEach(async entry => {
        if (entry.isIntersecting) {
          const pageNum = parseInt(entry.target.dataset.pageNum);
          console.log(`BBOX_DEBUG: Page ${pageNum} intersecting, starting render`);
          
          // --- Dispatch INITIALIZED event here, only once --- 
          if (!this.initializedEventDispatched) {
            this._dispatchPDFEvent('pdf-initialized', { 
              fileId: this.fileId,
              numPages: this.document.numPages,
              source: this.document.loadingParams?.url, // Get source from document if possible
              container: this.container.id, // Add container ID
              fileType: 'pdf' // Add fileType
            });
            this.initializedEventDispatched = true; // Ensure it only fires once
          }
          // --- End event dispatch ---
          
          await this.renderer.renderPage(pageNum);

          // Update current page when a new page is rendered
          this.currentPage = pageNum;
          
          // Get page dimensions after rendering for BBOX_DEBUG
          try {
            const page = await this.document.getPage(pageNum);
            const pageViewport = page.getViewport({ scale: this.viewport.scale, rotation: this.viewport.rotation });
            console.log(`BBOX_DEBUG: Rendered Page ${pageNum} - originalSize=${page.view[2]}x${page.view[3]}, viewport=${pageViewport.width}x${pageViewport.height}, scale=${this.viewport.scale}, rotation=${this.viewport.rotation}`);
            
            // Add detailed viewport transformation info
            console.log(`BBOX_DEBUG: Page ${pageNum} viewport transform matrix: [${pageViewport.transform.join(', ')}]`);
          } catch (err) {
            console.error(`Error getting page dimensions for debugging: ${err.message}`);
          }
          
          this.observer.unobserve(entry.target);
          
          // Dispatch event for the rendered page
          this._dispatchPDFEvent('pdf-page-rendered', { 
            pageNumber: pageNum,
            currentScale: this.viewport.scale,
            currentRotation: this.viewport.rotation
          });
        }
      });
    }, { root: this.container, rootMargin: '500px' });

    // Add a small delay before observing elements to prevent race conditions
    setTimeout(() => {
      document.querySelectorAll('.pdf-page-container').forEach(el => this.observer.observe(el));
    }, 50);
  }

  /**
   * Dispatch a standardized PDF event.
   * @private
   * @param {string} eventName - The event name
   * @param {Object} detail - The event details
   */
  _dispatchPDFEvent(eventName, detail = {}) {
    document.dispatchEvent(new CustomEvent(eventName, {
      detail: {
        ...detail,
        timestamp: Date.now(),
        source: 'pdf-viewer'
      }
    }));
  }

  /**
   * Get the current PDF page.
   * This method is used by the annotation system to correctly position annotations.
   * @param {number} pageNumber - Optional specific page number, defaults to current page
   * @returns {Promise<Object>} - The PDF.js page object
   */
  async getCurrentPage(pageNumber = null) {
    const pageNum = pageNumber || this.currentPage || 1;
    try {
      return await this.document.getPage(pageNum);
    } catch (error) {
      console.error(`Error getting page ${pageNum}:`, error);
      return null;
    }
  }

  /**
   * Navigate to a specific page smoothly.
   */
  navigateToPage(pageNumber) {
    const pageEl = document.getElementById(`page-container-${pageNumber}`);
    if (pageEl) pageEl.scrollIntoView({ behavior: 'smooth' });
  }

  /**
   * Zoom methods
   */
  zoomIn(factor = 0.1) {
    const newScale = this.viewport.scale * (1 + factor);
    return this.setZoom(newScale);
  }

  zoomOut(factor = 0.1) {
    const newScale = this.viewport.scale * (1 - factor);
    return this.setZoom(newScale);
  }

  setZoom(scale) {
    // Ensure scale is within valid bounds
    const clampedScale = Math.min(Math.max(scale, this.viewport.minScale), this.viewport.maxScale);
    this.viewport.setScale(clampedScale);
    
    // Clear and re-render pages
    this.renderer.clearAllPages();
    
    // Setup intersection observer with a slight delay to avoid race conditions
    setTimeout(() => {
      this._setupIntersectionObserver();
    }, 10);
    
    // Notify about transform change for annotations
    this._notifyTransformChanged();
    
    return clampedScale;
  }

  /**
   * Set the viewport to fit the PDF width to the container.
   */
  async maximize() {
    try {
      // If no current page is loaded, use first page or just the viewport's method
      let currentPage = null;
      
      try {
        // Try to get the current visible page if possible
        const visiblePages = this.viewport.getVisiblePages(this.document.numPages);
        if (visiblePages.length > 0) {
          currentPage = await this.document.getPage(visiblePages[0].pageNumber);
        } else {
          // Fall back to first page
          currentPage = await this.document.getPage(1);
        }
      } catch (error) {
        console.warn('Could not get current page for maximize, using default scaling');
      }
      
      // Calculate fit to width scale
      const maxScale = await this.viewport.fitToWidth(currentPage);
      
      // Apply the new scale using setZoom to ensure consistent behavior
      return this.setZoom(maxScale);
    } catch (error) {
      console.error('Error maximizing view:', error);
      return this.viewport.scale;
    }
  }

  /**
   * Rotate PDF view.
   */
  rotate(degrees = 90) {
    this.viewport.setRotation(this.viewport.rotation + degrees);
    this.renderer.clearAllPages();
    
    // Setup intersection observer with a slight delay to avoid race conditions
    setTimeout(() => {
      this._setupIntersectionObserver();
    }, 10);
    
    // Notify about transform change for annotations
    this._notifyTransformChanged();
    
    return this.viewport.rotation;
  }

  /**
   * Notify about transform changes (for annotations).
   */
  _notifyTransformChanged() {
    // Dispatch standardized event for annotation system
    this._dispatchPDFEvent('document-transform-changed', this.getTransformState());
  }

  /**
   * Get current scale and rotation for external systems.
   * @returns {Object} Current transform state
   */
  getTransformState() {
    return this.viewport.getTransformState();
  }

  /**
   * Get viewport for the current page.
   * Used by annotation system to access viewport for coordinate conversions.
   * @param {number} pageNumber - Optional page number, defaults to current page
   * @returns {Promise<Object>} - The viewport object or null if unavailable
   */
  async getPageViewport(pageNumber = null) {
    try {
      const page = await this.getCurrentPage(pageNumber);
      if (!page) return null;
      
      return this.viewport.calculateViewport(page);
    } catch (error) {
      console.error(`Error getting page viewport:`, error);
      return null;
    }
  }

  /**
   * Convert normalized coordinates (0-1) to viewport coordinates.
   * Bridge method for the annotation system to correctly position annotations.
   * @param {Object} normalizedCoords - Coordinates in normalized space (0-1)
   * @param {number} pageNumber - Optional page number, defaults to current page
   * @returns {Promise<Object>} - Coordinates in viewport space
   */
  async normalizedToViewport(normalizedCoords, pageNumber = null) {
    try {
      const page = await this.getCurrentPage(pageNumber);
      if (!page) return normalizedCoords;
      
      return this.viewport.normalizedToPdfViewport(normalizedCoords, page);
    } catch (error) {
      console.error(`Error converting coordinates:`, error);
      return normalizedCoords;
    }
  }

  /**
   * Convert viewport coordinates to normalized coordinates (0-1).
   * Bridge method for the annotation system to store annotations in normalized format.
   * @param {Object} viewportCoords - Coordinates in viewport space
   * @param {number} pageNumber - Optional page number, defaults to current page
   * @returns {Promise<Object>} - Coordinates in normalized space (0-1)
   */
  async viewportToNormalized(viewportCoords, pageNumber = null) {
    try {
      const page = await this.getCurrentPage(pageNumber);
      if (!page) return viewportCoords;
      
      return this.viewport.pdfViewportToNormalized(viewportCoords, page);
    } catch (error) {
      console.error(`Error converting coordinates:`, error);
      return viewportCoords;
    }
  }

  /**
   * Cleanup resources to prevent memory leaks.
   */
  cleanup() {
    if (this.observer) this.observer.disconnect();
    this.renderer.clearAllPages();
    // Ensure document resources are properly destroyed
    this.document.destroy();
    
    // Dispatch cleanup event
    this._dispatchPDFEvent('pdf-cleanup');
  }
}

// Expose globally for compatibility
window.PDFViewer = PDFViewer;
