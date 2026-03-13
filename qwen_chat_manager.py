from openai import OpenAI
import json
import re
import math
import base64
import time

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

def chat_with_mllm_with_probs(prompt, model_info, image_path = None):
    max_retries = 3
    base_timeout = 600  # 10分钟基础超时
    
    for attempt in range(max_retries):
        try:
            # 计算当前尝试的超时时间
            current_timeout = base_timeout * (1.5 ** attempt)
            
            client = OpenAI(
                api_key=model_info.get("api_key", "EMPTY"),
                base_url=model_info.get("base_url")
            )

            if(image_path):
                # 读取图像文件并编码为base64
                with open(image_path, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode('utf-8')
                
                # 构建包含图像的多模态消息
                messages = [
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url", 
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ]
            else:
                messages = [
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": prompt}
                        ]
                    }
                ]

            response = client.chat.completions.create(
                model=model_info.get("model_name"),
                messages=messages,
                stream=False,  # 关闭流式输出
                logprobs=True,  # 启用概率信息
                top_logprobs=1,  # 返回前1个候选token的概率
                timeout=current_timeout,  # 动态设置超时时间
                extra_body={
                    "temperature": model_info.get("temperature", 0),
                }
            )
            
            resp = ""
            # 获取概率信息
            for token_info in response.choices[0].logprobs.content:
                prob = math.exp(token_info.logprob)
                if(token_info.token in ["true", "false", " true", " false"] ):
                    resp = f"{resp}\"{token_info.token.strip()}|{prob:.4f}\""
                else:
                    resp = f"{resp}{token_info.token}"

            usage = response.usage
            if usage:
                input_tokens = usage.prompt_tokens
                output_tokens = usage.completion_tokens

            return response.choices[0].message.content, resp, input_tokens, output_tokens
            
        except Exception as e:
            print(f"第 {attempt + 1} 次调用失败: {str(e)}")
            if attempt < max_retries - 1:  # 如果不是最后一次尝试
                print(f"等待 60 秒后重试...")
                time.sleep(60)  # 等待1分钟
            else:
                print("所有重试次数已用完，调用失败")
                raise e

def chat_with_mllm(prompt, model_info, image_path = None):
    max_retries = 3
    base_timeout = 600  # 10分钟基础超时
    
    for attempt in range(max_retries):
        try:
            # 计算当前尝试的超时时间
            current_timeout = base_timeout * (1.5 ** attempt)
            
            client = OpenAI(
                api_key=model_info.get("api_key", "EMPTY"),
                base_url=model_info.get("base_url")
            )

            if(image_path):
                # 读取图像文件并编码为base64
                with open(image_path, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode('utf-8')
                
                # 构建包含图像的多模态消息
                messages = [
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url", 
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ]
            else:
                messages = [
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": prompt}
                        ]
                    }
                ]

            response = client.chat.completions.create(
                model=model_info.get("model_name"),
                messages=messages,
                stream=False,  # 关闭流式输出
                timeout=current_timeout,  # 动态设置超时时间
                extra_body={
                    "temperature": model_info.get("temperature", 0),
                }
            )
            
            full_content = response.choices[0].message.content

            # 获取token使用情况
            usage = response.usage
            if usage:
                input_tokens = usage.prompt_tokens
                output_tokens = usage.completion_tokens

            return full_content, input_tokens, output_tokens
            
        except Exception as e:
            print(f"第 {attempt + 1} 次调用失败: {str(e)}")
            if attempt < max_retries - 1:  # 如果不是最后一次尝试
                print(f"等待 60 秒后重试...")
                time.sleep(60)  # 等待1分钟
            else:
                print("所有重试次数已用完，调用失败")
                raise e
