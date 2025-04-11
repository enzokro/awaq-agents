/**
 * PDFViewport - Manages scaling, rotation, and viewport calculations for PDF pages.
 * Simplified for clarity, maintainability, and robust coordinate management.
 */

export class PDFViewport {
  constructor({ minScale = 0.25, maxScale = 5.0, scale = 1.0, rotation = 0, container = null } = {}) {
    this.scale = scale;
    this.rotation = rotation;
    this.minScale = minScale;
    this.maxScale = maxScale;
    this.container = container;
  }

  /**
   * Set container element (required for viewport calculations).
   * @param {HTMLElement} container 
   */
  setContainer(container) {
    this.container = container;
  }

  /**
   * Set the viewport scale (zoom level).
   * @param {number} scale 
   */
  setScale(scale) {
    const clampedScale = Math.min(Math.max(scale, this.minScale), this.maxScale);
    this.scale = clampedScale;
    return this.scale;
  }

  /**
   * Get current viewport scale.
   */
  getScale() {
    return this.scale;
  }

  /**
   * Adjust viewport rotation (0, 90, 180, 270 degrees).
   * @param {number} rotation 
   */
  setRotation(rotation) {
    this.rotation = ((rotation % 360) + 360) % 360;
  }

  /**
   * Get viewport rotation.
   */
  getRotation() {
    return this.rotation;
  }

  /**
   * Calculate a page viewport with current scale and rotation.
   * @param {Object} page - PDF.js page object
   */
  calculateViewport(page) {
    return page.getViewport({ scale: this.scale, rotation: this.rotation });
  }

  /**
   * Create a viewport object from a page that can be used by the annotation system.
   * @param {Object} page - PDF.js page object
   * @param {Object} options - Viewport options
   * @returns {Object} - A viewport object compatible with the annotation system
   */
  toPdfViewport(page, options = {}) {
    // Get the native PDF.js viewport
    const nativeViewport = page.getViewport({ 
      scale: options.scale || this.scale, 
      rotation: options.rotation || this.rotation 
    });
    
    // Return an object with only the properties needed by our annotation system
    return {
      width: nativeViewport.width,
      height: nativeViewport.height,
      scale: nativeViewport.scale,
      rotation: nativeViewport.rotation,
      offsetX: nativeViewport.offsetX || 0,
      offsetY: nativeViewport.offsetY || 0,
      transform: nativeViewport.transform,
      
      // Add conversion methods needed by annotations
      convertToViewportPoint: (x, y) => {
        const point = nativeViewport.convertToViewportPoint(x, y);
        return point;
      },
      
      convertToPdfPoint: (x, y) => {
        const point = nativeViewport.convertToPdfPoint(x, y);
        return point;
      }
    };
  }

  /**
   * Calculate the scale to fit a page to the width of the container.
   * @param {Object} page - PDF.js page object (optional)
   * @returns {number} - The calculated scale
   */
  async fitToWidth(page = null) {
    if (!this.container) {
      console.warn('Container not set, using default scale');
      return this.scale;
    }

    try {
      const containerWidth = this.container.clientWidth;
      
      // If no page is provided, use a standard page size (A4)
      if (!page) {
        const standardWidth = 595; // A4 width in points
        const scale = (containerWidth / standardWidth) * 0.95;
        return this.setScale(scale);
      }
      
      // Get the page viewport at scale 1 to calculate the proper fit
      const viewport = page.getViewport({ scale: 1, rotation: this.rotation });
      const scale = (containerWidth / viewport.width) * 0.95;
      
      // Set the scale within min/max bounds
      return this.setScale(scale);
    } catch (error) {
      console.error('Error calculating fit to width:', error);
      return this.scale;
    }
  }

  /**
   * Convert PDF coordinates to viewport coordinates.
   * @param {number[]} rect - PDF coordinates [x1, y1, x2, y2]
   * @param {Object} page - PDF.js page object
   */
  pdfRectToViewport(rect, page) {
    const viewport = this.calculateViewport(page);
    return viewport.convertToViewportRectangle(rect);
  }

  /**
   * Get currently visible pages in a scrollable container.
   * @param {number} numPages - Total number of pages.
   * @returns {number[]} Array of visible page numbers.
   */
  getVisiblePages(numPages) {
    if (!this.container) return [];

    const visiblePages = [];
    const { scrollTop, clientHeight } = this.container;
    const scrollBottom = scrollTop + clientHeight;

    for (let pageNum = 1; pageNum <= numPages; pageNum++) {
      const pageEl = document.getElementById(`page-container-${pageNum}`);
      if (!pageEl) continue;

      const { offsetTop, offsetHeight } = pageEl;
      const pageBottom = offsetTop + offsetHeight;

      if (offsetTop < scrollBottom && pageBottom > scrollTop) {
        visiblePages.push({ pageNumber: pageNum, visibility: Math.min(pageBottom, scrollBottom) - Math.max(offsetTop, scrollTop) });
      }
    }

    return visiblePages;
  }

  /**
   * Determine the most visible page within the viewport.
   * @param {number} numPages - Total number of pages
   * @returns {number|null} - Most visible page number
   */
  getMostVisiblePage(numPages) {
    const visiblePages = this.getVisiblePages(numPages);
    if (visiblePages.length === 0) return null;
    
    let mostVisiblePage = visiblePages[0].pageNumber;
    let maxVisibleArea = visiblePages[0].visibility;

    visiblePages.forEach(page => {
      if (page.visibility > maxVisibleArea) {
        maxVisibleArea = page.visibility;
        mostVisiblePage = page.pageNumber;
      }
    });

    return mostVisiblePage;
  }

  /**
   * Get the current transform state for use by the annotation system.
   * This provides a standardized interface for annotations to access viewport state.
   * @returns {Object} Current transform state
   */
  getTransformState() {
    return {
      scale: this.scale,
      rotation: this.rotation,
      fileType: 'pdf'
    };
  }

  /**
   * Convert normalized coordinates (0-1) to PDF viewport coordinates.
   * Bridge method for the annotation system to correctly position annotations.
   * @param {Object} normalizedCoords - Coordinates in normalized space (0-1)
   * @param {Object} page - PDF.js page object
   * @returns {Object} Coordinates in viewport space
   */
  normalizedToPdfViewport(normalizedCoords, page) {
    if (!page) return normalizedCoords;
    
    // Get page dimensions in original PDF space (scale 1)
    const originalViewport = page.getViewport({ scale: 1, rotation: 0 });
    const pageWidth = originalViewport.width;
    const pageHeight = originalViewport.height;
    
    // Convert normalized (0-1) coordinates to PDF space
    const pdfX = normalizedCoords.x * pageWidth;
    const pdfY = (1 - normalizedCoords.y - normalizedCoords.height) * pageHeight; // PDF coords start from bottom
    const pdfWidth = normalizedCoords.width * pageWidth;
    const pdfHeight = normalizedCoords.height * pageHeight;
    
    // Get current viewport with proper scale/rotation
    const viewport = this.calculateViewport(page);
    
    // Convert PDF space to viewport space
    const [vx1, vy1] = viewport.convertToViewportPoint(pdfX, pdfY);
    const [vx2, vy2] = viewport.convertToViewportPoint(pdfX + pdfWidth, pdfY + pdfHeight);
    
    // Return in format expected by annotation system
    return {
      x: Math.min(vx1, vx2),
      y: Math.min(vy1, vy2),
      width: Math.abs(vx2 - vx1),
      height: Math.abs(vy2 - vy1)
    };
  }

  /**
   * Convert viewport coordinates to normalized coordinates (0-1).
   * Bridge method for the annotation system to store annotations in a format independent of scale/rotation.
   * @param {Object} viewportCoords - Coordinates in viewport space
   * @param {Object} page - PDF.js page object
   * @returns {Object} Coordinates in normalized space (0-1)
   */
  pdfViewportToNormalized(viewportCoords, page) {
    if (!page) return viewportCoords;
    
    // Get current viewport with proper scale/rotation
    const viewport = this.calculateViewport(page);
    
    // Convert viewport coordinates to PDF space
    const [pdfX, pdfY] = viewport.convertToPdfPoint(viewportCoords.x, viewportCoords.y);
    const [pdfX2, pdfY2] = viewport.convertToPdfPoint(
      viewportCoords.x + viewportCoords.width, 
      viewportCoords.y + viewportCoords.height
    );
    
    // Get page dimensions in original PDF space (scale 1)
    const originalViewport = page.getViewport({ scale: 1, rotation: 0 });
    const pageWidth = originalViewport.width;
    const pageHeight = originalViewport.height;
    
    // Calculate PDF dimensions
    const pdfWidth = Math.abs(pdfX2 - pdfX);
    const pdfHeight = Math.abs(pdfY2 - pdfY);
    
    // Convert to normalized (0-1) coordinates
    // For y-axis, need to flip from PDF bottom-origin to normalized top-origin
    return {
      x: Math.min(pdfX, pdfX2) / pageWidth,
      y: 1 - (Math.max(pdfY, pdfY2) / pageHeight), // Convert from bottom-left to top-left origin
      width: pdfWidth / pageWidth,
      height: pdfHeight / pageHeight
    };
  }
}

// Expose globally for legacy compatibility
window.PDFViewport = PDFViewport;
