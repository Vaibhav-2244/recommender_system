// Toggle connections list
document.getElementById("toggle-connections").addEventListener("click", function() {
    var connectionsList = document.getElementById("connections-list");
    if (connectionsList.style.display === "none") {
        connectionsList.style.display = "block";
    } else {
        connectionsList.style.display = "none";
    }
});

// Profile picture upload preview
document.getElementById("profile_pic_upload").addEventListener("change", function(event) {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            document.getElementById("profile_pic_preview").src = e.target.result;
            const overlay = document.getElementById("profile_pic_overlay");
            if (overlay) overlay.style.display = "none";
        };
        reader.readAsDataURL(file);
    }
});

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tags input
    const interestsInput = document.getElementById('interests');
    
    // Show dropdown when input is focused
    interestsInput.addEventListener('focus', function() {
        document.getElementById('interestsDropdown').style.display = 'block';
    });
    
    // Hide dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('#interestsDropdown') && e.target !== interestsInput) {
            document.getElementById('interestsDropdown').style.display = 'none';
        }
    });
    
    // Add interest when clicked
    document.querySelectorAll('.interest-option').forEach(option => {
        option.addEventListener('click', function() {
            const interest = this.textContent;
            const currentValue = interestsInput.value;
            
            if (!currentValue.includes(interest)) {
                const newValue = currentValue ? `${currentValue},${interest}` : interest;
                interestsInput.value = newValue;
                
                // Trigger change event for any listeners
                const event = new Event('change');
                interestsInput.dispatchEvent(event);
            }
            
            // Add visual feedback
            this.style.backgroundColor = '#4f46e5';
            setTimeout(() => {
                document.getElementById('interestsDropdown').style.display = 'none';
            }, 300);
        });
    });
});

// Remove profile picture
function removeProfilePicture() {
    if (confirm("Are you sure you want to remove your profile picture?")) {
        fetch("/remove_profile_pic", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) window.location.reload();
            else alert("Failed to remove profile picture.");
        })
        .catch(error => console.error("Error:", error));
    }
}

//chatbot
// Add to your profile.js or in a script tag
document.addEventListener('DOMContentLoaded', function() {
    const chatbotBtn = document.querySelector('.chatbot-btn');
    
    // Add hover effect
    chatbotBtn.addEventListener('mouseenter', function() {
        this.querySelector('.chatbot-pulse').style.animation = 'pulse 1s infinite';
    });
    
    chatbotBtn.addEventListener('mouseleave', function() {
        this.querySelector('.chatbot-pulse').style.animation = 'pulse 2s infinite';
    });
    
    // Add click effect
    chatbotBtn.addEventListener('click', function(e) {
        e.preventDefault();
        // Add a ripple effect
        const ripple = document.createElement('span');
        ripple.classList.add('chatbot-ripple');
        this.appendChild(ripple);
        
        // Remove ripple after animation
        setTimeout(() => {
            ripple.remove();
        }, 1000);
        
        // Navigate to chatbot page after slight delay
        setTimeout(() => {
            window.location.href = this.href;
        }, 300);
    });
});