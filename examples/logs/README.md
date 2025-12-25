# 示例日志文件说明

本目录包含多个示例日志文件，用于演示DetectTool在不同场景下的检测能力。

## 📁 文件列表

### 1. sample.log - 基础示例
**用途**: 快速演示和测试
**场景**: 包含所有6种异常类型各一个实例
**适合**: 新手入门、功能验证

**包含的异常**:
- ✅ OOM (1个)
- ✅ Oops (1个)
- ✅ Panic (1个)
- ✅ Deadlock (1个)
- ✅ Reboot (1个)
- ✅ FS_Exception (1个)

**快速测试**:
```bash
detecttool scan -f examples/logs/sample.log
detecttool stats -f examples/logs/sample.log
```

---

### 2. oom_storm.log - OOM风暴
**用途**: 展示stats统计能力
**场景**: 内存压力导致短时间内多个进程被杀
**适合**: 统计分析、Top N演示

**特点**:
- 12个OOM事件
- 10个不同进程（java, mysql, python3, redis-server, nginx, node, postgres, chrome, docker）
- 展示冷却机制（部分重复进程）
- 真实的内存占用信息

**演示命令**:
```bash
# 查看OOM统计
detecttool stats -f examples/logs/oom_storm.log

# 查看Top进程
detecttool stats -f examples/logs/oom_storm.log --top 5

# JSON格式
detecttool stats -f examples/logs/oom_storm.log --json
```

**预期输出**:
- Top进程: java (2次), python3 (2次)
- 总事件数: ~10-12个（取决于冷却机制）
- 严重级别: 全部 high

---

### 3. kernel_panic_full.log - 完整Kernel Panic
**用途**: 展示多行聚合能力
**场景**: 真实的内核崩溃，包含完整堆栈信息
**适合**: 多行context演示、调试分析

**特点**:
- 完整的Oops信息（NULL pointer dereference）
- 详细的寄存器状态（RAX, RBX, RCX...）
- 完整的Call Trace堆栈（40+行）
- Kernel Panic结束标记
- 展示多行聚合（所有堆栈作为context）

**演示命令**:
```bash
# 扫描并查看context
detecttool scan -f examples/logs/kernel_panic_full.log

# JSON查看完整context
detecttool scan -f examples/logs/kernel_panic_full.log --json | jq '.[0].context'
```

**预期输出**:
- 检测到1个Oops + 1个Panic
- Panic包含40+行context
- 字段: 进程mysqld, PID 12890

---

### 4. deadlock_scenario.log - 死锁场景
**用途**: 展示字段提取和多种死锁检测
**场景**: 多个进程因不同原因进入hung task状态
**适合**: 字段提取演示、进程分析

**特点**:
- 4个不同的hung task事件
- 不同的阻塞时间（120s, 180s, 240s, 300s）
- 不同的进程类型（kworker, docker, systemd-journal, postgres）
- 每个都有完整的Call Trace
- 展示字段提取（pid, comm, secs）

**演示命令**:
```bash
# 查看所有死锁
detecttool scan -f examples/logs/deadlock_scenario.log

# 查看提取的字段
detecttool scan -f examples/logs/deadlock_scenario.log --json | jq '.[].extracted'

# 统计死锁
detecttool stats -f examples/logs/deadlock_scenario.log
```

**预期输出**:
- 检测到4个DEADLOCK事件
- 提取字段: comm (进程名), pid, secs (阻塞秒数)
- Top进程: kworker/u16:2, docker-containe, systemd-journal, postgres

---

### 5. mixed_production.log - 生产环境混合
**用途**: 展示从噪音中提取信号的能力
**场景**: 真实生产环境，大量正常日志中夹杂异常
**适合**: 实际演示、过滤能力展示

**特点**:
- 50+行日志，包含大量正常事件
- 系统启动、Docker、网络、USB设备等正常日志
- 5种异常混杂其中：
  - 1个 FS_EXCEPTION (EXT4错误)
  - 1个 OOM (java进程)
  - 1个 FS_EXCEPTION (XFS错误)
  - 1个 DEADLOCK (nginx)
  - 1个 REBOOT
- 模拟真实信噪比

**演示命令**:
```bash
# 从噪音中提取异常
detecttool scan -f examples/logs/mixed_production.log

# 统计分析
detecttool stats -f examples/logs/mixed_production.log
```

**预期输出**:
- 总行数: 50+
- 检测事件: 5个
- 类型分布: FS_EXCEPTION (2), OOM (1), DEADLOCK (1), REBOOT (1)

---

### 6. filesystem_errors.log - 文件系统异常集合
**用途**: 展示各种文件系统错误检测
**场景**: 多种文件系统（EXT4, XFS, BTRFS）的各类错误
**适合**: 存储故障分析

**特点**:
- 覆盖3种主流文件系统（EXT4, XFS, BTRFS）
- 多种错误类型：
  - 元数据损坏
  - I/O错误
  - 磁盘坏块
  - Journal错误
  - 文件系统只读
- 10+个FS_EXCEPTION事件
- 真实的错误信息和修复建议

**演示命令**:
```bash
# 查看所有文件系统错误
detecttool scan -f examples/logs/filesystem_errors.log

# 统计各类错误
detecttool stats -f examples/logs/filesystem_errors.log

# 只看EXT4错误
detecttool scan -f examples/logs/filesystem_errors.log --json | jq '.[] | select(.message | contains("EXT4"))'
```

**预期输出**:
- 检测到10+个FS_EXCEPTION事件
- 文件系统: EXT4, XFS, BTRFS
- 设备: sda1, sdb1, sdc1, sdd1, sde1, sdf1, sdg1

---

## 🎯 使用场景建议

### 场景1: 快速演示工具功能
```bash
detecttool scan -f examples/logs/sample.log
detecttool stats -f examples/logs/sample.log
```

### 场景2: 演示统计分析能力
```bash
detecttool stats -f examples/logs/oom_storm.log --top 5
detecttool stats -f examples/logs/deadlock_scenario.log
```

### 场景3: 演示多行聚合
```bash
detecttool scan -f examples/logs/kernel_panic_full.log
# 观察Panic的完整堆栈context
```

### 场景4: 演示字段提取
```bash
detecttool scan -f examples/logs/deadlock_scenario.log --json | jq '.[].extracted'
# 查看提取的pid, comm, secs字段
```

### 场景5: 演示实际应用
```bash
# 模拟生产环境检测
detecttool monitor -f examples/logs/mixed_production.log --from-start

# 文件系统故障分析
detecttool scan -f examples/logs/filesystem_errors.log
```

---

## 📊 统计对比

| 文件 | 总行数 | 事件数 | 异常类型数 | 亮点 |
|------|--------|--------|-----------|------|
| sample.log | 17 | 6 | 6 | 基础全覆盖 |
| oom_storm.log | 20 | 12 | 1 | Top N统计 |
| kernel_panic_full.log | 45 | 2 | 2 | 多行聚合 |
| deadlock_scenario.log | 60 | 4 | 1 | 字段提取 |
| mixed_production.log | 50+ | 5 | 4 | 噪音过滤 |
| filesystem_errors.log | 45 | 10+ | 1 | FS详尽 |

---

## 💡 测试建议

### 完整测试流程
```bash
# 1. 基础功能测试
detecttool scan -f examples/logs/sample.log

# 2. 统计功能测试
detecttool stats -f examples/logs/oom_storm.log

# 3. JSON输出测试
detecttool scan -f examples/logs/deadlock_scenario.log --json

# 4. 多行聚合测试
detecttool scan -f examples/logs/kernel_panic_full.log --json | jq '.[].context | length'

# 5. 真实场景测试
detecttool scan -f examples/logs/mixed_production.log
```

### 性能测试
```bash
# 测试大文件处理
time detecttool scan -f examples/logs/filesystem_errors.log

# 测试stats性能
time detecttool stats -f examples/logs/oom_storm.log
```

---

## 📝 添加自定义示例

如果需要添加自己的示例日志：

1. 从真实系统提取日志：
```bash
sudo grep -i "error\|panic\|oom" /var/log/kern.log > my_example.log
```

2. 测试检测效果：
```bash
detecttool scan -f my_example.log
```

3. 调整规则（如需要）：
```bash
# 编辑 configs/rules.yaml 添加或修改规则
```

---

**提示**: 所有示例日志都基于真实Linux内核日志格式创建，但数据已脱敏和简化，仅用于演示和测试。
