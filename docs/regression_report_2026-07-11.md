# DAT 回归验证报告（第一轮）

## 样本保护

所有读取均来自原始样本；输出只写入 `generated/microsoft_pinyin_dat/output/`，未写桌面、未写 Windows 输入法目录、未自动导入。

## 自动测试结果

以下四项均通过：

1. ChsPinyinUDL 两词黄金样本：解析正确、原样写回后 SHA256 完全一致。
2. UserDefinedPhrase 两词备份样本：解析正确、原样写回后 SHA256 完全一致。
3. ChsPinyinUDL 标准生成：生成后可由解析器读回，词条、逐字拼音一致。
4. UserDefinedPhrase 标准生成：生成后可由解析器读回，词条、编码、排序值一致。

## 自动验证与实机兼容性

“标准生成”尚未获得微软拼音实机导入确认，不能视为最终兼容。

- `self_study_standard_generated.dat` 与两词黄金样本长度一致（10240 字节），语义一致，但有 162 字节差异。
- 差异含词条前缀及 0x2400 前的保留区域；这些字段尚未获得足够证据来重建。
- `user_phrase_standard_generated.dat` 与原样本语义一致，但在每条记录的未确认前缀中有 8 字节差异。

## 已确认的安全结论

- 模板无损模式：两个格式均可逐字节复刻真实样本。
- 标准生成模式：两个格式均可完成语义往返。
- **实机验证通过（用户于 2026-07-11 确认）**：以下两个标准生成文件均已成功导入微软拼音：
  - `output/self_study_standard_generated.dat`
  - `output/user_phrase_standard_generated.dat`

这证明本项目当前的标准生成规则可被本机微软拼音接受。二进制差异仍保留为格式研究事项，但不构成当前版本的导入兼容性障碍。

## 下一阶段

按用户决定，在 DAT 验证成功后开始设计微软拼音词库管理 GUI；GUI 设计与实现须另行走设计确认流程。
