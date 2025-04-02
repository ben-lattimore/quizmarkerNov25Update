document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const uploadForm = document.getElementById('uploadForm');
    const dropArea = document.getElementById('dropArea');
    const fileInput = document.getElementById('fileInput');
    const browseButton = document.getElementById('browseButton');
    const filePreviewList = document.getElementById('filePreviewList');
    const fileList = document.getElementById('fileList');
    const processButton = document.getElementById('processButton');
    const processingCard = document.getElementById('processingCard');
    const progressBar = document.getElementById('progressBar');
    const statusMessage = document.getElementById('statusMessage');
    const resultsCard = document.getElementById('resultsCard');
    const resultsPreview = document.getElementById('resultsPreview');
    const jsonOutput = document.getElementById('jsonOutput');
    const downloadJsonBtn = document.getElementById('downloadJsonBtn');
    const newUploadBtn = document.getElementById('newUploadBtn');
    const errorModal = new bootstrap.Modal(document.getElementById('errorModal'));
    const errorModalBody = document.getElementById('errorModalBody');

    // Store the processed results
    let processedResults = null;

    // Add event listeners for drag and drop functionality
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });

    function highlight() {
        dropArea.classList.add('dragover');
    }

    function unhighlight() {
        dropArea.classList.remove('dragover');
    }

    // Handle file drops
    dropArea.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    // Open file dialog when browse button is clicked
    browseButton.addEventListener('click', () => {
        fileInput.click();
    });

    // Handle file selection from the file input
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    // Process files when selected
    function handleFiles(files) {
        if (files.length === 0) return;

        // Clear the previous file list
        filePreviewList.innerHTML = '';
        
        // Display file list area
        fileList.classList.remove('d-none');
        
        // Validate and preview files
        let validFiles = 0;
        const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
        const maxSize = 16 * 1024 * 1024; // 16MB
        
        Array.from(files).forEach(file => {
            const fileItem = document.createElement('li');
            fileItem.className = 'list-group-item d-flex justify-content-between align-items-center';
            
            // Validate file type
            if (!allowedTypes.includes(file.type)) {
                fileItem.innerHTML = `
                    <div class="file-preview-item">
                        <i class="fas fa-exclamation-triangle text-warning file-icon"></i>
                        <span class="file-name">${file.name}</span>
                        <span class="badge bg-warning text-dark">Invalid file type</span>
                    </div>
                `;
            } 
            // Validate file size
            else if (file.size > maxSize) {
                fileItem.innerHTML = `
                    <div class="file-preview-item">
                        <i class="fas fa-exclamation-triangle text-warning file-icon"></i>
                        <span class="file-name">${file.name}</span>
                        <span class="badge bg-warning text-dark">File too large (max 16MB)</span>
                    </div>
                `;
            } 
            // Valid file
            else {
                validFiles++;
                fileItem.innerHTML = `
                    <div class="file-preview-item">
                        <i class="fas fa-image text-primary file-icon"></i>
                        <span class="file-name">${file.name}</span>
                        <span class="badge bg-secondary">${formatFileSize(file.size)}</span>
                    </div>
                `;
            }
            
            filePreviewList.appendChild(fileItem);
        });
        
        // Enable/disable process button based on valid files
        if (validFiles > 0) {
            processButton.disabled = false;
        } else {
            processButton.disabled = true;
        }
    }

    // Helper to format file size
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        else return (bytes / 1048576).toFixed(1) + ' MB';
    }

    // Form submission
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        const files = fileInput.files;
        
        if (files.length === 0) {
            showError('Please select at least one image file');
            return;
        }
        
        // Show processing card and hide upload form
        processingCard.classList.remove('d-none');
        progressBar.style.width = '10%';
        statusMessage.textContent = 'Uploading images...';
        
        try {
            // Upload files
            progressBar.style.width = '25%';
            
            // Update status with file count info
            const fileCountMessage = files.length === 1 
                ? 'Processing 1 image with GPT-4o...'
                : `Processing ${files.length} images with GPT-4o...`;
            statusMessage.textContent = fileCountMessage;
            
            // Use more robust error handling with better timeout management
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 60000); // 60-second timeout
            
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
                signal: controller.signal
            }).finally(() => {
                clearTimeout(timeoutId);
            });
            
            progressBar.style.width = '75%';
            
            // Handle different types of errors
            if (!response.ok) {
                let errorMessage = 'Failed to process images';
                
                try {
                    // Attempt to parse error response as JSON
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorMessage;
                } catch (parseError) {
                    // If response is not valid JSON, use status text
                    errorMessage = `Server error (${response.status}): ${response.statusText}`;
                }
                
                throw new Error(errorMessage);
            }
            
            // Safely parse the JSON response with error handling
            let data;
            try {
                data = await response.json();
            } catch (jsonError) {
                throw new Error('Invalid response format from server');
            }
            
            // Validate data structure
            if (!data || !data.results || !Array.isArray(data.results)) {
                throw new Error('Server returned an invalid response format');
            }
            
            // Handle successful processing
            progressBar.style.width = '100%';
            statusMessage.textContent = 'Processing complete!';
            
            // Check if there were any invalid files
            if (data.invalid_files && data.invalid_files.length > 0) {
                console.warn('Some files were invalid:', data.invalid_files);
            }
            
            // Store results and display them
            processedResults = data.results;
            displayResults(processedResults);
            
            // Show results card and hide processing after short delay
            setTimeout(() => {
                processingCard.classList.add('d-none');
                resultsCard.classList.remove('d-none');
            }, 500);
            
        } catch (error) {
            console.error('Error:', error);
            progressBar.className = 'progress-bar bg-danger';
            
            // Provide more helpful error messages based on error type
            let errorMessage = error.message;
            
            // Check for specific error conditions
            if (error.name === 'AbortError') {
                errorMessage = 'Request timed out. The server took too long to respond.';
            } else if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
                errorMessage = 'Network error. Please check your connection and try again.';
            }
            
            statusMessage.textContent = 'Error: ' + errorMessage;
            
            // Show error modal
            showError(errorMessage);
            
            // Reset UI after delay
            setTimeout(() => {
                processingCard.classList.add('d-none');
                progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated';
            }, 1000);
        }
    });

    // Display results in the preview area
    function displayResults(results) {
        if (!results || results.length === 0) {
            resultsPreview.innerHTML = '<div class="alert alert-info">No results to display</div>';
            jsonOutput.textContent = '{}';
            return;
        }
        
        // Format the JSON output
        const formattedJson = JSON.stringify(results, null, 2);
        jsonOutput.textContent = formattedJson;
        
        // Clear previous results
        resultsPreview.innerHTML = '';
        
        // Show summary of results
        const successCount = results.filter(r => !r.error).length;
        const errorCount = results.filter(r => r.error).length;
        
        if (results.length > 1) {
            const summaryDiv = document.createElement('div');
            summaryDiv.className = 'alert alert-info mb-4';
            summaryDiv.innerHTML = `
                <h5 class="alert-heading"><i class="fas fa-info-circle me-2"></i>Processing Summary</h5>
                <p>Processed ${results.length} image${results.length !== 1 ? 's' : ''}</p>
                <ul class="mb-0">
                    <li>Successfully extracted: ${successCount} image${successCount !== 1 ? 's' : ''}</li>
                    ${errorCount > 0 ? `<li>Failed to process: ${errorCount} image${errorCount !== 1 ? 's' : ''}</li>` : ''}
                </ul>
            `;
            resultsPreview.appendChild(summaryDiv);
        }
        
        // Create preview cards for each result
        results.forEach(result => {
            const resultCard = document.createElement('div');
            resultCard.className = 'card result-card mb-4';
            
            // Ensure we have basic fields to prevent errors
            const filename = result.filename || 'Unknown file';
            const imageId = result.image_id || '?';
            
            // Check if there was an error with this image
            if (result.error) {
                resultCard.innerHTML = `
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h6 class="mb-0"><i class="fas fa-exclamation-circle text-danger me-2"></i>Image: ${filename}</h6>
                        <span class="badge bg-danger">ID: ${imageId}</span>
                    </div>
                    <div class="card-body">
                        <div class="alert alert-danger mb-0">
                            <strong>Processing Error:</strong> ${result.error}
                        </div>
                    </div>
                `;
            } else {
                // Success case - show structured extracted text
                // Safety check for data property
                if (!result.data || typeof result.data !== 'object') {
                    // Handle malformed result data
                    resultCard.innerHTML = `
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h6 class="mb-0"><i class="fas fa-exclamation-triangle text-warning me-2"></i>Image: ${filename}</h6>
                            <span class="badge bg-warning text-dark">ID: ${imageId}</span>
                        </div>
                        <div class="card-body">
                            <div class="alert alert-warning mb-0">
                                The extracted data format is invalid or empty
                            </div>
                        </div>
                    `;
                } else {
                    // Get the data object safely
                    const data = result.data;
                    
                    // Helper function to render a content section if it exists
                    const renderSection = (title, content, icon, cssClass = '') => {
                        // Ensure content exists and is not undefined or null
                        if (!content || String(content).trim() === '') return '';
                        
                        // Safely display content, escaping HTML if needed
                        const safeContent = String(content)
                            .replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;')
                            .replace(/\n/g, '<br>');
                        
                        return `
                            <div class="mb-3 ${cssClass}">
                                <h6><i class="fas ${icon} me-2"></i>${title}:</h6>
                                <div class="p-2 border rounded bg-dark">
                                    ${safeContent}
                                </div>
                            </div>
                        `;
                    };
                    
                    // Format the content sections
                    resultCard.innerHTML = `
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h6 class="mb-0"><i class="fas fa-file-image me-2"></i>Image: ${filename}</h6>
                            <span class="badge bg-success">ID: ${imageId}</span>
                        </div>
                        <div class="card-body">
                            ${renderSection('Document Type', data.document_type, 'fa-file-alt')}
                            ${renderSection('Title', data.title, 'fa-heading', 'text-primary')}
                            ${renderSection('Subtitle', data.subtitle, 'fa-heading fs-sm')}
                            ${renderSection('Main Instructions', data.main_instructions, 'fa-info-circle')}
                            ${renderSection('Handwritten Content', data.handwritten_content, 'fa-pen', 'text-info')}
                            ${renderSection('Printed Content', data.printed_content, 'fa-print')}
                            ${renderSection('Reference Information', data.reference_info, 'fa-bookmark')}
                            ${renderSection('Other Elements', data.other_elements, 'fa-layer-group')}
                        </div>
                    `;
                }
            }
            
            resultsPreview.appendChild(resultCard);
        });
    }

    // Download JSON results
    downloadJsonBtn.addEventListener('click', function() {
        if (!processedResults) {
            showError('No data available to download');
            return;
        }
        
        const dataStr = JSON.stringify(processedResults, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
        
        const exportFileName = `image-extraction-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
        
        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileName);
        linkElement.click();
    });

    // New upload button - reset UI
    newUploadBtn.addEventListener('click', function() {
        // Reset form and UI
        uploadForm.reset();
        filePreviewList.innerHTML = '';
        fileList.classList.add('d-none');
        processButton.disabled = true;
        resultsCard.classList.add('d-none');
        processedResults = null;
    });

    // Helper to show errors
    function showError(message) {
        errorModalBody.textContent = message;
        errorModal.show();
    }
});
