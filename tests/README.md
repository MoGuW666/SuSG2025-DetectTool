# 测试文档

本目录包含 SuSG DetectTool 的完整测试套件。

## 测试结构

```
tests/
├── __init__.py          # 测试包初始化
├── conftest.py          # pytest配置和共享fixtures
├── test_engine.py       # 核心检测引擎测试
├── test_stats.py        # 统计功能测试
├── test_cli.py          # CLI命令集成测试
└── fixtures/            # 测试数据文件
    └── test.log         # 测试用日志文件
```

## 测试覆盖

### test_engine.py - 核心引擎测试
- ✅ 6种异常类型检测（OOM, Oops, Panic, Deadlock, Reboot, FS_Exception）
- ✅ 字段提取（pid, comm, secs等）
- ✅ 多行聚合功能
- ✅ 冷却机制
- ✅ 边界情况处理

### test_stats.py - 统计功能测试
- ✅ 统计数据生成
- ✅ 计数准确性（按类型、严重级别、规则）
- ✅ Top N排名
- ✅ 空结果处理
- ✅ 字段聚合

### test_cli.py - CLI命令测试
- ✅ scan命令（表格和JSON输出）
- ✅ stats命令（表格和JSON输出）
- ✅ 参数处理（--top, --json等）
- ✅ 错误处理（文件不存在等）

## 运行测试

### 安装测试依赖

```bash
# 安装包含测试依赖
pip install -e ".[dev]"
```

### 运行所有测试

```bash
# 运行所有测试
pytest

# 详细输出
pytest -v

# 显示测试覆盖率
pytest --cov=detecttool --cov-report=term-missing
```

### 运行特定测试

```bash
# 只运行引擎测试
pytest tests/test_engine.py

# 只运行统计测试
pytest tests/test_stats.py

# 只运行CLI测试
pytest tests/test_cli.py

# 运行特定的测试类
pytest tests/test_engine.py::TestDetection

# 运行特定的测试方法
pytest tests/test_engine.py::TestDetection::test_oom_detection
```

### 使用markers运行分类测试

```bash
# 运行标记为engine的测试
pytest -m engine

# 运行标记为stats的测试
pytest -m stats

# 运行标记为cli的测试
pytest -m cli
```

## 预期结果

运行所有测试时，预期输出：

```
================================ test session starts =================================
collected 40+ items

tests/test_cli.py ................                                             [ xx%]
tests/test_engine.py ....................                                      [ xx%]
tests/test_stats.py ................                                           [100%]

================================ XX passed in X.XXs ==================================
```

所有测试应该通过（绿色），没有失败或错误。

## 测试数据

### fixtures/test.log
包含所有6种异常类型的示例日志，用于验证检测功能：
- OOM (进程1234, python3)
- Oops (内核错误)
- Panic (系统崩溃，带多行堆栈)
- Deadlock (进程4321, kworker/0:1, 120秒)
- Reboot (系统重启)
- FS_Exception (EXT4文件系统错误)

## 持续集成

测试可以轻松集成到CI/CD流程中：

```yaml
# GitHub Actions示例
- name: Run tests
  run: |
    pip install -e ".[dev]"
    pytest --cov=detecttool --cov-report=xml
```

## 故障排查

### 测试失败
1. 确保已安装测试依赖：`pip install -e ".[dev]"`
2. 确保在项目根目录运行测试
3. 检查Python版本 >= 3.10

### import错误
- 确保已安装项目：`pip install -e .`
- 检查PYTHONPATH包含src目录

### 文件路径问题
- 测试使用相对路径，应该从项目根目录运行
- 所有路径都通过pathlib.Path处理，跨平台兼容
