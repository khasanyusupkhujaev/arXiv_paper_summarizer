document.addEventListener('DOMContentLoaded', function() {
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            const query = document.getElementById('search_query').value.trim();
            if (!query) {
                e.preventDefault();
                alert(window.translations.emptyQueryMessage);
            }
        });
    } 
});

document.addEventListener('DOMContentLoaded', function() {
    const searchForm = document.getElementById('search-form');
    const searchButton = searchForm ? searchForm.querySelector('button[type="submit"]') : null;

    if (searchForm && searchButton) {
        const originalButtonText = searchButton.textContent.trim();
        searchForm.addEventListener('submit', function(e) {
            const query = document.getElementById('search_query').value.trim();
            if (!query) {
                e.preventDefault();
                alert(window.translations.emptyQueryMessage);
                return;
            }

            // Disable button and add loading animation
            searchButton.disabled = true;
            searchButton.classList.add('animate-pulse');
            searchButton.innerHTML = '<svg class="animate-spin h-5 w-5 mr-2 inline-block" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>' + window.translations.searchingMessage;

            // Animation persists until search completes (handled by form submission)
        });

        // Reset button on page load or error (optional, if page doesn't reload)
        window.addEventListener('pageshow', function() {
            searchButton.disabled = false;
            searchButton.classList.remove('animate-pulse');
            searchButton.textContent = originalButtonText;
        });
    }
});