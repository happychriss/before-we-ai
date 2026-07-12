# Dev Container Cheat Sheet

Quick reference for working inside this container. For bad memory. No apologies.
Remember this is a dev container running inside a docker container.

---

## Starting Claude

### Normal mode (Claude asks before doing dangerous things)
```bash
claude
```

### Autonomous mode (Claude acts without asking — use for long tasks)
```bash
claude --dangerously-skip-permissions
```

> **When to use dangerous mode:** Long multi-step tasks where you don't want
> to babysit every file write or shell command. Claude still won't push to
> git automatically — that requires you to run git commands or explicitly ask.
> Keep an eye on what it's doing. It can delete files in `/workspace`.

---

## Git & GitHub (SSH)

SSH agent forwarding is configured. Your private key **never enters the container** —
the host agent handles signing. No passwords, no key files to manage.

### Verify SSH auth is working
```bash
ssh -T git@github.com
# Expected: Hi <username>! You've successfully authenticated...
```

If you see "Permission denied": the host SSH agent isn't forwarding.
Exit the container, run `ssh-add ~/.ssh/id_ed25519` on the host, then reopen.

### Common git commands
```bash
git clone git@github.com:yourname/repo.git   # clone via SSH (not HTTPS)
git push                                      # works, uses forwarded agent
git push origin --delete branch-name         # deletes remote branch — careful
git push --force                             # rewrites history — careful
```

> **HTTPS remotes won't work** — no credentials are stored. If a repo was cloned
> with `https://github.com/...`, switch it: `git remote set-url origin git@github.com:org/repo.git`

### GitHub CLI (`gh`)
`gh` requires a token, not SSH. If `GH_TOKEN` is set in your host `.env`, it works automatically:
```bash
gh pr list
gh pr create
gh issue list
```

If `GH_TOKEN` is not set, `gh` commands will fail with an auth error.
Add `GH_TOKEN=ghp_...` to `.env` on the host and restart the container.

---

## Anthropic API Key

Claude stores your API key in its own config after the first login. It persists in the
`claude-home` named volume — so you only enter it once, ever (unless you nuke the volume).

### First time setup (inside the container)
```bash
claude
# Claude will prompt: "Enter your Anthropic API key:"
# Paste sk-ant-... and hit Enter — it's saved, never asked again
```

The key is stored in `/home/ubuntu/.claude/` and survives container rebuilds.

### If Claude asks for the key again
This only happens if the `claude-home` volume was deleted (e.g. `docker compose down -v`).
Just paste the key again when prompted — it'll be saved for next time.

### If you ran `docker compose down -v` by accident
That wipes the volume including Claude's memory, settings and key. Re-enter the key on next
`claude` start. Everything else (your code in `/workspace`) is fine — that's the host bind-mount.

---

## Firewall (optional)

The outbound firewall restricts Claude to allowlisted domains only.
This prevents any accidental (or malicious) exfiltration of your API key or tokens.

**Enable it** by adding to host `.env`:
```
ENABLE_FIREWALL=true
```

Then restart the container. The firewall runs silently at startup.
Check `/tmp/firewall.log` if something network-related stops working.

**Allowed domains:** `api.anthropic.com`, GitHub, npm registry, VS Code marketplace.
Everything else is blocked.

---

## Container facts to remember

| Thing | Value |
|-------|-------|
| Your user | `ubuntu` (non-root, passwordless sudo) |
| Workspace | `/workspace` — bind-mounted from `./project` on the host |
| Claude config | `/home/ubuntu/.claude` — persists across rebuilds (named volume) |
| Shell | `zsh` with Oh My Zsh, git + fzf plugins |
| Node / npm | Node 20, global packages in `/usr/local/share/npm-global` |

### Files that persist across container rebuilds
- `/workspace/**` — your code (it's the host `project/` folder)
- `/home/ubuntu/.claude/**` — Claude's memory, settings, MCP config

### Files that are lost on rebuild
- Anything else in `/home/ubuntu` (installed apt packages, pip installs outside /workspace, etc.)
- If you install something you need permanently, add it to `.devcontainer/Dockerfile`

### Locale (fixed 2026-07-12 — redo after a rebuild)
`~/.zshrc` exports `LC_ALL=en_US.UTF-8`, but the image doesn't generate that
locale — every `bash` subprocess then warns `setlocale: LC_ALL: cannot change
locale`. Fix (or add to the Dockerfile permanently):
```bash
sudo apt-get install -y locales && sudo locale-gen en_US.UTF-8
```

---

## Useful one-liners

```bash
# Check what env vars are set (useful for debugging missing keys)
env | grep -E 'GH_TOKEN|SSH'

# Check SSH agent is forwarded and key is loaded
ssh-add -l

# Check firewall status / recent log
cat /tmp/firewall.log


