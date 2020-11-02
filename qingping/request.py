import re
import logging
import datetime
import base64

from http.client import responses
import json as simplejson  # For Python 2.6+
from os import (getenv, path)
from urllib.parse import (parse_qs, quote, urlencode, urlsplit, urlunsplit)
import httplib2

#: Hostname for API access
DEFAULT_QINGPING_URL = "https://apis.cleargrass.com"
DEFAULT_QINGPING_OAUTH = "https://oauth.cleargrass.com"

_LOGGER = logging.getLogger(__name__)

def charset_from_headers(headers):
    """Parse charset from headers.
    :param httplib2.Response headers: Request headers
    :return: Defined encoding, or default to ASCII
    """
    match = re.search("charset=([^ ;]+)", headers.get('content-type', ""))
    if match:
        charset = match.groups()[0]
    else:
        charset = "ascii"
    return charset

class QingPingError(Exception):

    """An error occurred when making a request to the QingPing API."""

class HttpError(RuntimeError):

    """A HTTP error occured when making a request to the QingPing API."""

    def __init__(self, message, content, code):
        """Create a HttpError exception.
        :param str message: Exception string
        :param str content: Full content of HTTP request
        :param int code: HTTP status code
        """
        self.args = (message, content, code)
        self.message = message
        self.content = content
        self.code = code
        if code in responses:
            self.code_reason = responses[code]
        else:
            self.code_reason = "<unknown status code>"
            _LOGGER.warning('Unknown HTTP status %r, please file an issue',
                           code)

class QingPingRequest(object):

    """Make an API request.

    :see: :class:`qingping.client.QingPing`

    """

    url_format = "%(qingping_url)s/%(api_version)s/apis"
    oauth_format = "%(oauth_url)s/oauth2/token"
    api_version = "v1"
    QingPingError = QingPingError

    def __init__(self, app_key, app_secret, requests_per_second=None, url_prefix=None, cache=None):
        self.app_key = app_key
        self.app_secret = app_secret
        self.qingping_url = DEFAULT_QINGPING_URL
        self.url_prefix = url_prefix

        if not self.url_prefix:
            self.url_prefix = self.url_format % {
                "qingping_url": self.qingping_url,
                "api_version": self.api_version,
            }

        self.oauth_url = DEFAULT_QINGPING_OAUTH
        self.oauth_prefix = None

        if not self.oauth_prefix:
            self.oauth_prefix = self.oauth_format % {
                "oauth_url": self.oauth_url,
            }
        self.last_request = datetime.datetime(1900, 1, 1)
        self._http = httplib2.Http(cache=cache, disable_ssl_certificate_validation=True)

    def encode_authentication_data(self, extra_post_data):
        post_data = []

        for key, value in extra_post_data.items():
            if isinstance(value, list):
                for elem in value:
                    post_data.append((key, elem))
            else:
                post_data.append((key, value))

        return urlencode(post_data)

    def get(self, *path_components):
        path_components = filter(None, path_components)
        return self.make_request("/".join(path_components))

    def post(self, *path_components, **extra_post_data):
        path_components = filter(None, path_components)
        return self.make_request("/".join(path_components), extra_post_data,
            method="POST")

    def put(self, *path_components, **extra_post_data):
        path_components = filter(None, path_components)
        return self.make_request("/".join(path_components), extra_post_data,
            method="PUT")

    def delete(self, *path_components, **extra_post_data):
        path_components = filter(None, path_components)
        return self.make_request("/".join(path_components), extra_post_data,
            method="DELETE")

    def make_request(self, path, extra_post_data=None, method="GET"):
        if self.delay:
            since_last = (datetime.datetime.utcnow() - self.last_request)
            if since_last.days == 0 and since_last.seconds < self.delay:
                duration = self.delay - since_last.seconds
                LOGGER.warning("delaying API call %g second(s)", duration)
                time.sleep(duration)

        extra_post_data = extra_post_data or {}
        url = "/".join([self.url_prefix, quote(path)])
        result = self.raw_request(url, extra_post_data, method=method)

        if self.delay:
            self.last_request = datetime.datetime.utcnow()
        return result

    def raw_request(self, url, extra_post_data, method="GET"):
        scheme, netloc, path, query, fragment = urlsplit(url)
        post_data = None
        headers = self.http_headers.copy()

        if self.access_token:
            headers.update({
                "Authorization": f"Bearer {self.access_token}"
            })

        method = method.upper()
        if extra_post_data or method == "POST":
            post_data = self.encode_authentication_data(extra_post_data)
            headers["Content-Length"] = str(len(post_data))
        else:
            query = self.encode_authentication_data(parse_qs(query))
        url = urlunsplit((scheme, netloc, path, query, fragment))
        response, content = self._http.request(url, method, post_data, headers)
        if LOGGER.isEnabledFor(logging.DEBUG):
            logging.debug("URL: %r POST_DATA: %r RESPONSE_TEXT: %r", url,
                          post_data, content)
        if response.status >= 400:
            raise HttpError("Unexpected response from cleargrass.com %d: %r"
                            % (response.status, content), content,
                            response.status)
        json = simplejson.loads(content.decode(charset_from_headers(response)))
        if json.get("error"):
            raise self.QingPingError(json["error"][0]["error"])

        return json

    def get_token(self):
        self.access_token = None

        scheme, netloc, path, query, fragment = urlsplit(self.oauth_prefix)
        post_data = None
        headers = self.http_headers.copy()
        headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Basic " + base64.b64encode(f"{self.app_key}:{self.app_secret}".encode("utf-8")).decode("utf-8")
        })
        extra_post_data = {
            "grant_type": "client_credentials",
            "scope": "device_full_access"
        }

        post_data = self.encode_authentication_data(extra_post_data)
        headers["Content-Length"] = str(len(post_data))

        url = urlunsplit((scheme, netloc, path, query, fragment))
        print(url)
        print(headers)
        print(post_data)
        response, content = self._http.request(url, "POST", post_data, headers)
        _LOGGER.debug("URL: %r POST_DATA: %r RESPONSE_TEXT: %r", url,
                      post_data, content)
        if response.status >= 400:
            raise HttpError("Unexpected response from cleargrass.com %d: %r"
                            % (response.status, content), content,
                            response.status)
        json = simplejson.loads(content.decode(charset_from_headers(response)))
        if json.get("error"):
            raise self.QingPingError(json["error"][0]["error"])

        self.access_token = json["access_token"]

        return json

    @property
    def http_headers(self):
        return {
            "User-Agent": "pyqingping v1",
            "Accept": "application/json",
        }
