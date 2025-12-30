# SuSG DetectTool - Linux系统异常检测工具

> 2025年全国大学生计算机系统能力大赛 - 操作系统设计赛 - 西北区域赛

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-47%20passed-brightgreen.svg)](tests/)
**所选题目**：
- **ID**：proj407
- **内容**：设计一个操作系统异常信息检测工具

**演示视频**：
链接: https://pan.baidu.com/s/1QeAtJyTJ-2CZ2lF6zhaw9A?pwd=xcni 提取码: xcni
**项目设计文档**:
在本项目的docs文件夹下，[Design.pdf](docs/Design.pdf) 描述详细的设计思路、架构图及实现原理等。

---
## 项目信息

- **项目名称**: 操作系统异常信息检测工具
- **比赛**: 2025年全国大学生计算机系统能力大赛-操作系统设计赛-西北区域赛
- **参赛队伍名称**: 自强不息独树一帜
- **参赛队伍编号**: T202510730997619
- **队伍成员**: 李尚泽，阮野，潘胜圆
- **指导老师**: 刘刚 (andyliu@lzu.edu.cn)
- **赛题导师**: 宋凯 (songkai01@ieisystem.com)
- **支持单位**: 浪潮电子信息产业股份有限公司、龙蜥社区


---

## 功能特性

### 基础功能

支持检测以下**6种**系统异常状态：

| 异常类型 | 描述 | 严重级别 | 提取字段 |
|---------|------|---------|---------|
| **OOM** | 内存不足导致进程被杀 | High | pid, comm |
| **Oops** | 内核错误/崩溃 | High | - |
| **Panic** | 系统无法恢复的致命错误 | Critical | - |
| **Deadlock** | 进程死锁/hung task | High | pid, comm, secs |
| **Reboot** | 非正常系统重启 | Medium | - |
| **FS_Exception** | 文件系统异常 | High | - |

### 进阶功能

- **实时监控**: 通过`monitor`命令实时跟随日志文件（类似`tail -f`）
- **守护进程**: 通过`install-service`安装为systemd服务，后台持续运行
- **统计分析**: 提供按类型、严重级别、频率的统计和分类功能
- **多行聚合**: 自动聚合Oops/Panic/Deadlock的多行堆栈信息
- **冷却机制**: 防止短时间内重复告警（可配置冷却时间）
- **字段提取**: 自动提取关键字段（进程名、PID、阻塞时间等）
- **多种输出**: 支持美化表格和JSON两种输出格式


---

## 快速开始

### 系统要求

- **操作系统**: Linux (Ubuntu 20.04+, CentOS 7+, 等)
- **Python版本**: Python 3.10 或更高
- **依赖**: PyYAML, Typer, Rich

### 安装步骤

#### 1. 克隆项目

```bash
git clone https://github.com/MoGuW666/SuSG2025-DetectTool.git
cd SuSG2025-DetectTool
```

#### 2. 创建虚拟环境（推荐）

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### 3. 安装工具

```bash
# 基础安装
pip install -e .

# 或安装包含测试依赖
pip install -e ".[dev]"
```

#### 4. 验证安装

```bash
detecttool --help
```

### 快速示例

```bash
# 扫描示例日志文件
detecttool scan -f examples/logs/sample.log

# 查看统计分析
detecttool stats -f examples/logs/sample.log

# 实时监控日志（Ctrl+C停止）
detecttool monitor -f /var/log/kern.log
```

---

## 详细使用说明

### 1. scan - 扫描日志文件

扫描日志文件并检测所有异常事件。

**基本用法**:
```bash
detecttool scan -f <日志文件路径> [-c <配置文件>] [--json]
```

**参数说明**:
- `-f, --file`: 要扫描的日志文件路径（必需）
- `-c, --config`: 规则配置文件路径（默认: `configs/rules.yaml`）
- `--json`: 以JSON格式输出结果

**示例**:

```bash
# 扫描系统内核日志
detecttool scan -f /var/log/kern.log

# 使用自定义规则
detecttool scan -f mylog.log -c custom_rules.yaml

# JSON格式输出（便于脚本处理）
detecttool scan -f /var/log/kern.log --json > incidents.json
```

**输出示例**:

```
┏━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Line ┃ Type     ┃ Severity ┃ Rule           ┃ Extracted ┃ Ctx ┃ Message          ┃
┡━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━╇━━━━━━━━━━━━━━━━━━┩
│    2 │ OOM      │ high     │ oom_basic      │ {"pid":…} │   0 │ Out of memory…   │
│    9 │ DEADLOCK │ high     │ deadlock_hung… │ {"pid":…} │   6 │ task blocked…    │
└──────┴──────────┴──────────┴────────────────┴───────────┴─────┴──────────────────┘
```

---

### 2. monitor - 实时监控日志

实时跟随日志文件，检测新出现的异常事件。

**基本用法**:
```bash
detecttool monitor -f <日志文件路径> [选项]
```

**参数说明**:
- `-f, --file`: 要监控的日志文件路径（必需）
- `-c, --config`: 规则配置文件路径（默认: `configs/rules.yaml`）
- `--json`: 以JSON Lines格式输出（每行一个事件）
- `--from-start`: 从文件开头开始读取（默认只跟随新行）
- `--poll`: 轮询间隔秒数（默认: 0.2）

**示例**:

```bash
# 监控内核日志
detecttool monitor -f /var/log/kern.log

# 从头读取并监控
detecttool monitor -f /var/log/syslog --from-start

# JSON格式输出（便于日志收集系统）
detecttool monitor -f /var/log/kern.log --json

# 调整轮询间隔（降低CPU占用）
detecttool monitor -f /var/log/kern.log --poll 1.0
```

**实时输出示例**:

```
Monitoring /var/log/kern.log  (Ctrl+C to stop)
Config: configs/rules.yaml | from_start=False | poll=0.2s

DEADLOCK (rule=deadlock_hung_task, severity=high, line=125)
INFO: task kworker/0:1:4321 blocked for more than 120 seconds.
extracted={"comm": "kworker/0:1", "pid": "4321", "secs": "120"}
--- context (6) ---
      Tainted: G        W         6.8.0 #1
task:kworker/0:1 state:D stack:0 pid:4321 ppid:2 flags:0x00000008
...
```

---

### 3. stats - 统计分析

对日志文件进行统计分析，提供按类型、严重级别、Top N等多维度统计。

**基本用法**:
```bash
detecttool stats -f <日志文件路径> [选项]
```

**参数说明**:
- `-f, --file`: 要分析的日志文件路径（必需）
- `-c, --config`: 规则配置文件路径（默认: `configs/rules.yaml`）
- `--json`: 以JSON格式输出统计结果
- `-n, --top`: 显示Top N项（默认: 10）

**示例**:

```bash
# 生成统计报告
detecttool stats -f /var/log/kern.log

# JSON格式（便于可视化）
detecttool stats -f /var/log/kern.log --json

# 只显示Top 5
detecttool stats -f /var/log/kern.log --top 5
```

**输出示例**:

```
═══════════════════════════════════════
    Log Analysis Statistics Report
═══════════════════════════════════════

Total lines scanned: 1,245
Total incidents detected: 18
Unique incident types: 4

              Incidents by Type
┏━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━┓
┃ Type         ┃ Count ┃ Percentage ┃
┡━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━┩
│ OOM          │    10 │      55.6% │
│ DEADLOCK     │     5 │      27.8% │
│ FS_EXCEPTION │     2 │      11.1% │
│ OOPS         │     1 │       5.6% │
└──────────────┴───────┴────────────┘

      Top 5 Affected Processes
┏━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃   Rank ┃ Process Name ┃ Incidents ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│      1 │ java         │         6 │
│      2 │ python3      │         3 │
│      3 │ mysqld       │         1 │
└────────┴──────────────┴───────────┘
```

---

### 4. 守护进程模式（Daemon Mode）

将 detecttool 安装为 systemd 服务，实现后台持续运行。

#### 安装服务

```bash
# 安装守护进程服务（需要root权限）
# 注意：-c 参数请使用配置文件的绝对路径或相对路径
sudo detecttool install-service -f /var/log/kern.log -c ./configs/rules.yaml

# 自定义配置（完整示例）
sudo detecttool install-service \
    -f /var/log/syslog \
    -c /path/to/your/rules.yaml \
    -o /var/log/detecttool \
    --name detecttool-syslog
```

**参数说明**:
- `-f, --log-file`: 要监控的日志文件（默认: `/var/log/kern.log`）
- `-c, --config`: 规则配置文件路径（默认: `/etc/detecttool/rules.yaml`）
- `-o, --output-dir`: 输出日志目录（默认: `/var/log/detecttool`）
- `--name`: 服务名称（默认: `detecttool`）

#### 管理服务

```bash
# 启动服务
sudo systemctl start detecttool

# 停止服务
sudo systemctl stop detecttool

# 重启服务
sudo systemctl restart detecttool

# 查看状态
sudo systemctl status detecttool
# 或使用
detecttool service-status

# 设置开机自启动
sudo systemctl enable detecttool

# 禁用开机自启动
sudo systemctl disable detecttool

# 一键启动并设置开机自启
sudo systemctl enable --now detecttool
```

#### 查看日志

```bash
# 查看检测到的异常事件
tail -f /var/log/detecttool/incidents.log

# 查看错误日志
tail -f /var/log/detecttool/error.log

# 使用 journalctl 查看
journalctl -u detecttool -f
```

#### 卸载服务

```bash
# 卸载服务
sudo detecttool uninstall-service

# 卸载并删除日志文件
sudo detecttool uninstall-service --remove-logs
```

#### 多实例监控

可以安装多个服务实例监控不同的日志文件：

```bash
# 监控内核日志
sudo detecttool install-service -f /var/log/kern.log -c ./configs/rules.yaml --name detecttool-kern

# 监控系统日志
sudo detecttool install-service -f /var/log/syslog -c ./configs/rules.yaml --name detecttool-syslog

# 分别管理
sudo systemctl start detecttool-kern
sudo systemctl start detecttool-syslog
```

---

## 规则配置

### 配置文件格式

规则配置使用YAML格式，位于 `configs/rules.yaml`。


### 示例规则

**OOM检测规则**:
```yaml
- id: oom_basic
  type: OOM
  severity: high
  keywords_any:
    - "Out of memory"
    - "Killed process"
  regex_any:
    - 'Killed process (?P<pid>\d+)\s+\((?P<comm>[^)]+)\)'
  cooldown_seconds: 30
```




---

## 使用场景

### 场景1: 事后分析

服务器出现故障后，快速分析日志找出异常事件：

```bash
# 扫描完整日志
detecttool scan -f /var/log/kern.log > incidents.txt

# 生成统计报告
detecttool stats -f /var/log/kern.log
```

### 场景2: 实时监控

在开发/测试环境实时监控系统异常：

```bash
# 监控内核日志
detecttool monitor -f /var/log/kern.log

# JSON格式输出到日志收集系统
detecttool monitor -f /var/log/kern.log --json | logger
```

### 场景3: 定时检查

结合cron定时检查并报告：

```bash
# 添加到crontab
0 */6 * * * detecttool scan -f /var/log/kern.log --json > /tmp/check.json && mail -s "System Check" admin@example.com < /tmp/check.json
```

### 场景4: CI/CD集成

在自动化测试中检测系统异常：

```bash
#!/bin/bash
# 测试前开始监控
detecttool monitor -f /var/log/kern.log --json > incidents.log &
MONITOR_PID=$!

# 运行测试
./run_tests.sh

# 停止监控
kill $MONITOR_PID

# 检查是否有critical事件
if grep -q '"severity": "critical"' incidents.log; then
    echo "Critical incidents detected!"
    exit 1
fi
```

---

## 常见问题

### Q1: 为什么没有检测到某些异常？

**A**: 检查以下几点：
1. 规则配置是否匹配日志格式
2. 是否被冷却机制过滤（查看`cooldown_seconds`）
3. 日志权限是否允许读取

### Q2: 如何添加自定义异常类型？

**A**: 编辑 `configs/rules.yaml`，添加新规则：

```yaml
- id: my_custom_rule
  type: MY_EXCEPTION
  severity: high
  keywords_any:
    - "my error pattern"
```

### Q3: monitor命令占用CPU过高？

**A**: 增加轮询间隔：

```bash
detecttool monitor -f /var/log/kern.log --poll 1.0
```

### Q4: 如何处理日志轮转？

**A**: `monitor`命令已支持日志轮转检测，会自动重新打开文件。

---

## 许可证

本项目遵循以下开源协议：
- **代码**: [GNU General Public License v3.0 (GPL-3.0)](LICENSE)
- **文档**: [Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)](
     https://creativecommons.org/licenses/by-sa/4.0/)

---



## 致谢
- **指导老师**: 刘刚 (andyliu@lzu.edu.cn)
- **赛题导师**: 宋凯 (songkai01@ieisystem.com)
- **支持单位**: 浪潮电子信息产业股份有限公司、龙蜥社区
- **比赛**: 2025年全国大学生计算机系统能力大赛




