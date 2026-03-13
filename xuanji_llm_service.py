from typing import Any, List, Optional, Iterator
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    AIMessage,
    HumanMessage,
    SystemMessage,
    AIMessageChunk,
    ToolMessage
)
from langchain_core.outputs import ChatGeneration, ChatResult, ChatGenerationChunk
from pydantic import Field, ConfigDict
import uuid
import base64
import requests
from PIL import Image
import io
import re

import uuid
import time
import requests
import base64
import random
import string
import time
import hashlib
import hmac
import base64
import urllib.parse
from PIL import Image
import base64
import os
import time

from PIL import Image
import  uuid
import requests
import json
import pandas as pd
from tqdm import tqdm
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from typing import Sequence, Union
from langchain_core.tools import BaseTool
from langchain_core.messages.tool import ToolCall
from langchain_core.messages.ai import UsageMetadata
import logging
from evaluation_context import get_context

logger = logging.getLogger(__name__)

LLM_SERVICE_INFO = {
}

def advanced_json_loader(text):
    try:
        if("</think>" in text):
            text = text.split("</think>")[-1]

        # 匹配第一个 ```json 和最后一个 ``` 之间的内容，前后可以有任意文本
        pattern = r'```json\s*(.*)\s*```'
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            text = match.group(1)
        return json.loads(text)
    except Exception as e:
        """修复JSON中的嵌套引号问题"""
        # 先找到所有可能有问题的字符串
        lines = text.split('\n')
        fixed_lines = []
        
        for line in lines:
            # 检查是否包含可能的嵌套引号问题
            if line.count('"') > 2 and ':' in line:
                # 找到冒号后的值部分
                if ':' in line:
                    key_part, value_part = line.split(':', 1)
                    # 如果值部分包含多个引号，进行修复
                    if value_part.count('"') > 2:
                        # 简单的修复策略：将值部分中间的引号转义
                        value_part = value_part.strip()
                        if value_part.startswith('"') and value_part.endswith('"') or value_part.endswith('",'):
                            # 提取实际内容
                            if value_part.endswith('",'):
                                end_part = '",'
                                content = value_part[1:-2]
                            else:
                                end_part = '"'
                                content = value_part[1:-1]
                            
                            # 转义内部引号
                            escaped_content = content.replace('"', '\\"')
                            value_part = f'"{escaped_content}{end_part}'
                    
                    line = key_part + ':' + value_part
            fixed_lines.append(line)
        text = '\n'.join(fixed_lines)
        try:
            return json.loads(text)
        except Exception as e:
            return None

# 随机字符串
def gen_nonce(length=8):
    chars = string.ascii_lowercase + string.digits
    return ''.join([random.choice(chars) for _ in range(length)])


# 如果query项只有key没有value时，转换成params[key] = ''传入
def gen_canonical_query_string(params):
    if params:
        escape_uri = urllib.parse.quote
        raw = [(escape_uri(k), escape_uri(str(params[k])) if isinstance(params[k], (int, float)) else escape_uri(params[k]))
            for k in sorted(params.keys())]
        s = "&".join("=".join(kv) for kv in raw )
        return s
    else:
        return ''

class XuanjiChatModel(BaseChatModel):
    
    def _call_api(self, formatted_messages: List[dict], tools: List[dict] = None) -> str:
        """调用玄机 API"""
        
        ctx = get_context()
        test_flag = ctx.get('current_test', "")

        try:
            # # DEBUG 输出当前调用工具时使用的prompt
            # for item in data["messages"]:
            #     if "content_type" in item and item["content_type"] != "image":
            #         print(item)
            #     if "content_type" in item and item["content_type"] == "image":
            #         print(len(item['content']))
            
                    
            response = self.session.post(
                url,
                json=data,
                headers=headers,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()

            content = result.get('data', {}).get('content', '')
            ret = json.loads(content)[0]["text"]

            # EVALUATION 做n hop实验用的
            if test_flag == 'n_hop':
                if not ctx:
                    logger.warning("[WARN] No context found for N-Hop logging")

                png_name = ctx.get("png_name", "unknown").replace('.png', '')
                start_time = ctx.get("start_time", 0)
                
                # 构造这条记录的数据对象
                record = {
                    "pngName": png_name,   # 图片名/测试用例ID
                    "modelName": self.model_name,  # 模型名称
                    "inputFormat": "text" if self.use_text_mode else "image", # 模态
                    "usage": {  # Token 消耗
                        "promptTokens": result['data']['usage']['promptTokens'],
                        "completionTokens": result['data']['usage']['completionTokens'],
                        "totalTokens": result['data']['usage']['totalTokens']
                    },
                    "passedHop": ctx.get("n_hops"),
                    "response": ret
                }

                
                # 记录本次实验结果
                output_path = f"evaluations/image_vs_text/n_hop/{self.model_name}/{'image' if not self.use_text_mode else 'text'}/{png_name}/"
                os.makedirs(output_path, exist_ok=True)
                output_path = os.path.join(output_path, f"{png_name}_{start_time}.jsonl")
                with open(output_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                
                # 打印控制台结果
                print("="*120)
                print("="*40, end="")
                print(f"[{'IMAGE' if not self.use_text_mode else 'TEXT'}]", end="")
                print("="*40)
                print(f"Saved to: {output_path}")
                print(f"Result: {ret}")
                print("="*120)
                print()
                print()
            elif test_flag == 'dpi_selection':
                if not ctx:
                    logger.warning("[WARN] No context found for N-Hop logging")

                png_name = ctx.get("png_name", "unknown").replace('.png', '')
                start_time = ctx.get("start_time", 0)
                language = ctx.get('language', 'unknown')
                method = ctx.get('method', '')

                current_dpi = png_name.split('_dpi_')[-1]
                png_name = png_name.split('_dpi_')[0]

                if method == 'locate':
                    ret = json.loads(ret.replace('```json', '').replace('```', ''))
                    ret['all_nodes'] = [x['name'] for x in ret['all_nodes']]
                    ret = f"```json\n{json.dumps(ret, ensure_ascii=False, indent=4)}\n```"
                
                # 构造这条记录的数据对象
                record = {
                    "pngName": png_name,   # 图片名/测试用例ID
                    "modelName": self.model_name,  # 模型名称,
                    'temperature': self.temperature,  # temperature
                    'language': language,
                    'prompt': os.path.basename(ctx.get('prompt_template_path', "unknown")),
                    'currentDpi': current_dpi,  # 当前测试的DPI
                    "usage": {  # Token 消耗
                        "promptTokens": result['data']['usage']['promptTokens'],
                        "completionTokens": result['data']['usage']['completionTokens'],
                        "totalTokens": result['data']['usage']['totalTokens'],
                        "mediaTokens": result['data']['usage']['mediaTokens'],
                        'cachedTokens': result['data']['usage']['cachedTokens'],
                        'imageCost': result['data']['usage']['imageCost'],
                        'inputImages': result['data']['usage']['inputImages'],
                        "costLevel": result['data']['usage']['costLevel']
                    },
                    "response": ret
                }

                
                # 记录本次实验结果
                output_path = f"evaluations/dpi_selection/{self.model_name}/{png_name}/"
                os.makedirs(output_path, exist_ok=True)
                output_path = os.path.join(output_path, f"{png_name}{'-'+method if method else ''}_{start_time}.jsonl")
                with open(output_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                
                # 打印控制台结果
                print("="*120)
                print(f"Saved to: {output_path}")
                # print(f"Result: {record}")
                print("="*120)
                print()
                print()


            return ret, result['data']['usage']['promptTokens'], result['data']['usage']['completionTokens']
        except requests.exceptions.RequestException as e:
            print(f"请求发生异常: {e}")
            return "err"
        except (KeyError, json.JSONDecodeError) as e:
            print(f"解析响应失败: {e}")
            return "err"
    
