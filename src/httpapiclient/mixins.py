from __future__ import print_function, division, absolute_import, unicode_literals
from . import utils, exceptions, ApiRequest, DEFAULT_TIMEOUT


class JsonResponseMixin(object):
    def clean_response(self, response, request):
        try:
            super(JsonResponseMixin, self).clean_response(response, request)
        except exceptions.ApiError as err:
            if utils.get_content_type(response) == 'application/json':
                try:
                    err.data = response.json()
                except ValueError:
                    pass
            raise err

        if request.raw_response:
            return response
        elif utils.get_content_type(response) == 'application/json':
            try:
                return response.json()
            except ValueError as e:
                raise self.ServerError(e, level='json')
        else:
            return response.content


class JsonSchemaResponseMixin(JsonResponseMixin):
    def clean_response(self, response, request):
        from jsonschema import ValidationError
        from jsonschema import Draft4Validator

        result = super(JsonSchemaResponseMixin, self).clean_response(response, request)
        if request.raw_response:
            return result

        try:
            schema = request.schema
        except AttributeError:
            raise exceptions.JsonSchemaMissingError()

        try:
            Draft4Validator(schema).validate(result)
        except ValidationError as e:
            raise self.ServerError(e, schema=schema, level='json')

        return result


class HelperMethodsMixin(object):
    request_class = ApiRequest

    def __init__(self, *args, **kwargs):
        super(HelperMethodsMixin, self).__init__(*args, **kwargs)

        def add_method(name):
            name_upper = name.upper()

            def method(path, timeout=DEFAULT_TIMEOUT, **kwargs):
                request = self.request_class(name_upper, path, **kwargs)
                return self.request(request, timeout=timeout)

            method.func_name = method_name
            setattr(self, name, method)

        for method_name in (b'get', b'post', b'put', b'delete', b'patch'):
            add_method(method_name)
