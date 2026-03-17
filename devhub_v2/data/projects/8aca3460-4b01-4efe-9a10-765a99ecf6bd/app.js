const statusPanel = document.getElementById('status-panel');
const featureButton = document.getElementById('feature-button');
const chatButton = document.getElementById('chat-button');

function writeStatus(message) {
  const timestamp = new Date().toLocaleTimeString();
  statusPanel.textContent = `[${timestamp}] ${message}`;
}

featureButton.addEventListener('click', () => {
  writeStatus('Ask DevHub to implement your first real feature in this project.');
});

chatButton.addEventListener('click', () => {
  writeStatus('The project chat is embedded beside the editor in DevHub.');
});

writeStatus('"Calculator app" is running from a real project folder.');
