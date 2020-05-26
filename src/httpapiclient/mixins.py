from . import utils, exceptions, ApiRequest, DEFAULT_TIMEOUT


class JsonResponseMixin:
    def clean_response(self, response, request):
        try:
            super().clean_response(response, request)
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

        result = super().clean_response(response, request)
        if request.raw_response:
            return result

        try:
            schema = request.schema
        except AttributeError:
            raise exceptions.JsonSchemaMissingError()

        try:
            Draft4Validator(schema).validate(result)
        except ValidationError as e:
            raise self.ServerError(reason=e, schema=schema, level='json')

        return result


class HelperMethodsMixin:
    request_class = ApiRequest

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def add_method(name):
            name_upper = name.upper()

            def method(path, timeout=DEFAULT_TIMEOUT, **kwargs):
                request = self.request_class(name_upper, path, **kwargs)
                return self.request(request, timeout=timeout)

            method.__name__ = method_name
            setattr(self, name, method)

        for method_name in ('head', 'get', 'post', 'put', 'delete', 'patch'):
            add_method(method_name)
