"""CQHelper.parse_segments 与 cq_unescape 的单元测试。"""

from utils.CQHelper import CQCodeSegment, CQHelper, CQTextSegment, cq_unescape


def test_cq_unescape_restores_all_escapes():
    assert cq_unescape("&#44;") == ","
    assert cq_unescape("&#91;") == "["
    assert cq_unescape("&#93;") == "]"
    assert cq_unescape("a&amp;b") == "a&b"


def test_cq_unescape_amp_must_be_last():
    # 转义过的字面量 "&#91;" 本身不应被二次还原为 "["
    assert cq_unescape("&amp;#91;") == "&#91;"


def test_parse_segments_preserves_text_and_code_order():
    message = "登录报500[CQ:image,file=shot.image,url=https://qq/img]看下[CQ:at,qq=10001]谢谢"
    segments = CQHelper.parse_segments(message)

    assert [type(s).__name__ for s in segments] == [
        "CQTextSegment",
        "CQCodeSegment",
        "CQTextSegment",
        "CQCodeSegment",
        "CQTextSegment",
    ]
    assert segments[0].text == "登录报500"
    assert segments[1].cq_type == "image"
    assert segments[1].params["url"] == "https://qq/img"
    assert segments[2].text == "看下"
    assert segments[3].params["qq"] == "10001"
    assert segments[4].text == "谢谢"


def test_parse_segments_unescapes_param_values():
    # 真实 NTQQ 场景：url 中的 & 会被转义成 &amp;
    message = "[CQ:image,url=https://multimedia.nt.qq.com.cn/download?appid=1407&amp;rkey=abc]"
    segments = CQHelper.parse_segments(message)

    assert segments[0].params["url"] == (
        "https://multimedia.nt.qq.com.cn/download?appid=1407&rkey=abc"
    )


def test_parse_segments_supports_code_without_params():
    segments = CQHelper.parse_segments("hi[CQ:face]!")

    assert [type(s).__name__ for s in segments] == [
        "CQTextSegment",
        "CQCodeSegment",
        "CQTextSegment",
    ]
    assert segments[1].cq_type == "face"
    assert segments[1].params == {}


def test_parse_segments_param_without_value_maps_to_empty_string():
    segments = CQHelper.parse_segments("[CQ:shuffle,flag]")

    assert segments[0].params == {"flag": ""}


def test_parse_segments_consecutive_codes_have_no_empty_text():
    segments = CQHelper.parse_segments("[CQ:at,qq=1][CQ:at,qq=2]后缀")

    assert [type(s).__name__ for s in segments] == [
        "CQCodeSegment",
        "CQCodeSegment",
        "CQTextSegment",
    ]
    assert segments[0].params["qq"] == "1"
    assert segments[2].text == "后缀"


def test_parse_segments_unescapes_text_parts():
    segments = CQHelper.parse_segments("数组写法 a&#91;0&#93;[CQ:face]逗号&#44;分号")

    assert segments[0].text == "数组写法 a[0]"
    assert segments[2].text == "逗号,分号"


def test_loads_cq_legacy_api_still_extracts_codes():
    cqs = CQHelper.loads_cq("123[CQ:image,file=xx/xx]321[CQ:at,qq=12345]456")

    assert [cq.cq_type for cq in cqs] == ["image", "at"]
    assert cqs[0].file == "xx/xx"
    assert isinstance(cqs[0], object) and not isinstance(cqs[0], CQCodeSegment | CQTextSegment)
