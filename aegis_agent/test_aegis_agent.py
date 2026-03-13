#!/usr/bin/env python3
"""
AegisAgent 测试脚本
用于验证封装后的AegisAgent类功能
"""

import openai

# 初始化客户端
client = openai.OpenAI(
    # ✅ 关键：指向我们配置的透传端点路径
    # 注意：openai 库会自动在后面拼接 /chat/completions
    # 所以这里写到 /zhulu 即可
    base_url="http://10.24.4.150:8000/xuanji", 
    # api_key="9319482842:spOzrOiORtNooPTR" 
    api_key="8122602127:BxwqQHAZVrLEVsSO"
)

# 同步调用
def test_sync_streaming():
    """测试同步流式调用"""
    try:
        print("正在发起请求...")
        response = client.chat.completions.create(
            # model="Baidu-DeepSeek-V3.2",
            model="qwen-vl-max",
            messages=[
                {"role": "user", "content": "你好，请介绍一下你自己。"}
            ],
            stream=True,
            temperature=0.7
        )
        
        print("开始接收流式响应...")
        for chunk in response:
            # 兼容性处理：有些模型返回的 chunk 可能不含内容
            if chunk.choices and chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
        print("\n响应结束。")
                
    except Exception as e:
        print(f"\n调用错误: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_sync_streaming()