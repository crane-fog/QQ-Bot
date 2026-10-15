from collections.abc import Callable
from typing import Literal, TypedDict

from openai.types.chat import ChatCompletionToolUnionParam

import src.agent.Tools as Tool
from src.Api import api


class ToolDef(TypedDict):
    func: Callable
    type: Literal["default", "async", "image", "travily", "restricted"]
    declaration: ChatCompletionToolUnionParam


tool_defs: list[ToolDef] = [
    {
        "func": api.asyncPrivateService.send_private_msg,
        "type": "async",
        "declaration": {
            "type": "function",
            "function": {
                "name": "send_private_msg",
                "strict": False,
                "description": "Send a private message to a user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "integer",
                            "description": "The user ID of the recipient.",
                        },
                        "message": {
                            "type": "string",
                            "description": "The message content to send.",
                        },
                    },
                    "required": ["user_id", "message"],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": api.asyncGroupService.send_group_msg,
        "type": "async",
        "declaration": {
            "type": "function",
            "function": {
                "name": "send_group_msg",
                "strict": False,
                "description": "Send a message to a group. Be aware that your output will always be sent to the current group by default, so you should only use this tool when you have to send multiple messages to the current group. You shouldn't send messages to other groups unless necessary.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_id": {
                            "type": "integer",
                            "description": "The group ID to send the message to.",
                        },
                        "message": {"type": "string", "description": "The message to send."},
                    },
                    "required": ["group_id", "message"],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": api.asyncGroupService.get_group_member_list,
        "type": "async",
        "declaration": {
            "type": "function",
            "function": {
                "name": "get_group_member_list",
                "strict": False,
                "description": "Get the list of members in a group. Be careful when using this tool, as it may return a large amount of data.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_id": {
                            "type": "integer",
                            "description": "The group ID to retrieve members from.",
                        },
                        "no_cache": {
                            "type": "boolean",
                            "description": "Whether to bypass the cache and fetch fresh data. Defaults to true.",
                        },
                    },
                    "required": ["group_id"],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": api.asyncGroupService.get_group_member_info,
        "type": "async",
        "declaration": {
            "type": "function",
            "function": {
                "name": "get_group_member_info",
                "strict": False,
                "description": "Get information about a specific member in a group.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_id": {
                            "type": "integer",
                            "description": "The group ID where the member is located.",
                        },
                        "user_id": {
                            "type": "integer",
                            "description": "The user ID of the member to retrieve information for.",
                        },
                        "no_cache": {
                            "type": "boolean",
                            "description": "Whether to bypass the cache and fetch fresh data. Defaults to true.",
                        },
                    },
                    "required": ["group_id", "user_id"],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": api.asyncGroupService.set_group_ban,
        "type": "async",
        "declaration": {
            "type": "function",
            "function": {
                "name": "set_group_ban",
                "strict": False,
                "description": "Ban a user in a group, the user will not be able to send messages in the group for a certain period of time. You can unset the ban by use duration 0. You should prudently use this tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "integer",
                            "description": "The user ID of the person to ban.",
                        },
                        "group_id": {
                            "type": "integer",
                            "description": "The group ID where the ban will be applied.",
                        },
                        "duration": {
                            "type": "integer",
                            "description": "The duration of the ban in seconds. Must be in the range of 0 to 2592000.",
                        },
                    },
                    "required": ["user_id", "group_id", "duration"],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": api.asyncGroupService.set_group_kick,
        "type": "async",
        "declaration": {
            "type": "function",
            "function": {
                "name": "set_group_kick",
                "strict": False,
                "description": "Kick a user from a group. You should prudently use this tool. Use this tool may cause serious consequences. ONLY USE THIS TOOL WHEN ADMINISTRATORS OR YOUR OWNER REQUESTS YOU TO DO SO.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_id": {
                            "type": "integer",
                            "description": "The group ID where the kick will be applied.",
                        },
                        "user_id": {
                            "type": "integer",
                            "description": "The user ID of the person to kick.",
                        },
                    },
                    "required": ["group_id", "user_id"],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": api.asyncGroupService.delete_msg,
        "type": "async",
        "declaration": {
            "type": "function",
            "function": {
                "name": "delete_msg",
                "strict": False,
                "description": "Delete / Recall a group message by its ID. The message will be deleted for all users in the group. You should prudently use this tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message_id": {
                            "type": "integer",
                            "description": "The ID of the message to delete.",
                        }
                    },
                    "required": ["message_id"],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": api.asyncGroupService.get_group_info,
        "type": "async",
        "declaration": {
            "type": "function",
            "function": {
                "name": "get_group_info",
                "strict": False,
                "description": "Get information about a specific group.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_id": {
                            "type": "integer",
                            "description": "The group ID to retrieve information for.",
                        }
                    },
                    "required": ["group_id"],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": api.asyncGroupService.set_msg_emoji_like,
        "type": "async",
        "declaration": {
            "type": "function",
            "function": {
                "name": "set_msg_emoji_like",
                "strict": False,
                "description": "Like an emoji on a message.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message_id": {
                            "type": "integer",
                            "description": "The ID of the message to like.",
                        },
                        "emoji_id": {
                            "type": "string",
                            "description": "The ID of the emoji to like.",
                        },
                    },
                    "required": ["message_id", "emoji_id"],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": api.asyncGroupService.send_group_poke,
        "type": "async",
        "declaration": {
            "type": "function",
            "function": {
                "name": "send_group_poke",
                "strict": False,
                "description": "Send a poke to a user in a group.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_id": {
                            "type": "integer",
                            "description": "The group ID where the poke will be sent.",
                        },
                        "user_id": {
                            "type": "integer",
                            "description": "The user ID of the person to poke.",
                        },
                    },
                    "required": ["group_id", "user_id"],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": api.asyncMessageService.get_msg,
        "type": "async",
        "declaration": {
            "type": "function",
            "function": {
                "name": "get_msg",
                "strict": False,
                "description": "Get the content of a message by its ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message_id": {
                            "type": "integer",
                            "description": "The ID of the message to retrieve.",
                        }
                    },
                    "required": ["message_id"],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": Tool.restricted_shell,
        "type": "restricted",
        "declaration": {
            "type": "function",
            "function": {
                "name": "shell",
                "strict": False,
                "description": "Execute a shell command on the server. This tool is restricted to the owner of the bot. You should prudently use this tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cmd": {"type": "string", "description": "The shell command to execute."}
                    },
                    "required": ["cmd"],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": Tool.read_img_file,
        "type": "image",
        "declaration": {
            "type": "function",
            "function": {
                "name": "read_img_file",
                "strict": False,
                "description": "Read an image file with its full path or URL. You must provide one of the two parameters.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "The path of the image file to read.",
                        },
                        "url": {"type": "string", "description": "The URL of the image to read."},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": Tool.travily_search,
        "type": "travily",
        "declaration": {
            "type": "function",
            "function": {
                "name": "travily_search",
                "strict": False,
                "description": "Search the web for information using the Travily API.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to execute with Tavily.",
                        },
                        "chunks_per_source": {
                            "type": "integer",
                            "description": "Chunks are short content snippets (maximum 500 characterseach) pulled directly from the source. Use`chunks_per_source` to define the maximum number of relevant chunks returned per source and to control the `content` length. Chunks will appear in the `content` field as: `<chunk 1> [...] <chunk 2> [...] <chunk 3>`. Available only when `search_depth` is `advanced`.\ndefault: 3\nminimum: 1\nmaximum: 3",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "The maximum number of search results to return.\ndefault: 5\nminimum: 0\nmaximum: 20",
                        },
                        "topic": {
                            "type": "string",
                            "description": "The category of the search.`news` is useful for retrieving real-time updates, particularly about politics, sports, and major current events covered by mainstream media sources. `general` is for broader, more general-purpose searches that may include a wide range of sources.\ndefault: general\nenum:\n- general\n- news\n- finance",
                        },
                        "exact_match": {
                            "type": "boolean",
                            "description": 'Ensure that only search results containing the exact quoted phrase(s) in the query are returned, bypassing synonyms or semantic variations. Wrap target phrases in quotes within your query (e.g. `"John Smith" CEO Acme Corp`). Punctuation is typically ignored inside quotes.\ndefault: False',
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": Tool.travily_extract,
        "type": "travily",
        "declaration": {
            "type": "function",
            "function": {
                "name": "travily_extract",
                "strict": False,
                "description": "Extract web page content from one or more specified URLs using the Tavily API.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "urls": {
                            "type": "string",
                            "description": "The URL to extract content from.",
                        },
                        "query": {
                            "type": "string",
                            "description": "User intent for reranking extracted content chunks. When provided, chunks are reranked based on relevance to this query.\ndefault: null",
                        },
                        "chunks_per_source": {
                            "type": "integer",
                            "description": "Chunks are short content snippets (maximum 500 characterseach) pulled directly from the source. Use`chunks_per_source` to define the maximum number of relevant chunks returned per source and to control the `content` length. Chunks will appear in the `content` field as: `<chunk 1> [...] <chunk 2> [...] <chunk 3>`. Available only when `search_depth` is `advanced`.\ndefault: 3\nminimum: 1\nmaximum: 5",
                        },
                    },
                    "required": ["urls"],
                    "additionalProperties": False,
                },
            },
        },
    },
    {
        "func": Tool.set_notification,
        "type": "default",
        "declaration": {
            "type": "function",
            "function": {
                "name": "set_notification",
                "strict": False,
                "description": "Set a notification message to be sent after a specified wait time. You may use [CQ:at,id=123456] to mention specific users in the notification message. Be aware that the message will be later sent by yourself, so you should keep your persona.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "wait_time": {
                            "type": "integer",
                            "description": "The time in seconds to wait before sending the notification.",
                        },
                        "msg": {
                            "type": "string",
                            "description": "The notification message to send.",
                        },
                        "group_id": {
                            "type": "integer",
                            "description": "The group ID where the notification will be sent.",
                        },
                    },
                    "required": ["wait_time", "msg", "group_id"],
                    "additionalProperties": False,
                },
            },
        },
    },
]
