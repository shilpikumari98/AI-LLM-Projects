document.addEventListener('DOMContentLoaded', () => {
  const searchBtn = document.getElementById('search-btn');
  const searchInput = document.getElementById('search-input');
  const searchResults = document.getElementById('search-results');
  const settingsTableContainer = document.getElementById('settings-table');
  const modal = document.getElementById('insight-modal');
  const modalContent = document.getElementById('insight-content');
  const modalCloseBtn = document.getElementById('insight-close');

  // Render settings
  function renderSettingsTable(settings) {
    settingsTableContainer.innerHTML = '';
    const table = document.createElement('table');
    table.innerHTML = `
      <thead>
        <tr>
          <th>Name</th>
          <th>Current Value</th>
          <th>Default Value</th>
          <th>Description</th>
          <th>Context</th>
          <th>Type</th>
          <th>Min</th>
          <th>Max</th>
          <th>AI Insights</th>
        </tr>
      </thead>
      <tbody>
        ${settings.map(s => `
          <tr>
            <td>${s.name ?? ''}</td>
            <td>${s.current_value ?? ''}</td>
            <td>${s.default_value ?? ''}</td>
            <td title="${s.short_desc ?? ''}">${s.short_desc ?? ''}</td>
            <td>${s.context ?? ''}</td>
            <td>${s.vartype ?? ''}</td>
            <td>${s.min_val ?? ''}</td>
            <td>${s.max_val ?? ''}</td>
            <td><button class="ask-ai-btn" data-setting="${s.name}">AI Insights</button></td>
          </tr>`).join('')}
      </tbody>
    `;
    settingsTableContainer.appendChild(table);

    // Button events
    table.querySelectorAll('.ask-ai-btn').forEach(button => {
      button.addEventListener('click', async () => {
        const settingName = button.dataset.setting;
        if (!settingName) return;
        try {
          const response = await fetch(`/insight/${settingName}`);
          if (!response.ok) {
            alert(`No AI insight found for ${settingName}`);
            return;
          }
          const data = await response.json();
          modalContent.textContent = data.ai_insights || "No AI insight available.";
          modal.classList.add('show');
          modalContent.focus();
        } catch (err) {
          console.error(err);
          alert("Error fetching AI insight.");
        }
      });
    });
  }

  // Close modal
  function closeModal() {
    modal.classList.remove('show');
  }
  modalCloseBtn.addEventListener('click', closeModal);
  modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && modal.classList.contains('show')) closeModal();
  });

  // Fetch settings
  async function fetchSettings() {
    try {
      const res = await fetch('/settings');
      const settings = await res.json();
      renderSettingsTable(settings);
    } catch {
      settingsTableContainer.innerHTML = `<p style="color:red">Failed to load settings</p>`;
    }
  }

  // Search
  searchBtn.addEventListener('click', async () => {
    const query = searchInput.value.trim();
    if (!query) {
      searchResults.textContent = 'Please enter a search query.';
      return;
    }
    searchResults.textContent = 'Searching...';
    try {
      const res = await fetch('/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      const data = await res.json();
      searchResults.textContent = data.answer || 'No relevant information found.';
    } catch {
      searchResults.textContent = 'Error occurred while searching.';
    }
  });

  fetchSettings();
});
