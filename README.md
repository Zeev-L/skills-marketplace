# Zeev's Claude Skills Playground

A repository for building and distributing Claude Code skills.

## Repo Structure

```
playground/
├── plugin.yaml              # Repo identity file (created once)
├── marketplace.json         # List of all skills (update with each new skill)
└── skills/
    └── skill-name/
        ├── skill.md         # Instructions for Claude — what to do
        └── plugin.yaml      # Command definition — how to invoke it
```

## Adding a New Skill

1. Create a folder `skills/skill-name/`
2. Add `skill.md` — instructions for Claude
3. Add `plugin.yaml` — command definition
4. Update `marketplace.json` — add the skill to the list

## Installation

```bash
/plugin marketplace add https://github.com/Zeev-L/playground
/plugin install skill-name@zeev-playground
```
```
