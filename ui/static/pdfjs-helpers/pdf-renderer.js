/**
 * PDFRenderer - Manages PDF page rendering with canvas.
 * Simplified for clarity, maintainability, and optimized for high-DPI displays.
 */

import { PDFDocument } from './pdf-document.js';
import { PDFViewport } from './pdf-viewport.js';

export class PDFRenderer {
  constructor(document, viewport) {
    this.document = document;
    this.viewport = viewport;
    this.renderedPages = new Set();
    this.renderTasks = new Map(); // Track active render tasks
  }

  /**
   * Render a PDF page into its container element.
   * @param {number} pageNum - The page number (1-based index).
   */
  async renderPage(pageNum) {
    // Cancel any existing render task for this page
    if (this.renderTasks.has(pageNum)) {
      const existingTask = this.renderTasks.get(pageNum);
      existingTask.cancel();
      this.renderTasks.delete(pageNum);
    }

    const page = await this.document.getPage(pageNum);
    const container = document.getElementById(`page-container-${pageNum}`);
    if (!container) return;

    const viewport = this.viewport.calculateViewport(page);
    const pixelRatio = window.devicePixelRatio || 1;

    // Prepare canvas - always create a new canvas to avoid reuse issues
    let canvas = container.querySelector('canvas');
    if (canvas) {
      canvas.remove(); // Remove existing canvas to avoid reuse
    }
    
    canvas = document.createElement('canvas');
    canvas.className = 'pdf-page-canvas';
    container.appendChild(canvas);

    const context = canvas.getContext('2d');

    // Set canvas size for high-DPI
    canvas.width = Math.floor(viewport.width * pixelRatio);
    canvas.height = Math.floor(viewport.height * pixelRatio);
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;

    // Scale context for DPI
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    context.clearRect(0, 0, viewport.width, viewport.height);

    // Prepare annotation layer if it doesn't exist
    let annotationLayer = container.querySelector('.annotation-layer');
    if (!annotationLayer) {
      annotationLayer = this._createAnnotationLayer(container, viewport);
    } else {
      // Update existing annotation layer dimensions
      annotationLayer.style.width = `${viewport.width}px`;
      annotationLayer.style.height = `${viewport.height}px`;
    }

    // Store page metadata for annotation system
    container.dataset.pageWidth = viewport.width;
    container.dataset.pageHeight = viewport.height;
    container.dataset.pageScale = viewport.scale;
    container.dataset.pageRotation = viewport.rotation;
    container.dataset.pageNumber = pageNum;

    // Render the page and track the render task
    const renderTask = page.render({ canvasContext: context, viewport });
    this.renderTasks.set(pageNum, renderTask);
    
    try {
      await renderTask.promise;
      this.renderedPages.add(pageNum);
      
      // Dispatch event to notify that the page is rendered
      this._dispatchRenderedEvent(pageNum, viewport);
    } catch (error) {
      if (error.name !== 'RenderingCancelled') {
        console.error(`Error rendering page ${pageNum}:`, error);
      }
    } finally {
      // Clean up the render task reference
      this.renderTasks.delete(pageNum);
    }
  }

  /**
   * Create an annotation layer for the PDF page.
   * @private
   * @param {HTMLElement} container - The page container
   * @param {Object} viewport - The page viewport
   * @returns {HTMLElement} The created annotation layer
   */
  _createAnnotationLayer(container, viewport) {
    const annotationLayer = document.createElement('div');
    annotationLayer.className = 'annotation-layer';
    Object.assign(annotationLayer.style, {
      position: 'absolute',
      top: '0',
      left: '0',
      right: '0',
      bottom: '0',
      width: `${viewport.width}px`,
      height: `${viewport.height}px`,
      pointerEvents: 'none'
    });
    
    // Add data attributes for easy access by annotation system
    annotationLayer.dataset.pageScale = viewport.scale;
    annotationLayer.dataset.pageRotation = viewport.rotation;
    
    container.appendChild(annotationLayer);
    return annotationLayer;
  }

  /**
   * Dispatch an event when a page is rendered.
   * @private
   * @param {number} pageNum - The page number that was rendered
   * @param {Object} viewport - The viewport used for rendering
   */
  _dispatchRenderedEvent(pageNum, viewport) {
    document.dispatchEvent(new CustomEvent('pdf-page-rendered', {
      detail: {
        pageNumber: pageNum,
        viewport: {
          width: viewport.width,
          height: viewport.height,
          scale: viewport.scale,
          rotation: viewport.rotation
        },
        timestamp: Date.now()
      }
    }));
  }

  /**
   * Render multiple pages.
   * @param {Array<number>} pageNumbers 
   */
  renderPages(pageNumbers) {
    return Promise.all(pageNumbers.map(pageNum => this.renderPage(pageNum)));
  }

  /**
   * Clear rendered canvas for a given page.
   * @param {number} pageNum 
   */
  clearPage(pageNum) {
    // Cancel any active rendering task
    if (this.renderTasks.has(pageNum)) {
      const renderTask = this.renderTasks.get(pageNum);
      renderTask.cancel();
      this.renderTasks.delete(pageNum);
    }
    
    const container = document.getElementById(`page-container-${pageNum}`);
    const canvas = container?.querySelector('canvas');
    if (canvas) canvas.remove();
    this.renderedPages.delete(pageNum);
  }

  /**
   * Clear all canvases.
   */
  clearAllPages() {
    // Cancel all active render tasks first
    this.renderTasks.forEach((task, pageNum) => {
      task.cancel();
    });
    this.renderTasks.clear();
    
    // Then remove the canvases
    this.renderedPages.forEach(pageNum => {
      const container = document.getElementById(`page-container-${pageNum}`);
      const canvas = container?.querySelector('canvas');
      if (canvas) canvas.remove();
    });
    this.renderedPages.clear();
  }

  /**
   * Get the annotation layer for a specific page.
   * @param {number} pageNum - The page number
   * @returns {HTMLElement|null} The annotation layer element or null if not found
   */
  getAnnotationLayer(pageNum) {
    const container = document.getElementById(`page-container-${pageNum}`);
    if (!container) return null;
    
    let annotationLayer = container.querySelector('.annotation-layer');
    if (!annotationLayer) {
      // If the page is rendered but annotation layer doesn't exist, create it
      if (this.renderedPages.has(pageNum)) {
        const page = this.document.getPage(pageNum);
        if (page) {
          const viewport = this.viewport.calculateViewport(page);
          annotationLayer = this._createAnnotationLayer(container, viewport);
        }
      }
    }
    
    return annotationLayer;
  }
}

// Global exposure for legacy compatibility
window.PDFRenderer = PDFRenderer;
