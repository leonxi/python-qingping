import logging
import sys

_LOGGER = logging.getLogger(__name__)

#: Running under Python 3
PY3K = sys.version_info[0] == 3

#: Running under Python 2.7, or newer
PY27 = sys.version_info[:2] >= (2, 7)

now_time = lambda:int(round(t * 1000))

class Attribute(object):

    """Generic object attribute for use with :class:`BaseData`."""

    def __init__(self, help):
        """Setup Attribute object.
        :param str help: Attribute description
        """
        self.help = help

    def to_python(self, value):
        return value

    from_python = to_python

class DateAttribute(Attribute):

    """Date handling attribute for use with :class:`BaseData`."""

    format = "github"
    converter_for_format = {
        "github": datetime_to_ghdate,
        "commit": datetime_to_commitdate,
        "user": datetime_to_ghdate,
        "iso": datetime_to_isodate,
    }

    def __init__(self, *args, **kwargs):
        """Setup DateAttribute object.
        :param str format: The date format to support, see
            :data:`convertor_for_format` for supported options
        """
        self.format = kwargs.pop("format", self.format)
        super(DateAttribute, self).__init__(*args, **kwargs)

    def to_python(self, value):
        if value and not isinstance(value, datetime):
            return string_to_datetime(value)
        return value

    def from_python(self, value):
        if value and isinstance(value, datetime):
            return self.converter_for_format[self.format](value)
        return value

class BaseDataType(type):

    def __new__(cls, name, bases, attrs):
        super_new = super(BaseDataType, cls).__new__

        _meta = dict([(attr_name, attr_value)
                      for attr_name, attr_value in attrs.items()
                      if isinstance(attr_value, Attribute)])
        attrs["_meta"] = _meta
        attributes = _meta.keys()
        attrs.update(dict([(attr_name, None) for attr_name in attributes]))

        def _contribute_method(name, func):
            func.__name__ = name
            attrs[name] = func

        def constructor(self, **kwargs):
            for attr_name, attr_value in kwargs.items():
                attr = self._meta.get(attr_name)
                if attr:
                    setattr(self, attr_name, attr.to_python(attr_value))
                else:
                    setattr(self, attr_name, attr_value)
        _contribute_method("__init__", constructor)

        def iterate(self):
            not_empty = lambda e: e[1] is not None
            return iter(filter(not_empty, vars(self).items()))
        _contribute_method("__iter__", iterate)

        result_cls = super_new(cls, name, bases, attrs)
        result_cls.__doc__ = doc_generator(result_cls.__doc__, _meta)
        return result_cls

class BaseData(BaseDataType('BaseData', (object, ), {})):

    """Wrapper for API responses.
    .. warning::
       Supports subscript attribute access purely for backwards compatibility,
       you shouldn't rely on that functionality in new code
    """

    def __getitem__(self, key):
        """Access objects's attribute using subscript notation.
        This is here purely to maintain compatibility when switching ``dict``
        responses to ``BaseData`` derived objects.
        """
        _LOGGER.warning("Subscript access on %r is deprecated, use object "
                       "attributes" % self.__class__.__name__)
        if not key in self._meta.keys():
            raise KeyError(key)
        return getattr(self, key)

    def __setitem__(self, key, value):
        """Update object's attribute using subscript notation.
        :see: :meth:`BaseData.__getitem__`
        """
        _LOGGER.warning("Subscript access on %r is deprecated, use object "
                       "attributes" % self.__class__.__name__)
        if not key in self._meta.keys():
            raise KeyError(key)
        setattr(self, key, value)

class QingPingCommand(object):

    """Main API binding interface."""

    def __init__(self, request):
        """Setup command object.
        :param qingping.request.QingPingRequest request: HTTP request handler
        """
        self.request = request

    def make_request(self, command, *args, **kwargs):
        """Make an API request.
        Various options are supported if they exist in ``kwargs``:
        * The value of a ``method`` argument will define the HTTP method
          to perform for this request, the default is ``GET``
        * The value of a ``filter`` argument will restrict the response to that
          data
        * The value of a ``page`` argument will be used to fetch a specific
          page of results, default of 1 is assumed if not given
        """
        filter = kwargs.get("filter")
        post_data = kwargs.get("post_data") or {}
        page = kwargs.pop("page", 1)
        if page and not page == 1:
            post_data["page"] = page
        method = kwargs.get("method", "GET").upper()
        if method == "POST" or method == "GET" and post_data:
            response = self.request.post(self.domain, command, *args,
                                         **post_data)
        elif method == "PUT":
            response = self.request.put(self.domain, command, *args,
                                        **post_data)
        elif method == "DELETE":
            response = self.request.delete(self.domain, command, *args,
                                           **post_data)
        else:
            response = self.request.get(self.domain, command, *args)
        if filter:
            return response[filter]
        return response

    def get_value(self, *args, **kwargs):
        """Process a single-value response from the API.
        If a ``datatype`` parameter is given it defines the
        :class:`BaseData`-derived class we should build from the provided data
        """
        datatype = kwargs.pop("datatype", None)
        value = self.make_request(*args, **kwargs)
        if datatype:
            if not PY27:
                # unicode keys are not accepted as kwargs by python, until 2.7:
                # http://bugs.python.org/issue2646
                # So we make a local dict with the same keys but as strings:
                return datatype(**dict((str(k), v)
                                       for (k, v) in value.items()))
            else:
                return datatype(**value)
        return value

    def get_values(self, *args, **kwargs):
        """Process a multi-value response from the API.
        :see: :meth:`get_value`
        """
        datatype = kwargs.pop("datatype", None)
        values = self.make_request(*args, **kwargs)
        if datatype:
            if not PY27:
                # Same as above, unicode keys will blow up in **args, so we
                # need to create a new 'values' dict with string keys
                return [datatype(**dict((str(k), v)
                                        for (k, v) in value.items()))
                        for value in values]
            else:
                return [datatype(**value) for value in values]
        else:
            return values
