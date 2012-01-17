"""
Google OpenID and OAuth support

OAuth works straightforward using anonymous configurations, username
is generated by requesting email to the not documented, googleapis.com
service. Registered applications can define settings GOOGLE_CONSUMER_KEY
and GOOGLE_CONSUMER_SECRET and they will be used in the auth process.
Setting GOOGLE_OAUTH_EXTRA_SCOPE can be used to access different user
related data, like calendar, contacts, docs, etc.

OAuth2 works similar to OAuth but application must be defined on Google
APIs console https://code.google.com/apis/console/ Identity option.

OpenID also works straightforward, it doesn't need further configurations.
"""
import logging
logger = logging.getLogger(__name__)

from urllib import urlencode
from urllib2 import Request, urlopen

from oauth2 import Request as OAuthRequest

from django.conf import settings
from django.utils import simplejson

from social_auth.backends import OpenIdAuth, ConsumerBasedOAuth, BaseOAuth2, \
                                 OAuthBackend, OpenIDBackend, USERNAME


# Google OAuth base configuration
GOOGLE_OAUTH_SERVER = 'www.google.com'
GOOGLE_OAUTH_AUTHORIZATION_URL = 'https://www.google.com/accounts/OAuthAuthorizeToken'
GOOGLE_OAUTH_REQUEST_TOKEN_URL = 'https://www.google.com/accounts/OAuthGetRequestToken'
GOOGLE_OAUTH_ACCESS_TOKEN_URL = 'https://www.google.com/accounts/OAuthGetAccessToken'

# Google OAuth2 base configuration
GOOGLE_OAUTH2_SERVER = 'accounts.google.com'
GOOGLE_OATUH2_AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/auth'

# scope for user email, specify extra scopes in settings, for example:
# GOOGLE_OAUTH_EXTRA_SCOPE = ['https://www.google.com/m8/feeds/']
GOOGLE_OAUTH_SCOPE = ['https://www.googleapis.com/auth/userinfo#email']
GOOGLEAPIS_EMAIL = 'https://www.googleapis.com/userinfo/email'
GOOGLE_OPENID_URL = 'https://www.google.com/accounts/o8/id'

EXPIRES_NAME = getattr(settings, 'SOCIAL_AUTH_EXPIRATION', 'expires')

# white-listed domains (else accept all)
WHITE_LISTED_DOMAINS = getattr(settings, 'WHITE_LISTED_DOMAINS', [])

# Backends
class GoogleOAuthBackend(OAuthBackend):
    """Google OAuth authentication backend"""
    name = 'google-oauth'

    def get_user_id(self, details, response):
        "Use google email as unique id"""
        return details['email']

    def get_user_details(self, response):
        """Return user details from Orkut account"""
        email = response['email']
        return {USERNAME: email.split('@', 1)[0],
                'email': email,
                'fullname': '',
                'first_name': '',
                'last_name': ''}


class GoogleOAuth2Backend(GoogleOAuthBackend):
    """Google OAuth2 authentication backend"""
    name = 'google-oauth2'
    EXTRA_DATA = [('refresh_token', 'refresh_token'),
                  ('expires_in', EXPIRES_NAME)]


class GoogleBackend(OpenIDBackend):
    """Google OpenID authentication backend"""
    name = 'google'

    def get_user_id(self, details, response):
        """Return user unique id provided by service. For google user email
        is unique enought to flag a single user. Email comes from schema:
        http://axschema.org/contact/email"""
        # only include white-listed domains
        if WHITE_LISTED_DOMAINS and details['email'].split('@')[1] not in WHITE_LISTED_DOMAINS: 
            raise ValueError('INVALID DOMAIN')

        return details['email']


# Auth classes
class GoogleAuth(OpenIdAuth):
    """Google OpenID authentication"""
    AUTH_BACKEND = GoogleBackend

    def openid_url(self):
        """Return Google OpenID service url"""
        return GOOGLE_OPENID_URL


class BaseGoogleOAuth(ConsumerBasedOAuth):
    """Base class for Google OAuth mechanism"""
    AUTHORIZATION_URL = GOOGLE_OAUTH_AUTHORIZATION_URL
    REQUEST_TOKEN_URL = GOOGLE_OAUTH_REQUEST_TOKEN_URL
    ACCESS_TOKEN_URL = GOOGLE_OAUTH_ACCESS_TOKEN_URL
    SERVER_URL = GOOGLE_OAUTH_SERVER

    def user_data(self, access_token):
        """Loads user data from G service"""
        raise NotImplementedError('Implement in subclass')


class GoogleOAuth(BaseGoogleOAuth):
    """Google OAuth authorization mechanism"""
    AUTH_BACKEND = GoogleOAuthBackend
    SETTINGS_KEY_NAME = 'GOOGLE_CONSUMER_KEY'
    SETTINGS_SECRET_NAME = 'GOOGLE_CONSUMER_SECRET'

    def user_data(self, access_token):
        """Return user data from Google API"""
        request = self.oauth_request(access_token, GOOGLEAPIS_EMAIL,
                                     {'alt': 'json'})
        url, params = request.to_url().split('?', 1)
        return googleapis_email(url, params)

    def oauth_authorization_request(self, token):
        """Generate OAuth request to authorize token."""
        return OAuthRequest.from_consumer_and_token(self.consumer,
                    token=token,
                    http_url=self.AUTHORIZATION_URL)

    def oauth_request(self, token, url, extra_params=None):
        extra_params = extra_params or {}
        scope = GOOGLE_OAUTH_SCOPE + \
                getattr(settings, 'GOOGLE_OAUTH_EXTRA_SCOPE', [])
        extra_params.update({
            'scope': ' '.join(scope),
        })
        if not self.registered():
            xoauth_displayname = getattr(settings, 'GOOGLE_DISPLAY_NAME',
                                         'Social Auth')
            extra_params['xoauth_displayname'] = xoauth_displayname
        return super(GoogleOAuth, self).oauth_request(token, url, extra_params)

    def get_key_and_secret(self):
        """Return Google OAuth Consumer Key and Consumer Secret pair, uses
        anonymous by default, beware that this marks the application as not
        registered and a security badge is displayed on authorization page.
        http://code.google.com/apis/accounts/docs/OAuth_ref.html#SigningOAuth
        """
        try:
            return super(GoogleOAuth, self).get_key_and_secret()
        except AttributeError:
            return 'anonymous', 'anonymous'

    @classmethod
    def enabled(cls):
        """Google OAuth is always enabled because of anonymous access"""
        return True

    def registered(self):
        """Check if Google OAuth Consumer Key and Consumer Secret are set"""
        return self.get_key_and_secret() != ('anonymous', 'anonymous')


# TODO: Remove this setting name check, keep for backward compatibility
_OAUTH2_KEY_NAME = hasattr(settings, 'GOOGLE_OAUTH2_CLIENT_ID') and \
                   'GOOGLE_OAUTH2_CLIENT_ID' or \
                   'GOOGLE_OAUTH2_CLIENT_KEY'


class GoogleOAuth2(BaseOAuth2):
    """Google OAuth2 support"""
    AUTH_BACKEND = GoogleOAuth2Backend
    AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/auth'
    ACCESS_TOKEN_URL = 'https://accounts.google.com/o/oauth2/token'
    SETTINGS_KEY_NAME = _OAUTH2_KEY_NAME
    SETTINGS_SECRET_NAME = 'GOOGLE_OAUTH2_CLIENT_SECRET'

    def get_scope(self):
        return GOOGLE_OAUTH_SCOPE + \
               getattr(settings, 'GOOGLE_OAUTH_EXTRA_SCOPE', [])

    def user_data(self, access_token):
        """Return user data from Google API"""
        data = {'oauth_token': access_token, 'alt': 'json'}
        return googleapis_email(GOOGLEAPIS_EMAIL, urlencode(data))


def googleapis_email(url, params):
    """Loads user data from googleapis service, only email so far as it's
    described in http://sites.google.com/site/oauthgoog/Home/emaildisplayscope

    Parameters must be passed in queryset and Authorization header as described
    on Google OAuth documentation at:
        http://groups.google.com/group/oauth/browse_thread/thread/d15add9beb418ebc
    and:
        http://code.google.com/apis/accounts/docs/OAuth2.html#CallingAnAPI
    """
    request = Request(url + '?' + params, headers={'Authorization': params})
    try:
        return simplejson.loads(urlopen(request).read())['data']
    except (ValueError, KeyError, IOError):
        return None


# Backend definition
BACKENDS = {
    'google': GoogleAuth,
    'google-oauth': GoogleOAuth,
    'google-oauth2': GoogleOAuth2,
}
