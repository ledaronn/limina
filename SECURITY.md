# Security policy

Pevrai is an AI agent that can read and change files on your computer and act in a browser.
Its permission gate is the most important part of the project, so security reports are very
welcome.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.** Report it privately:

1. Go to the [Security tab](https://github.com/ledaronn/pevrai/security) of this repository.
2. Click **Report a vulnerability** and describe the problem.

Please include the Pevrai version, your Windows version, the steps to reproduce, and what an
attacker could achieve. A minimal `policy.toml` excerpt or a prompt that triggers the issue is
very helpful. You will get an answer within 14 days. Once a fix is released, you will be credited
in the release notes unless you prefer otherwise.

## Supported versions

Only the latest release receives security fixes.

| Version | Supported |
|---|---|
| 0.1.x (latest) | ✅ |
| older | ❌ |

## What is in scope

Anything that lets the agent do something the user did not allow, for example:

- **Gate bypass:** a tool call that runs without the confirmation the policy requires, or a tool
  that is not classified in `policy.toml` running at all.
- **Path jail escape:** reading or writing outside the configured read/write roots (`..`, links,
  junctions, short 8.3 names, UNC paths, trailing dots…), or touching blocked files such as keys
  and credentials inside them.
- **Prompt injection that leads to action:** text in a web page, document, tool output or MCP
  response that makes the agent call a tool or change a file without the user's approval.
- **Self-modification:** the agent changing its own code, `policy.toml` or system prompt.
- **Undo failures:** a write that is not journaled or cannot be undone as documented.
- **Secret leakage:** API keys written to `policy.toml`, the journal, chats or logs.

Out of scope: problems in the AI model itself (wrong answers, refusals), issues that require an
already compromised user account, and third-party MCP servers you add yourself.

The design of the permission model and the threats it addresses are described (in Turkish) in
[docs/SECURITY.md](docs/SECURITY.md).
