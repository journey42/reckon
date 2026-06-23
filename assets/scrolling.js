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

// Infinite scroll: a single global IntersectionObserver watches the sentinel
// element at the bottom of paginated lists and clicks the hidden "load more"
// button when it scrolls into view. Runs once; re-attaches across client-side
// navigations as the sentinel element is created/removed.
(function () {
  if (window.__rhizInfiniteScroll) return;
  window.__rhizInfiniteScroll = true;
  var observed = null;
  var observer = new IntersectionObserver(
    function (entries) {
      for (var i = 0; i < entries.length; i++) {
        if (entries[i].isIntersecting) {
          var btn = document.getElementById("infinite-load-trigger");
          if (btn) btn.click();
        }
      }
    },
    { rootMargin: "300px" }
  );
  function ensure() {
    var s = document.getElementById("infinite-scroll-sentinel");
    if (s) {
      if (s !== observed) {
        if (observed) observer.unobserve(observed);
        observer.observe(s);
        observed = s;
      }
    } else if (observed) {
      observer.unobserve(observed);
      observed = null;
    }
  }
  ensure();
  setInterval(ensure, 500);
})();

// Debate "how this works" overlay: auto-open once per slug (anonymous-safe),
// reopen on demand. The Reflex dialog is controlled by a hidden checkbox-style
// trigger button (#debate-howto-open) we click programmatically.
window.rhizDebateOverlayInit = function (slug) {
  try {
    if (!slug) {
      var m = location.pathname.split("/debate/")[1] || "";
      slug = m.split("/")[0];
    }
    if (!slug) return;
    var key = "rhiz_debate_seen_" + slug;
    if (!localStorage.getItem(key)) {
      localStorage.setItem(key, "1");
      var btn = document.getElementById("debate-howto-open");
      if (btn) btn.click();
    }
  } catch (e) {
    /* localStorage unavailable: skip auto-open */
  }
};
