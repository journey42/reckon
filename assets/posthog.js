if (!window.__posthog_loaded__) {
  window.__posthog_loaded__ = true;
  (function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="capture identify alias people.set people.set_once register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures getActiveMatchingSurveys getSurveys onSessionId".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)})(document,window.posthog||[]);
  if (window.posthog && typeof window.posthog.init === 'function') {
    window.posthog.init('phc_rQPhVDnHM6wgc44Eq3lQayCH4rSOZH3jevGH2B4aFpo', {
      api_host: 'https://app.posthog.com',
      respect_dnt: true,
      capture_pageview: 'history_change',
      disable_session_recording: false,
    });
    // Mirror the PostHog session id into a first-party cookie so the
    // server-side event handlers can attach $session_id to their captures
    // (events then join the same session replay as browser activity).
    function rhizSetSid() {
      try {
        var sid = window.posthog.get_session_id ? window.posthog.get_session_id() : null;
        if (sid) {
          document.cookie = 'rhiz_ph_sid=' + encodeURIComponent(sid) +
            '; path=/; max-age=1800; SameSite=Lax' +
            (location.protocol === 'https:' ? '; Secure' : '');
        }
      } catch (e) { /* never break the app for telemetry */ }
    }
    rhizSetSid();
    window.posthog.on('session_id', function () { rhizSetSid(); });
  }
}
