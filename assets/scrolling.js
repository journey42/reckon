// Before the page unloads, save the scroll position
function saveScrollPosition() {
    sessionStorage.setItem('scrollPosition', window.scrollY);
  };
  
  // When the page is fully loaded, scroll to the saved position
function scrollToSavedPosition() {
    if (sessionStorage.getItem('scrollPosition') !== null) {
      window.scrollTo(0, sessionStorage.getItem('scrollPosition'));
      sessionStorage.setItem('scrollPosition', null);
    }
  };