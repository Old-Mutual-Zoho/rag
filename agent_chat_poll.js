// Add this script to agent_chat_ui.html for polling new messages
setInterval(async function() {
    const chatId = document.getElementById('chatId').value;
    if (!chatId) return;
    const resp = await fetch(`/api/v1/agent/messages?chat_id=${encodeURIComponent(chatId)}`);
    const data = await resp.json();
    if (data.success && Array.isArray(data.messages)) {
        const chat = document.getElementById('chat');
        chat.innerHTML = '';
        data.messages.forEach(msg => {
            const p = document.createElement('p');
            p.className = msg.sender;
            p.textContent = msg.sender + ': ' + msg.message;
            chat.appendChild(p);
        });
        chat.scrollTop = chat.scrollHeight;
    }
}, 2000); // Poll every 2 seconds
