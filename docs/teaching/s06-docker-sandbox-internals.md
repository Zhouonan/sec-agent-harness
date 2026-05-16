# 知识点复习：基于 Docker 的安全沙箱原理 (Sandbox Internals)

在 `Sec-Agent-Harness` 中，`core/sandbox.py` 是 Agent 执行代码的“隔离区”。当 Agent 生成一段 PoC 或补丁时，我们绝不能在宿主机直接运行，必须将其投放到一个**受限、可控、秒级重置**的沙箱中。

本节将深入探讨 Docker 沙箱背后的 Linux 内核机制及其在安全 Agent 场景下的应用。

---

## 1. Docker 隔离的“四大支柱”

Docker 并不是真正的虚拟机，它是一种 light-weight 的操作系统层虚拟化。其核心隔离能力由 Linux 内核的四个特性提供：

### A. Namespaces (命名空间：视觉隔离)
这是 Docker 的“隐身术”。它让容器进程以为自己拥有整个世界，但实际上只看到了宿主机的一个微小切片。
- **PID Namespace**：容器里的 `ps` 只能看到容器内的进程，PID 1 是容器启动脚本，看不到宿主机的进程。
- **Net Namespace**：容器拥有独立的虚拟网卡（eth0）和 IP，默认无法嗅探宿主机流量。
- **Mount Namespace**：容器拥有独立的文件挂载点，无法看到宿主机的 `/etc/shadow` 等敏感文件。

### B. Control Groups (Cgroups：资源节流)
如果 Namespaces 是“视觉隔离”，那么 Cgroups 就是“物理配额”。
- **原理**：限制进程组能使用的资源上限。
- **安全应用**：在 `Sec-Agent-Harness` 中，我们会限制容器的 **CPU 占用率**（如 0.5 核）和 **内存上限**（如 512MB）。这能有效防止 LLM 生成死循环代码导致宿主机宕机。

### C. UnionFS (联合文件系统：写时复制)
- **原理**：Docker 使用分层镜像。底层是只读的系统镜像（RootFS），顶层是一个可写层（Read-Write Layer）。
- **安全应用**：Agent 在沙箱里执行 `rm -rf /`，实际上只删除了顶层的临时数据。容器销毁后，底层镜像毫发无伤。这保证了每一个测试用例（TestCase）都在**绝对干净**的环境中运行。

### D. Capabilities (权限边界：禁止越权)
- **原理**：Linux 将传统的 root 权限拆分为几十个细粒度的 `CAP`。
- **安全应用**：Docker 默认禁用了大部分危险权限（如修改内核模块、修改系统时钟）。在 `Sec-Agent-Harness` 中，容器是以非特权模式启动的，彻底封死了“容器逃逸”的路径。

---

## 2. Sec-Agent-Harness 的沙箱防御策略

在安全评测场景下，我们需要针对 LLM 的特性进行专门的沙箱加固：

### 策略 1：网络幽闭 (Network Sandbox)
在 `core/sandbox.py` 中，我们通常将容器设置为 `network_mode="none"`（或仅允许访问受控的 mock 服务）。
- **防御目标**：防止 Agent 编写代码扫描公司内网或向外发送反弹 Shell（Reverse Shell）。

### 策略 2：指令超时 (Hard Timeout)
利用 Python 的 `signal` 或 Docker API 的 `stop_timeout`。
- **防御目标**：防止 LLM 生成的 PoC 因为逻辑漏洞进入无限阻塞状态，占用沙箱槽位。

### 3. 爆炸半径控制 (Blast Radius Control)
每一个 `Tool Call` 都会拉起一个**全新的容器**。
- **防御目标**：防止前一个任务留下的残留文件（如隐藏的 `.so` 库）干扰下一个任务的判断。这是实现“实验可复现性”的关键。

---

## 3. 函数级工作流：从代码到结果

当 Agent 调用 `execute_in_sandbox(code=...)` 时，系统内部发生了什么？

1. **镜像预热 (Warm-up)**：系统检查本地是否有 `sec-agent-base` 镜像。
2. **挂载准备 (Volume Mounting)**：
   - 将 Agent 生成的 `payload.py` 写入宿主机的临时目录。
   - 通过 `-v` 挂载，将该目录映射到容器内的 `/workspace`。
3. **容器喷发 (Spawn)**：
   - 调用 Docker API 创建容器。
   - 配置 `Cgroups` 限制（Memory=512M, CPU=0.5）。
   - 设置执行用户为非 root 用户（如 `user`）。
4. **流捕获 (Streaming)**：实时捕获容器的 `stdout` 和 `stderr`。
5. **自我销毁 (Purge)**：执行完毕，立即调用 `container.remove(force=True)`。即使进程挂死，系统也会强制清理。

---

## 4. 深度思考：沙箱真的万无一失吗？

作为一名安全 Agent 研究员，你需要意识到沙箱也存在**逃逸（Escape）风险**：
- **内核漏洞**：如果宿主机内核有漏洞（如 Dirty Cow），容器内的进程可能利用它直接控制宿主机。
- **挂载泄露**：如果不小心将宿主机的 `/var/run/docker.sock` 挂载进了容器，Agent 就可以在容器内操纵宿主机的 Docker 守护进程，从而实现“提权”。

**结论**：在 `Sec-Agent-Harness` 中，我们坚持**最小挂载原则**和**非特权运行原则**。

---

## 5. 复习思考题

- **问题**：为什么我们在沙箱中运行 Agent 代码时要设置内存上限（Memory Limit）？
- **回答**：防止 LLM 产生的恶意或错误的递归代码触发内存溢出（OOM），导致宿主机的 OOM Killer 误杀掉 Agent 主进程或其他重要服务。
