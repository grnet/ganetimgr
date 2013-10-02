Copyright © 2010-2012 Greek Research and Technology Network (GRNET S.A.)

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND ISC DISCLAIMS ALL WARRANTIES WITH REGARD
TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS. IN NO EVENT SHALL ISC BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR
CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE,
DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS
ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS
SOFTWARE.


To setup an instance:

manage.py syncdb (*** Do not create superuser yet ***)
manage.py migrate
manage.py createsuperuser
run the watcher.py

Migrating to v.1.2.3

- Make sure to include HELPDESK_INTEGRATION_JAVASCRIPT_PARAMS in settings.py.
If you deploy Jira and want to set custom javascript parameters, set
HELPDESK_INTEGRATION_JAVASCRIPT_PARAMS = { 'key' : 'value' # eg. 'customfield_23123': '1stline' }
In any other case set HELPDESK_INTEGRATION_JAVASCRIPT_PARAMS = False

======================================================================

Migrating to v1.2.2

- Make sure to restart watcher.py

======================================================================

Migrating to >= v1.2
- Make sure to:
    - Set the RAPI_TIMEOUT in settings.py (see .dist)
    - Set the NODATA_IMAGE path in settings.py.dist
    - Update urls.py to urls.py.dist
Copy templates/analytics.html.dist to templates/analytics.html.
Set your prefered (we use piwik) analytics inclussion script in templates/analytics.html:

Eg.
    <!-- Piwik -->
<script type="text/javascript">
  var _paq = _paq || [];
  _paq.push(['trackPageView']);
  _paq.push(['enableLinkTracking']);
  (function() {
    var u=(("https:" == document.location.protocol) ? "https" : "http") + "://piwik.example.com//";
    _paq.push(['setTrackerUrl', u+'piwik.php']);
    _paq.push(['setSiteId', 1]);
    var d=document, g=d.createElement('script'), s=d.getElementsByTagName('script')[0]; g.type='text/javascript';
    g.defer=true; g.async=true; g.src=u+'piwik.js'; s.parentNode.insertBefore(g,s);
  })();

</script>
<noscript><p><img src="http://piwik.example.com/piwik.php?idsite=1" style="border:0" alt="" /></p></noscript>
<!-- End Piwik Code -->

If you do not wish analytics, leave this file empty.

=====================================================================

Migrating to v1.0:
-install python-ipaddr lib
-update settings.py and urls.py with latest changes from dist files
Run:
manage.py migrate

If your web server is nginx, consider placing:

proxy_set_header X-Forwarded-Host <hostname>;
in your nginx site location part
and
USE_X_FORWARDED_HOST = True
in your settings.py. 
The above ensure that i18n operates properly when switching between languages. 

=====================================================================


