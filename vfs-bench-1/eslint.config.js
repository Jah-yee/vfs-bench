// Our three .mjs files only. Every other .js in this repo is either inside a
// submodule -- which pre-commit never sees, the outer repo tracking it as a
// gitlink -- or a task fixture, a third-party tree vendored verbatim that the
// agent reads, so linting it would change the input the model sees.
//
// No imports on purpose. `@eslint/js` would have to resolve from the repo
// root, which has no node_modules of its own; the rules below are ESLint's
// own and need nothing installed beyond ESLint.
export default [
  {
    files: ['cli/*.mjs', 'cli/toolathlon/*.mjs', 'vfs/*.mjs',
      'tests/kubernetes_mount.mjs', 'tests/service_mounts.mjs', 'tests/fixture_network.mjs',
      'server/clients/browser.mjs', 'server/clients/kubernetes.mjs', 'server/clients/service_api.mjs', 'server/clients/workspace_daemon.mjs', 'redirect/**/*.mjs', 'server/fakes/wandb_api.mjs'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      // Declared rather than taken from the `globals` package, for the same
      // reason: one less thing that has to resolve.
      globals: {
        Buffer: 'readonly',
        Headers: 'readonly',
        Request: 'readonly',
        Response: 'readonly',
        TextDecoder: 'readonly',
        TextEncoder: 'readonly',
        URL: 'readonly',
        URLSearchParams: 'readonly',
        console: 'readonly',
        fetch: 'readonly',
        process: 'readonly',
        setTimeout: 'readonly',
        structuredClone: 'readonly',
      },
    },
    rules: {
      'no-const-assign': 'error',
      'no-dupe-args': 'error',
      'no-dupe-keys': 'error',
      'no-duplicate-case': 'error',
      'no-fallthrough': 'error',
      'no-self-assign': 'error',
      'no-undef': 'error',
      'no-unreachable': 'error',
      'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'no-var': 'error',
      eqeqeq: ['error', 'smart'],
      'prefer-const': 'error',
    },
  },
]
