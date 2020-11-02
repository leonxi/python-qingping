import logging
import sys

import time
from datetime import datetime
from dateutil import (parser, tz)

_LOGGER = logging.getLogger(__name__)

#: Running under Python 3
PY3K = sys.version_info[0] == 3

#: Running under Python 2.7, or newer
PY27 = sys.version_info[:2] >= (2, 7)

now_time = lambda:int(round(time.time() * 1000))

GITHUB_DATE_FORMAT = "%Y/%m/%d %H:%M:%S %z"
# We need to manually mangle the timezone for commit date formatting because it
# uses -xx:xx format
COMMIT_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
#: GitHub timezone used in API output
GITHUB_TZ = tz.gettz("America/Los_Angeles")

def string_to_datetime(string):
    """Convert a string to Python datetime.

    :param str github_date: date string to parse

    """
    parsed = parser.parse(string)
    if NAIVE:
        parsed = parsed.replace(tzinfo=None)
    return parsed


def _handle_naive_datetimes(f):
    """Decorator to make datetime arguments use GitHub timezone.

    :param func f: Function to wrap

    """
    def wrapper(datetime_):
        if not datetime_.tzinfo:
            datetime_ = datetime_.replace(tzinfo=GITHUB_TZ)
        else:
            datetime_ = datetime_.astimezone(GITHUB_TZ)
        return f(datetime_)
    wrapped = wrapper
    wrapped.__name__ = f.__name__
    wrapped.__doc__ = (
        f.__doc__
        + """\n    .. note:: Supports naive and timezone-aware datetimes"""
    )
    return wrapped


@_handle_naive_datetimes
def datetime_to_ghdate(datetime_):
    """Convert Python datetime to GitHub date string.

    :param datetime datetime_: datetime object to convert

    """
    return datetime_.strftime(GITHUB_DATE_FORMAT)


@_handle_naive_datetimes
def datetime_to_commitdate(datetime_):
    """Convert Python datetime to GitHub date string.

    :param datetime datetime_: datetime object to convert

    """
    date_without_tz = datetime_.strftime(COMMIT_DATE_FORMAT)
    utcoffset = GITHUB_TZ.utcoffset(datetime_)
    hours, minutes = divmod(utcoffset.days * 86400 + utcoffset.seconds, 3600)

    return "".join([date_without_tz, "%+03d:%02d" % (hours, minutes)])


def datetime_to_isodate(datetime_):
    """Convert Python datetime to GitHub date string.

    :param str datetime_: datetime object to convert

    .. note:: Supports naive and timezone-aware datetimes
    """
    if not datetime_.tzinfo:
        datetime_ = datetime_.replace(tzinfo=tz.tzutc())
    else:
        datetime_ = datetime_.astimezone(tz.tzutc())
    return "%sZ" % datetime_.isoformat()[:-6]

def doc_generator(docstring, attributes):
    """Utility function to augment BaseDataType docstring.

    :param str docstring: docstring to augment
    :param dict attributes: attributes to add to docstring

    """
    docstring = docstring or ""

    def bullet(title, text):
        return """.. attribute:: %s\n\n   %s\n""" % (title, text)

    b = "\n".join([bullet(attr_name, attr.help)
                   for attr_name, attr in attributes.items()])
    return "\n\n".join([docstring, b])

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
        query_data = kwargs.get("query_data") or {}
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
            response = self.request.get(self.domain, command, *args,
                                           **query_data)
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
