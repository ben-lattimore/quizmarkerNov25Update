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
    const gradeAnswersBtn = document.getElementById('gradeAnswersBtn');
    const standardSelector = document.getElementById('standardSelector');
    const gradesContent = document.getElementById('gradesContent');
    const gradesTab = document.getElementById('grades-tab');
    const errorModal = new bootstrap.Modal(document.getElementById('errorModal'));
    const errorModalBody = document.getElementById('errorModalBody');
    const gradingModal = new bootstrap.Modal(document.getElementById('gradingModal'));
    const gradingModalBody = document.getElementById('gradingModalBody');

    // Store the processed results and grading results
    let processedResults = null;
    let gradingResults = null;
    let availableStandards = [];

    // Load available standards when the page loads
    async function loadStandards() {
        try {
            const response = await fetch('/standards');
            if (!response.ok) {
                console.error('Failed to load standards');
                return;
            }
            
            const data = await response.json();
            if (data.success && Array.isArray(data.standards)) {
                availableStandards = data.standards;
                
                // Clear and populate the standards dropdown
                standardSelector.innerHTML = '';
                
                // Add a default instruction option
                const defaultOption = document.createElement('option');
                defaultOption.value = '';
                defaultOption.textContent = 'Select a standard...';
                defaultOption.disabled = true;
                defaultOption.selected = true;
                standardSelector.appendChild(defaultOption);
                
                // Add each standard as an option
                availableStandards.forEach(standard => {
                    const option = document.createElement('option');
                    option.value = standard.id;
                    option.textContent = `Standard ${standard.id}`;
                    standardSelector.appendChild(option);
                });
                
                // If we have standards, enable the dropdown
                if (availableStandards.length > 0) {
                    standardSelector.disabled = false;
                }
            }
        } catch (error) {
            console.error('Error loading standards:', error);
        }
    }
    
    // Load standards when page loads
    loadStandards();

    // Add event listeners for drag and drop functionality
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Highlight drop area when dragging over it
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });

    function highlight() {
        dropArea.classList.add('highlight');
    }

    function unhighlight() {
        dropArea.classList.remove('highlight');
    }

    // Handle dropped files
    dropArea.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    // Handle browse button and file input
    browseButton.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });

    function handleFiles(files) {
        if (files.length === 0) return;

        // Show file list
        fileList.classList.remove('d-none');
        filePreviewList.innerHTML = '';

        // Count valid files
        let validFiles = 0;

        // Process each file
        Array.from(files).forEach(file => {
            const fileItem = document.createElement('li');
            fileItem.className = 'list-group-item d-flex align-items-center justify-content-between';

            // Check file type
            const isValidType = file.type.startsWith('image/');
            // Check file size (max 16MB)
            const isValidSize = file.size <= 16 * 1024 * 1024;

            // Invalid file type
            if (!isValidType) {
                fileItem.innerHTML = `
                    <div class="file-preview-item">
                        <i class="fas fa-exclamation-triangle text-warning file-icon"></i>
                        <span class="file-name">${file.name}</span>
                        <span class="badge bg-warning text-dark">Not an image file</span>
                    </div>
                `;
            } 
            // File too large
            else if (!isValidSize) {
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

    // Form submission - now processes each image individually to avoid timeouts
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const files = fileInput.files;
        
        if (files.length === 0) {
            showError('Please select at least one image file');
            return;
        }
        
        // Additional info for multiple files
        if (files.length > 1) {
            // Add info about sequential processing approach
            const infoElem = document.createElement('div');
            infoElem.id = 'multipleFilesInfo';
            infoElem.className = 'alert alert-info mb-3';
            infoElem.innerHTML = `
                <h5 class="alert-heading"><i class="fas fa-info-circle me-2"></i>Processing Multiple Images</h5>
                <p>You've selected ${files.length} images. To prevent API timeouts, each image will be processed one at a time.</p>
                <ul>
                    <li>Each image will be uploaded and processed individually</li>
                    <li>Results will appear as they're completed</li>
                    <li>Processing all images may take 1-2 minutes</li>
                </ul>
            `;
            
            // Remove previous info if exists
            const oldInfo = document.getElementById('multipleFilesInfo');
            if (oldInfo) oldInfo.remove();
            
            // Add the info before the processing card
            processingCard.parentNode.insertBefore(infoElem, processingCard);
        }
        
        // Show processing card and hide upload form
        processingCard.classList.remove('d-none');
        progressBar.style.width = '10%';
        statusMessage.textContent = 'Starting image processing...';
        
        try {
            // Initialize results array for collecting all processed images
            processedResults = [];
            
            // Success/failure counters
            let successCount = 0;
            let failCount = 0;
            
            // Process files one by one instead of all at once
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                
                // Skip invalid files
                if (!file || !file.name || !file.type.startsWith('image/')) {
                    failCount++;
                    continue;
                }
                
                // Update progress percentage based on how many files we've processed
                const progressPct = ((i / files.length) * 90) + 10; // 10-100%
                progressBar.style.width = `${progressPct}%`;
                
                // Update status message with current file
                statusMessage.textContent = `Processing image ${i+1}/${files.length}: ${file.name}`;
                
                try {
                    // Create a form with just this single file
                    const singleFileForm = new FormData();
                    singleFileForm.append('files[]', file);
                    
                    // Set a reasonable timeout for a single image (60 seconds)
                    const controller = new AbortController();
                    const timeoutMs = 60000;
                    
                    const timeoutId = setTimeout(() => {
                        controller.abort();
                        console.warn(`Request for ${file.name} aborted after ${timeoutMs/1000} seconds timeout`);
                    }, timeoutMs);
                    
                    // Process just this one image
                    const response = await fetch('/upload', {
                        method: 'POST',
                        body: singleFileForm,
                        signal: controller.signal
                    }).finally(() => {
                        clearTimeout(timeoutId);
                    });
                    
                    // Handle errors for this specific file
                    if (!response.ok) {
                        let errorMessage = `Failed to process image: ${file.name}`;
                        
                        try {
                            const errorData = await response.json();
                            errorMessage = errorData.error || errorMessage;
                        } catch (e) {
                            // If not JSON, use status text
                            errorMessage = `Server error (${response.status}): ${response.statusText}`;
                        }
                        
                        // Add error result for this file
                        processedResults.push({
                            image_id: i + 1,
                            filename: file.name,
                            error: errorMessage
                        });
                        
                        failCount++;
                        console.error(`Error processing ${file.name}:`, errorMessage);
                        continue; // Skip to next file
                    }
                    
                    // Parse the response
                    const data = await response.json();
                    
                    // Get the results array from the response
                    if (data && data.results && Array.isArray(data.results) && data.results.length > 0) {
                        // Add this file's result to our collection
                        const result = data.results[0]; // There should be only one result since we sent one file
                        
                        // Make sure the filename is correct (in case the server changed it)
                        result.filename = file.name;
                        result.image_id = i + 1;
                        
                        processedResults.push(result);
                        successCount++;
                        
                        // Show the current results as they come in
                        displayResults(processedResults);
                        
                        // Show results card so user can see progress
                        resultsCard.classList.remove('d-none');
                    } else {
                        // Handle invalid response format
                        processedResults.push({
                            image_id: i + 1,
                            filename: file.name,
                            error: 'Invalid response from server'
                        });
                        failCount++;
                    }
                } catch (error) {
                    // Handle any other errors for this file
                    console.error(`Error processing ${file.name}:`, error);
                    
                    processedResults.push({
                        image_id: i + 1,
                        filename: file.name,
                        error: error.message || 'Failed to process image'
                    });
                    
                    failCount++;
                }
                
                // Short delay between processing each file to avoid API rate limiting
                if (i < files.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }
            
            // All files processed
            progressBar.style.width = '100%';
            statusMessage.textContent = `Processing complete! Success: ${successCount}, Failed: ${failCount}`;
            
            // Display final results
            displayResults(processedResults);
        } catch (error) {
            console.error('Error in overall processing:', error);
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
        gradingResults = null;
        
        // Reset the grades tab
        gradesContent.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle me-2"></i>Click the "Mark these answers" button to grade handwritten answers against the reference material.
            </div>
        `;
    });
    
    // Mark these answers button
    gradeAnswersBtn.addEventListener('click', async function() {
        // Check if we have results to grade
        if (!processedResults || processedResults.length === 0) {
            showError('No results available to grade. Please process images first.');
            return;
        }
        
        // Filter valid entries (those without errors)
        const validResults = processedResults.filter(r => !r.error);
        
        if (validResults.length === 0) {
            showError('No valid results to grade. All images had processing errors.');
            return;
        }
        
        // Check if a standard is selected
        const selectedStandardId = standardSelector.value;
        if (!selectedStandardId) {
            showError('Please select a standard to grade against.');
            return;
        }
        
        try {
            // Show the grading modal with the selected standard
            gradingModalBody.innerHTML = `
                <div class="text-center p-4">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-3">Grading answers against Standard ${selectedStandardId}...</p>
                    <p class="small text-muted">This may take 30-60 seconds</p>
                </div>
            `;
            gradingModal.show();
            
            // Call the grading API with the selected standard
            const response = await fetch('/grade', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    data: validResults,
                    standard_id: parseInt(selectedStandardId)
                })
            });
            
            // Check for errors
            if (!response.ok) {
                let errorMessage = 'Failed to grade answers';
                
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorMessage;
                } catch (e) {
                    errorMessage = `Server error (${response.status}): ${response.statusText}`;
                }
                
                gradingModalBody.innerHTML = `
                    <div class="alert alert-danger">
                        <h5 class="alert-heading">Error</h5>
                        <p>${errorMessage}</p>
                    </div>
                `;
                return;
            }
            
            // Parse the response
            const gradeData = await response.json();
            
            if (!gradeData.success || !gradeData.results) {
                gradingModalBody.innerHTML = `
                    <div class="alert alert-danger">
                        <h5 class="alert-heading">Error</h5>
                        <p>Invalid response format from server</p>
                    </div>
                `;
                return;
            }
            
            // Store the grading results
            gradingResults = gradeData.results;
            
            // Display the results in the modal
            displayGradingResults(gradingResults);
            
            // Also update the grades tab
            updateGradesTab(gradingResults);
            
            // Show the grades tab
            const gradesTabEl = new bootstrap.Tab(gradesTab);
            gradesTabEl.show();
            
        } catch (error) {
            console.error('Error during grading:', error);
            
            gradingModalBody.innerHTML = `
                <div class="alert alert-danger">
                    <h5 class="alert-heading">Error</h5>
                    <p>An error occurred during grading: ${error.message || 'Unknown error'}</p>
                </div>
            `;
        }
    });
    
    // Display grading results in the modal
    function displayGradingResults(results) {
        // Create a summary of the grading results
        let html = `
            <div class="mb-4">
                <h5><i class="fas fa-check-circle text-success me-2"></i>Grading Complete</h5>
                <p>The handwritten answers have been graded against the reference material.</p>
            </div>
        `;
        
        // If the results have images property, display them one by one
        if (results.images && Array.isArray(results.images)) {
            results.images.forEach(image => {
                const score = image.score || '?';
                const scoreClass = score >= 7 ? 'success' : (score >= 5 ? 'warning' : 'danger');
                
                html += `
                    <div class="card mb-3">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h6 class="mb-0">${image.filename || 'Image'}</h6>
                            <span class="badge bg-${scoreClass}">Score: ${score}/10</span>
                        </div>
                        <div class="card-body">
                            <div class="mb-2">
                                <strong>Handwritten Content:</strong>
                                <div class="p-2 border rounded mb-3 bg-dark">
                                    ${image.handwritten_content || 'No handwritten content found'}
                                </div>
                            </div>
                            <div>
                                <strong>Feedback:</strong>
                                <div class="p-2 border rounded bg-dark">
                                    ${image.feedback || 'No feedback provided'}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });
        } else {
            // Display overall results if not using the images structure
            html += `
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0">Grading Results</h6>
                    </div>
                    <div class="card-body">
                        <pre class="bg-dark text-light p-3 rounded">${JSON.stringify(results, null, 2)}</pre>
                    </div>
                </div>
            `;
        }
        
        // Update the modal content
        gradingModalBody.innerHTML = html;
    }
    
    // Update the grades tab with the grading results
    function updateGradesTab(results) {
        const selectedStandardId = standardSelector.value;
        let html = `
            <div class="alert alert-success mb-4">
                <h5 class="alert-heading"><i class="fas fa-award me-2"></i>Grading Results</h5>
                <p>The handwritten answers have been graded against Standard ${selectedStandardId}.</p>
            </div>
        `;
        
        // If the results have images property, display them one by one
        if (results.images && Array.isArray(results.images)) {
            // Calculate overall score
            const totalScore = results.images.reduce((sum, image) => sum + (image.score || 0), 0);
            const averageScore = results.images.length > 0 ? (totalScore / results.images.length).toFixed(1) : 0;
            const overallScoreClass = averageScore >= 7 ? 'success' : (averageScore >= 5 ? 'warning' : 'danger');
            
            html += `
                <div class="text-center mb-4">
                    <div class="display-4 mb-2 text-${overallScoreClass}">${averageScore}/10</div>
                    <p class="lead">Overall Score</p>
                </div>
                
                <div class="row row-cols-1 row-cols-md-2 g-4 mb-4">
            `;
            
            results.images.forEach(image => {
                const score = image.score || '?';
                const scoreClass = score >= 7 ? 'success' : (score >= 5 ? 'warning' : 'danger');
                
                html += `
                    <div class="col">
                        <div class="card h-100">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h6 class="mb-0">${image.filename || 'Image'}</h6>
                                <span class="badge bg-${scoreClass}">Score: ${score}/10</span>
                            </div>
                            <div class="card-body">
                                <div class="mb-3">
                                    <strong>Handwritten Content:</strong>
                                    <div class="p-2 border rounded mb-3 bg-dark small" style="max-height: 150px; overflow-y: auto;">
                                        ${image.handwritten_content || 'No handwritten content found'}
                                    </div>
                                </div>
                                <div>
                                    <strong>Feedback:</strong>
                                    <div class="p-2 border rounded bg-dark small">
                                        ${image.feedback || 'No feedback provided'}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });
            
            html += `</div>`;
        } else {
            // Display overall results if not using the images structure
            html += `
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0">Grading Results</h6>
                    </div>
                    <div class="card-body">
                        <pre class="bg-dark text-light p-3 rounded">${JSON.stringify(results, null, 2)}</pre>
                    </div>
                </div>
            `;
        }
        
        // Update the grades tab content
        gradesContent.innerHTML = html;
    }

    // Helper to show errors
    function showError(message) {
        errorModalBody.textContent = message;
        errorModal.show();
    }
});