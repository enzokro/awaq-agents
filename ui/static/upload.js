// Get references to elements
const dropzone = me();
const fileInput = me('#file-input');
const progressBar = me('#upload-progress');
const progressContainer = me('#progress-container');
const statusText = me('#upload-status');

// Add this at the top of your upload.js to help with debugging
document.addEventListener('htmx:beforeRequest', function(event) {
    console.log("HTMX request starting:", event.detail);
});

document.addEventListener('htmx:afterRequest', function(event) {
    console.log("HTMX request completed:", event.detail);
});

document.addEventListener('htmx:responseError', function(event) {
    console.error("HTMX request error:", event.detail);
});

// Helper function to get auth data from cookies or local storage
function getAuthData() {
    // Try to get auth from cookie
    const cookies = document.cookie.split(';').map(c => c.trim());
    for (const cookie of cookies) {
        if (cookie.startsWith('auth=')) {
            return cookie.substring(5);
        }
    }
    
    // Try local storage as fallback
    return localStorage.getItem('auth') || sessionStorage.getItem('auth');
}

// Handle click on dropzone
dropzone.on('click', (ev) => {
    if (ev.target.id !== 'file-input') {
        fileInput.click();
    }
});

// Handle file selection from input
fileInput.on('change', (ev) => {
    if (ev.target.files.length > 0) {
        uploadFiles(ev.target.files);
    }
});

// Handle drag events
dropzone.on('dragover', (ev) => { 
    halt(ev); 
    dropzone.classAdd('border-primary');
    dropzone.classAdd('bg-primary/10'); 
});

dropzone.on('dragleave', (ev) => { 
    halt(ev); 
    dropzone.classRemove('border-primary');
    dropzone.classRemove('bg-primary/10'); 
});

dropzone.on('drop', (ev) => { 
    halt(ev); 
    dropzone.classRemove('border-primary');
    dropzone.classRemove('bg-primary/10');
    if (ev.dataTransfer.files.length > 0) {
        uploadFiles(ev.dataTransfer.files);
    }
});

// Validate file types
function validateFileType(file) {
    const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf'];
    return validTypes.includes(file.type) || file.name.toLowerCase().endsWith('.pdf');
}

// Handle file upload
function uploadFiles(files) {
    if (files.length === 0) return;
    
    // Filter for valid file types
    const validFiles = Array.from(files).filter(validateFileType);
    
    // Show progress container and update status
    progressContainer.classRemove('hidden');
    progressBar.value = 0;
    statusText.textContent = `Uploading ${validFiles.length} file(s)...`;
    
    // Create FormData and append files
    const formData = new FormData();
    for (let i = 0; i < validFiles.length; i++) {
        formData.append('file', validFiles[i]);
    }
    
    // Create XMLHttpRequest to track progress
    const xhr = new XMLHttpRequest();
    
    // Track upload progress
    xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
            const percentComplete = (event.loaded / event.total) * 100;
            progressBar.value = percentComplete;
            statusText.textContent = `Uploading ${validFiles.length} file(s)... ${Math.round(percentComplete)}%`;
        }
    });
    
    // Handle upload completion
    xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
            // Success
            statusText.textContent = 'Upload complete! Processing document, please wait...';

            // Keep progress bar visible but change to indeterminate style
            progressBar.removeAttribute('value'); // Makes it indeterminate

            // Always reset file input
            fileInput.value = '';
            fileInput.classAdd('hidden');
            
            // // Use htmx.trigger for reliable event firing
            // console.log("Triggering HTMX event 'fileUploaded'");
            // htmx.trigger(document.body, 'fileUploaded');
            
            // // Debug: Let's log what elements would respond to this event
            // console.log("Elements listening for fileUploaded:", 
            //             document.querySelectorAll('[hx-trigger*="fileUploaded"]'));

            // Wait for any existing HTMX requests to complete
            setTimeout(function() {
                // Check if the file list element still has the htmx-request class
                const fileList = document.getElementById('file-list');
                if (fileList.classList.contains('htmx-request')) {
                    console.log("Element still processing another request, waiting...");
                    // Wait a bit longer before trying again
                    setTimeout(function() {
                        console.log("Triggering fileUploaded after waiting");
                        htmx.trigger(document.body, 'fileUploaded');
                    }, 500);
                } else {
                    console.log("Triggering fileUploaded");
                    htmx.trigger(document.body, 'fileUploaded');
                }
            }, 100);
            

        } else {
            // Error
            statusText.textContent = 'Upload failed';
            
            // Hide progress after a delay
            setTimeout(() => {
                progressContainer.classAdd('hidden');
                
                // Always reset and ensure file input is hidden
                fileInput.value = '';
                fileInput.classAdd('hidden');
                
            }, 1000);
        }
    });

    // // Reset text after upload with loadend events
    // xhr.addEventListener('loadend', () => {
    //     statusText.textContent = 'File uploaded! Ready to upload another.';
    // });
    
    // Handle errors
    xhr.addEventListener('error', () => {
        statusText.textContent = 'Upload failed';
        
        // Hide progress after a delay
        setTimeout(() => {
            progressContainer.classAdd('hidden');
            
            // Always reset and ensure file input is hidden
            fileInput.value = '';
            fileInput.classAdd('hidden');
            
        }, 1000);
    });
    
    // Send the request - use a URL with no trailing slash
    xhr.open('POST', '/files/upload');
    
    // Add authentication header if needed
    if (dropzone.dataset.includeAuth === "true") {
        const authToken = getAuthData();
        if (authToken) {
            xhr.setRequestHeader('X-Auth', authToken);
        }
    }
    
    xhr.send(formData);
}