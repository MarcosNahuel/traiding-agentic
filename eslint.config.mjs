import nextConfig from "eslint-config-next";

const eslintConfig = [
  ...nextConfig,
  {
    ignores: [
      "backend/**",
      "data/**",
      "scripts/**",
      "docs/**",
      "CODEX/**",
      "documentacion-codex/**",
    ],
  },
];

export default eslintConfig;
