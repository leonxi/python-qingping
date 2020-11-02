import logging

from .request import QingPingRequest

class QingPing(object):

    """Interface to QingPing's API v1."""
    def __init__(self, app_key=None, app_secret=None, requests_per_second=None):

        self.request = QingPingRequest(app_key=app_key, app_secret=app_secret, requests_per_second=requests_per_second)

        token = self.request.get_token()

        print(token)
