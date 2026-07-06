# 贡献指南

感谢您考虑为 DFT-parameter-recommendation 做出贡献！

## 🔍 提交 Issue

- 使用提供的 Issue 模板
- 清楚描述问题或建议
- 附上复现步骤（如是 Bug）

## 🚀 提交 Pull Request

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 确保代码风格与现有代码一致
4. 更新相关文档
5. 提交 PR，说明改动内容和原因

## ✅ 代码规范

- 遵循 PEP 8 编码规范
- 所有 Python 脚本必须有模块级别的 docstring
- 函数必须有类型提示和 docstring
- 对新增 API 调用添加 User-Agent 配置

## 🧪 测试

```bash
pytest tests/
```

请确保新增代码有对应的测试覆盖。
