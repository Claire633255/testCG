# 漏洞点函数信息映射 - 中文版本
SINK_INFO_CN = {
    "exec": {
        "vulnerable_sink": "exec函数是Python内置函数，用于动态执行多行代码块（如字符串、代码对象）。当代码内容部分或全部来自用户可控数据且未经验证时，攻击者可能注入恶意代码逻辑，造成代码执行漏洞。"
    },
    
    "eval": {
        "vulnerable_sink": "eval函数是Python内置函数，用于动态执行单行Python表达式（如字符串）。当表达式内容来自用户可控数据且未经验证时，攻击者可能注入恶意表达式，造成代码执行漏洞。eval相比exec更危险，因为它返回表达式结果，可能被用于敏感信息泄露或系统操作。"
    },

    "os.system": {
        "vulnerable_sink": "os.system函数属于os模块，用于在子shell中执行系统命令。当命令字符串中包含未经转义或过滤的用户输入时（如拼接用户提供的参数），攻击者可注入额外命令，导致命令注入漏洞，进而控制操作系统。"
    },

    "pickle.loads": {
        "vulnerable_sink": "pickle.loads函数属于pickle模块，用于将字节数据反序列化为Python对象。当反序列化的数据来源不可信（如网络传输、未授权文件）且未进行完整性校验时，恶意构造的序列化数据可能触发任意代码执行。"
    },

    "pickle.load": {
        "vulnerable_sink": "pickle.load函数属于pickle模块，用于从文件对象反序列化Python对象。当文件来源不可控（如用户上传、外部下载）且未验证其真实性或签名时，恶意文件可能利用反序列化过程执行危险操作。"
    },

    "torch.load": {
        "vulnerable_sink": "torch.load函数属于PyTorch库，用于加载序列化的模型或张量。当加载的模型文件（通常为.pth、.pt）来自不可信来源，且未设置weights_only=True参数时，模型内可能包含恶意代码，在加载过程中被执行。"
    },

    "yaml.load": {
        "vulnerable_sink": "yaml.load函数属于PyYAML库，用于解析YAML字符串并转换为Python对象。当其Loader参数使用默认值或yaml.Loader或未禁用自定义构造函数时，恶意YAML内容可能通过特殊标签（如!!python/object）触发反序列化漏洞；当Loader参数使用yaml.FullLoader时，在PyYAML版本较低（<=5.3.1）时同样存在反序列化漏洞。"
    },

    "joblib.load": {
        "vulnerable_sink": "joblib.load函数属于joblib库，常用于高效序列化/反序列化Python对象（如机器学习模型）。当加载的文件（如.pkl）来源不可信且未在隔离环境中处理时，可能利用pickle机制执行任意代码。"
    }
}

# 漏洞点函数信息映射 - 英文版本
SINK_INFO_EN = {
    "exec": {
        "vulnerable_sink": "exec is a Python built-in function for dynamically executing multi-line code blocks (such as strings, code objects). When the code content partially or entirely comes from user-controllable data and is not validated, attackers may inject malicious code logic, causing code execution vulnerabilities."
    },

    "eval": {
        "vulnerable_sink": "eval is a Python built-in function for dynamically executing single-line Python expressions (such as strings). When the expression content comes from user-controllable data and is not validated, attackers may inject malicious expressions, causing code execution vulnerabilities. eval is more dangerous than exec because it returns the expression result, which could be used for sensitive information disclosure or system operations."
    },

    "os.system": {
        "vulnerable_sink": "os.system function belongs to the os module and is used to execute system commands in a sub-shell. When the command string contains unescaped or unfiltered user input (such as concatenating user-provided parameters), attackers can inject additional commands, leading to command injection vulnerabilities and potentially gaining control of the operating system."
    },

    "pickle.loads": {
        "vulnerable_sink": "pickle.loads function belongs to the pickle module and is used to deserialize byte data into Python objects. When the deserialized data comes from untrusted sources (such as network transmission, unauthorized files) and is not integrity-verified, maliciously constructed serialized data may trigger arbitrary code execution."
    },

    "pickle.load": {
        "vulnerable_sink": "pickle.load function belongs to the pickle module and is used to deserialize Python objects from file objects. When the file source is uncontrollable (such as user uploads, external downloads) and its authenticity or signature is not verified, malicious files may exploit the deserialization process to perform dangerous operations."
    },

    "torch.load": {
        "vulnerable_sink": "torch.load function belongs to the PyTorch library and is used to load serialized models or tensors. When loading model files (typically .pth, .pt) from untrusted sources and without setting weights_only=True parameter, the model may contain malicious code that gets executed during the loading process."
    },

    "yaml.load": {
        "vulnerable_sink": "yaml.load function is part of the PyYAML library and is used to parse YAML strings into Python objects. When the Loader parameter is set to its default value, yaml.Loader, or when custom constructors are not disabled, malicious YAML content may exploit special tags (e.g., !!python/object) to trigger deserialization vulnerabilities. Even when the Loader parameter is set to yaml.FullLoader, deserialization vulnerabilities still exist in older versions of PyYAML (<=5.3.1)."
    },

    "joblib.load": {
        "vulnerable_sink": "joblib.load function belongs to the joblib library and is commonly used for efficient serialization/deserialization of Python objects (such as machine learning models). When loading files (such as .pkl) from untrusted sources and without processing in an isolated environment, it may exploit the pickle mechanism to execute arbitrary code."
    }
}
