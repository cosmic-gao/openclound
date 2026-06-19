# @openclound/biome-config

openclound 共享 Biome 配置。仓库级设置(VCS、忽略文件)放在根 `biome.json`,通用规则与框架预设集中在这里。

## 基线(base)

根 `biome.json` 通过相对路径继承基线:

```jsonc
{
  "$schema": "https://biomejs.dev/schemas/2.5.0/schema.json",
  "extends": ["./configs/biome/base.jsonc"],
  "vcs": { "enabled": true, "clientKind": "git", "useIgnoreFile": true },
  "files": { "ignoreUnknown": false }
}
```

基线内容:2 空格缩进、行宽 100、双引号、`recommended` lint 预设、自动整理 import。

## 框架预设(Biome lint domains)

基于 Biome 2.x 的 lint [domains](https://biomejs.dev/linter/domains/),在 base 之上按框架启用对应规则。检测到对应依赖时自动激活(如 `react>=16`、`next>=14`)。

| 入口 | 继承自 | 启用 domain |
| --- | --- | --- |
| `base` | — | 通用基线 |
| `react` | base | `react` |
| `next` | react | `react` + `next` |
| `vue` | base | `vue` |
| `solid` | base | `solid` |

在某个 React 应用的 `biome.json` 中继承(相对路径指向本目录):

```jsonc
{
  "$schema": "https://biomejs.dev/schemas/2.5.0/schema.json",
  "root": false,
  "extends": ["../../configs/biome/react.jsonc"]
}
```

> **重要**:本仓库根已有 `biome.json`(Biome 2.x 的 root 配置)。子包自己的 `biome.json` **必须**显式声明 `"root": false`,否则 Biome 会报「嵌套 root 配置冲突」。
>
> 说明:Biome 的 `extends` 以「配置文件路径」解析,monorepo 内用相对路径最稳妥。Biome 还支持 `svelte`、`qwik`、`test` 等更多 domain,可按需新增预设。
