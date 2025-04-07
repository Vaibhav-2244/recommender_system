async function loadSpamMessages() {
    const spamContainer = document.getElementById('spam-messages');
    const loadingSpinner = document.getElementById('spam-loading');
    const userId = document.body.dataset.userId;
    
    try {
        loadingSpinner.classList.remove('d-none');
        spamContainer.innerHTML = '';

        if (!userId) throw new Error('User ID not found');

        const response = await fetch(`/api/spam/messages/${userId}`);
        if (!response.ok) throw new Error(`Server error: ${response.status}`);

        const data = await response.json();
        loadingSpinner.classList.add('d-none');

        if (!data.messages?.length) {
            spamContainer.innerHTML = `
                <div class="text-center py-4 text-muted">
                    No spam messages found
                </div>
            `;
            return;
        }

        // Render messages with hover effect
        spamContainer.innerHTML = data.messages.map(msg => `
            <div class="list-group-item spam-message-container"
                 data-message-id="${msg.id}">
                <div class="d-flex justify-content-between align-items-center">
                    <div class="d-flex align-items-center">
                        <img src="${msg.profile_pic ? '/static/' + msg.profile_pic : '/static/default_profile_pic.png'}" 
                             class="rounded-circle me-3" width="50" height="50" 
                             style="object-fit: cover;"
                             onerror="this.src='/static/default_profile_pic.png'">
                        <div>
                            <h6 class="mb-1">${msg.sender_username}</h6>
                            <p class="mb-1 text-muted">${msg.content.substring(0, 50)}${msg.content.length > 50 ? '...' : ''}</p>
                        </div>
                    </div>
                    <small class="text-muted">
                        ${new Date(msg.timestamp).toLocaleTimeString()}
                    </small>
                </div>
                
                <!-- Hover Details Window (hidden by default) -->
                <div class="spam-details-window">
                    <div class="d-flex align-items-center mb-3">
                        <img src="${msg.profile_pic ? '/static/' + msg.profile_pic : '/static/default_profile_pic.png'}" 
                             class="rounded-circle me-3" width="80" height="80"
                             style="object-fit: cover;"
                             onerror="this.src='/static/default_profile_pic.png'">
                        <div>
                            <h5>${msg.sender_username}</h5>
                            <small class="text-muted">${new Date(msg.timestamp).toLocaleString()}</small>
                        </div>
                    </div>
                    
                    <div class="message-content mb-3 p-3 bg-light rounded">
                        ${msg.content}
                    </div>
                    
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <small class="text-muted">Spam Confidence: ${Math.round((msg.spam_confidence || 0) * 100)}%</small>
                        </div>
                        <button class="btn btn-sm btn-success mark-not-spam" 
                                data-message-id="${msg.id}">
                            Mark as Not Spam
                        </button>
                    </div>
                </div>
            </div>
        `).join('');

        // Add hover event listeners
        document.querySelectorAll('.spam-message-container').forEach(container => {
            container.addEventListener('mouseenter', showSpamDetails);
            container.addEventListener('mouseleave', hideSpamDetails);
        });

        // Add click handler for "Not Spam" button
        document.querySelectorAll('.mark-not-spam').forEach(btn => {
            btn.addEventListener('click', handleNotSpam);
        });

    } catch (error) {
        console.error('Error loading spam messages:', error);
        loadingSpinner.classList.add('d-none');
        spamContainer.innerHTML = `
            <div class="alert alert-danger">
                ${error.message || 'Failed to load spam messages'}
                <button class="btn btn-sm btn-warning mt-2" onclick="loadSpamMessages()">
                    Retry
                </button>
            </div>
        `;
    }
}

function showSpamDetails(e) {
    const container = e.currentTarget;
    const detailsWindow = container.querySelector('.spam-details-window');
    detailsWindow.style.display = 'block';
}

function hideSpamDetails(e) {
    const container = e.currentTarget;
    const detailsWindow = container.querySelector('.spam-details-window');
    detailsWindow.style.display = 'none';
}

async function handleNotSpam(e) {
    e.stopPropagation();
    const button = e.currentTarget;
    const messageId = button.dataset.messageId;
    const originalText = button.innerHTML;
    
    try {
        // Show loading state
        button.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...`;
        button.disabled = true;
        
        const response = await fetch(`/report_not_spam/${messageId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error('Failed to mark as not spam');
        }

        // Refresh the spam list
        await loadSpamMessages();
        showToast('Message moved to regular inbox', 'success');
        
    } catch (error) {
        console.error('Error:', error);
        showToast(`Failed to update message: ${error.message}`, 'danger');
    } finally {
        // Reset button state
        button.innerHTML = originalText;
        button.disabled = false;
    }
}

// Toast notification functions
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container') || createToastContainer();
    const toastId = `toast-${Date.now()}`;
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.id = toastId;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remove toast after it's hidden
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'position-fixed bottom-0 end-0 p-3';
    container.style.zIndex = '11';
    document.body.appendChild(container);
    return container;
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Load spam messages when spam tab is shown
    const spamTab = document.getElementById('spam-tab');
    if (spamTab) {
        spamTab.addEventListener('shown.bs.tab', loadSpamMessages);
    }
});