// Background service worker for context menus

const serverUrl = 'https://basu001.pythonanywhere.com';
let apiToken = null;
let settingsLoaded = false;

// Load settings when extension starts
chrome.runtime.onInstalled.addListener(async () => {
  await loadSettings();
  setupContextMenus();
});

chrome.runtime.onStartup.addListener(async () => {
  await loadSettings();
  setupContextMenus();
});

// Cold start: preload settings so context-menu clicks work after service worker resumes
loadSettings();

// Listen for storage changes
chrome.storage.onChanged.addListener(async (changes) => {
  if (changes.apiToken) {
    await loadSettings();
  }
});

async function loadSettings() {
  const result = await chrome.storage.local.get(['apiToken']);
  if (result.apiToken) apiToken = result.apiToken;
  settingsLoaded = true;
}

async function ensureSettingsLoaded() {
  if (settingsLoaded && apiToken) return;
  await loadSettings();
}

function setupContextMenus() {
  // Remove existing menus
  chrome.contextMenus.removeAll(() => {
    // Context menu for images
    chrome.contextMenus.create({
      id: 'save-image-to-miohub',
      title: 'Save Image to MioHub',
      contexts: ['image']
    });
    
    // Context menu for links
    chrome.contextMenus.create({
      id: 'save-link-to-miohub',
      title: 'Save Link to MioHub',
      contexts: ['link']
    });
    
    // Context menu for selected text
    chrome.contextMenus.create({
      id: 'save-text-to-miohub',
      title: 'Save Text to MioHub',
      contexts: ['selection']
    });
    
    // Context menu for page
    chrome.contextMenus.create({
      id: 'save-page-to-miohub',
      title: 'Save Page URL to MioHub',
      contexts: ['page']
    });
  });
}

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  await ensureSettingsLoaded();

  if (!apiToken) {
    // Open popup to connect
    chrome.action.openPopup();
    return;
  }
  
  try {
    let content, title, type, sourceUrl;
    
    sourceUrl = tab.url;
    const pageTitle = tab.title;
    
    switch (info.menuItemId) {
      case 'save-image-to-miohub':
        type = 'image';
        title = `Image from ${pageTitle}`;

        // Convert image URL to base64
        content = await fetchImageAsDataUri(info.srcUrl);

        if (!content) {
          showNotification('Failed to load image', 'error');
          return;
        }
        break;
        
      case 'save-link-to-miohub':
        type = 'url';
        content = info.linkUrl;
        title = info.linkUrl;
        break;
        
      case 'save-text-to-miohub':
        type = 'text';
        content = info.selectionText || '';

        // Fallback: grab selection directly from the page if Chrome did not supply it
        if ((!content || !content.trim()) && tab?.id) {
          try {
            const results = await chrome.scripting.executeScript({
              target: { tabId: tab.id },
              func: () => window.getSelection()?.toString() || ''
            });
            content = results?.[0]?.result || '';
          } catch (err) {
            console.error('Failed to read selection via scripting:', err);
          }
        }

        if (!content || !content.trim()) {
          showNotification('No selected text to save', 'error');
          return;
        }

        title = `Selected text from ${pageTitle}`;
        break;
        
      case 'save-page-to-miohub':
        type = 'url';
        content = sourceUrl;
        title = pageTitle;
        break;
        
      default:
        return;
    }
    
    // Send to server (no folder selection needed - uses "Web Clippings" automatically)
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
        url: sourceUrl,
        page_title: pageTitle
      })
    });
    
    const data = await response.json();
    
    if (data.success) {
      showNotification(`Saved to ${data.file.folder_name}`, 'success');
    } else {
      showNotification(data.error || 'Failed to save', 'error');
    }
  } catch (error) {
    console.error('Context menu save failed:', error);
    showNotification('Failed to save to MioHub', 'error');
  }
});

// Fetch image as data URI
async function fetchImageAsDataUri(imageUrl) {
  try {
    const response = await fetch(imageUrl);
    const blob = await response.blob();
    
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  } catch (error) {
    console.error('Failed to fetch image:', error);
    return null;
  }
}

// Show notification
function showNotification(message, type = 'info') {
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icons/icon48.png',
    title: 'MioHub Saver',
    message: message
  });
}
