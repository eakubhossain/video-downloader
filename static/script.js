document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('video-url');
    const extractBtn = document.getElementById('extract-btn');
    const loader = document.getElementById('loader');
    const loaderText = loader.querySelector('p');
    const errorMsg = document.getElementById('error-msg');
    const resultSection = document.getElementById('result-section');
    
    // Video info elements
    const videoThumb = document.getElementById('video-thumb');
    const videoTitle = document.getElementById('video-title');
    const videoUploader = document.getElementById('video-uploader');
    const videoDuration = document.querySelector('#video-duration span');
    const formatsList = document.getElementById('formats-list');

    // Progress Modal elements
    const progressModal = document.getElementById('progress-modal');
    const progressStatus = document.getElementById('progress-status');
    const progressBarFill = document.getElementById('progress-bar-fill');
    const progressPercent = document.getElementById('progress-percent');

    let currentOriginalUrl = "";

    function formatTime(seconds) {
        if (!seconds) return 'Unknown';
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
        return `${m}:${s.toString().padStart(2, '0')}`;
    }

    function formatBytes(bytes, decimals = 2) {
        if (!bytes || bytes === 0) return 'Size unknown';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    function trackProgress(taskId) {
        progressModal.classList.remove('hidden');
        closeModalBtn.classList.add('hidden');
        doneModalBtn.classList.add('hidden');
        progressBarFill.style.width = '0%';
        progressBarFill.style.background = ''; // Reset background
        progressPercent.textContent = '0%';
        progressStatus.textContent = 'Preparing...';

        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/api/progress?task_id=${taskId}`);
                const data = await res.json();
                
                if (data.status === 'downloading') {
                    progressStatus.textContent = 'Downloading...';
                    const pct = data.percent ? data.percent.toFixed(1) : 0;
                    progressBarFill.style.width = `${pct}%`;
                    progressPercent.textContent = `${pct}%`;
                } else if (data.status === 'merging') {
                    progressStatus.textContent = 'Merging video and audio...';
                    progressBarFill.style.width = '100%';
                    progressPercent.textContent = '100%';
                } else if (data.status === 'completed') {
                    progressStatus.textContent = 'Downloaded Successfully!';
                    progressBarFill.style.width = '100%';
                    progressBarFill.style.background = 'linear-gradient(90deg, #10b981, #059669)'; // Green gradient
                    progressPercent.textContent = '100%';
                    clearInterval(interval);
                    closeModalBtn.classList.remove('hidden');
                    doneModalBtn.classList.remove('hidden');
                } else if (data.status === 'error') {
                    progressStatus.textContent = 'Error: ' + data.message;
                    progressBarFill.style.background = 'linear-gradient(90deg, #ef4444, #b91c1c)'; // Red gradient
                    clearInterval(interval);
                    closeModalBtn.classList.remove('hidden');
                    doneModalBtn.classList.remove('hidden');
                }
            } catch (e) {
                console.error("Progress check failed", e);
            }
        }, 1000);
    }

    extractBtn.addEventListener('click', async () => {
        const url = urlInput.value.trim();
        if (!url) return;
        
        currentOriginalUrl = url;

        // Reset UI
        errorMsg.classList.add('hidden');
        resultSection.classList.add('hidden');
        loader.classList.remove('hidden');
        loaderText.textContent = "Extracting video information...";
        formatsList.innerHTML = '';
        extractBtn.disabled = true;

        try {
            const response = await fetch('/api/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to extract video information');
            }

            // Populate UI
            videoThumb.src = data.thumbnail || 'https://via.placeholder.com/240x135?text=No+Thumbnail';
            videoTitle.textContent = data.title || 'Unknown Title';
            videoUploader.textContent = data.uploader ? `By ${data.uploader}` : '';
            videoDuration.textContent = formatTime(data.duration);

            if (data.formats && data.formats.length > 0) {
                data.formats.forEach(f => {
                    const li = document.createElement('li');
                    li.className = 'format-item';
                    
                    const btnId = 'btn-' + Math.random().toString(36).substr(2, 9);
                    
                    li.innerHTML = `
                        <div class="format-res">${f.resolution}</div>
                        <div class="format-ext">${f.ext.toUpperCase()} ${f.format_note ? `(${f.format_note})` : ''}</div>
                        <div class="format-size">${f.needs_merge ? 'Processing required' : formatBytes(f.filesize)}</div>
                        <button id="${btnId}" class="download-btn">Download</button>
                    `;
                    formatsList.appendChild(li);
                    
                    const btn = document.getElementById(btnId);
                    btn.addEventListener('click', () => {
                        const taskId = Math.random().toString(36).substr(2, 9);
                        trackProgress(taskId);
                        window.location.href = `/api/download?url=${encodeURIComponent(currentOriginalUrl)}&format_id=${encodeURIComponent(f.format_id)}&task_id=${taskId}`;
                    });
                });
            } else {
                formatsList.innerHTML = '<li>No suitable formats found.</li>';
            }

            resultSection.classList.remove('hidden');
            
            // Smooth scroll to results
            setTimeout(() => {
                resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 100);
            
        } catch (error) {
            errorMsg.textContent = error.message;
            errorMsg.classList.remove('hidden');
        } finally {
            loader.classList.add('hidden');
            extractBtn.disabled = false;
        }
    });

    // Handle Enter key
    urlInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') extractBtn.click();
    });
    
    // Clear button
    const clearBtn = document.getElementById('clear-btn');
    urlInput.addEventListener('input', () => {
        if (urlInput.value.length > 0) {
            clearBtn.classList.remove('hidden');
        } else {
            clearBtn.classList.add('hidden');
        }
    });
    
    clearBtn.addEventListener('click', () => {
        urlInput.value = '';
        clearBtn.classList.add('hidden');
        urlInput.focus();
    });
    
    // Paste button
    const pasteBtn = document.getElementById('paste-btn');
    pasteBtn.addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            urlInput.value = text;
            clearBtn.classList.remove('hidden');
        } catch (err) {
            console.error('Failed to read clipboard contents: ', err);
        }
    });

    // Close modal buttons
    const closeModalBtn = document.getElementById('close-modal-btn');
    const doneModalBtn = document.getElementById('done-modal-btn');
    
    const closeModal = () => {
        progressModal.classList.add('hidden');
    };
    
    closeModalBtn.addEventListener('click', closeModal);
    doneModalBtn.addEventListener('click', closeModal);

});
