The following code belongs to the {function_name} function. Identify the next-hop functions based on the call graph image, and analyze the code according to the following focus points:
- {focuses}

```python
{func_body}
```

Format the output as follows:
```json
{  
    "taint_propagation_analysis": "...", # Analyze whether the {function_name} generates taint sources or propagates tainted data (limited to the {function_name} scope). Note that the answer should be combined with specific code    
    "is_taint_propagation": true/false, # If the {function_name} contains code that generates or propagates taint, set to true
    "security_sanitizer_analysis": "...", # Analyze whether the {function_name} performs security sanitization for vulnerabilities corresponding to vulnerable_sink, and whether the sanitization measures can completely prevent the vulnerability
    "is_security_sanitizer": true/false, # If the {function_name} contains security sanitization measures for vulnerabilities corresponding to vulnerable_sink, set to true
    "summary": "...", # Summarize the above analysis. Must be short!!!
    "key_codes_in_function": "..."  # String format. Contains the key code of the {function_name}. The define of key code is: 1. Function definition, 2. Call of down-stream functions *** in the graph ***, 3. Code mentioned in the above analysis and summary. For key codes, add comments line-by-line. For other code (including unrealted excepiton hanlding, branch and so on) use '...' to represent. ***Note: Must be short!!!***
}
```

***Note***:
- The answer should be combined with specific code, such as "According to the statement `a = foo()`, it can be seen that `a` comes from the return of the `foo` function"