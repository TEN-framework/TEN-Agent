/**
 * Next.js WASM 临时修复文件
 * 同时支持 webpack 和 Turbopack (Next.js 14/15/16)
 *
 * 用法：
 *   import { withAvatarkitFixed } from './avatarkit-next-fix.mjs'
 *   export default withAvatarkitFixed({ ...your next config... })
 *
 * 等 SDK 发布修复版本后，换回：
 *   import { withAvatarkit } from '@spatialwalk/avatarkit/next'
 */

import { fileURLToPath } from 'url'
import { dirname, join } from 'path'
import {
  readFileSync, readdirSync, writeFileSync,
  mkdirSync, copyFileSync, existsSync,
} from 'fs'

// ── 定位 SDK 目录 ──
const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

let sdkDir = null
let searchDir = __dirname
while (searchDir !== dirname(searchDir)) {
  const candidate = join(searchDir, 'node_modules', '@spatialwalk', 'avatarkit')
  if (existsSync(join(candidate, 'package.json'))) {
    sdkDir = candidate
    break
  }
  searchDir = dirname(searchDir)
}
if (!sdkDir) {
  throw new Error(
    '[avatarkit] Cannot find @spatialwalk/avatarkit in node_modules!\n' +
    '  Searched from: ' + __dirname
  )
}
const sdkDistDir = join(sdkDir, 'dist')

// ── 主函数 ──
export function withAvatarkitFixed(nextConfig = {}) {
  const basePath = nextConfig.basePath || ''
  const wasmPublicPath = `${basePath}/_avatarkit/`

  // 1. 创建 Loader
  const loaderCode = `module.exports = function(source) {
  var pattern1 = /scriptDirectory\\s*=\\s*new\\s+URL\\(\\s*"\\."\\s*,\\s*_scriptName\\s*\\)\\.href\\s*;/;
  var result = source.replace(pattern1, 'scriptDirectory = "${wasmPublicPath}";');
  if (result !== source) return result;

  var pattern2 = /try\\s*\\{\\s*scriptDirectory\\s*=\\s*new\\s+URL\\(\\s*"\\."\\s*,\\s*_scriptName\\s*\\)\\.href\\s*;?\\s*\\}\\s*catch\\s*(\\([^)]*\\))?\\s*\\{\\s*\\}/;
  result = source.replace(pattern2, 'scriptDirectory = "${wasmPublicPath}";');
  if (result !== source) return result;

  console.warn('[avatarkit] WARNING: scriptDirectory pattern not matched in', this.resourcePath);
  return source;
}`
  const cacheDir = join(sdkDir, '.cache')
  mkdirSync(cacheDir, { recursive: true })
  const loaderPath = join(cacheDir, 'wasm-loader.cjs')
  writeFileSync(loaderPath, loaderCode)

  // 2. 复制 WASM 到 public/_avatarkit/
  const publicWasmDir = join(__dirname, 'public', '_avatarkit')
  mkdirSync(publicWasmDir, { recursive: true })
  try {
    const files = readdirSync(sdkDistDir)
    for (const file of files) {
      if (file.startsWith('avatar_core_wasm') && file.endsWith('.wasm')) {
        copyFileSync(join(sdkDistDir, file), join(publicWasmDir, file))
      }
    }
  } catch (err) {
    console.warn('[avatarkit] Failed to copy WASM:', err.message)
  }

  return {
    ...nextConfig,

    // Turbopack 配置 (Next.js 15+/16+)
    turbopack: {
      ...nextConfig.turbopack,
      rules: {
        ...nextConfig.turbopack?.rules,
        '**/avatar_core_wasm*.js': {
          loaders: [loaderPath],
          as: '*.js',
        },
      },
    },

    // Webpack 配置
    webpack: (config, context) => {
      if (config.module.generator?.asset?.filename) {
        const filename = config.module.generator.asset.filename
        delete config.module.generator.asset.filename
        config.module.generator['asset/resource'] = {
          ...config.module.generator['asset/resource'],
          filename,
        }
      }
      config.module.rules.push({
        test: /avatar_core_wasm.*\.js$/,
        enforce: 'pre',
        use: [{ loader: loaderPath }],
      })
      if (typeof nextConfig.webpack === 'function') {
        return nextConfig.webpack(config, context)
      }
      return config
    },

    async headers() {
      const userHeaders =
        typeof nextConfig.headers === 'function' ? await nextConfig.headers() : []
      return [
        ...userHeaders,
        {
          source: '/_avatarkit/:path*.wasm',
          headers: [{ key: 'Content-Type', value: 'application/wasm' }],
        },
      ]
    },
  }
}

export default withAvatarkitFixed
