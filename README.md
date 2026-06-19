# openclound

基于 **pnpm workspace** 的 TypeScript monorepo 骨架。

## 环境要求

- **Node.js >= 22** —— 由根 `package.json` 的 `devEngines.runtime` 声明,pnpm 安装时自动下载并固定该版本(替代 `.nvmrc`;`pnpm node -v` 可验证)
- **pnpm >= 11** —— 由 `packageManager` 字段锁定;`engineStrict: true`(在 `pnpm-workspace.yaml`)强制校验

## 目录结构

```
.
├── apps/                # 应用(私有,不发布)—— 暂空,.gitkeep 占位
├── packages/            # 可复用 / 可发布的包
│   └── deepagent/       # Python:基于 deepagents 的深度智能体基础包(uv 管理)
├── configs/             # 共享配置(零依赖纯配置包,可发布)
│   ├── tsconfig/        # @openclound/tsconfig:分层 TS 预设
│   └── biome/           # @openclound/biome-config:Biome 基线 + 框架 domain 预设
├── pnpm-workspace.yaml  # 工作区 / engineStrict / 供应链安全 / allowBuilds
├── tsconfig.json        # solution 文件,extends @openclound/tsconfig/monorepo
└── biome.json           # extends 共享 Biome 基线 + 仓库级(VCS / files)
```

> `apps/` 当前为空(`.gitkeep` 占位)。`packages/` 已含 Python 包 `deepagent`(无 `package.json`,pnpm 自动忽略,由 uv 管理);放入带 `package.json` 的 JS/TS 目录后 pnpm 会自动纳入工作区。

## 常用命令

| 命令 | 说明 |
| --- | --- |
| `pnpm install` | 安装并链接工作区依赖(并按 `devEngines` 准备 Node) |
| `pnpm build` | `pnpm -r run build`,递归构建各包(空仓时 no-op) |
| `pnpm test` | 递归运行各包测试(Vitest) |
| `pnpm check` / `check:fix` | Biome 检查 / 自动修复 |
| `pnpm format` | Biome 格式化 |

## 共享配置

- **TypeScript** — `@openclound/tsconfig`,分层可组合预设(环境 × 模块 × 包类型),含 React/Vue/Next/Nuxt/Solid/Electron。预设用 `${configDir}` 内置了 `rootDir`/`outDir`/`include`,使用方 `tsconfig.json` 可极简。详见 [configs/tsconfig/README.md](configs/tsconfig/README.md)。
- **Biome** — `@openclound/biome-config`,lint/格式化基线 + 框架 domain 预设(react/next/vue/solid)。详见 [configs/biome/README.md](configs/biome/README.md)。

## Python 包(polyglot)

`packages/deepagent` 是 Python 包,由 [uv](https://docs.astral.sh/uv/) 管理,与 pnpm 互不干扰——pnpm 只识别带 `package.json` 的目录,自动忽略纯 Python 目录。

```bash
uv sync --directory packages/deepagent        # 安装依赖
uv run --directory packages/deepagent pytest  # 测试
```

详见 [packages/deepagent/README.md](packages/deepagent/README.md)。

## 关键工程实践

- **Node 版本管理**:`devEngines.runtime`(pnpm 11 起替代 `useNodeVersion`/`.nvmrc`),由 pnpm 自动下载并固定。
- **供应链安全**:`minimumReleaseAge: 1440` —— 不采用发布不足 24h 的新版本;内部 `@openclound/*` 已放行。
- **TS 现代化**:`target/lib: ES2024`、`erasableSyntaxOnly`(代码可被 Node 原生剥离类型直接运行)、库预设启用 `isolatedDeclarations`(强制显式 API 边界)。

## 新增一个包

以 Node 库为例(预设已内置 `rootDir`/`outDir`/`include`,无需重复声明):

```jsonc
// packages/foo/package.json
{
  "name": "@openclound/foo",
  "type": "module",
  "devDependencies": {
    "@openclound/tsconfig": "workspace:*",
    "@types/node": "^25"
  }
}
```
```jsonc
// packages/foo/tsconfig.json
{ "extends": ["@openclound/tsconfig/node", "@openclound/tsconfig/lib"] }
```

随后在根 `tsconfig.json` 的 `references` 注册 `{ "path": "./packages/foo" }`,运行 `pnpm install`。

## 发布(Changesets)

`packages/`、`configs/` 下非私有的包可发布:

```bash
pnpm changeset          # 记录变更
pnpm version-packages   # 升级版本 + 生成 CHANGELOG
pnpm release            # 构建并 changeset publish
```
