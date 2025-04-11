// pdf-document.js
import { PDFCore } from './pdf-core.js';

/**
 * Manages PDF document loading, page access, and metadata retrieval.
 */
export class PDFDocument {
  constructor(pdfCore) {
    this.core = pdfCore instanceof PDFCore ? pdfCore : new PDFCore();
    this.pdfDocument = null;
    this.pageCache = new Map();
  }

  /**
   * Load the PDF document.
   * @param {string|ArrayBuffer} source
   */
  async load(source) {
    this.pdfDocument = await this.core.loadDocument(source);
    this.numPages = this.pdfDocument.numPages;
    return this;
  }

  /**
   * Get a PDF page by number, cached.
   * @param {number} pageNum - 1-based page number.
   */
  async getPage(pageNum) {
    if (this.pageCache.has(pageNum)) {
      return this.pageCache.get(pageNum);
    }
    const page = await this.core.getPage(this.pdfDocument, pageNum);
    this.pageCache.set(pageNum, page);
    return page;
  }

  /**
   * Fetch metadata from the document.
   */
  async getMetadata() {
    const meta = await this.pdfDocument.getMetadata();
    return {
      title: meta.info?.Title || '',
      author: meta.info?.Author || '',
      creator: meta.info?.Creator || '',
      producer: meta.info?.Producer || '',
      creationDate: meta.info?.CreationDate || '',
      modificationDate: meta.info?.ModDate || ''
    };
  }

  /**
   * Cleanup document resources.
   */
  destroy() {
    this.pageCache.clear();
    if (this.pdfDocument) {
      this.pdfDocument.destroy();
      this.pdfDocument = null;
    }
  }
}

window.PDFDocument = PDFDocument;
