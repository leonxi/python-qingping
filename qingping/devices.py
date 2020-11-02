from .core import BaseData, QingPingCommand, Attribute, now_time

class Product(BaseData):

    """Product container."""

    id = Attribute("产品ID（参考 规范说明）")
    name = Attribute("产品名称")
    en_name = Attribute("产品英文名称")

    def __repr__(self):
        return "<Product: %s>" % repr_string(self.title)

class Device(BaseData):

    """Device container."""

    name = Attribute("设备名称")
    mac = Attribute("设备mac地址")
    group_id = Attribute("分组id")
    group_name = Attribute("分组名称")
    status = Attribute("状态")
    version = Attribute("设备版本")
    created_at = Attribute("设备注册时间")
    product = Attribute("产品信息")

    def __repr__(self):
        return "<Device: %s>" % repr_string(self.title)

class Group(BaseData):

    """Group container."""

    id = Attribute("分组id")
    name = Attribute("分组名称")

class Devices(QingPingCommand):

    """QingPing API devices functionality."""

    domain = "devices"

    def bind(self, device_token, product_id):

        """Bind new device."""

        post_data = {
            "device_token": device_token,
            "product_id": product_id,
            "timestamp": str(now_time())
        }

        return self.get_values("", post_data=post_data, type=Device, method="POST")

    def unbind(self, macs):

        """Unbind devices."""

        post_data = {
            "mac": macs,
            "timestamp": str(now_time())
        }

        return self.get_values("", post_data=post_data, type=Device, method="DELETE")

    def list(self, group_id=None, offset=None, limit=50):

        """Get all devices."""

        query_data = {
            "timestamp": str(now_time()),
            "limit": limit
        }

        if group_id:
            query_data["group_id"] = group_id

        if offset:
            query_data["offset"] = offset

        return self.get_values("", query_data=query_data, type=Device, method="GET")

    def data(self, mac, start_time, end_time, offset=None, limit=200):

        """Get device history data."""

        query_data = {
            "mac": mac,
            "start_time": start_time,
            "end_time": end_time,
            "timestamp": str(now_time()),
            "limit": limit
        }

        if offset:
            query_data["offset"] = offset

        return self.get_values("data", query_data=query_data, type=Device, method="GET")

    def events(self, mac, start_time, end_time, offset=None, limit=200):

        """Get device history events."""

        query_data = {
            "mac": mac,
            "start_time": start_time,
            "end_time": end_time,
            "timestamp": str(now_time()),
            "limit": limit
        }

        if offset:
            query_data["offset"] = offset

        return self.get_values("events", query_data=query_data, type=Device, method="GET")

    def settings(self, macs, report_interval, collect_interval):

        """Modify device parameters."""

        post_data = {
            "mac": macs,
            "report_interval": report_interval,
            "collect_interval": collect_interval,
            "timestamp": str(now_time())
        }

        return self.get_values("settings", post_data=post_data, type=Device, method="PUT")

    def groups(self):

        """List groups."""

        query_data = {
            "timestamp": str(now_time())
        }

        return self.get_values("groups", query_data=query_data, type=Group, method="GET")
