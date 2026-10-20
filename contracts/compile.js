// Compiles AuditAnchor.sol with solc-js and writes AuditAnchor.json (abi + bytecode).
// Usage: cd contracts && npm i && node compile.js
const fs = require("fs");
const solc = require("solc");
const src = fs.readFileSync(__dirname + "/AuditAnchor.sol", "utf8");
const input = {
  language: "Solidity",
  sources: { "AuditAnchor.sol": { content: src } },
  settings: { optimizer: { enabled: true, runs: 200 }, outputSelection: { "*": { "*": ["abi", "evm.bytecode.object"] } } },
};
const out = JSON.parse(solc.compile(JSON.stringify(input)));
const errs = (out.errors || []).filter((e) => e.severity === "error");
if (errs.length) { console.error(errs.map((e) => e.formattedMessage).join("\n")); process.exit(1); }
const c = out.contracts["AuditAnchor.sol"].AuditAnchor;
fs.writeFileSync(__dirname + "/AuditAnchor.json", JSON.stringify({ contractName: "AuditAnchor", solc: solc.version(), abi: c.abi, bytecode: "0x" + c.evm.bytecode.object }, null, 2));
console.log("compiled with", solc.version());
