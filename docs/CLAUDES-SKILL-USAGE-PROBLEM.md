# Claude's Skill Usage Problem

Written 2026-06-26 after KKU-WiFi session. Self-critique.

## Symptoms

- 200+ skills available. Almost never invoked proactively.
- Skill router fires but instructions read after work already done.
- `paw recall` never called in sessions where it would help.
- ICM stores fire only when user reminds me.

## Root Causes

### Skills Too Abstract
Most skills are generic checklists (security-review, frontend-patterns, etc.). By time I read them, I already passed/failed the check naturally. Reading adds overhead for zero delta.

### Skills Don't Match Domain
KKU-WiFi project: PowerShell, Task Scheduler, NAC API, captive portal, DPAPI. No skill covers any of these. 200 skills are JS/TS/web-app centric. Router matched `security-review` which was generic enough to apply, but for everything else I worked from first principles.

### ICM/paw Is Reactive, Not Proactive
- `paw recall` runs only when I explicitly call it. I don't have a habit of "before any decision, recall."
- ICM stores only happen after user prompts ("paw ช่วยอะไรบ้าง")
- `Find-LocalNacByProbe` had empty catch `{ }` swallowing SSL errors for 20 hosts — no skill caught this because no PowerShell/network skill exists.

### Skill Router Timing Is Wrong
Router fires mid-response, after I already started reasoning. Context switch to read skill instructions breaks flow. Result: skim and ignore, or read and confirm I'm already doing it.

## Manifestations This Session

| Missed Opportunity | What Should Have Happened |
|---|---|
| cert validation: blind `{ $true }` | `security-review` skill caught this (eventually, after user asked) |
| raw body logged with password | Same — skill checklist says "no secrets in logs" |
| `Find-LocalNacByProbe` empty catch | No skill matched, but my own hygiene should flag empty catches |
| Dynamic NAC discovery approach | No skill for this — built from scratch reading working shell script |
| ICM store about NAC API approach | Only fired at end of session when user asked |

## Fix Ideas

1. **Pre-call recall hook** — Before any code change, run `paw recall "<topic>"` automatically. Makes ICM proactive.
2. **Skill filter by project type** — If project is PowerShell/shell/network, don't route JS/React skills. Inverse: if no skill matches, say so and proceed without guilt.
3. **Domain-specific skill request** — Skills I'd actually use: "WiFi captive portal patterns", "PowerShell security checklist", "network API debugging (curl/Invoke-WebRequest), "NAC appliance auth".
4. **Router at session start, not mid-turn** — Let skills load before first response, not while responding.
5. **Empty catch linter** — `catch { }` without comment or logging should auto-flag regardless of skill.

## Meta

This document exists because user asked "ทำไมนายไม่ค่อยใช้ skills" (why don't you use skills). Honest answer: they don't match my work, and I don't have a pre-call recall habit. Fixing #1 (pre-call recall) and #3 (domain skills) would help most.
