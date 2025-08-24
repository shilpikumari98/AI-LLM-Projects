// Chat history array to keep session messages
let chatHistory = [];

function renderChatHistory() {
    const chatHistoryDiv = document.getElementById('chat-history');
    chatHistoryDiv.innerHTML = '';
    if (chatHistory.length === 0) {
        const placeholder = document.createElement('div');
        placeholder.className = 'chat-placeholder';
        placeholder.innerText = 'Start the conversation...';
        chatHistoryDiv.appendChild(placeholder);
        return;
    }
    chatHistory.forEach(msg => {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'chat-message ' + (msg.sender === 'user' ? 'user-message' : 'agent-message');
        msgDiv.innerHTML = `
            <div class="chat-avatar">
                <img src="${msg.sender === 'user' ? '/static/logo_image.jpg' : '/static/logo_image.jpg'}" alt="${msg.sender}" />
            </div>
            <div class="chat-content">
                <div class="chat-meta">
                    <span class="chat-sender">${msg.sender === 'user' ? 'You' : 'Doctor Agent'}</span>
                    <span class="chat-time">${msg.time}</span>
                </div>
                <div class="chat-text">${msg.text}</div>
            </div>
        `;
        chatHistoryDiv.appendChild(msgDiv);
    });
    chatHistoryDiv.scrollTop = chatHistoryDiv.scrollHeight;
}

function getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function renderResult(data) {
    // Render agent message as chat
    let text = '';
    if (data && typeof data === 'object') {
        if (data.results && data.results.error) {
            text = `<div class="error">${data.results.error}</div>`;
        }
        
        // Handle help responses
        if (data.help) {
            text = `<div style="white-space: pre-line; line-height: 1.6;">${data.help}</div>`;
        }
        
        // Handle registration responses
        if (data.doctor_id) {
            text += `<div style="margin-bottom:10px;"><b>Doctor ID:</b> <span style="color:#00c6ff;font-weight:bold;">${data.doctor_id}</span></div>`;
        }
        if (data.patient_id) {
            text += `<div style="margin-bottom:10px;"><b>Patient ID:</b> <span style="color:#00c6ff;font-weight:bold;">${data.patient_id}</span></div>`;
        }
        if (data.specialization_id) {
            text += `<div style="margin-bottom:10px;"><b>Specialization ID:</b> <span style="color:#00c6ff;font-weight:bold;">${data.specialization_id}</span></div>`;
        }
        if (data.availability_id) {
            text += `<div style="margin-bottom:10px;"><b>Availability ID:</b> <span style="color:#00c6ff;font-weight:bold;">${data.availability_id}</span></div>`;
        }
        
        // Handle appointment responses
        if (data.appointment_id) {
            text += `<div style="margin-bottom:10px;"><b>Appointment ID:</b> <span style="color:#00c6ff;font-weight:bold;">${data.appointment_id}</span></div>`;
        }
        
        if (data.message) {
            text += `<div style="margin-bottom:10px; color:#ffd200; font-size:1.15em;">${data.message}</div>`;
        }
        
        if (data.details && typeof data.details === 'object') {
            // Determine the type of details based on which ID is present
            let detailsTitle = 'Details';
            if (data.appointment_id) {
                detailsTitle = 'Appointment Details';
            } else if (data.doctor_id) {
                detailsTitle = 'Doctor Details';
            } else if (data.patient_id) {
                detailsTitle = 'Patient Details';
            } else if (data.specialization_id) {
                detailsTitle = 'Specialization Details';
            } else if (data.availability_id) {
                detailsTitle = 'Availability Details';
            }
            
            text += `<div style="margin-bottom:10px;"><b>${detailsTitle}:</b></div>`;
            text += '<ul>' +
                Object.entries(data.details).map(([k, v]) => {
                    let displayKey = k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    return `<li><b>${displayKey}:</b> ${v || 'N/A'}</li>`;
                }).join('') +
                '</ul>';
        }
        
        if (Array.isArray(data.results)) {
            if (data.results.length === 0) {
                text += '<div>No results found.</div>';
            } else {
                data.results.forEach((row, idx) => {
                    text += `<div style="margin-bottom:10px;"><b>Result ${data.results.length > 1 ? idx+1 : ''}</b></div>`;
                    text += '<ul>' +
                        Object.entries(row).map(([k, v]) => `<li><b>${k.replace(/_/g, ' ')}:</b> ${v}</li>`).join('') +
                        '</ul>';
                });
            }
        } else if (typeof data.results === 'object' && data.results !== null && !data.results.error) {
            text += '<ul>' + Object.entries(data.results).map(([k, v]) => `<li><b>${k.replace(/_/g, ' ')}:</b> ${v}</li>`).join('') + '</ul>';
        }
    } else {
        text = data;
    }
    chatHistory.push({ sender: 'agent', text, time: getCurrentTime() });
    renderChatHistory();
}

document.getElementById('query-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const queryInput = document.getElementById('user-query');
    const query = queryInput.value;
    if (!query.trim()) return;
    chatHistory.push({ sender: 'user', text: query, time: getCurrentTime() });
    renderChatHistory();
    queryInput.value = '';
    try {
        const response = await fetch('/call_tool', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: 'ask_agent', arguments: { question: query } })
        });
        const data = await response.json();
        renderResult(data);
    } catch (err) {
        chatHistory.push({ sender: 'agent', text: `<div class="error">Error: ${err.message}</div>`, time: getCurrentTime() });
        renderChatHistory();
    }
});

// Initial render
renderChatHistory();
