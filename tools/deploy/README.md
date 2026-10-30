# 安装 Skill 与运行依赖

从完整开发仓根执行：

```powershell
.\deploy.ps1
```

交互仅询问 Skill 安装目录，默认 `~/.openflow/config/skills`。脚本覆盖复制 `repo/skills/common/knowledge/` 中含 `SKILL.md` 的能力包，然后用选定 Python 执行一次：

```text
python -m pip install -r repo/himate/himate-knowledge-wifi-mp/runtime/requirements.lock.txt
```

使用已准备的 Python 3.10–3.12；建议将 `-Python` 指向实际执行端的虚拟环境解释器。脚本不创建虚拟环境，不在任务运行中安装依赖。

```powershell
.\deploy.ps1 -NonInteractive -SkillsRoot 'SKILLS_ROOT' -Python 'PATH_TO_PYTHON'
```

`-SourceRoot` 可指定另一份完整源码仓。跨平台可直接使用同一后端；不传 `--python` 时安装到当前解释器：

```text
python tools/deploy/deploy.py --skills-root SKILLS_ROOT --python PATH_TO_PYTHON
```

安装器仅复制 Skill 并执行 pip，不部署知识仓、Workflow、项目入口或配置，不制作压缩包或执行额外检查。运行端直接使用已取得的知识仓，Workflow 在宿主导入。目标中非同名能力包保留；已退役的旧能力包（如 `hs-knowledge-record`）由维护者手动移除。

开发冒烟位于 `tests/test_install_skills.py`，使用临时目录与模拟 pip 验证覆盖复制、保留无关能力包和解释器选择；不会向本机环境实际安装依赖。
