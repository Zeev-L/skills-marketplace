#!/usr/bin/env python3
"""Generate the zeev-playground skill catalog.

Reads .claude-plugin/marketplace.json, resolves each plugin's skill files from the
source clones (shallow-cloning any that are missing), and writes:
  - docs/skills.json  (data — the single source of truth for the HTML + humans)
  - SKILLS.md         (per-skill table, grouped by plugin)

Pure stdlib. Deterministic output (sorted) so re-runs only diff on real changes.
generated_at is taken from $CATALOG_GENERATED_AT if set (the Action injects it),
otherwise omitted — keeps local runs reproducible.
"""
import argparse, json, os, re, subprocess, sys
from pathlib import Path

# plugin name -> role (skills inherit their plugin's role)
ROLE = {
    "text-tools": "Utilities",
    "agent-skills": "Software dev",
    "gstack": "Software dev",
    "awesome-pm-skills": "Product mgmt",
    "pm-product-discovery": "Product mgmt",
    "pm-product-strategy": "Product mgmt",
    "pm-toolkit": "Product mgmt",
    "pm-market-research": "Product mgmt",
    "pm-ai-shipping": "Product mgmt",
    "pm-data-analytics": "Product mgmt",
    "pm-execution": "Project mgmt",
    "marketing-skills": "PMM / Biz dev",
    "x": "Utilities",
    "gdoc-math": "Utilities",
    "find-session": "Utilities",
    "setup-pulse": "Utilities",
    "claude-reviewer": "Utilities",
    "skill-reviewer": "Utilities",
}
ROLES_ORDER = ["Software dev", "Ops/DevOps", "Project mgmt", "Product mgmt",
               "PMM / Biz dev", "Utilities"]

# source clone dir name -> (upstream slug, attribution, license)
UPSTREAM = {
    "addyosmani-agent-skills": ("addyosmani/agent-skills", "Addy Osmani", "MIT"),
    "gstack": ("garrytan/gstack", "Garry Tan", "MIT"),
    "awesome-pm-skills": ("menkesu/awesome-pm-skills", "menkesu", "MIT"),
    "pm-skills": ("phuryn/pm-skills", "Pawel Huryn", "MIT"),
    "marketingskills": ("coreyhaines31/marketingskills", "Corey Haines", "MIT"),
    "omri-a.-cc-stuff": ("omriariav/omri-cc-stuff", "Omri Ariav", "MIT"),
    "_local": ("Zeev-L (original)", "Zeev-L", "—"),
}


def repo_dir_name(src):
    """Clone directory name + clone URL for a marketplace source entry."""
    if isinstance(src, str):                       # local "./text-tools"
        return None, None, src.lstrip("./")
    if src.get("source") == "github":              # whole-repo
        repo = src["repo"]                         # Zeev-L/X
        name = repo.split("/")[-1]
        return name, f"https://github.com/{repo}.git", "."
    if src.get("source") == "git-subdir":
        url = src["url"]                           # https://github.com/Zeev-L/X.git
        name = url.rstrip("/").split("/")[-1][:-4] if url.endswith(".git") else url.rstrip("/").split("/")[-1]
        return name, url, src.get("path", ".")
    raise ValueError(f"unknown source: {src}")


def ensure_clone(clones_dir, name, url):
    dest = clones_dir / name
    if dest.exists():
        return dest
    print(f"  cloning {url} -> {dest}", file=sys.stderr)
    subprocess.run(["git", "clone", "--depth", "1", "-q", url, str(dest)], check=True)
    return dest


def parse_frontmatter(text, fallback_name):
    """Return (name, one-line description) from a SKILL.md."""
    name, desc = fallback_name, ""
    lines = text.splitlines()
    if not (lines and lines[0].strip() == "---"):
        return name, desc
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        ln = lines[i]
        if ln.startswith("name:") and name == fallback_name:
            v = ln.split(":", 1)[1].strip().strip('"').strip("'")
            if v:
                name = v
        elif ln.startswith("description:"):
            v = ln.split(":", 1)[1].strip()
            if v in ("|", ">", "|-", ">-", "|+", ">+", ""):   # block scalar -> take following indented lines
                buf, j = [], i + 1
                while j < len(lines) and lines[j].strip() != "---" and (lines[j].startswith("  ") or not lines[j].strip()):
                    if lines[j].strip():
                        buf.append(lines[j].strip())
                    elif buf:
                        break
                    j += 1
                desc = " ".join(buf)
            else:
                desc = v.strip('"').strip("'")
        i += 1
    desc = re.sub(r"\s+", " ", desc).strip()
    if len(desc) > 280:
        desc = desc[:277] + "…"
    return name, desc


def collect_skills(root: Path):
    out = []
    for sk in sorted(root.rglob("SKILL.md")):
        if "/.git/" in str(sk):
            continue
        rel = sk.relative_to(root)
        text = sk.read_text(encoding="utf-8", errors="replace")
        name, desc = parse_frontmatter(text, sk.parent.name)
        out.append({"skill": name, "description": desc, "rel_path": str(rel)})
    # de-dupe by skill name, keep first (sorted) occurrence
    seen, uniq = set(), []
    for s in out:
        if s["skill"] in seen:
            continue
        seen.add(s["skill"])
        uniq.append(s)
    return uniq


def main():
    ap = argparse.ArgumentParser()
    here = Path(__file__).resolve().parent.parent          # playground/
    ap.add_argument("--marketplace", default=str(here / ".claude-plugin" / "marketplace.json"))
    ap.add_argument("--clones-dir", default=str(here.parent))   # default: sibling dir (marketplace-work)
    ap.add_argument("--out-json", default=str(here / "docs" / "skills.json"))
    ap.add_argument("--out-md", default=str(here / "SKILLS.md"))
    a = ap.parse_args()

    mkt = json.loads(Path(a.marketplace).read_text())
    clones_dir = Path(a.clones_dir); clones_dir.mkdir(parents=True, exist_ok=True)
    playground_root = here

    plugins, all_skills = [], []
    for pl in mkt["plugins"]:
        name = pl["name"]
        cdir, url, path = repo_dir_name(pl["source"])
        if cdir is None:                                   # local plugin (text-tools)
            root = playground_root / path
            up, attr, lic = UPSTREAM["_local"]
            src_repo = "Zeev-L/playground"
        else:
            repo_root = ensure_clone(clones_dir, cdir, url)
            root = repo_root / path if path not in (".", "") else repo_root
            up, attr, lic = UPSTREAM.get(cdir, (cdir, "—", "MIT"))
            src_repo = f"Zeev-L/{cdir}"
        role = ROLE.get(name, "Utilities")
        install = f"claude plugin install {name}@zeev-playground"
        # whole-repo `github` sources are cloned over SSH by the installer -> need a one-time
        # git-HTTPS config on machines without a GitHub SSH key. git-subdir + local are zero-setup.
        src = pl["source"]
        setup = "https" if (isinstance(src, dict) and src.get("source") == "github") else "zero"
        skills = collect_skills(root)
        for s in skills:
            all_skills.append({"skill": s["skill"], "description": s["description"],
                               "plugin": name, "role": role, "install": install,
                               "upstream": up, "source_repo": src_repo, "setup": setup})
        plugins.append({"name": name, "role": role, "upstream": up, "attribution": attr,
                        "license": lic, "install": install, "skill_count": len(skills),
                        "setup": setup, "skills": skills})
        print(f"  {name}: {len(skills)} skills", file=sys.stderr)

    all_skills.sort(key=lambda s: (s["plugin"], s["skill"]))
    roles_present = [r for r in ROLES_ORDER if any(p["role"] == r for p in plugins)]
    data = {"marketplace": mkt.get("name", "zeev-playground"),
            "roles": roles_present, "plugins": plugins, "skills": all_skills,
            "total_skills": len(all_skills), "total_plugins": len(plugins),
            "https_setup_cmd": 'git config --global url."https://github.com/".insteadOf "git@github.com:"'}
    ga = os.environ.get("CATALOG_GENERATED_AT")
    if ga:
        data["generated_at"] = ga

    Path(a.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out_json).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    # SKILLS.md
    md = [f"# Skills catalog — {data['total_skills']} skills across {data['total_plugins']} plugins",
          "",
          "Auto-generated by `scripts/generate-catalog.py` from "
          "[`marketplace.json`](.claude-plugin/marketplace.json). Do not edit by hand.",
          "Browse interactively: https://zeev-l.github.io/playground/", "",
          "Plugins marked **⚠ one-time git-HTTPS config needed** are whole-repo `github` sources the "
          "installer clones over SSH; on a machine without a GitHub SSH key, run once: "
          '`git config --global url."https://github.com/".insteadOf "git@github.com:"`. '
          "All others are **✓ zero setup**.", ""]
    for pl in plugins:
        setup_note = (" · ⚠ one-time git-HTTPS config needed" if pl["setup"] == "https"
                      else " · ✓ zero setup")
        md.append(f"## {pl['name']}  ·  _{pl['role']}_  ({pl['skill_count']} skills)")
        md.append("")
        md.append(f"Upstream: **{pl['upstream']}** · License: {pl['license']} · "
                  f"Install: `{pl['install']}`{setup_note}")
        md.append("")
        md.append("| Skill | Description |")
        md.append("|---|---|")
        for s in pl["skills"]:
            desc = s["description"].replace("|", "\\|") or "—"
            md.append(f"| `{s['skill']}` | {desc} |")
        md.append("")
    Path(a.out_md).write_text("\n".join(md))
    print(f"wrote {a.out_json} and {a.out_md} "
          f"({data['total_skills']} skills, {data['total_plugins']} plugins)", file=sys.stderr)


if __name__ == "__main__":
    main()
