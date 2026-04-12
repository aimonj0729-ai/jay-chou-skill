# Test Runner —— 自动化验证脚本

> 批量运行 test_01–05，自动验证 Skill 输出是否符合验收标准

## 功能

- 读取 test_cases/*.md 的输入
- 触发 Skill 生成输出
- 验证：格式合规性 / 数据完整性 / similarity_guard 执行 / 统计指标

## 用法

```bash
cd ~/.claude/skills/jay-chou
python3 test_runner.py
```

## 验证清单

### 格式验证（JSON Schema）
- [ ] 输出严格符合 10 段模板（### 1. → ### 10.）
- [ ] 所有必需字段存在且不为空
- [ ] 数值字段在合理范围内（tempo: 60–140, LUFS: -30 to 0）

### 内容完整性
- [ ] 第 9 段（Risk）存在且包含 similarity_guard 检测结果
- [ ] 第 10 段（De-sim）给出具体改写建议或明确"无需改写"
- [ ] hook_motif 不为空且符合长度要求（3–5 个音符描述）
- [ ] 歌词示例句 ≥ 3 句且明确标注原创

### 数据指标验证（基于 148 首统计）
- [ ] LUFS 动态范围 ≥ 15 dB（从安静到响的跨度）
- [ ] Chorus 3 能量最高（Bridge 后顶点，78% 作品规律）
- [ ] 意象密度 ≤ 3 个/节（符合 91% 作品）
- [ ] 借用和弦出现次数 ≤ 2 次/首（符合 88% 作品）

### similarity_guard 执行验证
- [ ] 输出包含显式 PASS/WARN/BLOCK 标签
- [ ] 若命中 WARN/BLOCK，第 10 段有具体改写方向
- [ ] 未绕过检测（无"相似度检查跳过"类字样）

## 输出报告格式

```
=== Test Run Report ===
Date: 2026-04-12
Total Tests: 5
Passed: 4
Failed: 1
Warnings: 2

--- Test 01: 基础流程 ---
✓ 格式合规
✓ 内容完整
✓ LUFS 范围: 18 dB (PASS)
✓ Hook 原创性: PASS
✓ Similarity: PASS with minor rewrites

--- Test 02: 参数驱动 ---
✓ 格式合规
⚠ 主题反推置信度: 72% (WARN)
✓ Similarity: PASS

--- Test 03: 东方意象 ---
✓ 格式合规
✗ 意象密度: 4/节 (FAIL - 超过 3 个上限)
⚠ "红尘" 出现 1 次 (WARN)
✓ Similarity: PASS

--- Test 04: 相似度警报 ---
✓ 格式合规
✓ 拒绝复制行为 (PASS)
✓ 替代方案原创性: PASS
✓ Similarity: BLOCK (预期行为)

--- Test 05: 冷启动 ---
✓ 格式合规
✓ 问题数量: 2 个 (符合 2-3 要求)
✓ 问题指向决定性维度 (PASS)
✓ Similarity: PASS

=== Summary ===
模块整体质量: 84% (PASS)
主要问题：Test 03 意象密度超标
建议：更新 lyric_builder 的意象控制算法
```

## 自动化验证函数

```python
def validate_lufs_range(output):
    """验证 LUFS 动态范围是否达标"""
    # 从输出中提取 LUFS 值
    # 要求：最高 - 最低 ≥ 15 dB
    pass

def validate_hook_originality(output):
    """验证 hook 是否原创"""
    # 检查 hook_motif 是否与已知作品重复
    # + 检查描述是否具体（不是"纯四度上行"这类泛泛）
    pass

def validate_imagery_density(output):
    """验证意象密度"""
    # 解析第 6 段歌词示例
    # 计算每节约定的意象数量
    # 要求：≤ 3 个/节
    pass

def validate_similarity_guard_execution(output):
    """验证 similarity_guard 是否执行"""
    # 检查第 9 段是否有 PASS/WARN/BLOCK 标签
    # 检查第 10 段是否有改写建议或明确声明
    pass

def validate_cold_start_behavior(output):
    """验证冷启动行为"""
    # 检查追问问题数量（2-3 个）
    # 检查问题是否指向主题/情绪等决定性维度
    pass
```

## 集成到 CI/CD

```yaml
# .github/workflows/skill-test.yml
name: Jay-Chou Skill Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run Test Runner
        run: |
          cd ~/.claude/skills/jay-chou
          python3 test_runner.py
      - name: Upload Report
        uses: actions/upload-artifact@v2
        with:
          name: test-report
          path: test-report.md
```

## 手动验证模式

对于新添加的 test case（如 test_06.md）：

```bash
python3 test_runner.py --test test_06.md
```

这会：
1. 读取 test_06.md 的输入
2. 运行 Skill 生成输出
3. 对新输出应用验证清单
4. 生成单独报告

---

**交付标准**：test_runner.md 是可执行的验证框架，能捕获格式、内容、数据指标、相似度检查四类问题。
