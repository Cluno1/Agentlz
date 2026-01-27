import re
import html
import json


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s)


def sql_escape(s):
    return (s or "").replace("'", "''")


def normalize(s):
    if s is None:
        return ""
    s = html.unescape(s)
    s = strip_tags(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_rows(src):
    m = re.search(r'<tbody id="tableBody">([\s\S]*?)</table>', src, re.S)
    if not m:
        return []
    body = m.group(1)
    parts = [p for p in re.split(r"<tr>", body) if 'class="name-text"' in p]
    rows = []
    for r in parts:
        name_m = re.search(r'<span class="name-text"[^>]*>(.*?)</span>', r, re.S)
        tds = re.findall(r"<td(?:[^>]*)>([\s\S]*?)</td>", r, re.S)
        manu_raw = tds[1] if len(tds) > 1 else ""
        tags_raw = tds[2] if len(tds) > 2 else ""
        dmxa_raw = tds[4] if len(tds) > 4 else ""
        desc_raw = tds[-1] if tds else ""
        tags = [m.group(1) for m in re.finditer(r'<span class="chip">(.*?)</span>', tags_raw, re.S)]
        price_text = ""
        price_box_m = re.search(r'<div class="price-box">([\s\S]*?)</div>', dmxa_raw, re.S)
        if price_box_m:
            inner = price_box_m.group(1)
            lines = re.findall(r"<div>([\s\S]*?)</div>", inner, re.S)
            lines = [normalize(line) for line in lines if normalize(line)]
            if lines:
                price_text = "；".join(lines)
        if not price_text:
            fixed_m = re.search(r"(固定价格：\s*￥[^<]+/ 次)", dmxa_raw)
            if fixed_m:
                price_text = normalize(fixed_m.group(1))
        name = normalize(name_m.group(1) if name_m else "")
        manu = normalize(strip_tags(manu_raw))
        price = price_text or normalize(strip_tags(dmxa_raw))
        desc = normalize(strip_tags(desc_raw))
        tags_list = [normalize(t) for t in tags if normalize(t)]
        rows.append((name, price, manu, desc, tags_list))
    return rows


def main():
    src_path = r"e:\python\agent\Agentlz\docs\temp\源.md"
    out_path = r"e:\python\agent\Agentlz\docs\temp\model_inserts.sql"
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()
    rows = parse_rows(src)
    values = []
    for n, p, m, d, tags_list in rows:
        if not n:
            continue
        name_sql = "'" + sql_escape(n) + "'"
        price_sql = "'" + sql_escape(p or "") + "'"
        desc_sql = "NULL" if not d else "'" + sql_escape(d) + "'"
        manu_sql = "NULL" if not m else "'" + sql_escape(m) + "'"
        tags_json = json.dumps(tags_list, ensure_ascii=False)
        tags_sql = "'" + sql_escape(tags_json) + "'"
        values.append(f"({name_sql}, {price_sql}, {desc_sql}, {manu_sql}, {tags_sql})")
    out = "INSERT INTO `model` (`name`, `price`, `description`, `manufacturer`, `tags`) VALUES\n" + ",\n".join(values) + ";"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)


if __name__ == "__main__":
    main()
