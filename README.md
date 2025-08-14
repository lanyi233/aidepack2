# Tgaide 插件仓库
适用于 [apt插件管理器](modules/apt_module.py) 的源仓库

- 添加源指令
```
,apt source add https://raw.githubusercontent.com/lanyi233/aidepack2/refs/heads/main/source.json
```

## Fork指南
### 文件要求
- 结尾为 `_module.py`
- 必须在文件开头有 `from modules.base_module import BaseModule`

### [仓库环境变量](settings/variables/actions)
- `MODULE_NAME`: 源名称
- `MODULE_ID`: 源ID
