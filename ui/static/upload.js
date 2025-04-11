// Get references to elements
const dropzone = me();
const fileInput = me('#file-input');
const progressBar = me('#upload-progress');
const progressContainer = me('#progress-container');
const statusText = me('#upload-status');

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
            statusText.textContent = 'Upload complete!';
            
            // Hide progress after a delay
            setTimeout(() => {
                progressContainer.classAdd('hidden');
                progressBar.value = 0;
                
                // Always reset and ensure file input is hidden
                fileInput.value = '';
                fileInput.classAdd('hidden');
                
                // Trigger the uploaded event to refresh file list
                // This uses the HTMX attributes we set in the HTML
                dropzone.send('uploaded');
                
            }, 1000);
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