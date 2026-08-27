"""Prompt templates for AI aggregation (S3).

Templates are plain constants so tests can assert exact content. ``{{DIGEST}}``
is replaced via ``str.replace`` — never f-string interpolation, because the
JSON skeleton in the user template contains literal ``{``/``}`` braces.
"""

from __future__ import annotations

# SYSTEM_PROMPT — constant across calls. Hard rules (9) mirror the manifest
# contract + frontend invariants (§5.4): drop-in shape, C2 coverage, no noise
# paths, deep-module bias.
SYSTEM_PROMPT = (
    "你是一个代码库模块地图的分析引擎。任务：把给定代码库的「生产文件」聚合为"
    "「功能原子」清单——每个功能原子代表一组共同实现一个能力的文件。\n\n"
    "严格规则（必须全部遵守）：\n"
    "1. 只输出一个合法 JSON 对象，不要任何其他文本、解释或 Markdown 代码块。\n"
    "2. 顶层结构必须是 {\"atoms\": [{\"id\", \"name\", \"description\", \"files\"}]}。\n"
    "3. id：kebab-case 英文，唯一，例如 \"scan-and-parse\"。\n"
    "4. name：中文，一句话，不超过 12 字。\n"
    "5. description：中文，一句话，不超过 40 字，说明该功能原子的职责。\n"
    "6. files：必须原样使用输入中的模块 id（与输入逐字一致），禁止编造或改写路径。\n"
    "7. 每个生产模块必须恰好出现在一个原子的 files 中：不遗漏、不重复。\n"
    "8. 禁止把任何包含 /tests/ 或 /fixtures/ 的路径写入 files。\n"
    "9. 倾向「深模块」：功能原子数量少而内聚——紧密耦合（互相 import、共享端口）"
    "的文件归入同一个原子。"
)

# USER_TEMPLATE — carries the digest. The digest is injected via {{DIGEST}} so
# callers never interpolate it directly (see module docstring).
USER_TEMPLATE = (
    "请根据下面的「代码库摘要」生成功能原子清单。\n\n"
    "代码库摘要：\n{{DIGEST}}\n\n"
    "输出要求：\n"
    "- 只输出合法 JSON，不要任何解释文字。\n"
    "- 结构：{\"atoms\": [{\"id\": \"...\", \"name\": \"...\", "
    "\"description\": \"...\", \"files\": [\"...\"]}]}\n\n"
    "参考示例（仅为格式示例，不是真实内容）：\n"
    "{\"atoms\": [{\"id\": \"scan-and-parse\", \"name\": \"扫描并解析代码库\", "
    "\"description\": \"解析源代码并构建模块依赖图\", "
    "\"files\": [\"parser/_scanner.py\", \"parser/_ports.py\"]}]}"
)

# REPAIR_TEMPLATE — fed back to the model when the output fails validation
# (S4 swaps this in as the retry_with_repair repair prompt).
REPAIR_TEMPLATE = (
    "你上次的输出不合法。请只输出修正后的合法 JSON，不要任何其他文本。\n\n"
    "校验错误：{{ERROR}}\n\n"
    "你上次的输出：\n{{RAW_OUTPUT}}"
)

# LEARN_TEMPLATE — the local model's learning role (S6/D14/U6): compare its own
# attempt with the API's authoritative answer and reflect on the difference.
# Deliberately loose format — it is learning material, not a product artifact.
LEARN_TEMPLATE = (
    "你是正在学习「代码库功能原子聚合」任务的本地模型。下面是同一个代码库的两个"
    "聚合结果：\n"
    "- 云端大模型的答案（权威参考）：\n{{API_OUTPUT}}\n"
    "- 你自己的答案：\n{{LOCAL_OUTPUT}}\n\n"
    "请对比两者，反思差异：\n"
    "1. 哪些文件被分到了不同的功能原子？\n"
    "2. 你漏掉了什么线索（imports、端口签名、docstring、功能相关性）？\n"
    "3. 云端的分组为什么更好（或你的为什么更好）？\n\n"
    "输出 2-5 句中文学习笔记，直接回答，不要 JSON。"
)


def build_user_prompt(digest: str) -> str:
    """Render the user prompt with the digest inlined (single call site for
    the placeholder replacement)."""
    return USER_TEMPLATE.replace("{{DIGEST}}", digest)


def render_repair_prompt(raw_output: str, error: str) -> str:
    """Render the repair prompt for a failed output (used as the repair_user
    seam in :func:`aggregate.providers.retry_with_repair`)."""
    return (
        REPAIR_TEMPLATE.replace("{{RAW_OUTPUT}}", raw_output).replace("{{ERROR}}", error)
    )


def render_learn_prompt(local_output: str, api_output: str) -> str:
    """Render the learning-reflection prompt for the local model (S6)."""
    return (
        LEARN_TEMPLATE.replace("{{LOCAL_OUTPUT}}", local_output).replace(
            "{{API_OUTPUT}}", api_output
        )
    )
