# 从字符串中提取 CQ 码并封装为对象的辅助工具

import re
from dataclasses import dataclass, field
from typing import Any

from .CQType import CQMessage

# 匹配无参数与有参数的 CQ 码；参数值按 CQ 转义规则编码（裸逗号即分隔符），按逗号切分是安全的
CQ_CODE_PATTERN = re.compile(r"\[CQ:(?P<type>\w+)(?:,(?P<params>[^\]]*))?\]")


@dataclass
class CQTextSegment:
    """消息中两段 CQ 码之间的纯文本，已做 CQ 反转义。"""

    text: str


@dataclass
class CQCodeSegment:
    """消息中的一个 CQ 码，参数值已做 CQ 反转义。"""

    cq_type: str
    params: dict[str, str] = field(default_factory=dict)


def cq_unescape(text: str) -> str:
    """按 CQ 码转义规则还原文本；&amp; 必须最后处理，避免二次反转义。"""
    return (
        text.replace("&#44;", ",").replace("&#91;", "[").replace("&#93;", "]").replace("&amp;", "&")
    )


class CQHelper:
    @classmethod
    def parse_segments(cls, message: str) -> list[CQTextSegment | CQCodeSegment]:
        """
        按原始顺序把 OneBot string 消息拆分为文本段与 CQ 码段。

        与 loads_cq 不同：保留文字与码的交错顺序，参数值与文本都做了 CQ 反转义，
        且支持无参数的码（如 [CQ:face]）。
        :param message: OneBot string 格式的消息
        :return: CQTextSegment / CQCodeSegment 的有序列表
        """
        segments: list[CQTextSegment | CQCodeSegment] = []
        pos = 0
        for m in CQ_CODE_PATTERN.finditer(message):
            if m.start() > pos:
                segments.append(CQTextSegment(cq_unescape(message[pos : m.start()])))
            pos = m.end()

            params: dict[str, str] = {}
            for item in (m.group("params") or "").split(","):
                key, _, value = item.partition("=")
                if key:
                    params[key] = cq_unescape(value)
            segments.append(CQCodeSegment(cq_type=m.group("type"), params=params))

        if pos < len(message):
            segments.append(CQTextSegment(cq_unescape(message[pos:])))
        return segments

    @classmethod
    def load_cq(cls, message: str) -> Any | None:
        """
        动态的封装 一个 记载CQ消息段的所有参数的对象
        :param message: 要实例化的CQ消息段
        :return: 一个实例化对象，可以直接取出其中的成员变量
        """
        # 匹配消息中的类型和属性
        cq_pattern = re.compile(r"\[CQ:(\w+),([^\]]+)\]")
        match = cq_pattern.search(message)

        if not match:
            return None

        cq_type = match.group(1)
        attrs = match.group(2)

        instance = CQMessage()
        instance.cq_type = cq_type

        # 改进的属性解析逻辑
        for attr in re.finditer(r"(\w+)=([^,]+)", attrs):
            key = attr.group(1)
            value = attr.group(2)
            setattr(instance, key, value)

        return instance

    @classmethod
    def loads_cq(cls, message: str) -> list[Any]:
        """
        :param message:
        :return:
        """
        cq_pattern = re.compile(r"\[CQ:(\w+),([^\]]+)\]")
        matches = cq_pattern.findall(message)

        cq_objects = []
        for match in matches:
            cq_msg = f"[CQ:{match[0]},{match[1]}]"
            cq_obj = cls.load_cq(cq_msg)
            if cq_obj:
                cq_objects.append(cq_obj)

        return cq_objects


if __name__ == "__main__":
    from CQType import At, Image

    # 示例
    msg1 = "[CQ:at,qq=12345]"
    msg2 = "[CQ:image,file=000001464e61704361744f6e65426f747c4d736746696c657c327c3832343339353639347c373437343937323537313739383632393630317c373437343937323537313739383632393630307c4568526b454e78706232347050334e52697472675f317934726e38686778694b2d6763675f776f6f383479656d62486369774d794248427962325251674c326a41566f51794a3643355f54536d477a372d2d572d444e70516251.28AFC869F0CB651D610615D38EE5BA9D.jpg,sub_type=0,file_id=000001464e61704361744f6e65426f747c4d736746696c657c327c3832343339353639347c373437343937323537313739383632393630317c373437343937323537313739383632393630307c4568526b454e78706232347050334e52697472675f317934726e38686778694b2d6763675f776f6f383479656d62486369774d794248427962325251674c326a41566f51794a3643355f54536d477a372d2d572d444e70516251.28AFC869F0CB651D610615D38EE5BA9D.jpg,url=https://multimedia.nt.qq.com.cn/download?appid=1407&amp;fileid=EhRkENxpb24pP3NRitrg_1y4rn8hgxiK-gcg_woo84yembHciwMyBHByb2RQgL2jAVoQyJ6C5_TSmGz7--W-DNpQbQ&amp;rkey=CAMSKMa3OFokB_Tl0f1oi0l7bE5CbT9uUjCKKVc_Ds0itNrRC-k5vajv7V4,file_size=130314,file_unique=28afc869f0cb651d610615d38ee5ba9d]"
    msg3 = "123[CQ:image,file=xx/xx]321"
    msg4 = "123[CQ321]"

    obj1: At = CQHelper.load_cq(msg1)
    obj2: Image = CQHelper.load_cq(msg2)
    obj3: Image = CQHelper.load_cq(msg3)
    obj4 = CQHelper.load_cq(msg4)

    print(obj1.cq_type)  # at
    print(obj2.__dict__)  # {'cq_type': 'image', 'file': 'xx/xx'}
    print(obj3.file)  # xx/xx
    print(obj4)  # None

    msg5 = "123[CQ:image,file=xx/xx]321[CQ:at,qq=12345]456"
    msg6 = "123[]ewq[]231"

    obj5 = CQHelper.loads_cq(msg5)
    obj6 = CQHelper.loads_cq(msg6)

    for obj in obj5:
        print(obj.__dict__)
        # {'cq_type': 'image', 'file': 'xx/xx'}, {'cq_type': 'at', 'qq': '12345'}
    for obj in obj6:
        print(obj)  # 什么都没有
