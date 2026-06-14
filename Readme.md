# Zeev's Claude Code Plugin Playground

A learning repo for building and distributing Claude Code plugins and skills.

## Correct Repo Structure

A repo that is BOTH a marketplace AND contains a plugin with skills:

```
playground/
├── .claude-plugin/
│   └── marketplace.json          # The STORE catalog — lists available plugins
└── text-tools/                    # A plugin (a wrapper that can hold many skills)
    ├── .claude-plugin/
    │   └── plugin.json            # The plugin's identity card
    └── skills/
        └── bulletize/             # One skill (add more folders here later)
            └── SKILL.md           # The skill definition
```

## The Three Files

### 1. `.claude-plugin/marketplace.json` (store catalog)
```json
{
  "name": "zeev-playground",
  "owner": { "name": "Zeev-L" },
  "plugins": [
    {
      "name": "text-tools",
      "source": "./text-tools",
      "description": "A collection of text manipulation skills"
    }
  ]
}
```

### 2. `text-tools/.claude-plugin/plugin.json` (plugin identity)
```json
{
  "name": "text-tools",
  "description": "A collection of text manipulation skills",
  "version": "1.0.0"
}
```

### 3. `text-tools/skills/bulletize/SKILL.md` (the skill)
```markdown
---
name: bulletize
description: Use when the user wants to convert text into clear, concise bullet points.
---

Take the text the user provides and rewrite it as clear, concise bullet points.
Keep each bullet short — one idea per bullet.
```

## Install & Use

```bash
/plugin marketplace add https://github.com/Zeev-L/playground
/plugin install text-tools@zeev-playground
/reload-plugins
```

Then just ask Claude in natural language:
```
use the bulletize skill on this text: <your text>
```

## Key Lessons Learned

1. **Check the official structure FIRST.** Before building, look at
   `anthropics/claude-plugins-official` -> `plugins/example-plugin`. Don't guess.

2. **`marketplace.json` != `plugin.json`** — two different files:
   - `marketplace.json` = the store (which plugins exist + where they live)
   - `plugin.json` = one plugin's identity

3. **Plugin vs Skill vs Command:**
   - **Plugin** = a wrapper/container; can hold many skills
   - **Skill** (`skills/<name>/SKILL.md`) = Claude invokes it automatically from natural language
   - **Command** (`commands/<name>.md`) = user invokes manually with `/plugin:command`

4. **A skill's `description` matters** — Claude reads it to decide when to use the skill.
   Make it clear and specific ("Use when the user wants to...").

5. **After any change in GitHub:**
   ```
   /plugin marketplace update <marketplace-name>
   /reload-plugins
   ```
   If state gets stuck, fully restart Claude Code.

6. **GitHub creates folders via the filename** — type `folder/sub/file.md` and all
   folders are created automatically. You can't rename a folder directly; create the
   new path and delete the old one.

7. **The "0 skills" count after /reload-plugins can be misleading** — the skill may
   still be loaded. Test it by asking Claude to use it.
