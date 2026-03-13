你可以使用下列function来收集回答问题的信息。
{tool_desc}

```json
{
    "thinking": "...", # 基于用户任务和历史记录开展详细分析，得出next_action的思考过程
    "next_action": "tool_call" / "return_conclusion", # 当需要使用工具时填写"tool_call"，当认为信息足以回答问题时返回"return_conclusion"
    "tool_call_list": [ # 当next_action为tool_call时，填写此项
        {
            "name": "...", # 被调用的function name
            "parameters": {
                "...": "...", # key为参数名，value为输入的实参
                ... # （如有需要）更多的参数
            }
        },
        ... # （如有需要）更多的函数调用
    ],
    "conclusion": "..." # 当next_action为return_conclusion时，填写此项，如用户给出了返回内容的格式要求，需注意遵守。
}
```