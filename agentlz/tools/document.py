from typing import Any, Dict, Optional
# 解析文档成md格式
def parse_document_to_md(payload: Dict[str, Any]) -> Optional[str]:
    """解析文档内容为 Markdown 格式，支持多种文档类型

    参数：
    - `payload`: 前端上传的文档内容，包含：
      - `document`: 文档内容或文件数据
      - `document_type`: 文档类型（pdf, doc, docx, md, txt, ppt, pptx, xls, xlsx, csv）
      - `title`: 文档标题
      - `tags`: 标签（可选）
      - `description`: 描述（可选）
      - `meta_https`: 元数据链接（可选）

    返回：
    - 解析后的 Markdown 内容字符串，如果文档不存在或解析失败则返回 None。

    """
    # 从payload中提取文档内容和相关信息
    document_content = payload.get("document")
    document_title = payload.get("title", "")
    document_type = payload.get("document_type", "md").lower()
    tags = payload.get("tags", [])
    description = payload.get("description", "")
    meta_https = payload.get("meta_https", "")
    
    if document_content is None:
        return None
    
    # 根据文档类型进行不同的处理
    if document_type == "md":
        # Markdown 文档直接返回内容
        return str(document_content)
    
    elif document_type == "txt":
        # 文本文档转换为Markdown格式
        content = str(document_content)
        # 简单的文本到Markdown转换
        content = content.replace('\n', '\n\n')  # 添加段落间距
        return content
    
    elif document_type in ["csv"]:
        # CSV文档转换为Markdown表格
        import csv
        import io
        try:
            # 假设document_content是CSV字符串或文件内容
            csv_content = str(document_content)
            csv_reader = csv.reader(io.StringIO(csv_content))
            rows = list(csv_reader)
            
            if not rows:
                return "空CSV文件"
            
            # 创建Markdown表格
            md_table = []
            # 表头
            headers = rows[0]
            md_table.append("| " + " | ".join(headers) + " |")
            md_table.append("| " + " | ".join(["---"] * len(headers)) + " |")
            
            # 数据行
            for row in rows[1:]:
                md_table.append("| " + " | ".join(row) + " |")
            
            return "\n".join(md_table)
        except Exception as e:
            return f"CSV解析错误: {str(e)}"
    
    elif document_type in ["pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"]:
        # 对于这些复杂格式，目前返回占位符文本
        # 在实际应用中，这里应该集成相应的解析库
        content = f"# {document_title}\n\n"
        content += f"**文档类型**: {document_type.upper()}\n\n"
        
        if description:
            content += f"**描述**: {description}\n\n"
        
        if tags:
            content += f"**标签**: {', '.join(tags)}\n\n"
        
        if meta_https:
            content += f"**元数据链接**: {meta_https}\n\n"
        
        content += "---\n\n"
        content += "**注意**: 此文档类型需要专门的解析器。\n\n"
        content += f"原始内容长度: {len(str(document_content))} 字符\n"
        
        return content
    
    else:
        # 未知类型，返回原始内容
        return str(document_content)
