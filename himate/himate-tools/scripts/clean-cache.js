"use strict";

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const DIRECTORIES = ["runtime", "governance", "tools"];

function removeCaches(directory) {
  if (!fs.existsSync(directory)) {
    return;
  }
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "__pycache__" || entry.name === ".pytest_cache") {
        fs.rmSync(target, { recursive: true, force: true });
        continue;
      }
      removeCaches(target);
    }
  }
}

for (const name of DIRECTORIES) {
  removeCaches(path.join(ROOT, name));
}
