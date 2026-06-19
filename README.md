# openclound

基于 **pnpm workspace** 的 TypeScript monorepo。

## 环境要求

- Node.js >= 22 —— 由根 `package.json` 的 `devEngines.runtime` 声明,pnpm 安装时会**自动下载并固定**该版本(替代 `.nvmrc`;`pnpm node -v` 可验证)
- pnpm >= 11(由 `package.json` 的 `packageManager` 字段锁定)

## 目录结构

```
.
├── apps/                # 应用(私有,不发布)
│   └── web/             # 示例应用,依赖 @openclound/utils
├── packages/            # 可复用 / 可发布的包
│   └── utils/           # 示例共享工具库(可发布到 npm)
├── configs/             # 共享配置(可发布)
│   ├── tsconfig/        # @openclound/tsconfig:分层 TS 预设
│   └── biome/           # @openclound/biome-config:Biome 规则基线
├── pnpm-workspace.yaml
├── tsconfig.json        # solution 文件,extends @openclound/tsconfig/monorepo
└── biome.json           # extends 共享 Biome 基线 + 仓库级设置
```

## 常用命令

| 命令 | 说明 |
| --- | --- |
| `pnpm install` | 安装并链接所有工作区依赖(并按 `devEngines` 准备 Node) |
| `pnpm build` | 用 `tsc --build` 按依赖顺序编译全部包 |
| `pnpm dev` | 并行运行各包的 `dev` 脚本 |
| `pnpm test` | 递归运行各包的 `test`(Vitest) |
| `pnpm check` | Biome 检查(lint + 格式) |
| `pnpm check:fix` | Biome 自动修复 |
| `pnpm format` | Biome 仅格式化 |

针对单个包操作用 `--filter`:

```bash
pnpm --filter @openclound/utils build
pnpm --filter @openclound/web dev
```

## 共享配置

- **TypeScript** — `configs/tsconfig`(`@openclound/tsconfig`)提供分层可组合预设。各包 `tsconfig.json` 按需 `extends` 组合,例如 Node 库用 `["@openclound/tsconfig/node", "@openclound/tsconfig/lib"]`。完整入口见 [configs/tsconfig/README.md](configs/tsconfig/README.md)。
- **Biome** — `configs/biome`(`@openclound/biome-config`)提供 lint/格式化基线。根 `biome.json` 以相对路径 `extends`,仅保留 VCS、忽略文件等仓库级设置。
- **Node 版本** — 根 `package.json` 的 `devEngines.runtime` 声明(`{ "name": "node", "version": "^22.22.3", "onFail": "download" }`),由 pnpm 自动下载并固定,无需 `.nvmrc`。

## 新增一个包

1. 在 `packages/` 或 `apps/` 下新建目录,放入 `package.json`(名称用 `@openclound/<name>`)。
2. 内部引用其他工作区包时,依赖写成 `"@openclound/utils": "workspace:*"`。
3. 添加 `tsconfig.json`,`extends` 合适的预设组合,并在该包 `package.json` 的 `devDependencies` 加上 `"@openclound/tsconfig": "workspace:*"`。
4. 若需参与统一构建,在根 `tsconfig.json` 的 `references` 中加入该包。
5. 运行 `pnpm install` 重新链接。

## 发布(Changesets)

非私有的包(如 `packages/`、`configs/` 下的)可发布到 npm:

```bash
pnpm changeset            # 记录一次变更(选择包、语义化版本、填写日志)
pnpm version-packages     # 根据变更升级版本号、生成 CHANGELOG
pnpm release              # 构建并 changeset publish
```

`apps/` 下标记为 `"private": true` 的包会被 Changesets 自动忽略。
