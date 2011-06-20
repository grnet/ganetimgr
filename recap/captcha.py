import urllib2, urllib

API_SSL_SERVER="https://www.google.com/recaptcha/api"
API_SERVER="http://www.google.com/recaptcha/api"
VERIFY_SERVER="www.google.com"

class RecaptchaResponse(object):
    def __init__(self, is_valid, error_code=None):
        self.is_valid = is_valid
        self.error_code = error_code

def displayhtml (public_key,
                 use_ssl = False,
                 error = None,
                 use_custom_theme = False):
    """Gets the HTML to display for reCAPTCHA
    
    #<script type="text/javascript" src="%(ApiServer)s/challenge?k=%(PublicKey)s%(ErrorParam)s"></script>

    public_key -- The public api key
    use_ssl -- Should the request be sent over ssl?
    error -- An error message to display (from RecaptchaResponse.error_code)"""

    error_param = ''
    if error:
        error_param = '&error=%s' % error

    if use_ssl:
        server = API_SSL_SERVER
    else:
        server = API_SERVER
        
    if use_custom_theme:
        custom_js = """<script type="text/javascript">
 var RecaptchaOptions = {
    theme : 'blackglass',
    custom_theme_widget: 'recaptcha_widget'
 };</script>"""
        custom_content = """<div id="recaptcha_widget" style="display:none"><div id="recaptcha_image"></div> 
<div class="recaptcha_only_if_incorrect_sol" style="color:red">Incorrect, please try again</div>
<br/>
<span class="recaptcha_only_if_image">Enter the words above:</span>
<span class="recaptcha_only_if_audio">Enter the numbers you hear:</span>

<input type="text" id="recaptcha_response_field" name="recaptcha_response_field" />

<span class="recaptcha_reload"><a href="javascript:Recaptcha.reload()">Get another CAPTCHA</a></span>
<div class="recaptcha_only_if_image"><a href="javascript:Recaptcha.switch_type('audio')">Get an audio CAPTCHA</a></div>
<div class="recaptcha_only_if_audio"><a href="javascript:Recaptcha.switch_type('image')">Get an image CAPTCHA</a></div>

<div class="recaptcha_help"><a href="javascript:Recaptcha.showhelp()">Help</a></div>

</div>"""
    else:
        custom_js = """<script type="text/javascript">
 var RecaptchaOptions = {
    theme : 'white',
 };</script>"""
        custom_content = ""

    return """%(CustomTheme)s
%(CustomContent)s
<script type="text/javascript" src="http://www.google.com/recaptcha/api/challenge?k=%(PublicKey)s"></script>
<noscript>
  <iframe src="%(ApiServer)s/noscript?k=%(PublicKey)s%(ErrorParam)s" height="300" width="500" frameborder="0"></iframe><br />
  <textarea name="recaptcha_challenge_field" rows="3" cols="40"></textarea>
  <input type='hidden' name='recaptcha_response_field' value='manual_challenge' />
</noscript>
""" % {
        'CustomTheme': custom_js,
        'CustomContent': custom_content,
        'ApiServer' : server,
        'PublicKey' : public_key,
        'ErrorParam' : error_param,
        }


def submit (recaptcha_challenge_field,
            recaptcha_response_field,
            private_key,
            remoteip, use_ssl=False):
    """
    Submits a reCAPTCHA request for verification. Returns RecaptchaResponse
    for the request

    recaptcha_challenge_field -- The value of recaptcha_challenge_field from the form
    recaptcha_response_field -- The value of recaptcha_response_field from the form
    private_key -- your reCAPTCHA private key
    remoteip -- the user's ip address
    """

    if not (recaptcha_response_field and recaptcha_challenge_field and
            len (recaptcha_response_field) and len (recaptcha_challenge_field)):
        return RecaptchaResponse (is_valid = False, error_code = 'incorrect-captcha-sol')
    

    def encode_if_necessary(s):
        if isinstance(s, unicode):
            return s.encode('utf-8')
        return s

    params = urllib.urlencode ({
            'privatekey': encode_if_necessary(private_key),
            'remoteip' :  encode_if_necessary(remoteip),
            'challenge':  encode_if_necessary(recaptcha_challenge_field),
            'response' :  encode_if_necessary(recaptcha_response_field),
            })

    if use_ssl:
        verify_url = 'https://%s/recaptcha/api/verify' % VERIFY_SERVER
    else:
        verify_url = 'http://%s/recaptcha/api/verify' % VERIFY_SERVER
    
    request = urllib2.Request (
        url = verify_url,
        data = params,
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "User-agent": "reCAPTCHA Python"
            }
        )
    
    httpresp = urllib2.urlopen (request)

    return_values = httpresp.read ().splitlines ();
    httpresp.close();

    return_code = return_values [0]

    if (return_code == "true"):
        return RecaptchaResponse(is_valid=True)
    else:
        return RecaptchaResponse(is_valid=False, error_code = return_values [1])