# Overview
Recent studies show that large language models (LLMs) offer a promising new approach to building vulnerability discovery tools. However, existing methods still face significant challenges, such as difficulty in representing complex code call relationships, over-reliance on traditional static analysis tools (SAST), high false positive rates, and a lack of cost-aware inference strategies.

To address these issues, we propose ***CG-VulMiner***, a ***dual-agent vulnerability discovery framework***. Its core innovation lies in deeply integrating a Vision-Language Model(***VLM***)​ into the analysis workflow. The VLM contributes two key advances:

- ***Call Graph Comprehension***:​ By processing call graph images during function summarization, the VLM identifies the function's role and enables targeted analyses like taint propagation and checking security measures.

- ***Visual Memory***:​ Intermediate results are directly recorded on function nodes and call edges during execution. This prevents redundant reasoning and mitigates the common problem of repetitive action planning with limited context over long iterations.

We evaluated the complementarity between SAST tools and LLM/VLM-based analysis and designed a collaborative architecture to generate vulnerability reports. To ***reduce false positives*** in reports, CG-VulMiner employs a ***dual-agent system*** that combines vulnerability analysis​ with automated PoC verification, significantly lowering the need for manual validation. We also introduce a ***strategy​*** that decides when to invoke basic or advanced VLM modules, effectively ***balancing detection accuracy with model inference costs***.

We evaluate CG-VulMiner on widely used AI training frameworks—including ***Megatron-LM, ms-swift, LLaMA-Factory, and Verl***—which constitute critical AI infrastructure. Our framework discovered ***10 previously unknown vulnerabilities***​ such as ***unsafe deserialization, code injection, and privilege escalation***. All vulnerabilities have been responsibly disclosed and assigned CVE identifiers.

Through case studies, we demonstrate the advantages of ***VLM-augmented auditing*** over traditional LLM-based methods in real-world vulnerability discovery.

# System Architecture and Workflow

```md
-------------- Project ---------------  Raw   -------------   Infor.  ------------  Reports   ------------
| LLM-Powered|  Call   |  K.G.-based |  Vul.  | MLLM-based|  Enhanced |   Vul.   |----------->|   Vul.   |
| Call Graph |-------->|  Vul. Call  |------->|  Function |---------->| Analysis |            |   PoC    |
| Construct  |  Graph  | Graph Query |  Call  |  Analysis |    Call   |   Agent  |<-----------|   Agent  |
-------------- in K.G. --------------- Graphs -------------   Graphs  ------------  Feedbacks -----------—
   Step 1                   Step2                 Step3                 Step4-1                  Step4-2
```

# Vulnerabilities Found by CG-Vulminer

Our tool detected ***10 vulnerabilities***, all of which have been assigned ***CVE IDs***.（***CVE-2025-23264***、***CVE-2025-23265***、***CVE-2025-23305***、***CVE-2025-23306***、***CVE-2025-23349***、***CVE-2025-23353***、***CVE-2025-23354***、***CVE-2025-46567***、***CVE-2025-50460***、***CVE-2025-50461***）

The vulnerabilities are described as follows.

## Deserialization vulnerabilities:

- ***CVE-2025-23264***、***CVE-2025-23265***:  NVIDIA Megatron-LM for all platforms contains a vulnerability in a python component where an attacker may cause a ***code injection*** issue by providing a ***malicious file***. A successful exploit of this vulnerability may lead to ***Code Execution, Escalation of Privileges, Information Disclosure and Data Tampering***.

- ***CVE-2025-23353***: NVIDIA Megatron-LM for all platforms contains a vulnerability in the ***msdp preprocessing script*** where ***malicious data*** created by an attacker may cause an ***injection***. A successful exploit of this vulnerability may lead to ***code execution, escalation of privileges, Information disclosure, and data tampering***.

- ***CVE-2025-23354***: NVIDIA Megatron-LM for all platforms contains a vulnerability in the ***ensemble_classifer script*** where ***malicious data*** created by an attacker may cause an ***injection***. A successful exploit of this vulnerability may lead to ***code execution, escalation of privileges, Information disclosure, and data tampering***.

- ***CVE-2025-46567***: LLama Factory enables fine-tuning of large language models. Prior to version 1.0.0, a ***critical vulnerability*** exists in the ***llamafy_baichuan2.py*** script of the LLaMA-Factory project. The script performs ***insecure deserialization*** using ***torch.load()*** on user-supplied ***.bin files*** from an input directory. An attacker can exploit this behavior by crafting a ***malicious .bin file*** that executes ***arbitrary commands*** during deserialization. This issue has been patched in version 1.0.0.

- ***CVE-2025-50460***: A ***remote code execution (RCE)*** vulnerability exists in the ms-swift project version 3.3.0 due to ***unsafe deserialization*** in ***tests/run.py*** using ***yaml.load()*** from the PyYAML library (versions = 5.3.1). If an attacker can control the content of the ***YAML configuration file*** passed to the ***--run_config*** parameter, ***arbitrary code*** can be executed during deserialization. This can lead to ***full system compromise***. The vulnerability is triggered when a ***malicious YAML file*** is loaded, allowing the execution of ***arbitrary Python commands*** such as ***os.system()***. It is recommended to upgrade PyYAML to version 5.4 or higher, and to use ***yaml.safe_load()*** to mitigate the issue.

- ***CVE-2025-50461***: A ***deserialization vulnerability*** exists in Volcengine's verl 3.0.0, specifically in the ***scripts/model_merger.py*** script when using the ***"fsdp" backend***. The script calls ***torch.load() with weights_only=False*** on user-supplied ***.pt files***, allowing attackers to execute ***arbitrary code*** if a ***maliciously crafted model file*** is loaded. An attacker can exploit this by convincing a victim to download and place a ***malicious model file*** in a local directory with a specific filename pattern. This vulnerability may lead to ***arbitrary code execution*** with the privileges of the user running the script.

## Command injection vulnerabilities:

- ***CVE-2025-23305***: NVIDIA Megatron-LM for all platforms contains a vulnerability in the ***tools component***, where an attacker may exploit a ***code injection*** issue. A successful exploit of this vulnerability may lead to ***code execution, escalation of privileges, information disclosure, and data tampering***.

- ***CVE-2025-23306***: NVIDIA Megatron-LM for all platforms contains a vulnerability in the ***megatron/training/ arguments.py*** component where an attacker could cause a ***code injection*** issue by providing a ***malicious input***. A successful exploit of this vulnerability may lead to ***code execution, escalation of privileges, information disclosure, and data tampering***.

- ***CVE-2025-23349***: NVIDIA Megatron-LM for all platforms contains a vulnerability in the ***tasks/orqa/unsupervised/nq.py*** component, where an attacker may cause a ***code injection***. A successful exploit of this vulnerability may lead to ***code execution, escalation of privileges, information disclosure, and data tampering***.

# Demo
- [***Vulnerability Analysis Agent Demo***](demo/vulnerability_analysis_agent_demo.mp4)
- [***Vulnerability PoC Agent Demo***](demo/vulnerability_poc_agent_demo.mp4)
