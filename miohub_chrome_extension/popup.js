// MioHub Chrome Extension - Popup Script

const serverUrl = 'https://basu001.pythonanywhere.com';
let apiToken = null;
let currentUser = null;

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  await checkAuthentication();
  setupEventListeners();
});

// Load saved settings
async function loadSettings() {
  const result = await chrome.storage.local.get(['apiToken', 'currentUser', 'serverUrl']);

  if (result.apiToken) {
    apiToken = result.apiToken;
    document.getElementById('api-token').value = apiToken;
  }

  if (result.currentUser) {
    currentUser = result.currentUser;
  }

  // Cleanup legacy server URL storage
  if (result.serverUrl) {
    await chrome.storage.local.remove('serverUrl');
  }
}

// Check if authenticated
async function checkAuthentication() {
  if (!apiToken) {
    showAuthSection();
    return;
  }
  
  try {
    const response = await fetch(`${serverUrl}/api/extension/verify-token`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiToken}`,
        'Content-Type': 'application/json'
      }
    });
    
    const data = await response.json();
    
    if (data.valid) {
      currentUser = data.user;
      await chrome.storage.local.set({ currentUser });
      showMainContent();
    } else {
      showAuthSection();
      showMessage('Authentication expired. Please reconnect.', 'error');
    }
  } catch (error) {
    console.error('Auth check failed:', error);
    showAuthSection();
    showMessage('Cannot connect to server.', 'error');
  }
}

// Setup event listeners
function setupEventListeners() {
  document.getElementById('connect-btn').addEventListener('click', handleConnect);
  document.getElementById('disconnect-btn').addEventListener('click', handleDisconnect);
  document.getElementById('save-page-btn').addEventListener('click', () => saveContent('url'));
  document.getElementById('save-selection-btn').addEventListener('click', () => saveContent('text'));
  document.getElementById('save-clean-page-btn').addEventListener('click', () => saveContent('clean-page'));

  document.getElementById('api-token').addEventListener('input', handleApiTokenInput);
}

// Save API token when user types
async function handleApiTokenInput(event) {
  const value = event.target.value.trim();
  await chrome.storage.local.set({ apiToken: value });
  apiToken = value;
}

// Handle connect
async function handleConnect() {
  const tokenInput = document.getElementById('api-token').value.trim();
  
  if (!tokenInput) {
    showMessage('Please enter your API token', 'error');
    return;
  }

  apiToken = tokenInput;

  showLoading('Connecting to MioHub...');
  
  try {
    const response = await fetch(`${serverUrl}/api/extension/verify-token`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiToken}`,
        'Content-Type': 'application/json'
      }
    });
    
    const data = await response.json();
    
    if (data.valid) {
      currentUser = data.user;
      
      // Save settings
      await chrome.storage.local.set({
        apiToken,
        currentUser
      });
      
      hideLoading();
      showMainContent();
      showMessage('Connected successfully!', 'success');
    } else {
      hideLoading();
      showMessage('Invalid API token', 'error');
    }
  } catch (error) {
    console.error('Connection failed:', error);
    hideLoading();
    showMessage('Connection failed. Please try again.', 'error');
  }
}

// Handle disconnect
async function handleDisconnect() {
  await chrome.storage.local.clear();
  apiToken = null;
  currentUser = null;
  showAuthSection();
}
  
// Save content
async function saveContent(type) {
  if (!apiToken) {
    showMessage('Please connect to MioHub first', 'error');
    return;
  }
  
  showLoading(`Saving ${type}...`);
  
  try {
    let content, title, url, pageTitle;
    
    // Get active tab info
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    url = tab.url;
    pageTitle = tab.title;
    
    if (type === 'url') {
      content = url;
      title = pageTitle;
    } else if (type === 'text') {
      // Execute script to get selected text
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        function: () => window.getSelection().toString()
      });
      
      content = results[0].result;
      
      if (!content || content.trim() === '') {
        hideLoading();
        showMessage('No text selected on page', 'error');
        return;
      }
      
      title = `Selected text from ${pageTitle}`;
    } else if (type === 'clean-page') {
      // Execute script to extract clean page content
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        function: extractCleanPageContent
      });
      
      content = results[0].result;
      
      if (!content || content.trim() === '') {
        hideLoading();
        showMessage('Could not extract page content', 'error');
        return;
      }
      
      title = pageTitle;
      type = 'clean-page';
    }
    
    // Send to server
    const response = await fetch(`${serverUrl}/api/extension/save-content`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        type,
        content,
        title,
        url,
        page_title: pageTitle
      })
    });
    
    const data = await response.json();
    
    hideLoading();
    
    if (data.success) {
      const typeLabel = type === 'url' ? 'URL' : type === 'text' ? 'Text' : type === 'clean-page' ? 'Clean page' : 'Content';
      showMessage(`${typeLabel} saved successfully!`, 'success');
      // Could add to recent saves here
    } else {
      showMessage(data.error || 'Failed to save content', 'error');
    }
  } catch (error) {
    hideLoading();
    console.error('Save failed:', error);
    showMessage('Failed to save content', 'error');
  }
}

// Extract clean page content with images (injected function)
async function extractCleanPageContent() {
  const article = document.querySelector('article') || 
                  document.querySelector('main') || 
                  document.querySelector('[role="main"]') ||
                  document.querySelector('.content') ||
                  document.querySelector('.post') ||
                  document.body;
  
  if (!article) return '';
  
  const clone = article.cloneNode(true);
  
  const unwanted = clone.querySelectorAll(
    'script, style, nav, header, footer, aside, .advertisement, .ad, .sidebar, .comments, .social-share, iframe, [class*="ad-"], [id*="ad-"]'
  );
  unwanted.forEach(el => el.remove());
  
  // Extract and convert images to data URIs
  const images = Array.from(clone.querySelectorAll('img'));
  const imageMap = new Map();
  
  for (const img of images) {
    const src = img.src;
    if (!src || src.startsWith('data:')) continue;
    
    try {
      // Fetch image and convert to data URI
      const response = await fetch(src);
      const blob = await response.blob();
      
      // Skip images larger than 5MB
      if (blob.size > 5 * 1024 * 1024) continue;
      
      const dataUri = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
      
      imageMap.set(src, dataUri);
    } catch (err) {
      console.warn('Failed to fetch image:', src, err);
    }
  }
  
  let content = '';
  
  const title = document.querySelector('h1')?.textContent || document.title;
  content += `# ${title}\n\n`;
  
  // Process elements including images
  const elements = clone.querySelectorAll('p, h1, h2, h3, h4, h5, h6, ul, ol, blockquote, pre, img');
  elements.forEach(el => {
    const tagName = el.tagName.toLowerCase();
    
    if (tagName === 'img') {
      const originalSrc = el.getAttribute('src');
      const dataUri = imageMap.get(originalSrc);
      if (dataUri) {
        const alt = el.getAttribute('alt') || 'Image';
        content += `\n![${alt}](${dataUri})\n\n`;
      }
      return;
    }
    
    const text = el.textContent.trim();
    if (!text) return;
    
    if (tagName === 'h1') content += `\n# ${text}\n\n`;
    else if (tagName === 'h2') content += `\n## ${text}\n\n`;
    else if (tagName === 'h3') content += `\n### ${text}\n\n`;
    else if (tagName === 'h4') content += `\n#### ${text}\n\n`;
    else if (tagName === 'h5') content += `\n##### ${text}\n\n`;
    else if (tagName === 'h6') content += `\n###### ${text}\n\n`;
    else if (tagName === 'blockquote') content += `> ${text}\n\n`;
    else if (tagName === 'pre') content += `\n\`\`\`\n${text}\n\`\`\`\n\n`;
    else content += `${text}\n\n`;
  });
  
  return content || article.textContent.trim();
}

function showAuthSection() {
  document.getElementById('auth-section').style.display = 'block';
  document.getElementById('main-content').style.display = 'none';
}

function showMainContent() {
  document.getElementById('auth-section').style.display = 'none';
  document.getElementById('main-content').style.display = 'block';
  
  if (currentUser) {
    document.getElementById('username').textContent = currentUser.username;
  }
}

function showLoading(text = 'Processing...') {
  document.getElementById('loading-text').textContent = text;
  document.getElementById('loading-overlay').style.display = 'flex';
}

function hideLoading() {
  document.getElementById('loading-overlay').style.display = 'none';
}

function showMessage(text, type = 'info') {
  const messageEl = document.getElementById('message');
  messageEl.textContent = text;
  messageEl.className = `message ${type}`;
  messageEl.style.display = 'block';
  
  setTimeout(() => {
    messageEl.style.display = 'none';
  }, 5000);
}
