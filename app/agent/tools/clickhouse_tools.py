"""ClickHouse 数据查询工具。

提供直接在 ClickHouse 上执行 SQL 查询的能力，
Agent 可以在 ReAct 推理过程中构造 SQL 并查询真实数据。
"""

from __future__ import annotations

import json
import logging

import clickhouse_connect
from langchain_core.tools import tool

from app.config import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    """获取或创建 ClickHouse 客户端单例。"""
    global _client
    if _client is None:
        _client = clickhouse_connect.get_client(
            host=settings.ck_host,
            port=settings.ck_port,
            username=settings.ck_user,
            password=settings.ck_password,
            database=settings.ck_database,
        )
        logger.info(
            "ClickHouse client connected: %s:%s/%s",
            settings.ck_host, settings.ck_port, settings.ck_database,
        )
    return _client


_MAX_ROWS = 200
_BLOCKED_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "ATTACH", "DETACH"}


def _is_safe_query(sql: str) -> bool:
    """检查 SQL 是否为安全的只读查询。"""
    first_keyword = sql.strip().split()[0].upper() if sql.strip() else ""
    return first_keyword not in _BLOCKED_KEYWORDS


def _sanitize_sql(sql: str) -> str:
    """清理 SQL 语句，修复常见的兼容性问题。

    - 去掉末尾分号（ClickHouse HTTP 接口不支持）
    - 去掉中文别名（ClickHouse 不支持非 ASCII 标识符作为别名）
    """
    import re

    sql = sql.strip().rstrip(";").strip()
    # 将中文别名替换为反引号包裹，例如 AS 评分 -> AS `评分`
    sql = re.sub(
        r'\bAS\s+([^\s,`()\[\]]+)',
        lambda m: m.group(0) if m.group(1).isascii() else f"AS `{m.group(1)}`",
        sql,
        flags=re.IGNORECASE,
    )
    return sql


@tool
def execute_sql(sql: str) -> str:
    """在 ClickHouse 上执行 SQL 查询并返回结果。

    只允许 SELECT 查询，禁止写入/修改操作。
    结果最多返回 200 行，超出时自动截断并提示。

    Args:
        sql: 要执行的 SQL 查询语句。例如：
            SELECT wareId, title, jdPrice FROM jd_1000000266_wares WHERE wareStatus = 8 LIMIT 10
    """
    if not _is_safe_query(sql):
        return "安全限制：只允许执行 SELECT 查询，不允许写入或修改操作。"

    sql = _sanitize_sql(sql)

    try:
        client = _get_client()
        result = client.query(sql)

        columns = result.column_names
        rows = result.result_rows

        if not rows:
            return f"查询成功，返回 0 行数据。\n\nSQL: {sql}"

        total = len(rows)
        truncated = False
        if total > _MAX_ROWS:
            rows = rows[:_MAX_ROWS]
            truncated = True

        header = " | ".join(columns)
        separator = " | ".join(["---"] * len(columns))
        body_lines = []
        for row in rows:
            cells = []
            for val in row:
                if val is None:
                    cells.append("NULL")
                elif isinstance(val, (dict, list)):
                    cells.append(json.dumps(val, ensure_ascii=False, default=str))
                else:
                    cells.append(str(val))
            body_lines.append(" | ".join(cells))

        table = f"{header}\n{separator}\n" + "\n".join(body_lines)

        footer = f"\n\n共 {total} 行"
        if truncated:
            footer += f"（已截断，仅显示前 {_MAX_ROWS} 行）"
        footer += f"\n\nSQL: {sql}"

        return table + footer

    except Exception as e:
        logger.warning("ClickHouse query error: %s\nSQL: %s", e, sql)
        return f"查询执行失败: {e}\n\nSQL: {sql}"


@tool
def list_tables(database: str = "") -> str:
    """列出 ClickHouse 数据库中的所有表。

    Args:
        database: 数据库名称，留空则使用默认数据库。
    """
    try:
        client = _get_client()
        db = database or settings.ck_database
        result = client.query(f"SHOW TABLES FROM `{db}`")
        tables = [row[0] for row in result.result_rows]
        if not tables:
            return f"数据库 '{db}' 中没有找到表。"
        return f"数据库 '{db}' 中的表（共 {len(tables)} 张）:\n" + "\n".join(f"  - {t}" for t in tables)
    except Exception as e:
        return f"获取表列表失败: {e}"


@tool
def describe_table(table_name: str) -> str:
    """查看 ClickHouse 表的结构（字段名、类型、注释）。

    Args:
        table_name: 表名，如 jd_1000000266_wares。
    """
    try:
        client = _get_client()
        result = client.query(f"DESCRIBE TABLE `{table_name}`")
        rows = result.result_rows
        if not rows:
            return f"表 '{table_name}' 不存在或没有字段。"

        lines = [f"表 `{table_name}` 结构:"]
        lines.append("字段名 | 类型 | 默认值 | 注释")
        lines.append("--- | --- | --- | ---")
        for row in rows:
            name = row[0] if len(row) > 0 else ""
            dtype = row[1] if len(row) > 1 else ""
            default = row[2] if len(row) > 2 else ""
            comment = row[4] if len(row) > 4 else ""
            lines.append(f"{name} | {dtype} | {default} | {comment}")
        return "\n".join(lines)
    except Exception as e:
        return f"获取表结构失败: {e}"
