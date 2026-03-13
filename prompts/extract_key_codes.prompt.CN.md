下列代码属于{function_name}函数，请基于调用图信息识别当前函数的下一跳函数有哪些，然后找出调用下一跳函数之前的代码内容，最终根据下列关注点针对找到的代码内容开展分析：
- {focuses}

```python
{func_body}
```

分析结果成下列格式：
```json
{  
    "thinking": "...", # 根据关注点，针对codes_before_callee中的代码开展思考、分析
    "taint_propagation_analysis": "...", # 分析当前函数代码是否产生了污点源或者对污点数据进行了传播（仅限当前函数代码范围），注意回答内容要结合具体代码    
    "is_taint_propagation": true/false, # 如当前函数代码中包含了污点产生或传播的代码，则为true
    "security_sanitizer_analysis": "...", # 分析当前函数代码是否针对vulnerable_sink对应的漏洞进行了安全消毒，以及消毒措施是否能完全防止漏洞发生
    "is_security_sanitizer": true/false, # 如当前函数代码中包含了针对vulnerable_sink对应漏洞的安全消毒措施，则为true
    "summary": "...", # 对当前函数的代码进行总结分析（基于上述分析的精炼内容）
    "key_codes_in_function": "..."  # 字符串格式。包含当前函数的关键代码，并在每行代码行尾进行逐行注释。这里关键代码的的范围是：1. 函数定义语句（只包含疑似参与污点传播的变量，其他变量用...表示）、2. 图中下游函数的调用语句、3. security_sanitizer_analysis、taint_propagation_analysis、summary分析过程提到的代码。对于其他代码、不涉及的参数声明一概用'...'表示。***注意，如果代码语句中包含了会影响本json格式解析的字符，应注意进行转移处理！！！***
}
```

***注意*** ：
- 注意回答内容要结合具体代码，如"根据`a = foo()`语句可知a来自于foo函数的返回"