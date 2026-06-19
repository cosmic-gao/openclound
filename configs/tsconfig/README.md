# @openclound/tsconfig

openclound 共享 TypeScript 配置预设,采用**分层可组合**设计:`环境(environments)` × `模块(modules)` × `包类型(packages)` 三个维度,使用方按需 `extends` 组合。

## 安装

工作区内的包直接用 `workspace:*`:

```jsonc
{
  "devDependencies": {
    "@openclound/tsconfig": "workspace:*"
  }
}
```

> 使用框架预设时,还需在该包安装对应运行时/类型依赖(本包将它们声明为**可选** peerDependencies)。例如 React 项目需 `react`、`react-dom`、`@types/react`、`@types/react-dom`、`vite`。

## 可用入口

### 基础

| 入口 | 说明 |
| --- | --- |
| `base` | 通用编译质量选项(strict 等),不锁定 module |
| `strict` | 在 base 之上叠加更严格的检查 |

### 环境(environments)

| 入口 | 继承自 | 说明 |
| --- | --- | --- |
| `node` | base | Node.js(NodeNext + `types: ["node"]`) |
| `browser` | base | 浏览器(bundler 解析 + DOM lib) |
| `vite` | browser | Vite(+ `vite/client`) |
| `react` | vite | React + Vite(`jsx: react-jsx`) |
| `vue` | vite | Vue 3 + Vite(`jsx: preserve` + `jsxImportSource: vue`) |
| `solid` | vite | SolidJS + Vite(`jsxImportSource: solid-js`) |
| `next` | browser | Next.js(`jsx: preserve` + `plugins: [next]` + `noEmit`) |
| `nuxt` | vue | Nuxt 3 |
| `electron` | node | Electron(node + DOM) |

### 模块(modules)

| 入口 | 说明 |
| --- | --- |
| `esm` | ESM 输出片段 |
| `cjs` | CommonJS 输出片段 |

### 包类型(packages)

| 入口 | 说明 |
| --- | --- |
| `lib` | 可发布库(composite + 产出 `.d.ts`) |
| `app` | 应用(composite) |
| `monorepo` | 根 solution 文件(`files: []` + `references`) |
| `test` | 测试(仅类型检查,不产出) |

## 组合示例

`extends` 支持数组(TS 5.0+),从左到右后者覆盖前者:**环境放前,包类型放后**。

```jsonc
// Node.js 库 / 应用
{ "extends": ["@openclound/tsconfig/node", "@openclound/tsconfig/lib"] }
{ "extends": ["@openclound/tsconfig/node", "@openclound/tsconfig/app"] }

// React + Vite 应用 / 组件库
{ "extends": ["@openclound/tsconfig/react", "@openclound/tsconfig/app"] }
{ "extends": ["@openclound/tsconfig/react", "@openclound/tsconfig/lib"] }

// Vue 应用
{ "extends": ["@openclound/tsconfig/vue", "@openclound/tsconfig/app"] }

// SolidJS 应用
{ "extends": ["@openclound/tsconfig/solid", "@openclound/tsconfig/app"] }

// Next.js(自带构建,直接用 next 预设)
{ "extends": "@openclound/tsconfig/next" }

// Nuxt(还需 extends Nuxt 生成的 .nuxt/tsconfig.json)
{ "extends": ["@openclound/tsconfig/nuxt", "./.nuxt/tsconfig.json"] }
```

## 继承链

```
base
├── node ──────── electron
└── browser ───── next
    └── vite
        ├── react
        ├── solid
        └── vue ──── nuxt
```
