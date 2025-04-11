/**
 * PDF.js ESM Bridge
 * 
 * This script bridges the gap between ESM modules and global scope.
 * It ensures that PDF.js library is available globally for non-module scripts.
 */

console.log('🔄 Setting up PDF.js bridge...');

// Define the version we expect
const EXPECTED_PDFJS_VERSION = '3.4.120';

// Some PDF.js versions expose the library differently
function findPDFJS() {
    // Check common places where PDF.js might expose itself
    if (typeof window.pdfjsLib === 'object') {
        console.log('✅ Found PDF.js in window.pdfjsLib');
        return window.pdfjsLib;
    }
    
    // For newer versions that use ES modules
    if (typeof globalThis.pdfjsLib === 'object') {
        console.log('✅ Found PDF.js in globalThis.pdfjsLib');
        return globalThis.pdfjsLib;
    }
    
    // Another common pattern in newer versions
    if (typeof window['pdfjs-dist/build/pdf'] === 'object') {
        console.log('✅ Found PDF.js in window["pdfjs-dist/build/pdf"]');
        return window['pdfjs-dist/build/pdf'];
    }
    
    // Check for pdf object directly
    if (typeof window.pdf === 'object') {
        console.log('✅ Found PDF.js in window.pdf');
        return window.pdf;
    }
    
    return null;
}

// For directly injecting the library
function injectPDFJS() {
    console.log('🔧 Attempting to inject PDF.js manually...');
    
    // Create script element
    const script = document.createElement('script');
    script.src = '/static/pdfjs/build/pdf.js';
    
    // Force synchronous loading
    script.async = false;
    
    // Add to document
    document.head.appendChild(script);
    
    // Add load event to know when it's done
    script.onload = function() {
        console.log('✅ PDF.js main script loaded');
        
        // Also add worker
        const workerScript = document.createElement('script');
        workerScript.src = '/static/pdfjs/build/pdf.worker.js';
        workerScript.async = false;
        document.head.appendChild(workerScript);
        
        workerScript.onload = function() {
            console.log('✅ PDF.js worker script loaded');
            // Try to expose the library again now that scripts are loaded
            exposeLibrary();
        };
    };
    
    console.log('📜 Manual script injection initiated');
}

// Wait for PDF.js to load and expose it globally
function exposeLibrary() {
    const pdfLib = findPDFJS();
    
    if (pdfLib) {
        // Make it available globally
        window.pdfjsLib = pdfLib;
        
        // Log version if available
        if (pdfLib.version) {
            console.log(`📄 PDF.js version: ${pdfLib.version}`);
            if (pdfLib.version !== EXPECTED_PDFJS_VERSION) {
                console.warn(`⚠️ Warning: Found PDF.js version ${pdfLib.version}, but expected ${EXPECTED_PDFJS_VERSION}`);
            }
        }
        
        // Make sure worker is set
        try {
            if (!pdfLib.GlobalWorkerOptions || !pdfLib.GlobalWorkerOptions.workerSrc) {
                console.log('🔧 Setting worker source...');
                pdfLib.GlobalWorkerOptions = pdfLib.GlobalWorkerOptions || {};
                pdfLib.GlobalWorkerOptions.workerSrc = '/static/pdfjs/build/pdf.worker.js';
            }
            console.log('✅ Worker source configured as:', pdfLib.GlobalWorkerOptions.workerSrc);
        } catch (e) {
            console.error('❌ Error setting worker source:', e);
        }
        
        // Verify we can actually use the library
        try {
            if (typeof pdfLib.getDocument === 'function') {
                console.log('✅ PDF.js getDocument function verified');
            } else {
                console.warn('⚠️ PDF.js getDocument function not found - may not be fully initialized');
            }
        } catch (e) {
            console.error('❌ Error verifying PDF.js functionality:', e);
        }
        
        return true;
    }
    
    return false;
}

// Main initialization function
function initPDFJSBridge() {
    console.log('🔄 Initializing PDF.js bridge...');
    
    // Try to find and expose the library
    if (exposeLibrary()) {
        console.log('✅ PDF.js bridge initialized successfully');
        // Dispatch an event to notify other components that PDF.js is ready
        try {
            document.dispatchEvent(new CustomEvent('pdfjs-ready', { 
                detail: { timestamp: Date.now() } 
            }));
            console.log('📢 Dispatched pdfjs-ready event');
        } catch (e) {
            console.error('❌ Error dispatching pdfjs-ready event:', e);
        }
        return;
    }
    
    // Look for script tags
    const scripts = document.querySelectorAll('script');
    let pdfJsFound = false;
    
    for (const script of scripts) {
        if (script.src && (script.src.includes('pdf.js') || script.src.includes('pdfjs'))) {
            pdfJsFound = true;
            console.log('🔍 Found PDF.js script:', script.src);
            break;
        }
    }
    
    if (!pdfJsFound) {
        console.warn('⚠️ PDF.js script not found in document');
        // Try injection as fallback
        injectPDFJS();
    } else {
        console.log('🔍 PDF.js script found, waiting for it to initialize...');
    }
    
    // Schedule retry with increasing backoff
    window.pdfJsBridgeRetries = (window.pdfJsBridgeRetries || 0) + 1;
    const retryDelay = Math.min(100 * window.pdfJsBridgeRetries, 1000); // Cap at 1 second
    
    setTimeout(function() {
        if (!window.pdfjsLib) {
            console.log(`🔄 PDF.js not found yet, retrying... (attempt ${window.pdfJsBridgeRetries})`);
            initPDFJSBridge();
        }
    }, retryDelay);
}

// Start the bridge initialization process
initPDFJSBridge();
