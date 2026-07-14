import type { Preview } from "@storybook/nextjs-vite";
import "../app/globals.css";

const preview: Preview = {
  parameters: {
    layout: "centered",
    a11y: { test: "error" },
    backgrounds: {
      default: "clinical",
      values: [{ name: "clinical", value: "#f4f7f8" }],
    },
  },
};

export default preview;
