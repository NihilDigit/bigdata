# Repository Guidelines

## Project Structure & Module Organization

This repository contains documentation and packaged source assets for a weather big-data system.

- `DESIGN.md`, `PRODUCT.md`, and `设计文档.md` describe product direction, UI style, and implementation scope.
- `大数据计算与可视化指导文档 最终.docx` is the course guide.
- `气象大数据采集、分析与可视化系统（模板）.doc` is the report template.
- `数据采集.zip` contains ESP32-C3 MicroPython examples, DHT11 code, a weather-station script, a simulator, and the MicroPython firmware binary.
- `服务器侧代码.zip` contains server-side Python modules under `exam/`, including HDFS, HBase, Spark processing, and MTAS/ECharts visualization code.
- `bigdata` links to `../../bigdata`; use it as read-only reference material for previous reports, experiments, and sample code.

Avoid committing extracted archives unless the project intentionally moves to a source-tree layout.

## Build, Test, and Development Commands

There is no root build system. Useful inspection and setup commands:

```bash
unzip -l 数据采集.zip
unzip -l 服务器侧代码.zip
pandoc --track-changes=all "大数据计算与可视化指导文档 最终.docx" -t markdown
soffice --headless --convert-to docx "气象大数据采集、分析与可视化系统（模板）.doc"
```

For local experimentation, extract code to a temporary or ignored workspace first:

```bash
unzip 服务器侧代码.zip -d /tmp/weather-server
unzip 数据采集.zip -d /tmp/weather-esp32
```

## Coding Style & Naming Conventions

Python code should use 4-space indentation, `snake_case` names, and small modules grouped by role, such as `weatherhdfs.py`, `weatherhbase.py`, and `weatherstation.py`. Keep ESP32 MicroPython scripts simple and runnable in Thonny. For frontend assets, keep HTML/CSS/JS under `static/`; follow `DESIGN.md` and do not use emoji.

## Testing Guidelines

No automated test suite is currently defined. Validate changes with targeted smoke tests:

- ESP32 scripts: run in MicroPython REPL or Thonny, then verify DHT11 readings and TCP output.
- Server modules: test HDFS, HBase, and Spark scripts independently before running `dataserver.py`.
- Visualization: open the MTAS app and confirm `/realdata`, `/meandata`, and charts update.

Do not commit `__pycache__/`, generated conversion files, or temporary extracted folders.

## Commit & Pull Request Guidelines

Existing commits use short imperative summaries, for example `Add design context`. Keep commit titles concise and action-oriented. Pull requests should include a clear description, affected documents or archive contents, verification steps, and screenshots for UI changes. Link related tasks or course requirements when available.

## Agent-Specific Instructions

Preserve original `.doc`, `.docx`, `.zip`, and `.mp4` assets unless explicitly asked to replace them. Treat linked materials under `bigdata/` as reference-only by default. When editing report files, work from a copy and keep generated intermediates outside the repository or in an ignored path.
