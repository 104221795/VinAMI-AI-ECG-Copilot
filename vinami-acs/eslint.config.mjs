import nextPlugin from "@next/eslint-plugin-next";
import storybook from "eslint-plugin-storybook";
import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";

export default [
  {
    ignores: [
      "**/.next/**",
      "**/coverage/**",
      "**/node_modules/**",
      "**/storybook-static/**",
      "packages/contracts/src/generated.ts"
    ]
  },
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: { ecmaFeatures: { jsx: true }, sourceType: "module" }
    },
    plugins: { "@next/next": nextPlugin, "@typescript-eslint": tsPlugin },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      "@next/next/no-html-link-for-pages": "off",
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/no-explicit-any": "error",
      "no-restricted-syntax": [
        "error",
        {
          "selector": "CallExpression[callee.object.name='localStorage']",
          "message": "Clinical sessions must never use localStorage."
        }
      ]
    }
  },
  ...storybook.configs["flat/recommended"]
];
