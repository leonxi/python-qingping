from .core import BaseData, QingPingCommand, now_time

class Device(BaseData):

    """Device container."""

    name = Attribute("")
    name = Attribute("")
    name = Attribute("")
    name = Attribute("")
    name = Attribute("")
    name = Attribute("")
    timestamp = Attribute("毫秒级时间戳(13位) 20s内有效,同一个请求不可重复")
    group_id = Attribute("分组id")
    offset = Attribute("偏移量")
    limit = Attribute("最大返回数据条数 不得超过50")

    def __repr__(self):
        return "<Device: %s>" % repr_string(self.title)

class Devices(QingPingCommand):

    """QingPing API devices functionality."""

    domain = "devices"

    def list(self, group_id=None, offset=None, limit=50)
        """Get all devices."""
        timestamp = now_time()
        return self.get_values("", str(timestamp), datatype=Device, method="GET")
