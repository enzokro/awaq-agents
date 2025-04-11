// pdf-core.js
export class PDFCore {
  constructor({workerSrc = '/static/pdfjs/build/pdf.worker.js'} = {}) {
    this.pdfjsLib = window.pdfjsLib;
    this.pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc;
  }

  async loadDocument(source) {
    const loadingTask = this.pdfjsLib.getDocument(source);
    const pdfDocument = await loadingTask.promise;
    return pdfDocument;
  }

  async getPage(pdfDocument, pageNum) {
    return pdfDocument.getPage(pageNum);
  }
}

window.PDFCore = PDFCore;
