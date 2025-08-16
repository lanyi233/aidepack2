# Tgaide 插件仓库

适用于 [Tgaide](https://t.me/tgaide_channel) [apt插件管理器](modules/apt_module.py) 的源仓库

## 使用apt

- 安装apt插件

```shell
cd ${tgaide_dir}
curl -L https://raw.githubusercontent.com/lanyi233/aidepack2/refs/heads/main/modules/apt_module.py -o third_party_modules/apt_module.py
```

- 更新tgaide

```text
,update
```

- 重启实例

```text
,reboot
```

- 添加源指令

```text
,apt source add https://raw.githubusercontent.com/lanyi233/aidepack2/refs/heads/main/source.json
```

## Fork指南

### 文件要求

- 结尾为 `_module.py`
- 必须在文件开头有 `from modules.base_module import BaseModule`
- 在 `__init__(self)` 内定义以下值

```python
class XXX(BaseModule):
    def __init__(self):
        super().__init__()
        self.name = "插件名称"
        self.description = "简介"
        self.version = "版本"
        self.author = "作者"
```

### 仓库环境变量

- `MODULE_NAME`: 源名称
- `MODULE_ID`: 源ID
