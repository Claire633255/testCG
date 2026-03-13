Please carefully analyze this function call graph or flowchart to identify all nodes and directed edges within the image. This is an extremely rigorous OCR and visual transcription test. You must extract the information directly and accurately.

**[Core Disciplines: Anti-Hallucination, Anti-Tampering, Anti-Infinite Loop]**
1. **STRICTLY PROHIBITED: "Smart" simplification or deduplication.** If a node name contains consecutive repeated words or namespaces (e.g., the text in the image is `training.training`), you MUST transcribe it entirely and exactly as is! You are absolutely forbidden to arbitrarily reduce, merge, or omit it to `training`. You must transcribe the exact number of repeated words as they appear, remaining absolutely faithful to the original image.
2. **STRICTLY PROHIBITED: Guessing or auto-completion.** You must act as a pure optical scanner, extracting ONLY the text that is "authentically visible to the naked eye" in the image. You must NEVER use your programming knowledge to auto-complete function names (for example, NEVER fabricate API sequences for libraries like `talloc` or `setfacl` on your own). If characters are blurry, transcribe them exactly as the pixels show, but NEVER make things up.
3. **CRITICAL: Exact punctuation transcription.** The function name on a node is usually located at the very top of each node with a white background. You MUST completely preserve all original underscores (`_`), dots (`.`), letter casing, parentheses (`()`), and any other special punctuation marks.
4. **STRICTLY PROHIBITED: Meaningless infinite loops.** The extracted nodes must be distinct nodes that genuinely exist in the image. Please self-check your output; you are absolutely NOT allowed to fall into a mindless infinite loop of repeating the same function name.

**[Requirements for Directed Edge Identification]**
Carefully observe the connecting lines and arrowhead directions to extract all transition relationships. You must clearly distinguish between the "source" node and the "target" node.

**[Output Format]**
Please strictly output a valid JSON object. Do not include any comments in your generated JSON, and do not include any extra explanatory text outside the markdown code block. Please strictly adhere to the following JSON structure and data types:

```json
{
    "node_counts": 0,
    "all_nodes":[
        "exact_function_name_1",
        "exact_function_name_2"
    ],
    "edge_counts": 0,
    "all_edges":[
        "source_function->target_function"
    ]
}
```