import time
import logging
import urllib.parse

import requests

from .exceptions import ApiClientError, ApiServerError

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = type('DEFAULT_TIMEOUT', (), {})()


class BaseApiClientMetaclass(type):
    def __new__(mcs, name, bases, attrs):
        klass = super().__new__(mcs, name, bases, attrs)

        class ClientError(ApiClientError):
            client_class = klass

        class ServerError(ApiServerError):
            client_class = klass

        class NotFoundError(ClientError):
            pass

        klass.ClientError = ClientError
        klass.ServerError = ServerError
        klass.NotFoundError = NotFoundError

        return klass


class BaseApiClient(metaclass=BaseApiClientMetaclass):
    base_url = None
    default_timeout = 6.1  # slightly larger than a multiple of 3, which is the default TCP packet retransmission window
    max_tries = 3
    retry_backoff_factor = 0.5

    def __init__(self):
        self.session = requests.session()

    def request(self, request, timeout=DEFAULT_TIMEOUT):
        request.url = urllib.parse.urljoin(self.base_url, request.url)
        prepared = self.session.prepare_request(request)

        if timeout is DEFAULT_TIMEOUT:
            timeout = self.default_timeout

        errors = []
        backoff_time = self.retry_backoff_factor
        for try_idx in range(self.max_tries):
            log.debug('Trying request %s %s (%d/%d tries)', request.method, request.url, try_idx + 1, self.max_tries)

            if try_idx > 0:
                time.sleep(backoff_time)
                backoff_time *= 2

            try:
                return self._request_once(request, prepared, timeout)
            except self.ClientError as e:
                if e.permanent:
                    raise e
                log.debug('Request failed: %r', e)
                errors.append(e)
            except self.ServerError as e:
                if not request.is_idempotent and e.has_side_effects:
                    raise e
                log.debug('Request failed: %r', e)
                errors.append(e)

        raise errors[-1]

    def _request_once(self, request, prepeared, timeout):
        try:
            response = self.session.send(prepeared, timeout=timeout)
        except requests.ConnectTimeout as e:
            raise self.ServerError(level='socket', reason=e, has_side_effects=False)
        except requests.ConnectionError as e:
            raise self.ServerError(level='socket', reason=e)
        except requests.ReadTimeout as e:
            raise self.ServerError(level='socket', reason=e)
        except requests.TooManyRedirects as e:
            raise self.ServerError(level='security', reason=e)

        return self.clean_response(response, request)

    def clean_response(self, response, request):
        """
        TODO: add general doc here

        If raised ClientError has attribute permanent=False then request may be retried even for
        non-idempotent request. For example - rate limit error.

        If raised ServerError has attribute has_side_effects=False then request may be retried even for
        non-idempotent request. For example - http 503.
        """
        code = response.status_code
        trace_id = response.headers.get('X-Trace-ID')
        err_class = None

        if 400 <= code < 500:
            if code == 404:
                err_class = self.NotFoundError
            else:
                err_class = self.ClientError
        elif 500 <= code < 600:
            err_class = self.ServerError

        if err_class:
            raise err_class(level='http', code=code, status_text=response.reason, content=response.content,
                            trace_id=trace_id)

        if request.raw_response:
            return response
        else:
            return response.content
