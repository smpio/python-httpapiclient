from . import exceptions, ApiRequest, DEFAULT_TIMEOUT


class JsonResponseMixin:
    def clean_response(self, response, request):
        from jsonschema import ValidationError
        from jsonschema import Draft4Validator

        super().clean_response(response, request)
        try:
            result = response.json()
        except ValueError as e:
            raise self.ServerError(e, level='json')

        try:
            schema = request.schema
        except AttributeError:
            raise exceptions.JsonSchemaMissingError()

        try:
            Draft4Validator(schema).validate(result)
        except ValidationError as e:
            raise self.ServerError(e, schema=schema, level='json')

        return result


class HelperMethodsMixinMetaclass(type):
    def __new__(mcs, name, bases, attrs):
        klass = super().__new__(mcs, name, bases, attrs)

        def add_method(name):
            name_upper = name.upper()

            def method(self, path, timeout=DEFAULT_TIMEOUT, **kwargs):
                request = klass.request_class(name_upper, path, **kwargs)
                return self.request(request, timeout=timeout)

            method.__name__ = method_name
            setattr(klass, name, method)

        for method_name in ('get', 'post', 'put', 'delete', 'patch'):
            add_method(method_name)

        return klass


class HelperMethodsMixin(metaclass=HelperMethodsMixinMetaclass):
    request_class = ApiRequest
