"""一次性脚本：删除所有 return jsonify(...) 调用"""
import re, sys

with open('qq_bot_ws.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 先删 jsonify 函数定义
content = re.sub(
    r'def jsonify\([^)]*\):\s*"""[^"]*"""\s*if obj is None[^}]*return obj or \{\}\s*',
    '# jsonify 已移除 — botpy WebSocket 模式下所有消息通过 send_message 发送\n',
    content, flags=re.DOTALL
)

# 删掉 jsonify 函数前后多余空行
content = re.sub(r'\n{3,}# jsonify 已移除', '\n\n# jsonify 已移除', content)

# 替换所有 return jsonify(...) — 包括单行和多行
# 策略：逐字符匹配括号深度
result = []
i = 0
while i < len(content):
    # 查找 "return jsonify("
    prefix = "return jsonify("
    pos = content.find(prefix, i)
    if pos == -1:
        result.append(content[i:])
        break

    # 保留 pos 之前的内容
    result.append(content[i:pos])

    # 找匹配的闭合括号
    j = pos + len(prefix)  # 跳过 "return jsonify("
    depth = 1
    while j < len(content) and depth > 0:
        ch = content[j]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == '"' or ch == "'":
            # 跳过字符串
            quote = ch
            j += 1
            while j < len(content) and content[j] != quote:
                if content[j] == '\\':
                    j += 1
                j += 1
        j += 1

    # 现在 j 指向闭合 ) 之后
    # 检查后面是否有 ", 500" 或其他尾部
    end = j
    tail = content[j:j+10]
    if tail.startswith(', 500'):
        end = j + 5
    elif tail.startswith(',500'):
        end = j + 4

    # 去掉尾部空白和换行
    # 找到行首位置，确保我们在行末
    line_start = content.rfind('\n', 0, pos) + 1
    indent = ' ' * (pos - line_start)

    # 检查下一行是否只有空白
    next_newline = content.find('\n', end)
    if next_newline != -1 and content[end:next_newline].strip() == '':
        end = next_newline + 1  # 吃掉空行

    result.append('return')
    i = end

new_content = ''.join(result)

# 清理连续空行
new_content = re.sub(r'\n{4,}', '\n\n\n', new_content)

with open('qq_bot_ws.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

remaining = len(re.findall(r'return jsonify\(', new_content))
print(f'Done. {remaining} remaining jsonify calls.')
